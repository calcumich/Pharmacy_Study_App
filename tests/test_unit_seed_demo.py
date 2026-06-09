from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
from uuid import UUID

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "seed_demo.py"
SPEC = importlib.util.spec_from_file_location("seed_demo", SCRIPT_PATH)
assert SPEC is not None
seed_demo = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["seed_demo"] = seed_demo
SPEC.loader.exec_module(seed_demo)


def test_demo_seed_data_is_valid() -> None:
    data = seed_demo.load_seed_data(seed_demo.DEFAULT_SEED_PATH)

    assert len(data["drugs"]) == 19
    assert len(data["interactions"]) >= 20
    assert {drug["slug"] for drug in data["drugs"]} >= {
        "amoxicillin",
        "ceftriaxone",
        "clarithromycin",
        "simvastatin",
        "warfarin",
        "apixaban",
        "clopidogrel",
    }


def test_validate_seed_rejects_unknown_interaction_drug() -> None:
    data = seed_demo.load_seed_data(seed_demo.DEFAULT_SEED_PATH)
    broken = deepcopy(data)
    broken["interactions"][0]["drug_slugs"] = ["warfarin", "missing-drug"]

    with pytest.raises(ValueError, match="unknown drug slugs"):
        seed_demo.validate_seed_data(broken)


def test_validate_seed_rejects_duplicate_interaction_pair() -> None:
    data = seed_demo.load_seed_data(seed_demo.DEFAULT_SEED_PATH)
    broken = deepcopy(data)
    first = broken["interactions"][0]
    broken["interactions"].append(
        {
            **first,
            "drug_slugs": list(reversed(first["drug_slugs"])),
        }
    )

    with pytest.raises(ValueError, match="Duplicate interaction pair"):
        seed_demo.validate_seed_data(broken)


def test_canonical_uuid_pair_orders_ids() -> None:
    larger = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    smaller = UUID("00000000-0000-0000-0000-000000000001")

    assert seed_demo.canonical_uuid_pair(larger, smaller) == (smaller, larger)
    assert seed_demo.canonical_uuid_pair(smaller, larger) == (smaller, larger)


def test_summarize_database_url_does_not_include_password() -> None:
    summary = seed_demo.summarize_database_url(
        "postgresql+asyncpg://app:secret@example.supabase.co:6543/postgres"
    )

    assert summary == "postgresql+asyncpg://app@example.supabase.co:6543/postgres"
    assert "secret" not in summary


@pytest.mark.parametrize(
    ("app_env", "database_url", "expected"),
    [
        ("local", "postgresql+asyncpg://app:secret@localhost:5433/pharmdb", False),
        ("production", "postgresql+asyncpg://app:secret@localhost:5433/pharmdb", True),
        ("local", "postgresql+asyncpg://postgres:secret@aws.supabase.com/postgres", True),
    ],
)
def test_is_production_like(app_env: str, database_url: str, expected: bool) -> None:
    assert seed_demo.is_production_like(app_env, database_url) is expected
