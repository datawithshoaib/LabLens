"""OIDC JWT verification and owner identity resolution."""

from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from lablens.core.config import Settings, get_settings
from lablens.db.models import User
from lablens.db.session import get_session

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    issuer: str
    subject: str


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, timeout=5, lifespan=300)


def _decode_token(token: str, settings: Settings) -> Principal:
    if not settings.oidc_jwks_url or not settings.oidc_issuer or not settings.oidc_audience:
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    signing_key = _jwks_client(settings.oidc_jwks_url).get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=settings.oidc_algorithms,
        audience=settings.oidc_audience,
        issuer=settings.oidc_issuer,
        options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        leeway=30,
    )
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject or len(subject) > 512:
        raise jwt.InvalidTokenError("Invalid subject")
    return Principal(issuer=settings.oidc_issuer, subject=subject)


async def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    settings = get_settings()
    token = credentials.credentials if credentials else None
    if settings.app_env == "development" and settings.development_auth_token is not None:
        if token and token == settings.development_auth_token.get_secret_value():
            return Principal(issuer="local-development", subject="developer")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return await run_in_threadpool(_decode_token, token, settings)
    except (jwt.InvalidTokenError, PyJWKClientError, OSError, TimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> User:
    statement = (
        insert(User)
        .values(issuer=principal.issuer, subject=principal.subject)
        .on_conflict_do_nothing(index_elements=["issuer", "subject"])
    )
    await session.execute(statement)
    await session.commit()
    result = await session.execute(
        select(User).where(User.issuer == principal.issuer, User.subject == principal.subject)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=503, detail="Account could not be resolved")
    return user
