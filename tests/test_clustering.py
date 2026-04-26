from app.schemas import RawKeyword, RawPage
from app.services.clustering import cluster
from app.services.normalizer import normalize_keywords, normalize_pages


def _page(domain: str, slug: str, title: str, kw: str = "") -> RawPage:
    return RawPage(
        competitor_domain=domain,
        page_url=f"https://{domain}{slug}",
        page_title=title,
        estimated_traffic=1000,
        top_keyword=kw,
        top_keyword_volume=500,
        days_since_seen=10,
        source="mock",
    )


def _kw(domain: str, kw: str) -> RawKeyword:
    return RawKeyword(
        competitor_domain=domain,
        keyword=kw,
        position=5,
        search_volume=1200,
        landing_url=None,
        days_since_seen=5,
        source="mock",
    )


def test_cluster_assigns_known_topics_and_dedupes_competitors():
    pages = [
        _page("a.com", "/blog/spc-vs-laminate", "SPC vs Laminate Flooring"),
        _page("b.com", "/spc-vs-laminate-guide", "SPC vs Laminate: Buyer's guide"),
        _page("c.com", "/wholesale-spc", "Wholesale SPC Flooring container pricing"),
    ]
    kws = [
        _kw("a.com", "spc vs laminate"),
        _kw("c.com", "wholesale flooring"),
        _kw("d.com", "moq"),
    ]
    clusters = cluster(normalize_pages(pages), normalize_keywords(kws))

    assert "SPC vs Laminate" in clusters
    spc_cluster = clusters["SPC vs Laminate"]
    assert len(spc_cluster.competitor_domains) == 2

    # MOQ falls under Procurement / "MOQ & Lead Time"
    assert any(c.topic.canonical == "MOQ & Lead Time" for c in clusters.values())


def test_unmatched_falls_back():
    pages = [_page("x.com", "/random/article", "Some random unrelated post")]
    clusters = cluster(normalize_pages(pages), [])
    assert any(c.topic.canonical == "Uncategorized Flooring Topic" for c in clusters.values())
