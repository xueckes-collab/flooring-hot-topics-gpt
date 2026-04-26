"""POST /analyze — the main endpoint GPT calls.

Pipeline:
  1. Pick adapter based on DATA_SOURCE_MODE:
       byok  → look up the user's Semrush key by `user_token`, instantiate
               SemrushRealAdapter with that key, enforce per-user quota
       real  → use the server-wide SEMRUSH_API_KEY
       mock  → SemrushMockAdapter
       csv   → reject (use /import-csv instead)
  2. Fetch raw pages + keywords.
  3. Normalize → cluster → score.
  4. Slice top_n and return.
"""
from __future__ import annotations

import logging
from typing import Tuple

from fastapi import APIRouter, Depends, HTTPException

from app import storage
from app.adapters import SemrushMockAdapter, SemrushRealAdapter
from app.adapters.base import AdapterResult, DataSourceAdapter
from app.config import settings
from app.crypto import decrypt
from app.routers.security import require_bearer
from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.services import quota
from app.services.clustering import cluster
from app.services.normalizer import normalize_keywords, normalize_pages
from app.services.scoring import score_clusters

log = logging.getLogger(__name__)
router = APIRouter()


def _pick_adapter(req: AnalyzeRequest) -> Tuple[DataSourceAdapter, str | None]:
    """Returns (adapter, user_token_to_record_usage_against)."""
    mode = settings.data_source_mode.lower()

    if mode == "byok":
        if not req.user_token:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Server is in BYOK mode but request has no `user_token`. "
                    "Visit /setup to register your Semrush key and get an access code."
                ),
            )
        # Existence first (401), THEN quota (429) — order matters for clear errors.
        row = storage.get_active_record(req.user_token)
        if not row:
            raise HTTPException(status_code=401, detail="Invalid or revoked access code. Re-register at /setup.")
        decision = quota.check(req.user_token)
        if not decision.allowed:
            raise HTTPException(status_code=429, detail=decision.reason)
        try:
            api_key = decrypt(row["encrypted_semrush_key"])
        except Exception as exc:
            log.error("decrypt failed for token %s: %s", req.user_token, exc)
            raise HTTPException(status_code=500, detail="Server cannot decrypt this access code. Re-register at /setup.")
        return SemrushRealAdapter(api_key=api_key), req.user_token

    if mode == "real":
        try:
            return SemrushRealAdapter(), None
        except Exception as exc:
            log.warning("Falling back to mock — real adapter init failed: %s", exc)
            return SemrushMockAdapter(), None

    if mode == "csv":
        raise HTTPException(
            status_code=400,
            detail="DATA_SOURCE_MODE=csv. Use POST /import-csv to push rows instead.",
        )

    return SemrushMockAdapter(), None


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    operation_id="analyzeHotTopics",
    summary="Analyze competitor flooring hot topics via Semrush",
    description=(
        "Given competitor domains and a BYOK `user_token`, calls Semrush, "
        "clusters returned pages/keywords into flooring topics, returns a "
        "ranked list with explainable scores + Blog/LinkedIn/email angles."
    ),
)
async def analyze(
    req: AnalyzeRequest,
    _auth: bool = Depends(require_bearer),
) -> AnalyzeResponse:
    domains = [_clean_domain(d) for d in req.competitor_domains]

    adapter, billed_token = _pick_adapter(req)

    try:
        raw: AdapterResult = await adapter.fetch(
            competitor_domains=domains,
            country=req.country,
            time_window_days=req.time_window_days,
        )
    finally:
        # Real adapters open an httpx client we should close.
        aclose = getattr(adapter, "aclose", None)
        if aclose:
            try:
                await aclose()
            except Exception:
                pass

    pages = normalize_pages(raw.pages)
    kws = normalize_keywords(raw.keywords)
    clusters = cluster(pages, kws)
    topics = score_clusters(
        list(clusters.values()),
        time_window_days=req.time_window_days,
        product_focus=req.product_focus,
        output_use_case=req.output_use_case,
    )

    # If the live source returned ZERO rows AND notes contain failure
    # markers, signal that loudly so the GPT warns the user instead of
    # silently saying "no hot topics".
    if raw.source == "semrush" and not pages and not kws:
        if any("failed" in n.lower() or "error" in n.lower() for n in raw.notes):
            raw.notes.insert(0, "ALL_SEMRUSH_CALLS_FAILED — check api key / quota / domain spelling")

    quota_used_today = None
    quota_limit_today = None
    if billed_token:
        storage.record_usage(billed_token)
        # Re-read AFTER record_usage — the read already reflects the +1.
        d = quota.check(billed_token)
        quota_used_today = d.daily_used
        quota_limit_today = d.daily_limit

    return AnalyzeResponse(
        data_source=raw.source,
        competitor_domains=domains,
        country=req.country,
        time_window_days=req.time_window_days,
        product_focus=req.product_focus,
        output_use_case=req.output_use_case,
        total_pages_analyzed=len(pages),
        total_keywords_analyzed=len(kws),
        topics=topics[: req.top_n],
        notes=raw.notes,
        quota_used_today=quota_used_today,
        quota_limit_today=quota_limit_today,
    )


def _clean_domain(d: str) -> str:
    d = d.strip().lower()
    for p in ("https://", "http://"):
        if d.startswith(p):
            d = d[len(p):]
    return d.rstrip("/")
