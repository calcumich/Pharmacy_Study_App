from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def _db_override(mock_db: AsyncMock):
    async def override():
        yield mock_db

    return override


def test_health_checks_database() -> None:
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = _db_override(mock_db)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}
    mock_db.execute.assert_awaited_once()


def test_health_returns_503_without_db_details() -> None:
    mock_db = AsyncMock()
    mock_db.execute.side_effect = ConnectionRefusedError("connection string leaked here")
    app.dependency_overrides[get_db] = _db_override(mock_db)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_cors_origins_default_to_vite_dev_server() -> None:
    settings = Settings(DATABASE_URL="postgresql+asyncpg://example")

    assert settings.cors_origins == ["http://localhost:5173"]


def test_cors_origins_parse_comma_separated_values() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://example",
        CORS_ORIGINS="http://localhost:5173, https://example.azurestaticapps.net,",
    )

    assert settings.cors_origins == [
        "http://localhost:5173",
        "https://example.azurestaticapps.net",
    ]


def test_cors_preflight_allows_configured_local_origin() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
