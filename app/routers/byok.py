"""BYOK 衣帽间 endpoints — register / revoke / usage.

These do NOT require the GPT bearer token because they're called from
the user's browser via the /setup page (or a CLI).  They DO take the
user's Semrush key directly, so they live behind HTTPS in production
and rely on Fernet at rest.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import storage
from app.adapters.semrush_real import SemrushRealAdapter
from app.config import settings
from app.crypto import encrypt, mask

log = logging.getLogger(__name__)
router = APIRouter()


class RegisterRequest(BaseModel):
    semrush_api_key: str = Field(..., min_length=8, max_length=200)
    label: str = Field(..., min_length=1, max_length=80,
                       description="Pick a nickname so you can identify this token later.")
    daily_quota: Optional[int] = Field(None, ge=0, le=100000)
    monthly_quota: Optional[int] = Field(None, ge=0, le=10000000)


class RegisterResponse(BaseModel):
    user_token: str
    label: str
    daily_quota: int
    monthly_quota: int
    semrush_key_masked: str
    notes: list[str] = []


class RevokeRequest(BaseModel):
    user_token: str


class RevokeResponse(BaseModel):
    revoked: bool


class UsageResponse(BaseModel):
    user_token: str
    label: str
    status: str
    daily_used: int
    daily_limit: int
    monthly_used: int
    monthly_limit: int
    total_requests: int
    last_used_at: Optional[str]


@router.post("/register", response_model=RegisterResponse, tags=["byok"],
             summary="Register a Semrush API key and receive an access code")
async def register(req: RegisterRequest) -> RegisterResponse:
    notes: list[str] = []
    api_key = req.semrush_api_key.strip()

    # Optional liveness check on the user's Semrush key
    if settings.validate_semrush_on_register:
        try:
            await _validate_semrush_key(api_key)
            notes.append("Semrush key validated against api.semrush.com (~10 units consumed).")
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Could not validate this Semrush key against api.semrush.com: {exc}. "
                    "Double-check the key in your Semrush account → Subscription info → API."
                ),
            )

    encrypted = encrypt(api_key)
    token = storage.create_user_key(
        label=req.label.strip(),
        encrypted_key=encrypted,
        daily_quota=req.daily_quota,
        monthly_quota=req.monthly_quota,
    )

    summary = storage.get_summary(token)
    return RegisterResponse(
        user_token=token,
        label=summary.label,
        daily_quota=req.daily_quota if req.daily_quota is not None else settings.default_daily_quota,
        monthly_quota=req.monthly_quota if req.monthly_quota is not None else settings.default_monthly_quota,
        semrush_key_masked=mask(api_key),
        notes=notes,
    )


@router.post("/revoke", response_model=RevokeResponse, tags=["byok"],
             summary="Revoke an access code")
async def revoke(req: RevokeRequest) -> RevokeResponse:
    return RevokeResponse(revoked=storage.revoke(req.user_token))


@router.get("/usage/{user_token}", response_model=UsageResponse, tags=["byok"],
            summary="Show usage stats for an access code")
async def usage(user_token: str) -> UsageResponse:
    s = storage.get_summary(user_token)
    if not s:
        raise HTTPException(status_code=404, detail="user_token not found or revoked")
    return UsageResponse(
        user_token=s.user_token,
        label=s.label,
        status=s.status,
        daily_used=s.day_request_count,
        daily_limit=s.daily_quota if s.daily_quota is not None else settings.default_daily_quota,
        monthly_used=s.month_request_count,
        monthly_limit=s.monthly_quota if s.monthly_quota is not None else settings.default_monthly_quota,
        total_requests=s.total_request_count,
        last_used_at=s.last_used_at,
    )


# ---------------------------------------------------------------------------

async def _validate_semrush_key(api_key: str) -> None:
    """Issue the cheapest possible Semrush call — domain_organic with
    display_limit=1 — to confirm the key is alive and has units left."""
    import httpx

    params = {
        "type": "domain_organic",
        "key": api_key,
        "domain": "example.com",
        "database": settings.default_database,
        "display_limit": 1,
        "export_columns": "Ph",
    }
    async with httpx.AsyncClient(base_url=settings.semrush_base_url, timeout=15.0) as client:
        resp = await client.get("/", params=params)
        text = resp.text.strip()
        if resp.status_code >= 500:
            raise RuntimeError(f"Semrush HTTP {resp.status_code}: {text[:200]}")
        if text.startswith("ERROR"):
            raise RuntimeError(text[:200])
