"""attribute_types catalog + drugs.attributes JSONB builder.

The pre-seeded set (slugs: moa, half_life, indications, adrs, metabolism, ddis)
comes from alembic/versions/f5ef1a0d7d64_seed_attribute_types.py. We re-emit
those rows alongside the four new scalar slugs the user chose to surface:
pharmacokinetics, dosing, boxed_warning, contraindications. The loader upserts
by slug so re-emitting pre-seeded rows is a no-op.

The `_sources` key (underscore prefix) inside `attributes` is a reserved
provenance breadcrumb, not an attribute_type. The frontend's flashcard loop
keys off attribute_types.slug, so the underscore key is invisible there.
"""

from __future__ import annotations

from typing import Any

from ingestion.extract.sections import ExtractedSections
from ingestion.sources.openfda import OpenFDAResult
from ingestion.sources.rxnorm import RxNormResult

ATTRIBUTE_TYPES: list[dict] = [
    {"slug": "moa", "label": "Mechanism of Action", "shape": "scalar", "source_table": "drugs", "display_order": 1, "is_system": True},
    {"slug": "half_life", "label": "Half-life", "shape": "scalar", "source_table": "drugs", "display_order": 2, "is_system": True},
    {"slug": "indications", "label": "Indications", "shape": "list", "source_table": "drug_indications", "display_order": 3, "is_system": True},
    {"slug": "adrs", "label": "Adverse Drug Reactions", "shape": "list", "source_table": "drug_adrs", "display_order": 4, "is_system": True},
    {"slug": "metabolism", "label": "Metabolism / CYP", "shape": "list", "source_table": "drug_metabolism", "display_order": 5, "is_system": True},
    {"slug": "ddis", "label": "Major Drug Interactions", "shape": "relational", "source_table": "drug_interactions", "display_order": 6, "is_system": True},
    {"slug": "pharmacokinetics", "label": "Pharmacokinetics", "shape": "scalar", "source_table": "drugs", "display_order": 7, "is_system": True},
    {"slug": "dosing", "label": "Dosing", "shape": "scalar", "source_table": "drugs", "display_order": 8, "is_system": True},
    {"slug": "boxed_warning", "label": "Boxed Warning", "shape": "scalar", "source_table": "drugs", "display_order": 9, "is_system": True},
    {"slug": "contraindications", "label": "Contraindications", "shape": "scalar", "source_table": "drugs", "display_order": 10, "is_system": True},
]


def build_attribute_dict(
    extracted: ExtractedSections,
    *,
    rxnorm: RxNormResult | None = None,
    openfda: OpenFDAResult | None = None,
) -> dict[str, Any]:
    """Map extracted prose + raw source records into the drugs.attributes JSONB.

    Contraindications are joined into a single scalar (the catalog row for
    contraindications is shape=scalar, narrative form). Only non-null/non-empty
    keys are emitted so the JSONB payload stays compact.

    The `_sources` key carries provenance breadcrumbs — a reserved underscore
    slug that no attribute_type references, so the frontend ignores it."""
    contraindications = (
        " ".join(extracted.contraindications).strip()
        if extracted.contraindications
        else None
    )
    candidates: dict[str, Any] = {
        "moa": extracted.mechanism_of_action,
        "half_life": extracted.half_life,
        "pharmacokinetics": extracted.pharmacokinetics,
        "dosing": extracted.dosing,
        "boxed_warning": extracted.boxed_warning,
        "contraindications": contraindications,
    }
    out: dict[str, Any] = {k: v for k, v in candidates.items() if v}

    sources = _build_sources(rxnorm, openfda)
    if sources:
        out["_sources"] = sources

    return out


def _build_sources(
    rxnorm: RxNormResult | None, openfda: OpenFDAResult | None
) -> dict[str, dict[str, str]]:
    sources: dict[str, dict[str, str]] = {}

    if rxnorm is not None and rxnorm.rxcui:
        sources["rxnorm"] = _compact(
            rxcui=rxnorm.rxcui,
            canonical_name=rxnorm.canonical_name,
            tty=rxnorm.tty,
            fetched_at=rxnorm.fetched_at,
        )

    if openfda is not None and openfda.sections:
        sources["openfda"] = _compact(
            document_id=openfda.document_id,
            matched_generic_name=openfda.matched_generic_name,
            fetched_at=openfda.fetched_at,
        )

    return sources


def _compact(**fields: str | None) -> dict[str, str]:
    return {k: v for k, v in fields.items() if v}
