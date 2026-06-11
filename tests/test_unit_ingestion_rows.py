"""Unit tests for ingestion.normalize.rows list-row builders."""
from __future__ import annotations

from ingestion.extract.sections import ExtractedSections
from ingestion.normalize.cache import DrugRawBundle
from ingestion.normalize.rows import build_adr_rows, build_indication_rows, build_metabolism_rows
from ingestion.sources.rxnorm import RxNormResult


def _bundle(query_name: str, rxcui: str | None, canonical_name: str | None = None) -> DrugRawBundle:
    rxnorm = RxNormResult(
        query_name=query_name,
        rxcui=rxcui,
        canonical_name=canonical_name,
        tty="IN" if rxcui else None,
        brand_names=[],
        fetched_at="2024-01-01T00:00:00+00:00",
    )
    return DrugRawBundle(query_name=query_name, rxnorm=rxnorm, openfda=None, leaf_class_ids=[])


def _no_rxnorm_bundle(query_name: str) -> DrugRawBundle:
    return DrugRawBundle(query_name=query_name, rxnorm=None, openfda=None, leaf_class_ids=[])


def _extracted(**kwargs) -> ExtractedSections:
    return ExtractedSections(**kwargs)


def test_drug_without_rxcui_produces_no_rows():
    bundle = _bundle("unknown", rxcui=None)
    rows = build_indication_rows([bundle], {"unknown": _extracted(indications=["Hypertension"])})
    assert rows == []


def test_drug_without_rxnorm_produces_no_rows():
    bundle = _no_rxnorm_bundle("unknown")
    rows = build_indication_rows([bundle], {"unknown": _extracted(indications=["Hypertension"])})
    assert rows == []


def test_indication_rows_contain_drug_name_and_value():
    bundle = _bundle("lisinopril", rxcui="29046", canonical_name="lisinopril")
    rows = build_indication_rows([bundle], {"lisinopril": _extracted(indications=["Hypertension", "Heart failure"])})
    assert len(rows) == 2
    assert all(r["drug_name"] == "Lisinopril" for r in rows)
    assert {r["value"] for r in rows} == {"Hypertension", "Heart failure"}


def test_notes_field_is_always_none():
    bundle = _bundle("lisinopril", rxcui="29046", canonical_name="lisinopril")
    rows = build_indication_rows([bundle], {"lisinopril": _extracted(indications=["Hypertension"])})
    assert all(r["notes"] is None for r in rows)


def test_deduplication_by_case_fold():
    bundle = _bundle("lisinopril", rxcui="29046", canonical_name="lisinopril")
    rows = build_indication_rows(
        [bundle],
        {"lisinopril": _extracted(indications=["Hypertension", "HYPERTENSION"])},
    )
    assert len(rows) == 1


def test_output_sorted_by_drug_name():
    bundle_m = _bundle("metoprolol", rxcui="41493", canonical_name="metoprolol")
    bundle_a = _bundle("atenolol", rxcui="33518", canonical_name="atenolol")
    rows = build_indication_rows(
        [bundle_m, bundle_a],
        {
            "metoprolol": _extracted(indications=["Angina"]),
            "atenolol": _extracted(indications=["Hypertension"]),
        },
    )
    assert rows[0]["drug_name"] == "Atenolol"
    assert rows[1]["drug_name"] == "Metoprolol"


def test_output_sorted_by_value_within_drug():
    bundle = _bundle("metformin", rxcui="6809", canonical_name="metformin")
    rows = build_indication_rows(
        [bundle],
        {"metformin": _extracted(indications=["Nausea", "Abdominal pain"])},
    )
    assert rows[0]["value"] == "Abdominal pain"
    assert rows[1]["value"] == "Nausea"


def test_adr_rows_notes_always_none():
    bundle = _bundle("metformin", rxcui="6809", canonical_name="metformin")
    rows = build_adr_rows([bundle], {"metformin": _extracted(adverse_reactions=["Nausea", "Diarrhea"])})
    assert all(r["notes"] is None for r in rows)


def test_metabolism_rows_use_cyp_enzymes():
    bundle = _bundle("omeprazole", rxcui="7646", canonical_name="omeprazole")
    rows = build_metabolism_rows([bundle], {"omeprazole": _extracted(cyp_enzymes=["CYP2C19", "CYP3A4"])})
    assert {r["value"] for r in rows} == {"CYP2C19", "CYP3A4"}
    assert all(r["notes"] is None for r in rows)


def test_metabolism_deduplication_by_case_fold():
    bundle = _bundle("omeprazole", rxcui="7646", canonical_name="omeprazole")
    rows = build_metabolism_rows([bundle], {"omeprazole": _extracted(cyp_enzymes=["CYP2C19", "cyp2c19"])})
    assert len(rows) == 1
