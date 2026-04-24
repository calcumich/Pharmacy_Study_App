from __future__ import annotations

import json
import time
import uuid
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
_JWKS_CACHE_TTL_SECONDS = 600
_jwks_cache: dict | None = None
_jwks_cache_expires_at = 0.0


def _jwks_url() -> str:
    base_url = settings.SUPABASE_URL.rstrip("/")
    if not base_url:
        raise RuntimeError("SUPABASE_URL is required for asymmetric Supabase JWT verification")
    return f"{base_url}/auth/v1/.well-known/jwks.json"


def _fetch_jwks(*, force_refresh: bool = False) -> dict:
    global _jwks_cache
    global _jwks_cache_expires_at

    now = time.time()
    if not force_refresh and _jwks_cache is not None and now < _jwks_cache_expires_at:
        return _jwks_cache

    with urlopen(_jwks_url(), timeout=5) as response:
        jwks = json.load(response)

    if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
        raise RuntimeError("Invalid JWKS response from Supabase")

    _jwks_cache = jwks
    _jwks_cache_expires_at = now + _JWKS_CACHE_TTL_SECONDS
    return jwks


def _decode_supabase_token(token: str) -> dict:
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
        jwks = _fetch_jwks()
        return jwt.decode(
            token,
            jwks,
            algorithms=[algorithm],
            options={"verify_aud": False},
        )
    except JWTError:
        # Retry once with a forced refresh in case Supabase rotated keys.
        jwks = _fetch_jwks(force_refresh=True)
        return jwt.decode(
            token,
            jwks,
            algorithms=[algorithm],
            options={"verify_aud": False},
        )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> uuid.UUID:
    try:
        payload = _decode_supabase_token(token)
        sub: str | None = payload.get("sub")
        if sub is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return uuid.UUID(sub)
    except (JWTError, URLError, RuntimeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
