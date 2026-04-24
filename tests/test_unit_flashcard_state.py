"""
Unit tests for PATCH /study/flashcard-state/{drug_id}/{attribute_type_id}.

Uses dependency_overrides to mock the DB session — no live database required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.study import FlashcardState


# ── constants ─────────────────────────────────────────────────────────────────

TEST_USER_ID   = uuid.UUID("00000000-dead-beef-0000-000000000001")
TEST_DRUG_ID   = uuid.uuid4()
TEST_ATTR_ID   = uuid.uuid4()


# ── mock helpers ──────────────────────────────────────────────────────────────

def _make_flashcard_row(
    *,
    is_buried: bool = False,
    is_flagged: bool = False,
    user_note: str | None = None,
) -> FlashcardState:
    row = FlashcardState()
    row.user_id          = TEST_USER_ID
    row.drug_id          = TEST_DRUG_ID
    row.attribute_type_id = TEST_ATTR_ID
    row.is_buried        = is_buried
    row.is_flagged       = is_flagged
    row.user_note        = user_note
    row.updated_at       = datetime.now(timezone.utc)
    return row


def _scalar_one_result(row) -> MagicMock:
    """Mock execute() result consumed via .scalar_one()."""
    result = MagicMock()
    result.scalar_one.return_value = row
    return result


def _db_override(refetch_row: FlashcardState):
    """
    get_db override for the flashcard-state endpoint.

    The endpoint makes two execute() calls:
      1. pg_insert upsert — result is not read
      2. SELECT re-fetch  — result consumed via .scalar_one()
    """
    async def override():
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                MagicMock(),                      # 1. upsert (ignored)
                _scalar_one_result(refetch_row),  # 2. re-fetch
            ]
        )
        yield mock_db

    return override


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


# ── tests ─────────────────────────────────────────────────────────────────────

def test_patch_creates_new_state() -> None:
    row = _make_flashcard_row(is_buried=True)
    app.dependency_overrides[get_db] = _db_override(row)

    with TestClient(app) as client:
        resp = client.patch(
            f"/study/flashcard-state/{TEST_DRUG_ID}/{TEST_ATTR_ID}",
            json={"user_id": str(TEST_USER_ID), "is_buried": True},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["drug_id"]          == str(TEST_DRUG_ID)
    assert body["attribute_type_id"] == str(TEST_ATTR_ID)
    assert body["is_buried"]        is True
    assert body["is_flagged"]       is False
    assert body["user_note"]        is None
    assert "updated_at" in body


def test_patch_with_all_none_fields_succeeds() -> None:
    row = _make_flashcard_row()  # all defaults: False / False / None
    app.dependency_overrides[get_db] = _db_override(row)

    with TestClient(app) as client:
        resp = client.patch(
            f"/study/flashcard-state/{TEST_DRUG_ID}/{TEST_ATTR_ID}",
            json={"user_id": str(TEST_USER_ID)},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["is_buried"]  is False
    assert body["is_flagged"] is False
    assert body["user_note"]  is None
