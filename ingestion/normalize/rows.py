"""Build the list-shape rows: drug_indications, drug_adrs, drug_metabolism."""

from __future__ import annotations

from ingestion.extract.sections import ExtractedSections
from ingestion.normalize.cache import DrugRawBundle
from ingestion.normalize.text import title_case_drug


def _drug_name(bundle: DrugRawBundle) -> str | None:
    if bundle.rxnorm is None or not bundle.rxnorm.rxcui:
        return None
    canonical = bundle.rxnorm.canonical_name or bundle.query_name
    return title_case_drug(canonical)


def _build_list_rows(
    bundles: list[DrugRawBundle],
    extracted_by_name: dict[str, ExtractedSections],
    field: str,
) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for bundle in bundles:
        name = _drug_name(bundle)
        if not name:
            continue
        extracted = extracted_by_name.get(bundle.query_name)
        if extracted is None:
            continue
        values = getattr(extracted, field, []) or []
        for value in values:
            key = (name, value.casefold())
            if key in seen:
                continue
            seen.add(key)
            rows.append({"drug_name": name, "value": value, "notes": None})
    rows.sort(key=lambda r: (r["drug_name"].casefold(), r["value"].casefold()))
    return rows


def build_indication_rows(
    bundles: list[DrugRawBundle],
    extracted_by_name: dict[str, ExtractedSections],
) -> list[dict]:
    return _build_list_rows(bundles, extracted_by_name, "indications")


def build_adr_rows(
    bundles: list[DrugRawBundle],
    extracted_by_name: dict[str, ExtractedSections],
) -> list[dict]:
    return _build_list_rows(bundles, extracted_by_name, "adverse_reactions")


def build_metabolism_rows(
    bundles: list[DrugRawBundle],
    extracted_by_name: dict[str, ExtractedSections],
) -> list[dict]:
    """One row per CYP enzyme. Half-life stays in drugs.attributes only."""
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for bundle in bundles:
        name = _drug_name(bundle)
        if not name:
            continue
        extracted = extracted_by_name.get(bundle.query_name)
        if extracted is None:
            continue
        for cyp in extracted.cyp_enzymes:
            key = (name, cyp.casefold())
            if key in seen:
                continue
            seen.add(key)
            rows.append({"drug_name": name, "value": cyp, "notes": None})
    rows.sort(key=lambda r: (r["drug_name"].casefold(), r["value"].casefold()))
    return rows
