"""Report drug_classes that contain no drugs in their descendant subtree.

Usage:
    uv run python scripts/report_empty_drug_classes.py
    uv run python scripts/report_empty_drug_classes.py --output empty-classes.md
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy import text

from ingestion.db import make_engine
from ingestion.settings import ingestion_settings


EMPTY_CLASS_REPORT_SQL = text("""
    WITH RECURSIVE class_tree AS (
        SELECT
            id,
            parent_id,
            slug,
            name,
            ARRAY[name]::text[] AS path_parts,
            0 AS depth
        FROM drug_classes
        WHERE parent_id IS NULL

        UNION ALL

        SELECT
            child.id,
            child.parent_id,
            child.slug,
            child.name,
            class_tree.path_parts || child.name,
            class_tree.depth + 1
        FROM drug_classes child
        JOIN class_tree ON child.parent_id = class_tree.id
    ),
    descendants AS (
        SELECT id AS ancestor_id, id AS descendant_id
        FROM drug_classes

        UNION ALL

        SELECT descendants.ancestor_id, child.id
        FROM descendants
        JOIN drug_classes child ON child.parent_id = descendants.descendant_id
    ),
    direct_counts AS (
        SELECT drug_class_id, COUNT(*)::int AS direct_drug_count
        FROM drugs
        WHERE drug_class_id IS NOT NULL
        GROUP BY drug_class_id
    ),
    descendant_counts AS (
        SELECT descendants.ancestor_id AS drug_class_id, COUNT(drugs.id)::int AS descendant_drug_count
        FROM descendants
        LEFT JOIN drugs ON drugs.drug_class_id = descendants.descendant_id
        GROUP BY descendants.ancestor_id
    ),
    child_counts AS (
        SELECT parent_id AS drug_class_id, COUNT(*)::int AS child_count
        FROM drug_classes
        WHERE parent_id IS NOT NULL
        GROUP BY parent_id
    )
    SELECT
        class_tree.slug,
        class_tree.name,
        array_to_string(class_tree.path_parts, ' > ') AS path,
        class_tree.depth,
        COALESCE(child_counts.child_count, 0) AS child_count,
        COALESCE(direct_counts.direct_drug_count, 0) AS direct_drug_count,
        COALESCE(descendant_counts.descendant_drug_count, 0) AS descendant_drug_count
    FROM class_tree
    LEFT JOIN child_counts ON child_counts.drug_class_id = class_tree.id
    LEFT JOIN direct_counts ON direct_counts.drug_class_id = class_tree.id
    LEFT JOIN descendant_counts ON descendant_counts.drug_class_id = class_tree.id
    ORDER BY class_tree.path_parts
""")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report drug classes with no drugs in their descendant subtree."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write Markdown report to this path instead of stdout.",
    )
    return parser


async def build_report() -> str:
    db_url = ingestion_settings.require_database_url()
    engine = make_engine(db_url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(EMPTY_CLASS_REPORT_SQL)
            rows = result.mappings().all()
    finally:
        await engine.dispose()

    total = len(rows)
    empty = [row for row in rows if row["descendant_drug_count"] == 0]
    empty_parents = [row for row in empty if row["child_count"] > 0]
    studyable = total - len(empty)

    lines = [
        "# Empty Drug Class Report",
        "",
        "| Metric | Count |",
        "|--------|------:|",
        f"| Total classes | {total} |",
        f"| Studyable classes | {studyable} |",
        f"| Empty classes hidden by `/drug-classes` | {len(empty)} |",
        f"| Empty parent branches | {len(empty_parents)} |",
        "",
    ]

    if empty_parents:
        lines += [
            "## Empty Parent Branches",
            "",
            "These are the dead-end branches that make users click through multiple levels with no studyable drugs.",
            "",
            "| Path | Slug | Children |",
            "|------|------|---------:|",
        ]
        for row in empty_parents:
            lines.append(f"| {row['path']} | `{row['slug']}` | {row['child_count']} |")
        lines.append("")

    lines += [
        "## All Empty Classes",
        "",
        "| Path | Slug | Depth | Children |",
        "|------|------|------:|---------:|",
    ]
    for row in empty:
        lines.append(
            f"| {row['path']} | `{row['slug']}` | {row['depth']} | {row['child_count']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = build_parser().parse_args()
    report = asyncio.run(build_report())
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
