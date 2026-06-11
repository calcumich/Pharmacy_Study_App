"""Upsert data/staged/ JSON files into Postgres.

Load order respects FK dependencies:
  1. attribute_types  (no foreign keys)
  2. drug_classes     (self-referential parent_id; staged JSON is topologically sorted ancestors-first)
  3. drugs            (FK → drug_classes)
  4. drug_indications (FK → drugs)
  5. drug_adrs        (FK → drugs)
  6. drug_metabolism  (FK → drugs)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.db import make_engine
from ingestion.settings import ingestion_settings

log = logging.getLogger(__name__)

_LIST_TABLES = frozenset({"drug_indications", "drug_adrs", "drug_metabolism"})


@dataclass
class _Counts:
    attr_types: int = 0
    classes: int = 0
    drugs_inserted: int = 0
    drugs_updated: int = 0
    indications_deleted: int = 0
    indications_inserted: int = 0
    adrs_deleted: int = 0
    adrs_inserted: int = 0
    metabolism_deleted: int = 0
    metabolism_inserted: int = 0
    warnings: int = 0


async def load(staged_dir: Path, *, confirm: bool) -> int:
    db_url = ingestion_settings.require_database_url()
    log.info("connecting to database…")
    engine = make_engine(db_url)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await session.begin()
            log.info("connected — opening transaction (%s)", "DRY RUN" if not confirm else "WILL COMMIT")
            try:
                counts = await _load_all(session, staged_dir)
            except Exception:
                await session.rollback()
                raise
            _log_summary(counts, confirm=confirm)
            if not confirm:
                await session.rollback()
                log.info("Transaction ROLLED BACK (dry run — rerun with --confirm to commit)")
            else:
                await session.commit()
                log.info("Transaction COMMITTED")
    finally:
        await engine.dispose()
    return 0


async def _load_all(session: AsyncSession, staged_dir: Path) -> _Counts:
    counts = _Counts()

    attribute_types = _read_json(staged_dir / "attribute_types.json")
    drug_classes    = _read_json(staged_dir / "drug_classes.json")
    drugs           = _read_json(staged_dir / "drugs.json")
    indications     = _read_json(staged_dir / "drug_indications.json")
    adrs            = _read_json(staged_dir / "drug_adrs.json")
    metabolism      = _read_json(staged_dir / "drug_metabolism.json")

    log.info("[1/6] upserting attribute_types (%d rows)…", len(attribute_types))
    await _upsert_attribute_types(session, attribute_types, counts)
    log.info("      done: %d upserted", counts.attr_types)

    log.info("[2/6] upserting drug_classes (%d rows)…", len(drug_classes))
    class_id_by_slug = await _upsert_drug_classes(session, drug_classes, counts)
    log.info("      done: %d upserted", counts.classes)

    log.info("[3/6] upserting drugs (%d rows)…", len(drugs))
    drug_id_by_name  = await _upsert_drugs(session, drugs, class_id_by_slug, counts)
    log.info("      done: %d inserted, %d updated", counts.drugs_inserted, counts.drugs_updated)

    log.info("[4/6] upserting drug_indications (%d rows)…", len(indications))
    d, i = await _upsert_list("drug_indications", session, indications, drug_id_by_name, counts)
    counts.indications_deleted, counts.indications_inserted = d, i
    log.info("      done: %d deleted, %d inserted", d, i)

    log.info("[5/6] upserting drug_adrs (%d rows)…", len(adrs))
    d, i = await _upsert_list("drug_adrs", session, adrs, drug_id_by_name, counts)
    counts.adrs_deleted, counts.adrs_inserted = d, i
    log.info("      done: %d deleted, %d inserted", d, i)

    log.info("[6/6] upserting drug_metabolism (%d rows)…", len(metabolism))
    d, i = await _upsert_list("drug_metabolism", session, metabolism, drug_id_by_name, counts)
    counts.metabolism_deleted, counts.metabolism_inserted = d, i
    log.info("      done: %d deleted, %d inserted", d, i)

    return counts


async def _upsert_attribute_types(
    session: AsyncSession,
    rows: list[dict],
    counts: _Counts,
) -> None:
    for row in rows:
        await session.execute(
            text("""
                INSERT INTO attribute_types
                    (slug, label, shape, source_table, display_order, is_system)
                VALUES
                    (:slug, :label, CAST(:shape AS attribute_shape),
                     :source_table, :display_order, :is_system)
                ON CONFLICT (slug) DO UPDATE SET
                    label         = EXCLUDED.label,
                    shape         = EXCLUDED.shape,
                    source_table  = EXCLUDED.source_table,
                    display_order = EXCLUDED.display_order
            """),
            {
                "slug":          row["slug"],
                "label":         row["label"],
                "shape":         row["shape"],
                "source_table":  row["source_table"],
                "display_order": row["display_order"],
                "is_system":     row["is_system"],
            },
        )
        counts.attr_types += 1


async def _upsert_drug_classes(
    session: AsyncSession,
    rows: list[dict],
    counts: _Counts,
) -> dict[str, object]:
    """Upsert drug_classes and return {slug: id} map. Rows must be ancestors-first."""
    for row in rows:
        parent_slug = row.get("parent_slug")
        await session.execute(
            text("""
                INSERT INTO drug_classes (slug, name, parent_id, description)
                VALUES (
                    :slug,
                    :name,
                    (SELECT id FROM drug_classes WHERE slug = :parent_slug),
                    :description
                )
                ON CONFLICT (slug) DO UPDATE SET
                    name      = EXCLUDED.name,
                    parent_id = EXCLUDED.parent_id
            """),
            {
                "slug":        row["slug"],
                "name":        row["name"],
                "parent_slug": parent_slug,
                "description": row.get("description"),
            },
        )
        counts.classes += 1

    result = await session.execute(text("SELECT slug, id FROM drug_classes"))
    return {r.slug: r.id for r in result}


async def _upsert_drugs(
    session: AsyncSession,
    rows: list[dict],
    class_id_by_slug: dict[str, object],
    counts: _Counts,
) -> dict[str, object]:
    """Upsert drugs. No unique constraint on name — select-then-insert-or-update."""
    result = await session.execute(text("SELECT name, id FROM drugs"))
    existing: dict[str, object] = {r.name: r.id for r in result}

    for row in rows:
        name = row["name"]
        drug_class_id = None
        slug = row.get("drug_class_slug")
        if slug:
            drug_class_id = class_id_by_slug.get(slug)
            if drug_class_id is None:
                log.warning("drug_class_slug %r not found for drug %r — inserting with NULL class", slug, name)
                counts.warnings += 1

        attrs_json = json.dumps(row.get("attributes", {}), ensure_ascii=False)

        if name in existing:
            await session.execute(
                text("""
                    UPDATE drugs SET
                        generic_name  = :generic_name,
                        drug_class_id = :drug_class_id,
                        attributes    = CAST(:attributes AS jsonb)
                    WHERE id = :id
                """),
                {
                    "generic_name":  row.get("generic_name"),
                    "drug_class_id": drug_class_id,
                    "attributes":    attrs_json,
                    "id":            existing[name],
                },
            )
            counts.drugs_updated += 1
        else:
            await session.execute(
                text("""
                    INSERT INTO drugs (name, generic_name, drug_class_id, attributes)
                    VALUES (:name, :generic_name, :drug_class_id, CAST(:attributes AS jsonb))
                """),
                {
                    "name":          name,
                    "generic_name":  row.get("generic_name"),
                    "drug_class_id": drug_class_id,
                    "attributes":    attrs_json,
                },
            )
            counts.drugs_inserted += 1

    # Reload to capture newly inserted rows
    result = await session.execute(text("SELECT name, id FROM drugs"))
    return {r.name: r.id for r in result}


async def _upsert_list(
    table: str,
    session: AsyncSession,
    rows: list[dict],
    drug_id_by_name: dict[str, object],
    counts: _Counts,
) -> tuple[int, int]:
    """Delete-then-insert all rows for each drug present in staged data."""
    assert table in _LIST_TABLES, f"unexpected table name: {table!r}"

    by_drug: dict[object, list[dict]] = {}
    skipped = 0
    for row in rows:
        drug_id = drug_id_by_name.get(row["drug_name"])
        if drug_id is None:
            skipped += 1
            continue
        by_drug.setdefault(drug_id, []).append(row)

    if skipped:
        log.warning("%s: skipped %d rows with no matching drug", table, skipped)
        counts.warnings += skipped

    total_deleted = 0
    total_inserted = 0

    for drug_id, drug_rows in by_drug.items():
        result = await session.execute(
            # table name is from a hardcoded frozenset — safe from injection
            text(f"DELETE FROM {table} WHERE drug_id = :drug_id"),
            {"drug_id": drug_id},
        )
        total_deleted += result.rowcount or 0

        for row in drug_rows:
            await session.execute(
                text(f"INSERT INTO {table} (drug_id, value, notes) VALUES (:drug_id, :value, :notes)"),
                {"drug_id": drug_id, "value": row["value"], "notes": row.get("notes")},
            )
            total_inserted += 1

    return total_deleted, total_inserted


def _log_summary(counts: _Counts, *, confirm: bool) -> None:
    label = "DRY RUN" if not confirm else "TO BE COMMITTED"
    log.info("--- load summary (%s) ---", label)
    log.info("  %-22s upserted:  %d", "attribute_types", counts.attr_types)
    log.info("  %-22s upserted: %d", "drug_classes", counts.classes)
    log.info("  %-22s inserted: %d  updated: %d", "drugs", counts.drugs_inserted, counts.drugs_updated)
    log.info("  %-22s deleted: %d  inserted: %d", "drug_indications", counts.indications_deleted, counts.indications_inserted)
    log.info("  %-22s deleted: %d  inserted: %d", "drug_adrs", counts.adrs_deleted, counts.adrs_inserted)
    log.info("  %-22s deleted: %d  inserted: %d", "drug_metabolism", counts.metabolism_deleted, counts.metabolism_inserted)
    if counts.warnings:
        log.warning("  warnings: %d", counts.warnings)
    else:
        log.info("  warnings: 0")


def _read_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))
