from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.engine import create_database_engine  # noqa: E402

DEFAULT_SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "demo_seed.json"
VALID_SEVERITIES = {"minor", "moderate", "major", "contraindicated"}


@dataclass(frozen=True)
class SeedSummary:
    classes: int
    drugs: int
    interactions: int


def load_seed_data(path: Path = DEFAULT_SEED_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    validate_seed_data(data)
    return data


def validate_seed_data(data: dict[str, Any]) -> None:
    required_top_level = {"classes", "drugs", "interactions"}
    missing_top_level = required_top_level - set(data)
    if missing_top_level:
        raise ValueError(f"Seed data missing top-level keys: {sorted(missing_top_level)}")

    class_slugs = _require_unique_slugs(data["classes"], "classes")
    drug_slugs = _require_unique_slugs(data["drugs"], "drugs")

    for klass in data["classes"]:
        _require_keys(klass, {"slug", "name", "description", "parent_slug"}, "class")
        parent_slug = klass["parent_slug"]
        if parent_slug is not None and parent_slug not in class_slugs:
            raise ValueError(f"Class {klass['slug']} references unknown parent {parent_slug}")

    for drug in data["drugs"]:
        _require_keys(
            drug,
            {
                "slug",
                "name",
                "generic_name",
                "class_slug",
                "attributes",
                "indications",
                "adrs",
                "metabolism",
            },
            "drug",
        )
        if drug["class_slug"] not in class_slugs:
            raise ValueError(f"Drug {drug['slug']} references unknown class {drug['class_slug']}")
        attributes = drug["attributes"]
        if not isinstance(attributes, dict) or not attributes.get("moa") or not attributes.get("half_life"):
            raise ValueError(f"Drug {drug['slug']} must include attributes.moa and attributes.half_life")
        for key in ("indications", "adrs", "metabolism"):
            if not isinstance(drug[key], list) or not drug[key]:
                raise ValueError(f"Drug {drug['slug']} must include at least one {key} value")

    seen_pairs: set[tuple[str, str]] = set()
    for interaction in data["interactions"]:
        _require_keys(interaction, {"drug_slugs", "severity", "description", "details"}, "interaction")
        drug_pair = interaction["drug_slugs"]
        if not isinstance(drug_pair, list) or len(drug_pair) != 2:
            raise ValueError("Each interaction must reference exactly two drug slugs")
        if drug_pair[0] == drug_pair[1]:
            raise ValueError(f"Interaction cannot reference the same drug twice: {drug_pair[0]}")
        missing_drugs = [slug for slug in drug_pair if slug not in drug_slugs]
        if missing_drugs:
            raise ValueError(f"Interaction references unknown drug slugs: {missing_drugs}")
        if interaction["severity"] not in VALID_SEVERITIES:
            raise ValueError(f"Invalid interaction severity: {interaction['severity']}")
        pair = tuple(sorted(drug_pair))
        if pair in seen_pairs:
            raise ValueError(f"Duplicate interaction pair: {pair[0]} / {pair[1]}")
        seen_pairs.add(pair)


def _require_keys(item: dict[str, Any], required_keys: set[str], label: str) -> None:
    missing = required_keys - set(item)
    if missing:
        identifier = item.get("slug") or item.get("name") or item
        raise ValueError(f"Seed {label} {identifier} missing keys: {sorted(missing)}")


def _require_unique_slugs(items: list[dict[str, Any]], label: str) -> set[str]:
    slugs: set[str] = set()
    for item in items:
        slug = item.get("slug")
        if not slug:
            raise ValueError(f"Seed {label} item is missing a slug")
        if slug in slugs:
            raise ValueError(f"Duplicate {label} slug: {slug}")
        slugs.add(slug)
    return slugs


def summarize_database_url(database_url: str) -> str:
    parsed = urlsplit(database_url)
    username = parsed.username or ""
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    database = parsed.path or ""
    netloc = f"{username}@{hostname}{port}" if username else f"{hostname}{port}"
    return urlunsplit((parsed.scheme, netloc, database, "", ""))


def is_production_like(app_env: str, database_url: str) -> bool:
    lowered_url = database_url.lower()
    return app_env in {"production", "staging"} or "supabase" in lowered_url


def canonical_uuid_pair(first: Any, second: Any) -> tuple[Any, Any]:
    return (first, second) if first < second else (second, first)


async def seed_database(session: AsyncSession, data: dict[str, Any]) -> SeedSummary:
    class_ids = await _upsert_classes(session, data["classes"])
    drug_ids = await _upsert_drugs(session, data["drugs"], class_ids)
    await _upsert_list_values(session, data["drugs"], drug_ids)
    await _upsert_interactions(session, data["interactions"], drug_ids)
    return SeedSummary(
        classes=len(data["classes"]),
        drugs=len(data["drugs"]),
        interactions=len(data["interactions"]),
    )


async def _upsert_classes(session: AsyncSession, classes: list[dict[str, Any]]) -> dict[str, Any]:
    class_ids: dict[str, Any] = {}

    for klass in classes:
        parent_id = class_ids.get(klass["parent_slug"])
        result = await session.execute(
            text(
                """
                INSERT INTO drug_classes (slug, name, description, parent_id, updated_at)
                VALUES (:slug, :name, :description, :parent_id, NOW())
                ON CONFLICT (slug) DO UPDATE
                SET name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    parent_id = EXCLUDED.parent_id,
                    updated_at = NOW()
                RETURNING id
                """
            ),
            {
                "slug": klass["slug"],
                "name": klass["name"],
                "description": klass["description"],
                "parent_id": parent_id,
            },
        )
        class_ids[klass["slug"]] = result.scalar_one()

    return class_ids


async def _upsert_drugs(
    session: AsyncSession,
    drugs: list[dict[str, Any]],
    class_ids: dict[str, Any],
) -> dict[str, Any]:
    drug_ids: dict[str, Any] = {}

    for drug in drugs:
        attributes = {**drug["attributes"], "seed_slug": drug["slug"]}
        existing = await session.execute(
            text("SELECT id FROM drugs WHERE name = :name"),
            {"name": drug["name"]},
        )
        existing_id = existing.scalar_one_or_none()

        if existing_id is None:
            result = await session.execute(
                text(
                    """
                    INSERT INTO drugs (name, generic_name, drug_class_id, attributes, updated_at)
                    VALUES (:name, :generic_name, :drug_class_id, CAST(:attributes AS jsonb), NOW())
                    RETURNING id
                    """
                ),
                {
                    "name": drug["name"],
                    "generic_name": drug["generic_name"],
                    "drug_class_id": class_ids[drug["class_slug"]],
                    "attributes": json.dumps(attributes),
                },
            )
            drug_ids[drug["slug"]] = result.scalar_one()
        else:
            await session.execute(
                text(
                    """
                    UPDATE drugs
                    SET generic_name = :generic_name,
                        drug_class_id = :drug_class_id,
                        attributes = CAST(:attributes AS jsonb),
                        updated_at = NOW()
                    WHERE id = :id
                    """
                ),
                {
                    "id": existing_id,
                    "generic_name": drug["generic_name"],
                    "drug_class_id": class_ids[drug["class_slug"]],
                    "attributes": json.dumps(attributes),
                },
            )
            drug_ids[drug["slug"]] = existing_id

    return drug_ids


async def _upsert_list_values(
    session: AsyncSession,
    drugs: list[dict[str, Any]],
    drug_ids: dict[str, Any],
) -> None:
    table_by_key = {
        "indications": "drug_indications",
        "adrs": "drug_adrs",
        "metabolism": "drug_metabolism",
    }

    for drug in drugs:
        drug_id = drug_ids[drug["slug"]]
        for key, table_name in table_by_key.items():
            for value in drug[key]:
                await session.execute(
                    text(
                        f"""
                        INSERT INTO {table_name} (drug_id, value)
                        VALUES (:drug_id, :value)
                        ON CONFLICT (drug_id, value) DO NOTHING
                        """
                    ),
                    {"drug_id": drug_id, "value": value},
                )


async def _upsert_interactions(
    session: AsyncSession,
    interactions: list[dict[str, Any]],
    drug_ids: dict[str, Any],
) -> None:
    for interaction in interactions:
        first_slug, second_slug = interaction["drug_slugs"]
        drug_a_id, drug_b_id = canonical_uuid_pair(drug_ids[first_slug], drug_ids[second_slug])
        await session.execute(
            text(
                """
                INSERT INTO drug_interactions (
                    drug_a_id, drug_b_id, severity, description, details, updated_at
                )
                VALUES (
                    :drug_a_id,
                    :drug_b_id,
                    CAST(:severity AS interaction_severity),
                    :description,
                    CAST(:details AS jsonb),
                    NOW()
                )
                ON CONFLICT (drug_a_id, drug_b_id) DO UPDATE
                SET severity = EXCLUDED.severity,
                    description = EXCLUDED.description,
                    details = EXCLUDED.details,
                    updated_at = NOW()
                """
            ),
            {
                "drug_a_id": drug_a_id,
                "drug_b_id": drug_b_id,
                "severity": interaction["severity"],
                "description": interaction["description"],
                "details": json.dumps(interaction["details"]),
            },
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the real demo drug dataset.")
    parser.add_argument(
        "--seed-file",
        type=Path,
        default=DEFAULT_SEED_PATH,
        help="Path to demo seed JSON.",
    )
    parser.add_argument(
        "--yes-production",
        action="store_true",
        help="Required when APP_ENV is production/staging or DATABASE_URL looks like Supabase.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    load_dotenv(override=False)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    if not database_url.startswith("postgresql+asyncpg://"):
        raise RuntimeError("DATABASE_URL must use the postgresql+asyncpg:// SQLAlchemy driver")

    app_env = os.getenv("APP_ENV", "local")
    target = summarize_database_url(database_url)
    print(f"Target database: {target}")
    print(f"APP_ENV: {app_env}")

    if is_production_like(app_env, database_url) and not args.yes_production:
        raise RuntimeError(
            "Refusing to seed a production-like database without --yes-production. "
            "Confirm DATABASE_URL points at the intended Supabase project, then rerun."
        )

    data = load_seed_data(args.seed_file)
    engine = create_database_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as session:
            summary = await seed_database(session, data)
            await session.commit()
    finally:
        await engine.dispose()

    print(
        "Seed complete: "
        f"{summary.classes} classes, {summary.drugs} drugs, "
        f"{summary.interactions} interactions."
    )


if __name__ == "__main__":
    asyncio.run(main())
