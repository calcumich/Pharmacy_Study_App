from __future__ import annotations

from urllib.error import URLError

import pytest
from jose import JWTError

from app.dependencies import auth


def test_decode_supabase_token_uses_legacy_secret_for_hs_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.settings, "SUPABASE_JWT_SECRET", "legacy-secret")
    monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda _token: {"alg": "HS256"})

    captured: dict = {}

    def fake_decode(token: str, key: object, algorithms: list[str], options: dict) -> dict:
        captured["token"] = token
        captured["key"] = key
        captured["algorithms"] = algorithms
        captured["options"] = options
        return {"sub": "00000000-dead-beef-0000-000000000001"}

    monkeypatch.setattr(auth.jwt, "decode", fake_decode)

    payload = auth._decode_supabase_token("token-value")

    assert payload["sub"] == "00000000-dead-beef-0000-000000000001"
    assert captured == {
        "token": "token-value",
        "key": "legacy-secret",
        "algorithms": ["HS256"],
        "options": {"verify_aud": False},
    }


def test_decode_supabase_token_uses_jwks_for_asymmetric_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    jwks = {"keys": [{"kid": "kid-1", "alg": "ES256", "kty": "EC"}]}
    monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda _token: {"alg": "ES256", "kid": "kid-1"})
    monkeypatch.setattr(auth, "_fetch_jwks", lambda force_refresh=False: jwks)

    captured: dict = {}

    def fake_decode(token: str, key: object, algorithms: list[str], options: dict) -> dict:
        captured["token"] = token
        captured["key"] = key
        captured["algorithms"] = algorithms
        captured["options"] = options
        return {"sub": "00000000-dead-beef-0000-000000000001"}

    monkeypatch.setattr(auth.jwt, "decode", fake_decode)

    payload = auth._decode_supabase_token("token-value")

    assert payload["sub"] == "00000000-dead-beef-0000-000000000001"
    assert captured == {
        "token": "token-value",
        "key": jwks,
        "algorithms": ["ES256"],
        "options": {"verify_aud": False},
    }


def test_decode_supabase_token_refreshes_jwks_after_jwt_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda _token: {"alg": "ES256", "kid": "kid-1"})

    calls: list[bool] = []

    def fake_fetch_jwks(force_refresh: bool = False) -> dict:
        calls.append(force_refresh)
        if force_refresh:
            return {"keys": [{"kid": "kid-1", "alg": "ES256", "kty": "EC", "fresh": True}]}
        return {"keys": [{"kid": "kid-1", "alg": "ES256", "kty": "EC", "fresh": False}]}

    attempts = {"count": 0}

    def fake_decode(_token: str, key: object, _algorithms: list[str], _options: dict) -> dict:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise JWTError("stale jwks")
        return {"sub": "00000000-dead-beef-0000-000000000001", "key": key}

    monkeypatch.setattr(auth, "_fetch_jwks", fake_fetch_jwks)
    monkeypatch.setattr(auth.jwt, "decode", fake_decode)

    payload = auth._decode_supabase_token("token-value")

    assert payload["sub"] == "00000000-dead-beef-0000-000000000001"
    assert calls == [False, True]


@pytest.mark.asyncio
async def test_get_current_user_returns_uuid_from_valid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        auth,
        "_decode_supabase_token",
        lambda _token: {"sub": "00000000-dead-beef-0000-000000000001"},
    )

    user_id = await auth.get_current_user("token-value")

    assert str(user_id) == "00000000-dead-beef-0000-000000000001"


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "_decode_supabase_token", lambda _token: (_ for _ in ()).throw(URLError("boom")))

    with pytest.raises(Exception) as exc_info:
        await auth.get_current_user("token-value")

    assert getattr(exc_info.value, "status_code", None) == 401
