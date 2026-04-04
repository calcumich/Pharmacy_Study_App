"""
Unit tests for the study-table endpoint's attribute-shape logic.

The smoke tests only exercise scalar and list shapes via seeded data.
These tests cover all three shapes — especially the relational (DDI) path
which has non-trivial bidirectionality logic — using a mocked DB session.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.drugs import AttributeShape, AttributeType, Drug
from app.models.interactions import DrugInteraction, InteractionSeverity


# ── object factories ──────────────────────────────────────────────────────────

def _make_attr_type(
    *,
    slug: str,
    shape: AttributeShape,
    source_table: str = "",
    id: uuid.UUID | None = None,
) -> AttributeType:
    obj = AttributeType()
    obj.id = id or uuid.uuid4()
    obj.slug = slug
    obj.label = slug.upper()
    obj.shape = shape
    obj.source_table = source_table
    return obj


def _make_drug(
    *,
    name: str,
    attributes: dict | None = None,
    id: uuid.UUID | None = None,
) -> Drug:
    obj = Drug()
    obj.id = id or uuid.uuid4()
    obj.name = name
    obj.attributes = attributes or {}
    return obj


def _make_interaction(
    *,
    drug_a_id: uuid.UUID,
    drug_b_id: uuid.UUID,
    severity: InteractionSeverity = InteractionSeverity.moderate,
    description: str = "Test interaction",
) -> DrugInteraction:
    obj = DrugInteraction()
    obj.id = uuid.uuid4()
    obj.drug_a_id = drug_a_id
    obj.drug_b_id = drug_b_id
    obj.severity = severity
    obj.description = description
    return obj


# ── mock helpers ──────────────────────────────────────────────────────────────

def _scalars_result(rows: list) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _db_override(sequential_results: list[list]):
    """
    Return a get_db override whose mock session returns each entry in
    *sequential_results* on successive calls to db.execute().
    """

    async def override():
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[_scalars_result(r) for r in sequential_results]
        )
        yield mock_db

    return override


def _table_request(drug_ids: list[uuid.UUID], at_ids: list[uuid.UUID]) -> dict:
    """Build params list for GET /study/table."""
    params = [("drug_ids", str(d)) for d in drug_ids]
    params += [("attribute_type_ids", str(a)) for a in at_ids]
    return params


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


# ── relational (DDI) shape ────────────────────────────────────────────────────

class TestRelationalShape:
    def test_drug_a_in_set_sees_interaction(self):
        """drug_a is requested; drug_b is not. Interaction must appear in drug_a's cell."""
        drug_a_id = uuid.uuid4()
        drug_b_id = uuid.uuid4()
        at_id = uuid.uuid4()

        at = _make_attr_type(slug="ddis", shape=AttributeShape.relational, id=at_id)
        drug_a = _make_drug(name="Drug A", id=drug_a_id)
        iact = _make_interaction(
            drug_a_id=drug_a_id,
            drug_b_id=drug_b_id,
            severity=InteractionSeverity.major,
            description="Serious risk",
        )

        app.dependency_overrides[get_db] = _db_override([[at], [drug_a], [iact]])
        with TestClient(app) as client:
            resp = client.get("/study/table", params=_table_request([drug_a_id], [at_id]))

        assert resp.status_code == 200
        cells = resp.json()["cells"]
        assert len(cells) == 1
        assert cells[0]["drug_id"] == str(drug_a_id)
        entry = cells[0]["content"][0]
        assert entry["severity"] == "major"
        assert entry["description"] == "Serious risk"
        assert entry["partner_id"] == str(drug_b_id)

    def test_drug_b_in_set_sees_interaction(self):
        """drug_b is requested; drug_a is not. Interaction must appear in drug_b's cell."""
        drug_a_id = uuid.uuid4()
        drug_b_id = uuid.uuid4()
        at_id = uuid.uuid4()

        at = _make_attr_type(slug="ddis", shape=AttributeShape.relational, id=at_id)
        drug_b = _make_drug(name="Drug B", id=drug_b_id)
        iact = _make_interaction(drug_a_id=drug_a_id, drug_b_id=drug_b_id, description="Moderate effect")

        app.dependency_overrides[get_db] = _db_override([[at], [drug_b], [iact]])
        with TestClient(app) as client:
            resp = client.get("/study/table", params=_table_request([drug_b_id], [at_id]))

        assert resp.status_code == 200
        cells = resp.json()["cells"]
        assert len(cells) == 1
        entry = cells[0]["content"][0]
        assert entry["partner_id"] == str(drug_a_id)
        assert entry["description"] == "Moderate effect"

    def test_both_drugs_in_set_each_see_interaction(self):
        """Both drug_a and drug_b requested — the interaction appears in BOTH cells."""
        drug_a_id = uuid.uuid4()
        drug_b_id = uuid.uuid4()
        at_id = uuid.uuid4()

        at = _make_attr_type(slug="ddis", shape=AttributeShape.relational, id=at_id)
        drug_a = _make_drug(name="Drug A", id=drug_a_id)
        drug_b = _make_drug(name="Drug B", id=drug_b_id)
        iact = _make_interaction(drug_a_id=drug_a_id, drug_b_id=drug_b_id)

        app.dependency_overrides[get_db] = _db_override([[at], [drug_a, drug_b], [iact]])
        with TestClient(app) as client:
            resp = client.get(
                "/study/table",
                params=_table_request([drug_a_id, drug_b_id], [at_id]),
            )

        assert resp.status_code == 200
        cells = resp.json()["cells"]
        assert len(cells) == 2

        by_drug = {c["drug_id"]: c["content"] for c in cells}
        assert len(by_drug[str(drug_a_id)]) == 1
        assert by_drug[str(drug_a_id)][0]["partner_id"] == str(drug_b_id)
        assert len(by_drug[str(drug_b_id)]) == 1
        assert by_drug[str(drug_b_id)][0]["partner_id"] == str(drug_a_id)

    def test_no_interactions_returns_empty_list(self):
        drug_id = uuid.uuid4()
        at_id = uuid.uuid4()

        at = _make_attr_type(slug="ddis", shape=AttributeShape.relational, id=at_id)
        drug = _make_drug(name="Drug", id=drug_id)

        app.dependency_overrides[get_db] = _db_override([[at], [drug], []])
        with TestClient(app) as client:
            resp = client.get("/study/table", params=_table_request([drug_id], [at_id]))

        assert resp.status_code == 200
        assert resp.json()["cells"][0]["content"] == []

    def test_interaction_severity_string_value_in_response(self):
        """The severity enum value (not the Python enum object) must appear in the JSON."""
        drug_a_id = uuid.uuid4()
        drug_b_id = uuid.uuid4()
        at_id = uuid.uuid4()

        at = _make_attr_type(slug="ddis", shape=AttributeShape.relational, id=at_id)
        drug_a = _make_drug(name="Drug A", id=drug_a_id)
        iact = _make_interaction(
            drug_a_id=drug_a_id,
            drug_b_id=drug_b_id,
            severity=InteractionSeverity.contraindicated,
        )

        app.dependency_overrides[get_db] = _db_override([[at], [drug_a], [iact]])
        with TestClient(app) as client:
            resp = client.get("/study/table", params=_table_request([drug_a_id], [at_id]))

        entry = resp.json()["cells"][0]["content"][0]
        assert entry["severity"] == "contraindicated"


# ── scalar shape ──────────────────────────────────────────────────────────────

class TestScalarShape:
    def test_scalar_present_in_jsonb(self):
        drug_id = uuid.uuid4()
        at_id = uuid.uuid4()

        at = _make_attr_type(slug="moa", shape=AttributeShape.scalar, id=at_id)
        drug = _make_drug(name="Amoxicillin", attributes={"moa": "Inhibits cell wall synthesis"}, id=drug_id)

        app.dependency_overrides[get_db] = _db_override([[at], [drug]])
        with TestClient(app) as client:
            resp = client.get("/study/table", params=_table_request([drug_id], [at_id]))

        assert resp.status_code == 200
        assert resp.json()["cells"][0]["content"] == "Inhibits cell wall synthesis"

    def test_scalar_missing_jsonb_key_returns_null(self):
        """A scalar attribute not in drug.attributes JSONB → content: null."""
        drug_id = uuid.uuid4()
        at_id = uuid.uuid4()

        at = _make_attr_type(slug="half_life", shape=AttributeShape.scalar, id=at_id)
        drug = _make_drug(name="Drug", attributes={}, id=drug_id)

        app.dependency_overrides[get_db] = _db_override([[at], [drug]])
        with TestClient(app) as client:
            resp = client.get("/study/table", params=_table_request([drug_id], [at_id]))

        assert resp.status_code == 200
        assert resp.json()["cells"][0]["content"] is None


# ── fallback / edge cases ─────────────────────────────────────────────────────

class TestEdgeCases:
    def test_unknown_attribute_type_id_produces_null_cell(self):
        """attribute_type_id not found in the DB → content: null for each drug."""
        drug_id = uuid.uuid4()
        ghost_at_id = uuid.uuid4()
        drug = _make_drug(name="Drug", id=drug_id)

        app.dependency_overrides[get_db] = _db_override([
            [],      # attr types query: nothing returned
            [drug],  # drugs query
        ])
        with TestClient(app) as client:
            resp = client.get("/study/table", params=_table_request([drug_id], [ghost_at_id]))

        assert resp.status_code == 200
        assert resp.json()["cells"][0]["content"] is None

    def test_list_shape_unknown_source_table_returns_empty_list(self):
        """list-shape attribute whose source_table isn't in _LIST_MODELS → content: []."""
        drug_id = uuid.uuid4()
        at_id = uuid.uuid4()

        at = _make_attr_type(
            slug="custom",
            shape=AttributeShape.list,
            source_table="nonexistent_table",
            id=at_id,
        )
        drug = _make_drug(name="Drug", id=drug_id)

        # Only 2 execute calls: attr types + drugs (no 3rd call for list rows
        # because the code short-circuits on unknown source_table).
        app.dependency_overrides[get_db] = _db_override([[at], [drug]])
        with TestClient(app) as client:
            resp = client.get("/study/table", params=_table_request([drug_id], [at_id]))

        assert resp.status_code == 200
        assert resp.json()["cells"][0]["content"] == []

    def test_response_preserves_requested_drug_and_attr_id_order(self):
        """drug_ids and attribute_type_ids in the response must match request order."""
        drug_a_id = uuid.uuid4()
        drug_b_id = uuid.uuid4()
        at_id = uuid.uuid4()

        at = _make_attr_type(slug="moa", shape=AttributeShape.scalar, id=at_id)
        drug_a = _make_drug(name="A", id=drug_a_id)
        drug_b = _make_drug(name="B", id=drug_b_id)

        app.dependency_overrides[get_db] = _db_override([[at], [drug_a, drug_b]])
        with TestClient(app) as client:
            resp = client.get(
                "/study/table",
                params=_table_request([drug_a_id, drug_b_id], [at_id]),
            )

        payload = resp.json()
        assert payload["drug_ids"] == [str(drug_a_id), str(drug_b_id)]
        assert payload["attribute_type_ids"] == [str(at_id)]
