from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _flatten_classes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for node in nodes:
        flat.append(node)
        flat.extend(_flatten_classes(node.get("children", [])))
    return flat


def _find_class_with_drugs(nodes: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    for node in _flatten_classes(nodes):
        response = client.get(f"/drug-classes/{node['id']}/drugs")
        assert response.status_code == 200
        drugs = response.json()
        if drugs:
            return node["id"], drugs
    raise AssertionError("Expected at least one seeded drug class with drugs")


def test_healthcheck() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_seeded_attribute_types_are_available() -> None:
    response = client.get("/attribute-types")

    assert response.status_code == 200
    payload = response.json()
    slugs = [item["slug"] for item in payload]

    assert slugs == ["moa", "half_life", "indications", "adrs", "metabolism", "ddis"]


def test_seeded_class_tree_and_drugs_are_available() -> None:
    response = client.get("/drug-classes")

    assert response.status_code == 200
    classes = response.json()
    assert classes, "Expected seeded drug classes"

    class_id, drugs = _find_class_with_drugs(classes)

    assert class_id
    assert drugs, "Expected seeded drugs for at least one class"
    assert {"id", "name", "drug_class_id"} <= set(drugs[0].keys())


def test_seeded_drug_detail_contains_attributes_and_lists() -> None:
    classes = client.get("/drug-classes").json()
    _, drugs = _find_class_with_drugs(classes)
    drug_id = drugs[0]["id"]

    response = client.get(f"/drugs/{drug_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == drug_id
    assert isinstance(payload["attributes"], dict)
    assert isinstance(payload["indications"], list)
    assert isinstance(payload["adrs"], list)
    assert isinstance(payload["metabolism"], list)


def test_study_table_returns_cells_for_seeded_data() -> None:
    classes = client.get("/drug-classes").json()
    _, drugs = _find_class_with_drugs(classes)
    attribute_types = client.get("/attribute-types").json()

    params = [
        ("drug_ids", drugs[0]["id"]),
        ("attribute_type_ids", attribute_types[0]["id"]),
        ("attribute_type_ids", attribute_types[2]["id"]),
    ]

    response = client.get("/study/table", params=params)

    assert response.status_code == 200
    payload = response.json()
    assert payload["drug_ids"] == [drugs[0]["id"]]
    assert payload["attribute_type_ids"] == [
        attribute_types[0]["id"],
        attribute_types[2]["id"],
    ]
    assert len(payload["cells"]) == 2

    cell_keys = set(payload["cells"][0].keys())
    assert {"drug_id", "attribute_type_id", "content"} <= cell_keys
