"""Deterministic mock Semrush adapter.

Returns the same data every run so GPT/Action wiring can be developed
without spending real Semrush units.  Generates realistic-looking pages
and keywords across the flooring taxonomy, varied by competitor domain
hash so different domains look like they cover different topic mixes.
"""
from __future__ import annotations

import hashlib
import random
from typing import List

from app.adapters.base import AdapterResult, DataSourceAdapter
from app.schemas import RawKeyword, RawPage

# A pool of realistic-sounding flooring slugs and keywords to draw from.
PAGE_TEMPLATES: list[tuple[str, str]] = [
    ("/blog/spc-vs-laminate-flooring", "SPC vs Laminate: Which is Better in 2026?"),
    ("/blog/lvt-vs-spc-which-to-choose", "LVT vs SPC Flooring — Buyer's Guide"),
    ("/commercial-flooring", "Commercial Flooring Solutions for High Traffic"),
    ("/commercial-flooring/hospitality", "Hotel Flooring: SPC and LVT for Hospitality"),
    ("/commercial-flooring/healthcare", "Healthcare Flooring: Slip-Resistant LVT"),
    ("/commercial-flooring/retail", "Retail Store Flooring — SPC for Showrooms"),
    ("/blog/waterproof-vinyl-flooring", "Waterproof Vinyl Flooring Explained"),
    ("/blog/wear-layer-explained", "What 12 mil and 20 mil Wear Layer Means"),
    ("/wholesale-flooring", "Wholesale SPC Flooring — Container Pricing"),
    ("/distributor-program", "Become a Flooring Distributor — MOQ & Lead Time"),
    ("/private-label-flooring", "Private Label SPC and LVT Manufacturing"),
    ("/floorscore-certification", "FloorScore Certified Low-VOC Flooring"),
    ("/blog/installation-click-lock-spc", "How to Install Click-Lock SPC Flooring"),
    ("/blog/underlayment-for-vinyl", "Best Underlayment for Vinyl and SPC"),
    ("/blog/clean-and-maintain-lvt", "How to Clean and Maintain LVT Flooring"),
    ("/blog/2026-flooring-trends", "2026 Commercial Flooring Trends"),
    ("/case-study/marriott-renovation", "Case Study: Marriott Hotel SPC Renovation"),
    ("/case-study/medical-clinic-lvt", "Case Study: LVT in a 30-Clinic Network"),
    ("/blog/spc-pricing-guide", "SPC Flooring Pricing Guide — Cost per Sqft"),
    ("/blog/sustainable-flooring", "Sustainable Flooring for LEED Projects"),
    ("/blog/fire-rating-flooring", "Fire Rating for Commercial SPC Flooring"),
    ("/blog/acoustic-flooring", "Acoustic Flooring: IIC Ratings Explained"),
    ("/blog/apartment-flooring-guide", "Best Flooring for Multifamily Apartments"),
    ("/blog/office-flooring-guide", "Best Flooring for Modern Offices"),
    ("/blog/school-flooring-guide", "School Flooring: Durability + Safety"),
]

KEYWORD_TEMPLATES = [
    "spc vs laminate", "lvt vs spc", "vinyl vs laminate", "spc or wpc",
    "best flooring for hotel", "hotel flooring", "hospitality flooring",
    "best flooring for apartment", "multifamily flooring",
    "best flooring for office", "office flooring",
    "school flooring", "healthcare flooring", "retail flooring",
    "commercial flooring", "commercial vinyl", "commercial lvt", "commercial spc",
    "wholesale flooring", "wholesale spc", "wholesale lvt",
    "flooring distributor", "flooring supplier", "flooring manufacturer",
    "private label flooring", "spc moq", "spc lead time",
    "spc price", "lvt price", "cost per sqft flooring",
    "waterproof flooring", "waterproof spc", "waterproof lvt",
    "wear layer", "12 mil vs 20 mil", "scratch resistant flooring",
    "slip resistant flooring", "fire rating flooring",
    "floorscore", "low voc flooring",
    "install spc", "click lock spc", "vinyl underlayment",
    "clean lvt", "clean spc",
    "2026 flooring trends", "lvt trends",
    "case study flooring", "commercial renovation flooring",
    "sustainable flooring",
]


class SemrushMockAdapter(DataSourceAdapter):
    name = "mock"

    async def fetch(
        self,
        competitor_domains: List[str],
        country: str,
        time_window_days: int,
    ) -> AdapterResult:
        result = AdapterResult(source="mock")
        for domain in competitor_domains:
            seed = int(hashlib.md5(domain.lower().encode()).hexdigest(), 16) % (2**32)
            rng = random.Random(seed)

            # 12-20 pages per domain, sampled without replacement
            n_pages = rng.randint(12, min(20, len(PAGE_TEMPLATES)))
            for slug, title in rng.sample(PAGE_TEMPLATES, n_pages):
                kw = rng.choice(KEYWORD_TEMPLATES)
                result.pages.append(RawPage(
                    competitor_domain=domain,
                    page_url=f"https://{domain}{slug}",
                    page_title=title,
                    estimated_traffic=float(rng.randint(80, 12000)),
                    top_keyword=kw,
                    top_keyword_volume=float(rng.randint(40, 9000)),
                    days_since_seen=rng.randint(0, time_window_days),
                    source="mock",
                ))

            # 25-40 keywords per domain
            n_kw = rng.randint(25, min(40, len(KEYWORD_TEMPLATES)))
            for kw in rng.sample(KEYWORD_TEMPLATES, n_kw):
                result.keywords.append(RawKeyword(
                    competitor_domain=domain,
                    keyword=kw,
                    position=float(rng.randint(1, 25)),
                    search_volume=float(rng.randint(50, 8000)),
                    landing_url=f"https://{domain}{rng.choice(PAGE_TEMPLATES)[0]}",
                    days_since_seen=rng.randint(0, time_window_days),
                    source="mock",
                ))

        result.notes.append(
            "DATA_SOURCE_MODE=mock — these rows are generated locally and "
            "do not reflect real Semrush data."
        )
        return result
