"""
Smoke tests for write endpoints:
  POST /study/sessions
  POST /study/review
  GET  /study/queue
  PATCH /study/flashcard-state

These tests hit the real database (DATABASE_URL must be set).
Auth is provided via app.dependency_overrides[get_current_user] in conftest.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_drug_id(client: TestClient) -> str:
    classes = client.get("/drug-classes").json()
    for node in _flatten(classes):
        drugs = client.get(f"/drug-classes/{node['id']}/drugs").json()
        if drugs:
            return drugs[0]["id"]
    raise AssertionError("No seeded drug found")


def _first_attribute_type_id(client: TestClient) -> str:
    attr_types = client.get("/attribute-types").json()
    if not attr_types:
        raise AssertionError("No seeded attribute types found")
    return attr_types[0]["id"]


def _two_drug_ids(client: TestClient) -> tuple[str, str]:
    classes = client.get("/drug-classes").json()
    found: list[str] = []
    for node in _flatten(classes):
        drugs = client.get(f"/drug-classes/{node['id']}/drugs").json()
        for d in drugs:
            if d["id"] not in found:
                found.append(d["id"])
            if len(found) == 2:
                return found[0], found[1]
    raise AssertionError("Need at least two seeded drugs")


def _flatten(nodes: list[dict]) -> list[dict]:
    out: list[dict] = []
    for n in nodes:
        out.append(n)
        out.extend(_flatten(n.get("children", [])))
    return out


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_create_session_returns_id(client: TestClient) -> None:
    drug_id = _first_drug_id(client)

    resp = client.post(
        "/study/sessions",
        json={"drug_ids": [drug_id], "mode": "flashcard"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert "session_id" in body
    assert "started_at" in body
    # session_id must be a valid UUID
    UUID(body["session_id"])


def test_review_new_card(client: TestClient) -> None:
    drug_id = _first_drug_id(client)

    resp = client.post(
        "/study/review",
        json={"drug_id": drug_id, "rating": 3},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] in {"learning", "review"}
    assert body["review_count"] >= 1
    due = datetime.fromisoformat(body["due_date"])
    assert due > datetime.now(timezone.utc)


def test_review_upserts_not_inserts(client: TestClient) -> None:
    drug_id = _first_drug_id(client)

    # First review
    r1 = client.post(
        "/study/review",
        json={"drug_id": drug_id, "rating": 3},
    )
    assert r1.status_code == 200
    count_after_first = r1.json()["review_count"]

    # Second review for the same (user, drug) — must trigger ON CONFLICT UPDATE
    r2 = client.post(
        "/study/review",
        json={"drug_id": drug_id, "rating": 3},
    )
    assert r2.status_code == 200
    count_after_second = r2.json()["review_count"]

    assert count_after_second == count_after_first + 1, (
        "review_count should increment on conflict-update, not stay at 1"
    )


def test_review_again_then_queue(client: TestClient) -> None:
    drug_id = _first_drug_id(client)

    # rating=1 (Again) keeps the card due immediately
    r = client.post(
        "/study/review",
        json={"drug_id": drug_id, "rating": 1},
    )
    assert r.status_code == 200

    resp = client.get("/study/queue")
    assert resp.status_code == 200
    drug_ids_in_queue = [item["drug_id"] for item in resp.json()["items"]]
    assert drug_id in drug_ids_in_queue, (
        "Drug rated Again should appear in the queue immediately"
    )


def test_queue_respects_drug_ids_filter(client: TestClient) -> None:
    drug_a, drug_b = _two_drug_ids(client)

    for drug_id in (drug_a, drug_b):
        r = client.post(
            "/study/review",
            json={"drug_id": drug_id, "rating": 1},
        )
        assert r.status_code == 200

    # Filter queue to drug_a only
    resp = client.get(
        "/study/queue",
        params={"drug_ids": drug_a},
    )
    assert resp.status_code == 200
    returned_ids = [item["drug_id"] for item in resp.json()["items"]]
    assert drug_a in returned_ids
    assert drug_b not in returned_ids, (
        "Queue with drug_ids filter must exclude drugs not in the filter list"
    )


def test_flashcard_state_conflict_update_preserves_unchanged_fields(client: TestClient) -> None:
    drug_id = _first_drug_id(client)
    attr_id = _first_attribute_type_id(client)

    # Reset to a known baseline before testing conflict-update semantics.
    client.patch(
        f"/study/flashcard-state/{drug_id}/{attr_id}",
        json={"is_buried": False, "is_flagged": False, "user_note": None},
    )

    # First patch: bury the card.
    r1 = client.patch(
        f"/study/flashcard-state/{drug_id}/{attr_id}",
        json={"is_buried": True},
    )
    assert r1.status_code == 201
    assert r1.json()["is_buried"] is True
    assert r1.json()["is_flagged"] is False

    # Second patch: flag the card only (is_buried omitted / None).
    r2 = client.patch(
        f"/study/flashcard-state/{drug_id}/{attr_id}",
        json={"is_flagged": True},
    )
    assert r2.status_code == 201
    assert r2.json()["is_buried"] is True, (
        "Conflict-update must not reset is_buried when it was not included in the patch"
    )
    assert r2.json()["is_flagged"] is True


def test_flashcard_state_user_note(client: TestClient) -> None:
    drug_id = _first_drug_id(client)
    attr_id = _first_attribute_type_id(client)

    resp = client.patch(
        f"/study/flashcard-state/{drug_id}/{attr_id}",
        json={"user_note": "review this mechanism"},
    )
    assert resp.status_code == 201
    assert resp.json()["user_note"] == "review this mechanism"
