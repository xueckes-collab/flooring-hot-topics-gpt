"""Normalize raw rows: lowercase, strip, dedupe, fold synonyms."""
from __future__ import annotations

import re
from typing import Iterable, List

from app.schemas import RawKeyword, RawPage


_WS = re.compile(r"\s+")


def _norm(s: str | None) -> str:
    if not s:
        return ""
    return _WS.sub(" ", s.strip().lower())


def normalize_pages(pages: Iterable[RawPage]) -> List[RawPage]:
    """Lowercase titles/keywords; dedupe by (domain, page_url)."""
    seen: dict[tuple, RawPage] = {}
    for p in pages:
        k = (p.competitor_domain.lower(), p.page_url.lower())
        if k in seen:
            # keep the row with higher traffic
            if p.estimated_traffic > seen[k].estimated_traffic:
                seen[k] = p
            continue
        # write a normalized copy back
        p2 = p.model_copy(update={
            "page_title": _norm(p.page_title) or None,
            "top_keyword": _norm(p.top_keyword) or None,
            "competitor_domain": p.competitor_domain.lower().strip(),
        })
        seen[k] = p2
    return list(seen.values())


def normalize_keywords(keywords: Iterable[RawKeyword]) -> List[RawKeyword]:
    """Lowercase keyword strings; dedupe by (domain, keyword)."""
    seen: dict[tuple, RawKeyword] = {}
    for k in keywords:
        key = (k.competitor_domain.lower(), _norm(k.keyword))
        if key in seen:
            # prefer higher search volume
            if k.search_volume > seen[key].search_volume:
                seen[key] = k
            continue
        seen[key] = k.model_copy(update={
            "keyword": _norm(k.keyword),
            "competitor_domain": k.competitor_domain.lower().strip(),
        })
    return list(seen.values())
