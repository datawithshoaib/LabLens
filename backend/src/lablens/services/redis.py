"""Redis client lifecycle and upload throttling dependency."""

from fastapi import HTTPException, Request
from redis.asyncio import Redis


async def get_redis(request: Request) -> Redis:
    redis: Redis | None = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=503, detail="Queue service is unavailable")
    return redis
