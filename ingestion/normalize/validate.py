"""Print a validation report after staging."""

from __future__ import annotations

import logging

from ingestion.extract.sections import ExtractedSections
from ingestion.normalize.cache import DrugRawBundle

log = logging.getLogger(__name__)


def print_report(
    bundles: list[DrugRawBundle],
    extracted_by_name: dict[str, ExtractedSections],
    counts: dict[str, int],
    class_tree_size: int,
) -> None:
    log.info("--- stage validation ---")
    for table, n in counts.items():
        log.info("  %-22s %d", table, n)

    log.info("ATC class tree size: %d", class_tree_size)

    not_fetched = [b.query_name for b in bundles if b.openfda is None]
    label_missing = [
        b.query_name for b in bundles
        if b.openfda is not None and b.openfda.note == "no openFDA label"
    ]
    label_empty = [
        b.query_name for b in bundles
        if b.openfda is not None and b.openfda.note is None and not b.openfda.sections
    ]
    log.info("openFDA fetch state: not fetched=%d, label missing=%d, label empty=%d",
             len(not_fetched), len(label_missing), len(label_empty))
    if label_missing:
        log.warning("drugs queried but openFDA had no label (%d): %s",
                    len(label_missing), ", ".join(label_missing[:10]))
    if label_empty:
        log.warning("drugs with empty label sections (%d): %s",
                    len(label_empty), ", ".join(label_empty[:10]))

    fetched_names = {b.query_name for b in bundles if b.openfda is not None and b.openfda.sections}
    zero_indications = [
        name for name in fetched_names
        if not extracted_by_name.get(name, ExtractedSections()).indications
    ]
    if zero_indications:
        log.warning("fetched drugs with zero indications (%d): %s",
                    len(zero_indications), ", ".join(zero_indications[:10]))

    no_class = [
        b.query_name for b in bundles
        if (b.rxnorm and b.rxnorm.rxcui) and not b.leaf_class_ids
    ]
    if no_class:
        log.warning("drugs with no ATC class (%d): %s",
                    len(no_class), ", ".join(no_class[:10]))

    referenced_classes: set[str] = set()
    for b in bundles:
        referenced_classes.update(b.leaf_class_ids)
    # Class tree integrity check belongs to the orchestrator; we don't have
    # the tree here. Counts above are enough for a stdout summary.

    distinct_cyps: set[str] = set()
    for extracted in extracted_by_name.values():
        distinct_cyps.update(extracted.cyp_enzymes)
    log.info("distinct CYP enzymes seen: %d %s",
             len(distinct_cyps), sorted(distinct_cyps))
