import json
import logging

from ingestion.drug_list import load_drug_names
from ingestion.settings import ingestion_settings
from ingestion.sources import openfda, rxclass, rxnorm

log = logging.getLogger(__name__)


async def run_fetch(*, refresh: bool = False, limit: int | None = None) -> int:
    ingestion_settings.raw_dir.mkdir(parents=True, exist_ok=True)
    names = load_drug_names()
    if limit is not None:
        names = names[:limit]
    log.info("fetching %d drugs (refresh=%s)", len(names), refresh)

    log.info("step 1/2: RxNorm — resolve names to RxCUIs")
    rxnorm_results = await rxnorm.fetch_all(names, refresh=refresh)
    resolved = [r for r in rxnorm_results if r.rxcui]
    unresolved = [r for r in rxnorm_results if not r.rxcui]
    log.info(
        "rxnorm: %d resolved, %d unresolved (%s)",
        len(resolved),
        len(unresolved),
        ", ".join(r.query_name for r in unresolved[:5]) + (" …" if len(unresolved) > 5 else ""),
    )

    rxcuis = [r.rxcui for r in resolved if r.rxcui]
    log.info("step 2/3: RxClass — fetch ATC hierarchy for %d RxCUIs", len(rxcuis))
    class_data = await rxclass.fetch_all(rxcuis, refresh=refresh)
    log.info(
        "rxclass: %d drugs mapped to ATC, %d unique classes in tree",
        sum(1 for v in class_data.drug_classes.values() if v),
        len(class_data.class_tree),
    )

    purged = openfda.purge_failed_cache()
    if purged:
        log.info("purged %d stale 'no openFDA label' cache entries", purged)

    log.info("step 3/3: openFDA — fetch structured label sections")
    label_targets = [(r.query_name, r.rxcui) for r in rxnorm_results]
    label_results = await openfda.fetch_all(label_targets, refresh=refresh)
    with_labels = [r for r in label_results if r.sections]
    without_labels = [r for r in label_results if not r.sections]
    section_counts: dict[str, int] = {}
    for r in with_labels:
        for section in r.sections:
            section_counts[section] = section_counts.get(section, 0) + 1
    log.info(
        "openfda: %d labels found, %d missing (%s)",
        len(with_labels),
        len(without_labels),
        ", ".join(r.query_name for r in without_labels[:5])
        + (" …" if len(without_labels) > 5 else ""),
    )

    summary_path = ingestion_settings.raw_dir / "fetch_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "total_requested": len(names),
                "rxnorm_resolved": len(resolved),
                "rxnorm_unresolved": [r.query_name for r in unresolved],
                "atc_classes_collected": len(class_data.class_tree),
                "openfda_labels_found": len(with_labels),
                "openfda_labels_missing": [r.query_name for r in without_labels],
                "openfda_section_coverage": section_counts,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info("wrote %s", summary_path)
    return 0


async def run_stage(*, skip_db_diff: bool = False) -> int:
    from ingestion.normalize.pipeline import run
    from ingestion.normalize.preview import append_db_diff
    rc = run(skip_db_diff=skip_db_diff)
    if rc == 0 and not skip_db_diff:
        db_url = ingestion_settings.database_url
        if db_url:
            log.info("querying DB for staged vs. DB diff…")
            await append_db_diff(ingestion_settings.staged_dir, db_url)
        else:
            log.info("DATABASE_URL not set — skipping DB diff (pass --skip-db-diff to silence)")
    return rc


def run_preview() -> int:
    from ingestion.normalize.preview import generate_preview
    staged_dir = ingestion_settings.staged_dir
    if not staged_dir.exists():
        log.error("data/staged/ not found — run `ingestion stage` first")
        return 1
    generate_preview(staged_dir)
    log.info("wrote PREVIEW.md to %s", staged_dir)
    return 0


async def run_load(*, confirm: bool = False) -> int:
    from ingestion.load.loader import load
    staged_dir = ingestion_settings.staged_dir
    if not staged_dir.exists():
        log.error("data/staged/ not found — run `ingestion stage` first")
        return 1
    return await load(staged_dir, confirm=confirm)
