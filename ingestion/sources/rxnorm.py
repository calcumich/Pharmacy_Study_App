"""RxNorm fetcher: resolve drug names to RxCUIs and collect brand names.

RxNorm is the US-standard drug naming vocabulary maintained by NLM. Each concept
has a Term Type (TTY): IN = ingredient (generic), BN = brand name, SCD/SBD =
clinical/branded drug strength forms. We resolve query names to the ingredient
RxCUI, then ask for related brand names.

Public REST API. No auth. Cap: 20 requests/sec per IP.
Docs: https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from ingestion.http import RateLimiter, get_with_retry, http_client
from ingestion.settings import ingestion_settings

log = logging.getLogger(__name__)

RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"
RXNORM_RATE = RateLimiter(rate=18, per=1.0)


@dataclass
class RxNormResult:
    query_name: str
    rxcui: str | None
    canonical_name: str | None
    tty: str | None
    brand_names: list[str]
    fetched_at: str
    note: str | None = None


async def _resolve_rxcui(client: httpx.AsyncClient, name: str) -> tuple[str, str] | None:
    """Return (rxcui, tty) for an ingredient name, or None if unresolved."""
    response = await get_with_retry(
        client,
        f"{RXNORM_BASE}/rxcui.json",
        params={"name": name, "search": 2},
        limiter=RXNORM_RATE,
    )
    if response.status_code != 200:
        log.warning("rxnorm rxcui lookup failed for %s: %d", name, response.status_code)
        return None
    payload = response.json()
    ids = (payload.get("idGroup") or {}).get("rxnormId") or []
    if not ids:
        return None
    rxcui = str(ids[0])
    tty = await _lookup_tty(client, rxcui)
    return rxcui, tty


async def _lookup_tty(client: httpx.AsyncClient, rxcui: str) -> str:
    response = await get_with_retry(
        client,
        f"{RXNORM_BASE}/rxcui/{rxcui}/property.json",
        params={"propName": "tty"},
        limiter=RXNORM_RATE,
    )
    if response.status_code != 200:
        return ""
    payload = response.json()
    props = ((payload.get("propConceptGroup") or {}).get("propConcept")) or []
    for p in props:
        if p.get("propName") == "TTY":
            return str(p.get("propValue") or "")
    return ""


async def _fetch_brand_names(client: httpx.AsyncClient, rxcui: str) -> list[str]:
    response = await get_with_retry(
        client,
        f"{RXNORM_BASE}/rxcui/{rxcui}/related.json",
        params={"tty": "BN"},
        limiter=RXNORM_RATE,
    )
    if response.status_code != 200:
        return []
    payload = response.json()
    groups = ((payload.get("relatedGroup") or {}).get("conceptGroup")) or []
    brands: list[str] = []
    seen: set[str] = set()
    for group in groups:
        if group.get("tty") != "BN":
            continue
        for prop in group.get("conceptProperties") or []:
            name = (prop.get("name") or "").strip()
            if name and name.lower() not in seen:
                seen.add(name.lower())
                brands.append(name)
    brands.sort()
    return brands


async def _lookup_canonical_name(client: httpx.AsyncClient, rxcui: str) -> str:
    response = await get_with_retry(
        client,
        f"{RXNORM_BASE}/rxcui/{rxcui}.json",
        limiter=RXNORM_RATE,
    )
    if response.status_code != 200:
        return ""
    payload = response.json()
    return ((payload.get("idGroup") or {}).get("name")) or ""


async def resolve_one(
    client: httpx.AsyncClient,
    name: str,
    *,
    cache_dir: Path,
    refresh: bool = False,
) -> RxNormResult:
    cache_path = cache_dir / f"{_slug(name)}.json"
    if cache_path.exists() and not refresh:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        return RxNormResult(**cached)

    resolved = await _resolve_rxcui(client, name)
    if resolved is None:
        result = RxNormResult(
            query_name=name,
            rxcui=None,
            canonical_name=None,
            tty=None,
            brand_names=[],
            fetched_at=_now(),
            note="no rxcui match",
        )
    else:
        rxcui, tty = resolved
        canonical, brands = await asyncio.gather(
            _lookup_canonical_name(client, rxcui),
            _fetch_brand_names(client, rxcui),
        )
        result = RxNormResult(
            query_name=name,
            rxcui=rxcui,
            canonical_name=canonical or None,
            tty=tty or None,
            brand_names=brands,
            fetched_at=_now(),
        )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    return result


async def fetch_all(
    names: list[str],
    *,
    refresh: bool = False,
    concurrency: int = 8,
) -> list[RxNormResult]:
    cache_dir = ingestion_settings.raw_dir / "rxnorm"
    semaphore = asyncio.Semaphore(concurrency)

    async with http_client() as client:

        async def bound(name: str) -> RxNormResult:
            async with semaphore:
                return await resolve_one(client, name, cache_dir=cache_dir, refresh=refresh)

        return await asyncio.gather(*(bound(name) for name in names))


def _slug(name: str) -> str:
    return name.strip().lower().replace(" ", "-").replace("/", "-")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
