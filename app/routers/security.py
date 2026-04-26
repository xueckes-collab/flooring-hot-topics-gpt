"""Bearer-token check used by every protected endpoint.

In production, the default placeholder bearer token MUST be replaced.
We refuse to authenticate ANY request when the token still equals the
placeholder AND the server is reachable on a non-loopback host (i.e. it
made it past localhost).  This stops a forgotten .env from quietly
shipping with an open API.
"""
from __future__ import annotations

import logging

from fastapi import Header, HTTPException, status

from app.config import settings

log = logging.getLogger(__name__)

_DEFAULT_BEARER = "changeme-replace-with-long-random-string"
_PUBLIC_HOSTS_LOCAL = ("127.0.0.1", "localhost", "0.0.0.0")


def _looks_like_local() -> bool:
    """Is PUBLIC_BASE_URL pointing at this machine?  We treat that as
    'dev mode' and allow the default token."""
    base = (settings.public_base_url or "").lower()
    return any(h in base for h in _PUBLIC_HOSTS_LOCAL)


async def require_bearer(authorization: str | None = Header(default=None)) -> bool:
    if not settings.api_bearer_token or settings.api_bearer_token == _DEFAULT_BEARER:
        if _looks_like_local():
            return True  # local dev convenience
        log.error(
            "API_BEARER_TOKEN is the default placeholder but PUBLIC_BASE_URL "
            "looks public (%s). Refusing all requests until you set a real "
            "token. Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'",
            settings.public_base_url,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Server misconfigured: API_BEARER_TOKEN is still the default "
                "placeholder. Refusing requests in non-local mode."
            ),
        )

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != settings.api_bearer_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid bearer token")
    return True
