from datetime import datetime, timezone
import asyncio
import time
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from apps.api.core.config import settings
from apps.api.core.logging import logger
from apps.api.schemas.health import HealthResponse, ReadinessResponse, ComponentHealth
from apps.api.api.v1.router import api_router


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    from services.streaming.producer import producer
    from apps.api.core.health import ensure_object_store_buckets

    logger.info(
        "BWIP API server initializing",
        extra={
            "environment": settings.ENVIRONMENT,
            "version": settings.VERSION,
            "api_prefix": settings.API_V1_STR,
            "stream_mode": settings.STREAM_MODE,
        },
    )
    await producer.start()
    try:
        object_store = await asyncio.wait_for(
            asyncio.to_thread(ensure_object_store_buckets), timeout=8
        )
        if object_store["created"]:
            logger.info(f"[ObjectStore] Created buckets: {object_store['created']}")
        if object_store["failures"]:
            logger.warning(f"[ObjectStore] Bucket bootstrap incomplete: {object_store['failures']}")
    except Exception as exc:
        logger.warning(f"[ObjectStore] Bucket bootstrap skipped: {exc}")
    yield
    await producer.stop()
    logger.info("BWIP API server shutting down")


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=(
            "National Weather Big Data Analytics Platform (BWIP) — Ministry of Earth Sciences (IMD).\n\n"
            "Central platform for heterogeneous weather observation ingestion, NLP/AI classification, "
            "geospatial clustering, multi-signal corroboration, and real-time incident intelligence across India."
        ),
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Security Headers Middleware
    application.add_middleware(SecurityHeadersMiddleware)

    # CORS Middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Mount API v1
    application.include_router(api_router, prefix=settings.API_V1_STR)

    return application


app = create_application()




@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System Probes"],
    summary="Liveness Probe",
    description="Returns HTTP 200 if the FastAPI application process is alive and accepting traffic."
)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        environment=settings.ENVIRONMENT,
        version=settings.VERSION,
        timestamp=datetime.now(timezone.utc)
    )


@app.get(
    "/ready",
    response_model=ReadinessResponse,
    tags=["System Probes"],
    summary="Readiness Probe",
    description="Validates connectivity to backing dependencies (PostGIS, Redis, Redpanda, MinIO)."
)
async def readiness_check() -> ReadinessResponse:
    from apps.api.core import health

    statuses = await asyncio.gather(
        health.check_database(),
        health.check_cache(),
        health.check_streaming(),
        health.check_object_store(),
    )

    components = {
        "database": ComponentHealth(status=statuses[0][0], details=statuses[0][1]),
        "cache": ComponentHealth(status=statuses[1][0], details=statuses[1][1]),
        "streaming": ComponentHealth(status=statuses[2][0], details=statuses[2][1]),
        "object_store": ComponentHealth(status=statuses[3][0], details=statuses[3][1]),
    }

    overall_status = "ready" if all(c.status == "healthy" for c in components.values()) else "degraded"

    return ReadinessResponse(
        status=overall_status,
        components=components,
        timestamp=datetime.now(timezone.utc)
    )
