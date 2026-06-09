from __future__ import annotations

from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def uses_supabase_pooler(database_url: str) -> bool:
    hostname = urlsplit(database_url).hostname or ""
    return hostname.endswith(".pooler.supabase.com")


def asyncpg_connect_args(database_url: str) -> dict[str, int]:
    if uses_supabase_pooler(database_url):
        return {"statement_cache_size": 0}
    return {}


def create_database_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=echo,
        connect_args=asyncpg_connect_args(database_url),
    )
