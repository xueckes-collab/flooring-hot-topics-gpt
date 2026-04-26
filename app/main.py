"""FastAPI entrypoint for the Flooring Hotspot GPT middleware."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
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


_PRIVACY_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Flooring Hotspot Scout — Privacy Policy</title>
<style>body{font-family:-apple-system,system-ui,sans-serif;max-width:680px;margin:40px auto;padding:0 20px;line-height:1.6;color:#222}h1{font-size:22px}h2{font-size:16px;margin-top:24px}</style>
</head><body>
<h1>Privacy Policy — Flooring Hotspot Scout</h1>
<p><em>Last updated: 2026-04-27</em></p>

<h2>What this service does</h2>
<p>Flooring Hotspot Scout is a ChatGPT GPT that calls a middleware API to query the Semrush API on behalf of users. The GPT helps analyze competitor flooring websites for content topic intelligence.</p>

<h2>What we collect</h2>
<ul>
<li><strong>Your Semrush API key.</strong> Submitted once via <code>/setup</code>, encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256), and used only to call <code>api.semrush.com</code> on your behalf during your <code>/analyze</code> calls.</li>
<li><strong>An access code (<code>floor-XXXX-XXXX</code>).</strong> A non-secret short token we issue to you so the GPT can identify which encrypted key to use.</li>
<li><strong>Usage counters.</strong> Daily and monthly call counts per access code, used solely for quota enforcement.</li>
<li><strong>Competitor domains you submit.</strong> Sent to Semrush as part of the query; not retained on our servers beyond ephemeral logs.</li>
</ul>

<h2>What we do NOT collect</h2>
<ul>
<li>We do not collect your name, email, ChatGPT conversation history, or browsing data.</li>
<li>We do not sell or share any data with third parties beyond Semrush itself (which receives only the data you ask us to query).</li>
</ul>

<h2>How to delete your data</h2>
<p>POST your access code to <code>/revoke</code> at any time to invalidate it. To fully erase your encrypted Semrush key from our database, contact the operator of this instance.</p>

<h2>Where data is stored</h2>
<p>Encrypted Semrush keys are stored in a SQLite database on the same Railway-hosted server that runs the API. The encryption key is held only on the server and is never logged or transmitted.</p>

<h2>Contact</h2>
<p>This is a self-hosted instance. Reach the operator of the GPT that linked you here.</p>
</body></html>"""


@app.get("/privacy", include_in_schema=False)
async def privacy_page():
    return HTMLResponse(_PRIVACY_HTML)


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
