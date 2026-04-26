"""Flooring industry taxonomy used for topic clustering, buyer relevance,
and product fit scoring.

The taxonomy is intentionally rule-based (no ML) so every score is
explainable: we can always point at which rule fired.

Each topic has:
  canonical:      stable label used in output
  patterns:       lowercase substrings or regex tokens that match in
                  page titles, URLs, or keywords
  buyer_signal:   how strongly this topic correlates with B2B procurement
                  decisions (0-1)
  product_signal: how strongly it correlates with SPC/PVC/LVT/Vinyl/
                  Commercial Flooring product space (0-1)
  use_case:       which downstream channel best fits (blog/linkedin/email)
  family:         coarse grouping (material_compare, scenario, procurement,
                  performance, install_maintain, trends)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Topic:
    canonical: str
    patterns: tuple
    buyer_signal: float
    product_signal: float
    use_case: tuple  # ("blog", "linkedin", "cold_email")
    family: str


# 1. 材料对比类
MATERIAL_COMPARE: List[Topic] = [
    Topic("SPC vs Laminate", ("spc vs laminate", "spc or laminate", "spc compared to laminate"), 0.7, 1.0, ("blog", "cold_email"), "material_compare"),
    Topic("SPC vs WPC", ("spc vs wpc", "spc or wpc", "wpc vs spc"), 0.65, 1.0, ("blog", "linkedin"), "material_compare"),
    Topic("Vinyl vs Laminate", ("vinyl vs laminate", "vinyl or laminate", "lvt vs laminate"), 0.7, 1.0, ("blog", "cold_email"), "material_compare"),
    Topic("LVT vs SPC", ("lvt vs spc", "spc vs lvt"), 0.7, 1.0, ("blog", "cold_email"), "material_compare"),
    Topic("Vinyl vs Hardwood", ("vinyl vs hardwood", "lvt vs hardwood"), 0.55, 0.85, ("blog",), "material_compare"),
    Topic("Vinyl vs Tile", ("vinyl vs tile", "lvt vs tile"), 0.5, 0.75, ("blog",), "material_compare"),
]

# 2. 场景应用类
SCENARIO: List[Topic] = [
    Topic("Best Flooring for Hotels", ("flooring for hotel", "hotel flooring", "hospitality flooring"), 0.85, 0.9, ("linkedin", "cold_email", "blog"), "scenario"),
    Topic("Best Flooring for Apartments", ("flooring for apartment", "multifamily flooring", "apartment flooring"), 0.8, 0.9, ("linkedin", "cold_email"), "scenario"),
    Topic("Best Flooring for Offices", ("flooring for office", "office flooring", "corporate flooring"), 0.75, 0.85, ("linkedin", "cold_email"), "scenario"),
    Topic("Healthcare / Hospital Flooring", ("hospital flooring", "healthcare flooring", "clinic flooring"), 0.85, 0.85, ("linkedin", "cold_email"), "scenario"),
    Topic("Education / School Flooring", ("school flooring", "education flooring", "classroom flooring"), 0.8, 0.85, ("linkedin", "cold_email"), "scenario"),
    Topic("Retail Store Flooring", ("retail flooring", "store flooring", "showroom flooring"), 0.75, 0.85, ("linkedin",), "scenario"),
    Topic("Commercial Flooring Solutions", ("commercial flooring", "commercial vinyl", "commercial lvt", "commercial spc"), 0.9, 1.0, ("linkedin", "cold_email", "blog"), "scenario"),
    Topic("Residential Flooring", ("residential flooring", "home flooring", "house flooring"), 0.4, 0.7, ("blog",), "scenario"),
]

# 3. 采购决策类
PROCUREMENT: List[Topic] = [
    Topic("Wholesale Flooring", ("wholesale flooring", "bulk flooring", "wholesale spc", "wholesale lvt", "wholesale vinyl"), 1.0, 0.95, ("cold_email", "linkedin"), "procurement"),
    Topic("Flooring Distributor", ("flooring distributor", "distributor flooring", "distribution partner flooring"), 1.0, 0.9, ("cold_email", "linkedin"), "procurement"),
    Topic("Flooring Supplier / Manufacturer", ("flooring supplier", "flooring manufacturer", "factory direct flooring", "oem flooring", "odm flooring"), 1.0, 0.95, ("cold_email", "linkedin"), "procurement"),
    Topic("MOQ & Lead Time", ("moq", "minimum order", "lead time flooring", "container flooring"), 0.95, 0.85, ("cold_email",), "procurement"),
    Topic("Flooring Pricing & Cost", ("flooring price", "flooring cost", "spc price", "lvt price", "cost per sqft flooring", "flooring quote"), 0.85, 0.95, ("cold_email", "blog"), "procurement"),
    Topic("Private Label Flooring", ("private label flooring", "white label flooring"), 0.95, 0.9, ("cold_email", "linkedin"), "procurement"),
]

# 4. 产品性能类
PERFORMANCE: List[Topic] = [
    Topic("Waterproof Flooring", ("waterproof flooring", "waterproof spc", "waterproof lvt", "waterproof vinyl"), 0.7, 1.0, ("blog", "linkedin"), "performance"),
    Topic("Wear Layer & Durability", ("wear layer", "12 mil", "20 mil", "durability flooring", "scratch resistant flooring"), 0.75, 1.0, ("blog", "cold_email"), "performance"),
    Topic("Slip Resistance", ("slip resistant flooring", "anti slip flooring", "r10 flooring", "r11 flooring"), 0.7, 0.9, ("linkedin", "cold_email"), "performance"),
    Topic("Fire Rating", ("fire rating flooring", "class b1 flooring", "fire resistant flooring", "astm e84"), 0.75, 0.85, ("linkedin", "cold_email"), "performance"),
    Topic("Eco / FloorScore / Indoor Air", ("floorscore", "greenguard", "low voc flooring", "phthalate free flooring", "eco friendly flooring"), 0.7, 0.95, ("linkedin", "blog"), "performance"),
    Topic("Acoustic / Sound Reduction", ("acoustic flooring", "iic rating", "sound reduction flooring"), 0.65, 0.85, ("linkedin", "cold_email"), "performance"),
]

# 5. 安装维护类
INSTALL_MAINTAIN: List[Topic] = [
    Topic("Installation Guide", ("install vinyl", "install spc", "install lvt", "click lock", "glue down flooring"), 0.5, 0.95, ("blog",), "install_maintain"),
    Topic("Underlayment", ("underlayment flooring", "vinyl underlayment", "spc underlayment"), 0.55, 0.95, ("blog",), "install_maintain"),
    Topic("Subfloor Preparation", ("subfloor prep", "subfloor preparation", "leveling subfloor"), 0.5, 0.85, ("blog",), "install_maintain"),
    Topic("Maintenance & Cleaning", ("clean vinyl", "clean lvt", "clean spc", "flooring maintenance", "how to clean flooring"), 0.4, 0.85, ("blog",), "install_maintain"),
    Topic("Lifecycle / Replacement", ("how long does vinyl last", "lvt lifespan", "spc lifespan", "replace flooring"), 0.5, 0.85, ("blog",), "install_maintain"),
]

# 6. 趋势 / 案例
TRENDS_CASES: List[Topic] = [
    Topic("Flooring Trends", ("flooring trends", "vinyl trends", "lvt trends", "interior flooring trends", "2025 flooring", "2026 flooring"), 0.65, 0.85, ("linkedin", "blog"), "trends"),
    Topic("Project Case Study", ("case study flooring", "project flooring", "flooring installation case", "commercial renovation flooring"), 0.85, 0.9, ("linkedin", "cold_email"), "trends"),
    Topic("Sustainability Trend", ("sustainable flooring", "recycled flooring", "circular flooring"), 0.6, 0.85, ("linkedin", "blog"), "trends"),
]

ALL_TOPICS: List[Topic] = (
    MATERIAL_COMPARE + SCENARIO + PROCUREMENT + PERFORMANCE + INSTALL_MAINTAIN + TRENDS_CASES
)


# Generic fallback bucket for items that match none of the rules.
FALLBACK_TOPIC = Topic(
    canonical="Uncategorized Flooring Topic",
    patterns=(),
    buyer_signal=0.2,
    product_signal=0.4,
    use_case=("blog",),
    family="other",
)


# Procurement keyword markers — used for buyer relevance scoring even
# when the page already matched a non-procurement topic.
BUYER_INTENT_MARKERS = (
    "wholesale", "distributor", "supplier", "manufacturer", "factory",
    "oem", "odm", "private label", "moq", "lead time", "container",
    "bulk", "quote", "rfq", "tender", "project", "contractor",
    "specification", "spec sheet", "data sheet",
)

# Product family markers for product fit scoring.
PRODUCT_MARKERS = {
    "spc": ("spc",),
    "pvc": ("pvc flooring",),
    "lvt": ("lvt", "luxury vinyl"),
    "vinyl": ("vinyl flooring", "vinyl plank", "vinyl tile"),
    "commercial": ("commercial flooring", "commercial vinyl", "commercial lvt", "commercial spc"),
}
