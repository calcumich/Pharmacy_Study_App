"""Build the drugs.json rows: one per resolved drug."""

from __future__ import annotations

from ingestion.extract.sections import ExtractedSections
from ingestion.normalize.attributes import build_attribute_dict
from ingestion.normalize.cache import DrugRawBundle
from ingestion.normalize.text import title_case_drug
from ingestion.sources.rxclass import ATCClass


def pick_leaf_slug(
    leaf_ids: list[str], tree: dict[str, ATCClass]
) -> str | None:
    """Choose the deepest ATC class for a drug.

    ATC level character lengths grow monotonically (1, 3, 4, 5, 7), so the
    longest class_id string IS the deepest level. Alphabetic tie-break keeps
    output deterministic when a drug has multiple equal-depth classes."""
    candidates = [cid for cid in leaf_ids if cid in tree]
    if not candidates:
        return None
    return sorted(candidates, key=lambda c: (-len(c), c))[0]


def build_drug_rows(
    bundles: list[DrugRawBundle],
    extracted_by_name: dict[str, ExtractedSections],
    tree: dict[str, ATCClass],
) -> list[dict]:
    rows: list[dict] = []
    for bundle in bundles:
        if bundle.rxnorm is None or not bundle.rxnorm.rxcui:
            continue
        canonical = bundle.rxnorm.canonical_name or bundle.query_name
        name = title_case_drug(canonical)
        generic_name = bundle.openfda.matched_generic_name if bundle.openfda else None
        drug_class_slug = pick_leaf_slug(bundle.leaf_class_ids, tree)
        extracted = extracted_by_name.get(bundle.query_name, ExtractedSections())
        rows.append(
            {
                "name": name,
                "generic_name": generic_name,
                "drug_class_slug": drug_class_slug,
                "attributes": build_attribute_dict(
                    extracted, rxnorm=bundle.rxnorm, openfda=bundle.openfda
                ),
            }
        )
    rows.sort(key=lambda r: r["name"].casefold())
    return rows
