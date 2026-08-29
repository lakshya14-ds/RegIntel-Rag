from app.api.routes_health import router as health_router
from app.api.routes_rag import router as rag_router
from app.api.routes_documents import router as documents_router

__all__ = ["health_router", "rag_router", "documents_router"]
