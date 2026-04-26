"""Explainable, rule-based scoring.

Four scores per topic, each 0-100:
  - hotness_score        : how loudly the market is talking about this NOW
  - buyer_relevance_score: how close to procurement / project decisions
  - product_fit_score    : how aligned with SPC / PVC / LVT / Vinyl /
                           Commercial Flooring product space
  - opportunity_score    : weighted combination biased by output_use_case

Every score returns alongside a short human-readable explanation that
GPT echoes back to the sales user, so they always see WHY a topic is hot.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from app.data.flooring_taxonomy import (
    BUYER_INTENT_MARKERS,
    PRODUCT_MARKERS,
    Topic,
)
from app.schemas import TopicResult, TopicSupportPage
from app.services.clustering import TopicCluster


# ---------- helpers ----------

def _clamp100(x: float) -> int:
    return max(0, min(100, int(round(x))))


def _hotness(cluster: TopicCluster, time_window_days: int) -> Tuple[int, str]:
    pages = cluster.pages
    kws = cluster.keywords
    n_competitors = len(cluster.competitor_domains)

    # Component 1: how many distinct competitors cover the topic
    competitor_signal = min(40.0, n_competitors * 12.0)

    # Component 2: traffic strength of supporting pages
    total_traffic = sum(p.estimated_traffic for p in pages)
    traffic_signal = min(30.0, total_traffic / 800.0)  # ~24,000 traffic = 30 pts

    # Component 3: keyword search volume strength
    total_volume = sum(k.search_volume for k in kws)
    volume_signal = min(20.0, total_volume / 1500.0)  # ~30,000 volume = 20 pts

    # Component 4: freshness — fraction of rows seen within window
    rows = [p.days_since_seen for p in pages] + [k.days_since_seen for k in kws]
    if rows:
        fresh_frac = sum(1 for d in rows if d <= time_window_days) / len(rows)
    else:
        fresh_frac = 0.0
    freshness_signal = fresh_frac * 10.0  # 0-10

    score = competitor_signal + traffic_signal + volume_signal + freshness_signal
    explanation = (
        f"competitors={n_competitors}({competitor_signal:.0f}/40), "
        f"traffic={total_traffic:.0f}({traffic_signal:.0f}/30), "
        f"kw_volume={total_volume:.0f}({volume_signal:.0f}/20), "
        f"freshness={fresh_frac:.0%}({freshness_signal:.0f}/10)"
    )
    return _clamp100(score), explanation


def _buyer_relevance(cluster: TopicCluster) -> Tuple[int, str]:
    base = cluster.topic.buyer_signal * 70.0  # taxonomy-defined baseline (0-70)

    # Bonus: count buyer-intent words found in titles/keywords
    blob_parts: List[str] = []
    for p in cluster.pages:
        blob_parts.append(p.page_title or "")
        blob_parts.append(p.top_keyword or "")
        blob_parts.append(p.page_url)
    for k in cluster.keywords:
        blob_parts.append(k.keyword)
    blob = " ".join(blob_parts).lower()

    hits = sum(1 for m in BUYER_INTENT_MARKERS if m in blob)
    intent_bonus = min(30.0, hits * 6.0)

    score = base + intent_bonus
    explanation = (
        f"taxonomy_signal={cluster.topic.buyer_signal:.2f}({base:.0f}/70), "
        f"intent_markers={hits}({intent_bonus:.0f}/30)"
    )
    return _clamp100(score), explanation


def _product_fit(cluster: TopicCluster, product_focus: str) -> Tuple[int, str]:
    base = cluster.topic.product_signal * 60.0  # 0-60

    blob_parts: List[str] = []
    for p in cluster.pages:
        blob_parts.append(p.page_title or "")
        blob_parts.append(p.top_keyword or "")
    for k in cluster.keywords:
        blob_parts.append(k.keyword)
    blob = " ".join(blob_parts).lower()

    family_hits = 0
    matched_families: List[str] = []
    for fam, markers in PRODUCT_MARKERS.items():
        if any(m in blob for m in markers):
            family_hits += 1
            matched_families.append(fam)
    family_signal = min(30.0, family_hits * 8.0)  # 0-30

    # Focus bonus: if user pinned a product_focus, reward overlap, penalize miss
    if product_focus != "any":
        if product_focus in matched_families:
            focus_bonus = 10.0
            focus_note = f"+focus({product_focus})=10"
        else:
            focus_bonus = -15.0
            focus_note = f"-focus_miss({product_focus})=-15"
    else:
        focus_bonus = 0.0
        focus_note = "focus=any"

    score = base + family_signal + focus_bonus
    explanation = (
        f"taxonomy_fit={cluster.topic.product_signal:.2f}({base:.0f}/60), "
        f"families={','.join(matched_families) or 'none'}({family_signal:.0f}/30), "
        f"{focus_note}"
    )
    return _clamp100(score), explanation


def _opportunity(
    hotness: int,
    buyer_relevance: int,
    product_fit: int,
    output_use_case: str,
) -> Tuple[int, str]:
    """Weighted blend, biased by intended downstream channel."""
    if output_use_case == "blog":
        w_hot, w_buy, w_fit = 0.45, 0.20, 0.35
    elif output_use_case == "linkedin":
        w_hot, w_buy, w_fit = 0.30, 0.40, 0.30
    elif output_use_case == "cold_email":
        w_hot, w_buy, w_fit = 0.20, 0.55, 0.25
    else:  # general
        w_hot, w_buy, w_fit = 0.34, 0.33, 0.33

    score = hotness * w_hot + buyer_relevance * w_buy + product_fit * w_fit
    expl = (
        f"weights({output_use_case}) hot×{w_hot} + buy×{w_buy} + fit×{w_fit} = {score:.1f}"
    )
    return _clamp100(score), expl


def _angles(topic: Topic, canonical: str) -> dict:
    """Channel-specific suggested angles. Lightweight templates the GPT
    can rephrase, not finished copy."""
    return {
        "blog": (
            f"Write a comparison/explainer post titled around \"{canonical}\" "
            "with side-by-side specs (wear layer, fire rating, MOQ, lead time). "
            "Include a downloadable spec sheet CTA."
        ),
        "linkedin": (
            f"Share a 3-bullet take on \"{canonical}\" framed for procurement "
            "and project managers. Open with a problem they have this week, "
            "close with a project case study tease."
        ),
        "cold_email": (
            f"Lead with the buyer pain behind \"{canonical}\" "
            "(spec mismatch, lead time, certification gap), reference a "
            "competitor's published page as social proof, offer a 1-page "
            "spec comparison as the next step."
        ),
    }


# ---------- public ----------

def score_clusters(
    clusters: List[TopicCluster],
    time_window_days: int,
    product_focus: str,
    output_use_case: str,
) -> List[TopicResult]:
    out: List[TopicResult] = []
    for c in clusters:
        hot, hot_expl = _hotness(c, time_window_days)
        buy, buy_expl = _buyer_relevance(c)
        fit, fit_expl = _product_fit(c, product_focus)
        opp, opp_expl = _opportunity(hot, buy, fit, output_use_case)

        # supporting pages: top 5 by traffic
        sup = sorted(c.pages, key=lambda p: p.estimated_traffic, reverse=True)[:5]
        support = [TopicSupportPage(
            competitor_domain=p.competitor_domain,
            page_url=p.page_url,
            page_title=p.page_title,
            estimated_traffic=p.estimated_traffic,
        ) for p in sup]

        # related keywords: top 8 by search volume
        kw_sorted = sorted(c.keywords, key=lambda k: k.search_volume, reverse=True)[:8]
        related = list({k.keyword for k in kw_sorted})

        angles = _angles(c.topic, c.topic.canonical)

        why = _why_it_matters(c.topic, hot, buy, fit)

        out.append(TopicResult(
            canonical_topic=c.topic.canonical,
            family=c.topic.family,
            competitor_count=len(c.competitor_domains),
            page_count=len(c.pages),
            keyword_count=len(c.keywords),
            related_keywords=related,
            supporting_pages=support,
            freshness_window_days=time_window_days,
            hotness_score=hot,
            buyer_relevance_score=buy,
            product_fit_score=fit,
            opportunity_score=opp,
            score_explanation=(
                f"HOT[{hot_expl}] | BUY[{buy_expl}] | FIT[{fit_expl}] | OPP[{opp_expl}]"
            ),
            suggested_blog_angle=angles["blog"],
            suggested_linkedin_angle=angles["linkedin"],
            suggested_cold_email_angle=angles["cold_email"],
            why_it_matters=why,
        ))

    out.sort(key=lambda r: r.opportunity_score, reverse=True)
    return out


def _why_it_matters(topic: Topic, hot: int, buy: int, fit: int) -> str:
    qualifiers: List[str] = []
    if hot >= 60:
        qualifiers.append("multiple competitors are actively ranking on it")
    if buy >= 60:
        qualifiers.append("the language maps to procurement and project decisions")
    if fit >= 60:
        qualifiers.append("it lives squarely in your SPC/PVC/LVT/Vinyl/Commercial product zone")
    if not qualifiers:
        qualifiers.append("it is currently a thin / lower-priority signal")
    return f"{topic.canonical}: " + "; ".join(qualifiers) + "."
