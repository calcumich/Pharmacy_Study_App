from __future__ import annotations

from app.db.engine import asyncpg_connect_args, uses_supabase_pooler


def test_uses_supabase_pooler_detects_pooler_host() -> None:
    assert uses_supabase_pooler(
        "postgresql+asyncpg://postgres.example:secret@aws-1-us-west-2.pooler.supabase.com:6543/postgres"
    )


def test_uses_supabase_pooler_ignores_direct_host() -> None:
    assert not uses_supabase_pooler(
        "postgresql+asyncpg://postgres:secret@db.example.supabase.co:5432/postgres"
    )


def test_asyncpg_connect_args_disable_statement_cache_for_pooler() -> None:
    assert asyncpg_connect_args(
        "postgresql+asyncpg://postgres.example:secret@aws-1-us-west-2.pooler.supabase.com:6543/postgres"
    ) == {"statement_cache_size": 0}


def test_asyncpg_connect_args_empty_for_non_pooler() -> None:
    assert asyncpg_connect_args(
        "postgresql+asyncpg://app:secret@localhost:5433/pharmdb"
    ) == {}
