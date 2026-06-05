from __future__ import annotations

import asyncio
import time
import uuid

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
_JWKS_CACHE_TTL_SECONDS = 600
_JWKS_FETCH_TIMEOUT_SECONDS = 5.0

_jwks_cache: dict | None = None
_jwks_cache_expires_at = 0.0
# Serialise concurrent JWKS fetches so the first cold-start request doesn't fan
# out into N upstream calls under load.
_jwks_fetch_lock = asyncio.Lock()


def _jwks_url() -> str:
    base_url = settings.SUPABASE_URL.rstrip("/")
    if not base_url:
        raise RuntimeError("SUPABASE_URL is required for asymmetric Supabase JWT verification")
    return f"{base_url}/auth/v1/.well-known/jwks.json"


async def _fetch_jwks(*, force_refresh: bool = False) -> dict:
    global _jwks_cache
    global _jwks_cache_expires_at

    now = time.time()
    if not force_refresh and _jwks_cache is not None and now < _jwks_cache_expires_at:
        return _jwks_cache

    async with _jwks_fetch_lock:
        # Re-check after acquiring the lock — another caller may have just refreshed.
        now = time.time()
        if not force_refresh and _jwks_cache is not None and now < _jwks_cache_expires_at:
            return _jwks_cache

        async with httpx.AsyncClient(timeout=_JWKS_FETCH_TIMEOUT_SECONDS) as client:
            response = await client.get(_jwks_url())
            response.raise_for_status()
            jwks = response.json()

        if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
            raise RuntimeError("Invalid JWKS response from Supabase")

        _jwks_cache = jwks
        _jwks_cache_expires_at = now + _JWKS_CACHE_TTL_SECONDS
        return jwks


async def _decode_supabase_token(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    algorithm = header.get("alg")
    if not algorithm:
        raise JWTError("Missing JWT alg header")

    if algorithm.startswith("HS"):
        if not settings.SUPABASE_JWT_SECRET:
            raise RuntimeError("SUPABASE_JWT_SECRET is required for HS* Supabase JWT verification")
        return jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=[algorithm],
            options={"verify_aud": False},
        )

    try:
        jwks = await _fetch_jwks()
        return jwt.decode(
            token,
            jwks,
            algorithms=[algorithm],
            options={"verify_aud": False},
        )
    except JWTError:
        # Retry once with a forced refresh in case Supabase rotated keys.
        jwks = await _fetch_jwks(force_refresh=True)
        return jwt.decode(
            token,
            jwks,
            algorithms=[algorithm],
            options={"verify_aud": False},
        )


async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> uuid.UUID:
    if settings.AUTH_MODE == "dev":
        try:
            return uuid.UUID(settings.DEV_USER_ID)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid dev user")

    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        payload = await _decode_supabase_token(token)
        sub: str | None = payload.get("sub")
        if sub is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return uuid.UUID(sub)
    except (JWTError, httpx.HTTPError, RuntimeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
