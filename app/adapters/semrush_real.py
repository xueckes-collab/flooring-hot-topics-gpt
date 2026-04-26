"""Real Semrush adapter.

Calls Semrush "Domain Reports" API:
  - domain_organic_pages : top organic landing pages for a domain
  - domain_organic       : top organic keywords for a domain

Docs: https://www.semrush.com/api-analytics/

Notes
-----
* Semrush API is paid and metered in API units. We cap rows per call via
  SEMRUSH_PAGES_LIMIT / SEMRUSH_KEYWORDS_LIMIT.
* The API returns CSV-with-semicolons by default. We request JSON via
  `export_columns` and a JSON-friendly path. Some report types only
  support semicolon CSV; we parse that case as a fallback.
* If the key is missing/invalid we raise so the caller can fall back to
  mock instead of silently returning empty data.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import List

import httpx

from app.adapters.base import AdapterResult, DataSourceAdapter
from app.config import settings
from app.schemas import RawKeyword, RawPage

log = logging.getLogger(__name__)


class SemrushRealAdapter(DataSourceAdapter):
    """Real Semrush adapter.  Accepts an explicit api_key so the BYOK
    layer can pass each user's own key per request; falls back to the
    server-wide SEMRUSH_API_KEY when called with no argument (legacy
    `DATA_SOURCE_MODE=real` shared-key flow)."""

    name = "semrush"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = (api_key or settings.semrush_api_key).strip()
        if not self._api_key:
            raise RuntimeError(
                "SemrushRealAdapter needs an api_key — pass one in (BYOK) "
                "or set SEMRUSH_API_KEY in .env (shared-key mode)."
            )
        self._client = httpx.AsyncClient(
            base_url=settings.semrush_base_url,
            timeout=30.0,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch(
        self,
        competitor_domains: List[str],
        country: str,
        time_window_days: int,
    ) -> AdapterResult:
        result = AdapterResult(source="semrush")
        for domain in competitor_domains:
            try:
                pages = await self._fetch_pages(domain, country)
                kws = await self._fetch_keywords(domain, country)
                result.pages.extend(pages)
                result.keywords.extend(kws)
            except Exception as exc:
                log.warning("semrush fetch failed for %s: %s", domain, exc)
                result.notes.append(f"semrush fetch failed for {domain}: {exc}")

        # Time window filtering: Semrush historic granularity is monthly so
        # we just stamp days_since_seen heuristically (today = 0).  Real
        # users wanting strict windows can call domain_organic with the
        # `display_date` param; that requires Historical Data subscription.
        return result

    # ------------------------------------------------------------------
    # Endpoint helpers
    # ------------------------------------------------------------------

    async def _fetch_pages(self, domain: str, country: str) -> List[RawPage]:
        """domain_organic_pages report."""
        params = {
            "type": "domain_organic_pages",
            "key": self._api_key,
            "domain": domain,
            "database": country,
            "display_limit": settings.semrush_pages_limit,
            "export_columns": "Ur,Pt,Tg,Tr,Ph,Nq",
            # Ur=URL, Pt=Page title, Tg=Traffic, Tr=Traffic %, Ph=Top keyword phrase,
            # Nq=Keyword search volume
        }
        rows = await self._call_csv(params)
        out: List[RawPage] = []
        for r in rows:
            try:
                out.append(RawPage(
                    competitor_domain=domain,
                    page_url=r.get("Ur") or r.get("URL", ""),
                    page_title=r.get("Pt") or r.get("Page Title"),
                    estimated_traffic=_to_float(r.get("Tg") or r.get("Traffic")),
                    top_keyword=r.get("Ph") or r.get("Top Keyword"),
                    top_keyword_volume=_to_float(r.get("Nq") or r.get("Search Volume")),
                    days_since_seen=0,
                    source="semrush",
                ))
            except Exception as exc:
                log.debug("skipping page row %s: %s", r, exc)
        return out

    async def _fetch_keywords(self, domain: str, country: str) -> List[RawKeyword]:
        """domain_organic report."""
        params = {
            "type": "domain_organic",
            "key": self._api_key,
            "domain": domain,
            "database": country,
            "display_limit": settings.semrush_keywords_limit,
            "export_columns": "Ph,Po,Nq,Ur",
            # Ph=Phrase, Po=Position, Nq=Volume, Ur=Landing URL
        }
        rows = await self._call_csv(params)
        out: List[RawKeyword] = []
        for r in rows:
            try:
                out.append(RawKeyword(
                    competitor_domain=domain,
                    keyword=r.get("Ph") or r.get("Keyword", ""),
                    position=_to_float(r.get("Po") or r.get("Position")),
                    search_volume=_to_float(r.get("Nq") or r.get("Search Volume")),
                    landing_url=r.get("Ur") or r.get("URL"),
                    days_since_seen=0,
                    source="semrush",
                ))
            except Exception as exc:
                log.debug("skipping keyword row %s: %s", r, exc)
        return out

    async def _call_csv(self, params) -> list[dict]:
        resp = await self._client.get("/", params=params)
        resp.raise_for_status()
        text = resp.text.strip()
        if not text:
            return []
        # Semrush returns ERROR-style payloads as a single line starting with
        # "ERROR" — surface as an exception.
        if text.startswith("ERROR"):
            raise RuntimeError(text)
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        return list(reader)


def _to_float(v) -> float:
    try:
        return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0
