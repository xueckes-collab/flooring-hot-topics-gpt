"""Export topic results to CSV, XLSX, or JSON.

Files are written to settings.export_dir.  The endpoint returns a public
download URL constructed from settings.public_base_url so GPT can hand
the user a clickable link.
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import pandas as pd

from app.config import settings
from app.schemas import TopicResult


EXPORT_COLUMNS = [
    "canonical_topic",
    "family",
    "competitor_count",
    "page_count",
    "keyword_count",
    "hotness_score",
    "buyer_relevance_score",
    "product_fit_score",
    "opportunity_score",
    "freshness_window_days",
    "related_keywords",
    "supporting_pages",
    "suggested_blog_angle",
    "suggested_linkedin_angle",
    "suggested_cold_email_angle",
    "why_it_matters",
    "score_explanation",
]


def _flatten(topics: List[TopicResult]) -> List[dict]:
    rows = []
    for t in topics:
        rows.append({
            "canonical_topic": t.canonical_topic,
            "family": t.family,
            "competitor_count": t.competitor_count,
            "page_count": t.page_count,
            "keyword_count": t.keyword_count,
            "hotness_score": t.hotness_score,
            "buyer_relevance_score": t.buyer_relevance_score,
            "product_fit_score": t.product_fit_score,
            "opportunity_score": t.opportunity_score,
            "freshness_window_days": t.freshness_window_days,
            "related_keywords": ", ".join(t.related_keywords),
            "supporting_pages": " | ".join(
                f"{p.competitor_domain} {p.page_url}" for p in t.supporting_pages
            ),
            "suggested_blog_angle": t.suggested_blog_angle,
            "suggested_linkedin_angle": t.suggested_linkedin_angle,
            "suggested_cold_email_angle": t.suggested_cold_email_angle,
            "why_it_matters": t.why_it_matters,
            "score_explanation": t.score_explanation,
        })
    return rows


def export(
    topics: List[TopicResult],
    fmt: str = "xlsx",
    filename_hint: str | None = None,
) -> Tuple[str, int]:
    """Write the file to disk and return (download_url, rows_written)."""
    rows = _flatten(topics)
    out_dir = Path(settings.export_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    rand = secrets.token_hex(3)
    safe_hint = "".join(c for c in (filename_hint or "topics") if c.isalnum() or c in ("-", "_"))[:40]
    base = f"{safe_hint}_{stamp}_{rand}"

    if fmt == "csv":
        path = out_dir / f"{base}.csv"
        pd.DataFrame(rows, columns=EXPORT_COLUMNS).to_csv(path, index=False)
    elif fmt == "json":
        path = out_dir / f"{base}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump([t.model_dump() for t in topics], f, ensure_ascii=False, indent=2)
    else:  # xlsx (default)
        path = out_dir / f"{base}.xlsx"
        pd.DataFrame(rows, columns=EXPORT_COLUMNS).to_excel(path, index=False)

    base_url = settings.public_base_url.rstrip("/")
    download_url = f"{base_url}/exports/{path.name}"
    return download_url, len(rows)
