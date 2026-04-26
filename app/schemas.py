"""Pydantic schemas — wire format used by the API and exposed in OpenAPI."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


# ---------- Inputs ----------

ProductFocus = Literal["spc", "pvc", "lvt", "vinyl", "commercial", "any"]
OutputUseCase = Literal["blog", "linkedin", "cold_email", "general"]


class AnalyzeRequest(BaseModel):
    user_token: Optional[str] = Field(
        None,
        description=(
            "BYOK access code from /setup, format `floor-XXXX-XXXX`. "
            "Required when the server runs in DATA_SOURCE_MODE=byok. "
            "Ignored in mock / shared-real / csv modes."
        ),
        examples=["floor-7K3Q-9WX2"],
    )
    competitor_domains: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="One or more competitor root domains, e.g. ['shaw.com', 'mohawkflooring.com']. Strip schemes and trailing slashes.",
    )
    product_focus: ProductFocus = Field(
        "any",
        description="Optional product family focus. 'any' keeps the full taxonomy.",
    )
    country: str = Field(
        "us", min_length=2, max_length=2,
        description="Two-letter Semrush database code (us, uk, de, fr, ...).",
    )
    time_window_days: Literal[30, 60, 90] = Field(
        90, description="Freshness window in days for hotness calculation.",
    )
    output_use_case: OutputUseCase = Field(
        "general",
        description="Bias suggested angles toward this downstream channel.",
    )
    top_n: int = Field(20, ge=5, le=50, description="Max topics returned.")


# ---------- Raw data flowing through the pipeline ----------

class RawPage(BaseModel):
    competitor_domain: str
    page_url: str
    page_title: Optional[str] = None
    estimated_traffic: float = 0.0
    top_keyword: Optional[str] = None
    top_keyword_volume: float = 0.0
    days_since_seen: int = 999
    source: Literal["semrush", "csv", "mock"]


class RawKeyword(BaseModel):
    competitor_domain: str
    keyword: str
    position: float = 0.0
    search_volume: float = 0.0
    landing_url: Optional[str] = None
    days_since_seen: int = 999
    source: Literal["semrush", "csv", "mock"]


# ---------- Outputs ----------

class TopicSupportPage(BaseModel):
    competitor_domain: str
    page_url: str
    page_title: Optional[str] = None
    estimated_traffic: float = 0.0


class TopicResult(BaseModel):
    canonical_topic: str
    family: str
    competitor_count: int
    page_count: int
    keyword_count: int
    related_keywords: List[str]
    supporting_pages: List[TopicSupportPage]
    freshness_window_days: int

    hotness_score: int = Field(..., ge=0, le=100)
    buyer_relevance_score: int = Field(..., ge=0, le=100)
    product_fit_score: int = Field(..., ge=0, le=100)
    opportunity_score: int = Field(..., ge=0, le=100)

    score_explanation: str
    suggested_blog_angle: str
    suggested_linkedin_angle: str
    suggested_cold_email_angle: str
    why_it_matters: str


class AnalyzeResponse(BaseModel):
    data_source: Literal["semrush", "mock", "csv"] = Field(
        ..., description="Where the underlying rows came from. GPT must surface this to the user when not 'semrush'.",
    )
    competitor_domains: List[str]
    country: str
    time_window_days: int
    product_focus: str
    output_use_case: str
    total_pages_analyzed: int
    total_keywords_analyzed: int
    topics: List[TopicResult]
    notes: List[str] = []
    quota_used_today: Optional[int] = Field(None, description="Only present when running BYOK")
    quota_limit_today: Optional[int] = None


class ImportCsvResponse(BaseModel):
    rows_received: int
    pages: int
    keywords: int
    competitor_domains: List[str]
    notes: List[str] = []


class ExportRequest(BaseModel):
    topics: List[TopicResult]
    format: Literal["csv", "xlsx", "json"] = "xlsx"
    filename_hint: Optional[str] = None


class ExportResponse(BaseModel):
    download_url: str
    format: str
    rows: int
