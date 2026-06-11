"""Shared async engine factory for the ingestion package."""

from __future__ import annotations

from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def pooler_connect_args(db_url: str) -> dict:
    """Return asyncpg connect_args required for Supabase pgbouncer transaction mode.

    pgbouncer transaction mode routes each transaction to a potentially different
    backend connection. asyncpg's prepared-statement cache breaks in that environment
    because prepared statements are connection-scoped. statement_cache_size=0 switches
    asyncpg to the simple query protocol, which works with any pooler mode."""
    hostname = urlsplit(db_url).hostname or ""
    if hostname.endswith(".pooler.supabase.com"):
        return {"statement_cache_size": 0}
    return {}


def make_engine(db_url: str, *, echo: bool = False) -> AsyncEngine:
    return create_async_engine(db_url, echo=echo, connect_args=pooler_connect_args(db_url))
