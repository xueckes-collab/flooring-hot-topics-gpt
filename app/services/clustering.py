"""Topic clustering — assigns each page/keyword to a canonical taxonomy
topic by matching against the rule patterns in flooring_taxonomy.

Output of this stage feeds the scoring module.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set

from app.data.flooring_taxonomy import ALL_TOPICS, FALLBACK_TOPIC, Topic
from app.schemas import RawKeyword, RawPage


@dataclass
class TopicCluster:
    topic: Topic
    pages: List[RawPage] = field(default_factory=list)
    keywords: List[RawKeyword] = field(default_factory=list)
    competitor_domains: Set[str] = field(default_factory=set)


def _matches(topic: Topic, *texts: str | None) -> bool:
    blob = " ".join((t or "") for t in texts)
    if not blob:
        return False
    return any(p in blob for p in topic.patterns)


def cluster(
    pages: List[RawPage],
    keywords: List[RawKeyword],
) -> Dict[str, TopicCluster]:
    """Bucket every page and keyword into one or more taxonomy topics.

    A row CAN belong to multiple topics (e.g. "wholesale spc flooring"
    matches both Wholesale Flooring and Commercial Flooring family).
    Unmatched rows go to the FALLBACK bucket.
    """
    clusters: Dict[str, TopicCluster] = {}
    for t in ALL_TOPICS + [FALLBACK_TOPIC]:
        clusters[t.canonical] = TopicCluster(topic=t)

    for p in pages:
        haystack = (p.page_title or "", p.top_keyword or "", p.page_url)
        matched = False
        for topic in ALL_TOPICS:
            if _matches(topic, *haystack):
                c = clusters[topic.canonical]
                c.pages.append(p)
                c.competitor_domains.add(p.competitor_domain)
                matched = True
        if not matched:
            c = clusters[FALLBACK_TOPIC.canonical]
            c.pages.append(p)
            c.competitor_domains.add(p.competitor_domain)

    for k in keywords:
        haystack = (k.keyword, k.landing_url or "")
        matched = False
        for topic in ALL_TOPICS:
            if _matches(topic, *haystack):
                c = clusters[topic.canonical]
                c.keywords.append(k)
                c.competitor_domains.add(k.competitor_domain)
                matched = True
        if not matched:
            c = clusters[FALLBACK_TOPIC.canonical]
            c.keywords.append(k)
            c.competitor_domains.add(k.competitor_domain)

    # Drop empty buckets so downstream code only sees clusters with content.
    return {k: v for k, v in clusters.items() if v.pages or v.keywords}
