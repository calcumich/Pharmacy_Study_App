"""
Unit tests for the drug-class tree-builder logic in GET /drug-classes.

The router assembles a nested tree from a flat DB result.  These tests inject
a mock session so no live database is needed.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.drugs import DrugClass


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_class(
    *,
    name: str,
    slug: str,
    parent_id: uuid.UUID | None = None,
    description: str | None = None,
    id: uuid.UUID | None = None,
) -> DrugClass:
    obj = DrugClass()
    obj.id = id or uuid.uuid4()
    obj.name = name
    obj.slug = slug
    obj.parent_id = parent_id
    obj.description = description
    return obj


def _db_override(classes: list[DrugClass]):
    """Return a get_db override that yields a mock session returning *classes*."""

    async def override():
        result = MagicMock()
        result.scalars.return_value.all.return_value = classes
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=result)
        yield mock_db

    return override


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


# ── tests ─────────────────────────────────────────────────────────────────────

def test_empty_db_returns_empty_list():
    app.dependency_overrides[get_db] = _db_override([])
    with TestClient(app) as client:
        resp = client.get("/drug-classes")
    assert resp.status_code == 200
    assert resp.json() == []


def test_single_root_no_children():
    root_id = uuid.uuid4()
    app.dependency_overrides[get_db] = _db_override([
        _make_class(name="Antibiotics", slug="antibiotics", id=root_id),
    ])
    with TestClient(app) as client:
        resp = client.get("/drug-classes")
    assert resp.status_code == 200
    tree = resp.json()
    assert len(tree) == 1
    assert tree[0]["id"] == str(root_id)
    assert tree[0]["name"] == "Antibiotics"
    assert tree[0]["children"] == []


def test_multiple_roots_returned():
    app.dependency_overrides[get_db] = _db_override([
        _make_class(name="Antibiotics", slug="antibiotics"),
        _make_class(name="Antifungals", slug="antifungals"),
    ])
    with TestClient(app) as client:
        resp = client.get("/drug-classes")
    assert resp.status_code == 200
    tree = resp.json()
    assert len(tree) == 2
    assert {n["name"] for n in tree} == {"Antibiotics", "Antifungals"}


def test_parent_child_nesting():
    root_id = uuid.uuid4()
    child_id = uuid.uuid4()
    app.dependency_overrides[get_db] = _db_override([
        _make_class(name="Antibiotics", slug="antibiotics", id=root_id),
        _make_class(name="Penicillins", slug="penicillins", parent_id=root_id, id=child_id),
    ])
    with TestClient(app) as client:
        resp = client.get("/drug-classes")
    assert resp.status_code == 200
    tree = resp.json()
    assert len(tree) == 1, "only the root should appear at the top level"
    root = tree[0]
    assert len(root["children"]) == 1
    assert root["children"][0]["id"] == str(child_id)
    assert root["children"][0]["children"] == []


def test_three_level_nesting():
    root_id = uuid.uuid4()
    mid_id = uuid.uuid4()
    leaf_id = uuid.uuid4()
    app.dependency_overrides[get_db] = _db_override([
        _make_class(name="Antibiotics", slug="antibiotics", id=root_id),
        _make_class(name="Beta-lactams", slug="beta-lactams", parent_id=root_id, id=mid_id),
        _make_class(name="Penicillins", slug="penicillins", parent_id=mid_id, id=leaf_id),
    ])
    with TestClient(app) as client:
        resp = client.get("/drug-classes")
    assert resp.status_code == 200
    tree = resp.json()
    assert len(tree) == 1
    mid = tree[0]["children"][0]
    assert mid["id"] == str(mid_id)
    assert len(mid["children"]) == 1
    assert mid["children"][0]["id"] == str(leaf_id)


def test_orphan_node_silently_dropped():
    """A child whose parent_id references no known class disappears from the tree."""
    ghost_parent_id = uuid.uuid4()
    root_id = uuid.uuid4()
    app.dependency_overrides[get_db] = _db_override([
        _make_class(name="Antibiotics", slug="antibiotics", id=root_id),
        _make_class(name="Orphan", slug="orphan", parent_id=ghost_parent_id),
    ])
    with TestClient(app) as client:
        resp = client.get("/drug-classes")
    assert resp.status_code == 200
    tree = resp.json()
    # Orphan is neither root nor attached — it simply disappears.
    assert len(tree) == 1
    assert tree[0]["id"] == str(root_id)
    assert tree[0]["children"] == []


def test_description_included_in_response():
    app.dependency_overrides[get_db] = _db_override([
        _make_class(name="Antibiotics", slug="antibiotics", description="Drugs that kill bacteria"),
    ])
    with TestClient(app) as client:
        resp = client.get("/drug-classes")
    assert resp.json()[0]["description"] == "Drugs that kill bacteria"


def test_null_description_is_none_in_response():
    app.dependency_overrides[get_db] = _db_override([
        _make_class(name="Antibiotics", slug="antibiotics", description=None),
    ])
    with TestClient(app) as client:
        resp = client.get("/drug-classes")
    assert resp.json()[0]["description"] is None
