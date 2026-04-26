from app.schemas import RawKeyword, RawPage
from app.services.clustering import cluster
from app.services.normalizer import normalize_keywords, normalize_pages
from app.services.scoring import score_clusters


def _page(domain, slug, title, traffic=1000, kw=""):
    return RawPage(
        competitor_domain=domain,
        page_url=f"https://{domain}{slug}",
        page_title=title,
        estimated_traffic=traffic,
        top_keyword=kw,
        top_keyword_volume=500,
        days_since_seen=10,
        source="mock",
    )


def _kw(domain, kw, vol=1500):
    return RawKeyword(
        competitor_domain=domain,
        keyword=kw,
        position=4,
        search_volume=vol,
        landing_url=None,
        days_since_seen=5,
        source="mock",
    )


def _run(pages, kws, *, focus="any", use_case="general", window=90):
    clusters = cluster(normalize_pages(pages), normalize_keywords(kws))
    return score_clusters(list(clusters.values()), window, focus, use_case)


def test_scores_within_bounds_and_explained():
    topics = _run(
        [_page("a.com", "/wholesale-spc", "Wholesale SPC Flooring", traffic=8000)],
        [_kw("a.com", "wholesale spc", vol=4000)],
    )
    assert topics, "expected at least one topic"
    for t in topics:
        for s in (t.hotness_score, t.buyer_relevance_score, t.product_fit_score, t.opportunity_score):
            assert 0 <= s <= 100
        assert t.score_explanation
        assert t.suggested_blog_angle and t.suggested_linkedin_angle and t.suggested_cold_email_angle


def test_cold_email_use_case_boosts_buyer_topics_above_pure_traffic():
    pages = [
        _page("hotel.com", "/blog/2026-flooring-trends", "2026 Flooring Trends", traffic=20000),
        _page("a.com", "/wholesale-spc", "Wholesale SPC Flooring", traffic=2000),
        _page("b.com", "/distributor-program", "Become a Flooring Distributor", traffic=1500),
        _page("c.com", "/private-label-flooring", "Private Label SPC", traffic=1000),
    ]
    kws = [
        _kw("hotel.com", "2026 flooring trends", vol=5000),
        _kw("a.com", "wholesale flooring", vol=4000),
        _kw("b.com", "flooring distributor", vol=3000),
    ]
    topics = _run(pages, kws, use_case="cold_email")
    # Expect a procurement topic to top the list under cold_email weighting,
    # not the pure-traffic Trends topic.
    top = topics[0]
    assert top.family in ("procurement", "scenario"), f"got {top.canonical_topic} ({top.family})"


def test_product_focus_miss_penalizes_score():
    pages = [_page("a.com", "/blog/clean-and-maintain-lvt", "How to clean LVT flooring", traffic=5000)]
    kws = [_kw("a.com", "clean lvt", vol=4000)]
    base = _run(pages, kws, focus="any")
    pinned = _run(pages, kws, focus="commercial")
    # find the same canonical topic in both lists
    base_topic = next(t for t in base if t.canonical_topic == "Maintenance & Cleaning")
    pinned_topic = next(t for t in pinned if t.canonical_topic == "Maintenance & Cleaning")
    assert pinned_topic.product_fit_score <= base_topic.product_fit_score
