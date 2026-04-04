"""
Tests for 404 and empty-result edge cases.

All tests use mocked DB sessions — no live database needed.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


# ── mock helpers ──────────────────────────────────────────────────────────────

def _orm_result(rows: list) -> MagicMock:
    """Mock for results consumed via .scalars().all()."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _scalar_result(value) -> MagicMock:
    """Mock for results consumed via .scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _cte_result(rows: list[tuple]) -> MagicMock:
    """Mock for results consumed via `for row in result` (raw CTE iteration)."""
    result = MagicMock()
    result.__iter__ = MagicMock(return_value=iter(rows))
    return result


def _db_override(sequential_results: list):
    async def override():
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=sequential_results)
        yield mock_db

    return override


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


# ── 404 paths ─────────────────────────────────────────────────────────────────

def test_get_drug_unknown_id_returns_404():
    app.dependency_overrides[get_db] = _db_override([_scalar_result(None)])
    with TestClient(app) as client:
        resp = client.get(f"/drugs/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Drug not found"


def test_get_drugs_by_class_unknown_id_returns_404():
    """class_id absent from the DB → CTE returns nothing → 404."""
    app.dependency_overrides[get_db] = _db_override([_cte_result([])])
    with TestClient(app) as client:
        resp = client.get(f"/drug-classes/{uuid.uuid4()}/drugs")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Drug class not found"


# ── empty-result (200) paths ──────────────────────────────────────────────────

def test_get_drugs_by_class_with_no_drugs_returns_empty_list():
    """A valid class that has no drugs should return 200 [], not 404."""
    class_id = uuid.uuid4()
    app.dependency_overrides[get_db] = _db_override([
        _cte_result([(class_id,)]),  # CTE: the class exists
        _orm_result([]),              # drugs query: none found
    ])
    with TestClient(app) as client:
        resp = client.get(f"/drug-classes/{class_id}/drugs")
    assert resp.status_code == 200
    assert resp.json() == []
