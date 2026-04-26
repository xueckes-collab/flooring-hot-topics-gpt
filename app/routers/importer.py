"""POST /import-csv — manual upload fallback when Semrush API is not
available, or when the user wants to seed analysis with their own
exported data (e.g. a Semrush UI export saved as CSV).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.adapters.csv_import import CsvImportAdapter
from app.routers.security import require_bearer
from app.schemas import AnalyzeResponse, ImportCsvResponse
from app.services.clustering import cluster
from app.services.normalizer import normalize_keywords, normalize_pages
from app.services.scoring import score_clusters

router = APIRouter()


@router.post(
    "/import-csv",
    response_model=AnalyzeResponse,
    operation_id="importCsv",
    summary="Analyze topics from a manually uploaded CSV",
    description=(
        "Upload a CSV with competitor_domain, page_url, page_title, "
        "estimated_traffic, top_keyword, search_volume, days_since_seen "
        "(see samples/sample_competitors.csv). Same scoring pipeline as "
        "/analyze but skips Semrush. data_source will be 'csv'."
    ),
)
async def import_csv(
    file: UploadFile = File(...),
    product_focus: str = "any",
    country: str = "us",
    time_window_days: int = 90,
    output_use_case: str = "general",
    top_n: int = 20,
    _auth: bool = Depends(require_bearer),
) -> AnalyzeResponse:
    raw_bytes = await file.read()
    text = raw_bytes.decode("utf-8", errors="ignore")
    raw = CsvImportAdapter.parse(text)

    pages = normalize_pages(raw.pages)
    kws = normalize_keywords(raw.keywords)
    clusters = cluster(pages, kws)
    topics = score_clusters(
        list(clusters.values()),
        time_window_days=time_window_days,
        product_focus=product_focus,
        output_use_case=output_use_case,
    )

    return AnalyzeResponse(
        data_source="csv",
        competitor_domains=sorted({p.competitor_domain for p in pages} | {k.competitor_domain for k in kws}),
        country=country,
        time_window_days=time_window_days,
        product_focus=product_focus,
        output_use_case=output_use_case,
        total_pages_analyzed=len(pages),
        total_keywords_analyzed=len(kws),
        topics=topics[:top_n],
        notes=raw.notes,
    )
