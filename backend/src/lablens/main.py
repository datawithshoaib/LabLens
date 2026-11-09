"""FastAPI application entry point."""

import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import RequestResponseEndpoint

from lablens.api.middleware import UploadBodyLimitMiddleware
from lablens.api.reports import router as reports_router
from lablens.api.routes import router
from lablens.core.config import get_settings
from lablens.db.session import engine

settings = get_settings()
logger = logging.getLogger("lablens.api")


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Create process-local connections and fail startup if Redis is unavailable."""
    redis = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=3,
        max_connections=50,
        health_check_interval=30,
    )
    try:
        await redis.ping()
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        application.state.redis = redis
        yield
    finally:
        await redis.aclose()
        await engine.dispose()


app = FastAPI(
    title="LabLens API",
    summary="Educational lab report comparison service",
    version="0.1.0",
    openapi_url="/openapi.json" if settings.app_env != "production" else None,
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(UploadBodyLimitMiddleware, max_upload_bytes=settings.max_upload_bytes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: RequestResponseEndpoint) -> Response:
    supplied_id = request.headers.get("X-Request-ID", "")
    request_id = (
        supplied_id if re.fullmatch(r"[A-Za-z0-9._-]{1,128}", supplied_id) else str(uuid4())
    )
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(Exception)
async def safe_unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    """Do not expose exception details or potentially sensitive payloads."""
    logger.error(
        "Unhandled application exception type=%s request_id=%s",
        type(exc).__name__,
        getattr(request.state, "request_id", "unknown"),
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health/live", tags=["health"])
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def readiness() -> dict[str, str]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        await app.state.redis.ping()
    except (SQLAlchemyError, RedisError, OSError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail="Service dependencies are unavailable") from exc
    return {"status": "ready"}


app.include_router(router, prefix=settings.api_v1_prefix)
app.include_router(reports_router, prefix=settings.api_v1_prefix)
