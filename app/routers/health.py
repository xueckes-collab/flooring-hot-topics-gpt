from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    data_source_mode: str
    semrush_configured: bool


@router.get("/health", operation_id="getHealth", summary="Liveness probe", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        data_source_mode=settings.data_source_mode,
        semrush_configured=bool(settings.semrush_api_key),
    )
