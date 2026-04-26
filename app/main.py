"""FastAPI entrypoint for the Flooring Hotspot GPT middleware."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import storage
from app.config import settings
from app.routers import analyze, byok, export, health, importer

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Flooring Hotspot GPT — Middleware",
    version="0.2.0",
    description=(
        "Middleware API called by the Flooring Hotspot ChatGPT GPT via "
        "Actions. Wraps Semrush, normalizes/clusters/scores topics for the "
        "SPC / PVC / LVT / Vinyl / Commercial Flooring B2B export use case. "
        "Supports BYOK (per-user Semrush keys) via the /setup page."
    ),
    servers=[{"url": settings.public_base_url, "description": "configured public host"}],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _init() -> None:
    storage.init_db()


# Routers
app.include_router(health.router, tags=["meta"])
app.include_router(analyze.router, tags=["analysis"])
app.include_router(importer.router, tags=["analysis"])
app.include_router(export.router, tags=["export"])
app.include_router(byok.router)

# Static — the /setup HTML page
_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/setup", include_in_schema=False)
async def setup_page():
    return FileResponse(_STATIC_DIR / "setup.html")


@app.get("/", include_in_schema=False)
async def root():
    # In BYOK mode, the most useful landing page is /setup.
    if settings.data_source_mode == "byok":
        return RedirectResponse(url="/setup")
    return {
        "service": "flooring-hotspot-gpt-middleware",
        "version": app.version,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "data_source_mode": settings.data_source_mode,
    }
