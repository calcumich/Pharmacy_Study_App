"""Stage orchestrator: read data/raw/, normalize, write data/staged/."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from ingestion.drug_list import load_drug_names
from ingestion.extract.sections import ExtractedSections, extract
from ingestion.normalize import classes, drugs, preview, rows, validate, writer
from ingestion.normalize.attributes import ATTRIBUTE_TYPES
from ingestion.normalize.cache import load_bundles, load_class_tree
from ingestion.settings import ingestion_settings

log = logging.getLogger(__name__)


def run(*, skip_db_diff: bool = False) -> int:
    names = load_drug_names()
    log.info("loading raw caches for %d drugs", len(names))
    bundles = load_bundles(names)
    tree = load_class_tree()
    log.info("class tree has %d nodes", len(tree))

    extracted_by_name: dict[str, ExtractedSections] = {}
    for bundle in bundles:
        if bundle.openfda and bundle.openfda.sections:
            extracted_by_name[bundle.query_name] = extract(bundle.openfda.sections)
        else:
            extracted_by_name[bundle.query_name] = ExtractedSections()

    class_rows = classes.build_drug_class_rows(tree)
    drug_rows = drugs.build_drug_rows(bundles, extracted_by_name, tree)
    indication_rows = rows.build_indication_rows(bundles, extracted_by_name)
    adr_rows = rows.build_adr_rows(bundles, extracted_by_name)
    metab_rows = rows.build_metabolism_rows(bundles, extracted_by_name)

    counts = {
        "attribute_types": len(ATTRIBUTE_TYPES),
        "drug_classes": len(class_rows),
        "drugs": len(drug_rows),
        "drug_indications": len(indication_rows),
        "drug_adrs": len(adr_rows),
        "drug_metabolism": len(metab_rows),
    }
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_dir": str(ingestion_settings.raw_dir),
        "drug_list_size": len(names),
        "counts": counts,
    }

    writer.wipe_staged_dir()
    out = ingestion_settings.staged_dir
    writer.write_json_atomic(out / "attribute_types.json", ATTRIBUTE_TYPES)
    writer.write_json_atomic(out / "drug_classes.json", class_rows)
    writer.write_json_atomic(out / "drugs.json", drug_rows)
    writer.write_json_atomic(out / "drug_indications.json", indication_rows)
    writer.write_json_atomic(out / "drug_adrs.json", adr_rows)
    writer.write_json_atomic(out / "drug_metabolism.json", metab_rows)
    writer.write_json_atomic(out / "manifest.json", manifest)
    log.info("wrote %d files to %s", 7, out)

    validate.print_report(bundles, extracted_by_name, counts, len(tree))
    preview.generate_preview(out)
    log.info("wrote PREVIEW.md to %s", out)
    return 0
