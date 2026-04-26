"""CSV import adapter — used when DATA_SOURCE_MODE=csv or as a manual
override called from /import-csv.

Expected CSV columns (case-insensitive, first match wins):
  competitor_domain,page_url,page_title,estimated_traffic,top_keyword,
  top_keyword_volume,keyword,position,search_volume,days_since_seen

A single row may carry either page-level fields, keyword-level fields,
or both. Rows missing a `page_url` are treated as keyword-only.
"""
from __future__ import annotations

import csv
import io
from typing import List

from app.adapters.base import AdapterResult, DataSourceAdapter
from app.schemas import RawKeyword, RawPage


def _ci(d: dict, *keys: str) -> str:
    """Case-insensitive dict lookup, first hit wins."""
    lower = {k.lower(): v for k, v in d.items()}
    for k in keys:
        v = lower.get(k.lower())
        if v not in (None, ""):
            return v
    return ""


def _to_float(v) -> float:
    try:
        return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def _to_int(v, default: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


class CsvImportAdapter(DataSourceAdapter):
    """Parse an in-memory CSV blob into AdapterResult."""

    name = "csv"

    def __init__(self, csv_text: str) -> None:
        self._csv_text = csv_text

    async def fetch(
        self,
        competitor_domains: List[str],   # unused for csv (kept for interface parity)
        country: str,
        time_window_days: int,
    ) -> AdapterResult:
        return self.parse(self._csv_text)

    @staticmethod
    def parse(csv_text: str) -> AdapterResult:
        result = AdapterResult(source="csv")
        reader = csv.DictReader(io.StringIO(csv_text))
        for row in reader:
            domain = _ci(row, "competitor_domain", "domain")
            if not domain:
                continue
            page_url = _ci(row, "page_url", "url")
            keyword = _ci(row, "keyword", "top_keyword", "phrase")

            if page_url:
                result.pages.append(RawPage(
                    competitor_domain=domain,
                    page_url=page_url,
                    page_title=_ci(row, "page_title", "title") or None,
                    estimated_traffic=_to_float(_ci(row, "estimated_traffic", "traffic")),
                    top_keyword=_ci(row, "top_keyword") or keyword or None,
                    top_keyword_volume=_to_float(_ci(row, "top_keyword_volume", "search_volume")),
                    days_since_seen=_to_int(_ci(row, "days_since_seen"), default=0),
                    source="csv",
                ))

            if keyword and not page_url:
                result.keywords.append(RawKeyword(
                    competitor_domain=domain,
                    keyword=keyword,
                    position=_to_float(_ci(row, "position", "rank")),
                    search_volume=_to_float(_ci(row, "search_volume", "volume")),
                    landing_url=_ci(row, "landing_url", "page_url") or None,
                    days_since_seen=_to_int(_ci(row, "days_since_seen"), default=0),
                    source="csv",
                ))

        result.notes.append(
            f"Imported from CSV: {len(result.pages)} page rows, "
            f"{len(result.keywords)} keyword rows."
        )
        return result
