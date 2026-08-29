"""
Health and Status Routes for RegIntel FastAPI Backend.
"""

import logging
from fastapi import APIRouter
from app.config import settings
from app.db import db
from app.schemas.responses import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="System Health Check")
def get_health() -> HealthResponse:
    """
    Checks MongoDB connection and Gemini embedding API key configuration.
    Returns status: 'ok', 'degraded', or 'unavailable'.
    """
    mongo_ok = False
    try:
        if db.client is not None:
            db.client.admin.command("ping")
            mongo_ok = True
    except Exception as e:
        logger.warning(f"MongoDB ping check failed during /health: {e}")
        mongo_ok = False

    embedding_service_ok = bool(settings.gemini_api_key and len(settings.gemini_api_key.strip()) > 5)

    if mongo_ok and embedding_service_ok:
        overall_status = "ok"
    elif embedding_service_ok:
        overall_status = "degraded"  # Local offline mode supported
    else:
        overall_status = "unavailable"

    return HealthResponse(
        status=overall_status,
        mongodb=mongo_ok,
        embedding_service=embedding_service_ok,
        environment="development" if settings.debug_mode else "production",
        version=settings.regintel_version
    )
