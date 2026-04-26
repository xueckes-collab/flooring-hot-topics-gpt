from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/health", operation_id="getHealth", summary="Liveness probe")
async def health() -> dict:
    return {
        "status": "ok",
        "data_source_mode": settings.data_source_mode,
        "semrush_configured": bool(settings.semrush_api_key),
    }
