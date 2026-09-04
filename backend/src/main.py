from contextlib import asynccontextmanager, suppress
import asyncio

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.core.exceptions import register_exception_handlers
from src.core.middleware import ProductionHTTPMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle events."""
    from src.services.integrations.whatsapp.runtime import notification_loop, baileys_poller_loop

    worker = asyncio.create_task(notification_loop(app))
    baileys_worker = asyncio.create_task(baileys_poller_loop(app))
    try:
        yield
    finally:
        worker.cancel()
        baileys_worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker
        with suppress(asyncio.CancelledError):
            await baileys_worker


def create_application() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="Contractor Financial SaaS - Single-Input Double-Entry Backend API",
        version="1.0.0",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )
    app.add_middleware(ProductionHTTPMiddleware)
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.BACKEND_CORS_ORIGINS,
            allow_credentials="*" not in settings.BACKEND_CORS_ORIGINS,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(app)
    from src.api.v1 import api_router

    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get("/health", tags=["System"])
    async def health_check():
        return {"status": "healthy", "environment": settings.ENVIRONMENT, "project": settings.PROJECT_NAME}

    @app.get("/ready", tags=["System"])
    async def readiness_check(db: AsyncSession = Depends(get_db)):
        try:
            await db.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {"status": "ready"}

    return app


app = create_application()
