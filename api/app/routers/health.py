from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "service": "brewing-api",
        "environment": s.environment,
        "settlement_provider": s.settlement_provider,
    }
