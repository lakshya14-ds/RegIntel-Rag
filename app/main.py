"""
Main FastAPI Application Entrypoint for RegIntel RAG.

Provides regulatory intelligence REST APIs for question answering, document comparison,
version tracking, multi-method search, and health monitoring.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.api.routes_health import router as health_router
from app.api.routes_rag import router as rag_router
from app.api.routes_documents import router as documents_router
from app.api.routes_compliance import router as compliance_router
from app.api.routes_connectors import router as connectors_router

# Setup logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug_mode else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("regintel.api")


import uuid

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    logger.info("Starting RegIntel RAG FastAPI service...")
    logger.info(f"Debug Mode: {settings.debug_mode} | Environment: {'DEV' if settings.debug_mode else 'PROD'}")
    yield
    logger.info("Shutting down RegIntel RAG FastAPI service...")
    try:
        from app.observability.langfuse_tracer import langfuse_tracer
        langfuse_tracer.flush()
        langfuse_tracer.shutdown()
    except Exception as e:
        logger.warning(f"Error during Langfuse shutdown flush: {e}")


app = FastAPI(
    title="RegIntel RAG — Regulatory Intelligence & Change Analysis API",
    description=(
        "Production-ready, grounded regulatory intelligence API with hybrid vector/BM25 retrieval, "
        "neural cross-encoder reranking, strict citation validation, and automated document version tracking."
    ),
    version=settings.regintel_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# -------------------------------------------------------------
# Request Correlation ID Middleware
# -------------------------------------------------------------
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
    # Attach to request state for downstream handlers
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# -------------------------------------------------------------
# CORS Middleware Configuration
# -------------------------------------------------------------
cors_origins_list = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
if not cors_origins_list:
    cors_origins_list = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8501", "http://127.0.0.1:8501"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list if not settings.debug_mode else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# Exception Handlers
# -------------------------------------------------------------
from fastapi.encoders import jsonable_encoder
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Formats Pydantic 422 validation errors cleanly."""
    logger.warning(f"Request validation failed on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "message": "Invalid request parameters or payload format.",
            "details": jsonable_encoder(exc.errors())
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Preserves specific HTTP error codes (400, 404, 422, etc.)."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catches unhandled server errors and logs them server-side without leaking traces."""
    logger.error(f"Unhandled exception processing {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected server error occurred while processing your regulatory request."
        }
    )


# -------------------------------------------------------------
# Include Routers
# -------------------------------------------------------------
app.include_router(health_router)
app.include_router(rag_router)
app.include_router(documents_router)
app.include_router(compliance_router)
app.include_router(connectors_router)
from app.api.routes_cross_regulator import router as cross_regulator_router
app.include_router(cross_regulator_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.fastapi_host,
        port=settings.fastapi_port,
        reload=settings.debug_mode
    )
