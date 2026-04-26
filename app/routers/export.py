"""POST /export — write a topic list to CSV/XLSX/JSON and return a URL.

We deliberately keep the API stateless: GPT passes the topic list it
just received from /analyze (or /import-csv) back into /export. This
keeps the middleware free of session storage while still letting users
download a polished file."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.routers.security import require_bearer
from app.schemas import ExportRequest, ExportResponse
from app.services.exporter import export

router = APIRouter()


@router.post(
    "/export",
    response_model=ExportResponse,
    operation_id="exportTopics",
    summary="Export a topic list to CSV / XLSX / JSON",
    description=(
        "Pass the `topics` array returned by /analyze (or /import-csv) and "
        "the desired format. Returns a `download_url` valid for ~24h."
    ),
)
async def do_export(
    req: ExportRequest,
    _auth: bool = Depends(require_bearer),
) -> ExportResponse:
    download_url, rows = export(req.topics, fmt=req.format, filename_hint=req.filename_hint)
    return ExportResponse(download_url=download_url, format=req.format, rows=rows)


@router.get("/exports/{filename}", include_in_schema=False)
async def serve_export(filename: str):
    # Basic path-traversal guard
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = Path(settings.export_dir) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename)
