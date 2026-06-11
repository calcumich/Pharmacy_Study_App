"""openFDA drug label fetcher — primary source for structured label sections.

openFDA returns the same SPL content as DailyMed but already split into named
JSON fields (indications_and_usage, mechanism_of_action, adverse_reactions,
etc.), which makes downstream extraction much simpler than parsing SPL XML.

Search strategy: `openfda.generic_name.exact:"<UPPER_NAME>"`.
The `.exact` subfield enforces a full-string match, so a query for
"LISINOPRIL" does NOT return combination products like
"LISINOPRIL AND HYDROCHLOROTHIAZIDE". For our hyphen-separated combo entries
(e.g., "lisinopril-hydrochlorothiazide"), we substitute " AND " to match
openFDA's canonical naming. Imperfect — some combos use other connectors
("-/-", " + ") — but covers the common case. Mismatches end up in the
fetch summary so we can curate the drug list.

Rate limit: 240 requests/min, free, with or without API key. The key only
raises the daily cap (1,000 → 120,000), which matters for big re-runs.
Docs: https://open.fda.gov/apis/drug/label/
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx

from ingestion.http import RateLimiter, get_with_retry, http_client
from ingestion.settings import ingestion_settings

log = logging.getLogger(__name__)

OPENFDA_BASE = "https://api.fda.gov/drug/label.json"
OPENFDA_RATE = RateLimiter(rate=200, per=60.0)

LABEL_SECTIONS = (
    "indications_and_usage",
    "contraindications",
    "warnings_and_cautions",
    "boxed_warning",
    "adverse_reactions",
    "drug_interactions",
    "mechanism_of_action",
    "pharmacokinetics",
    "clinical_pharmacology",
    "dosage_and_administration",
)


@dataclass
class OpenFDAResult:
    query_name: str
    rxcui: str | None
    matched_generic_name: str | None
    matched_brand_name: str | None
    sections: dict[str, list[str]] = field(default_factory=dict)
    fetched_at: str = ""
    note: str | None = None
    document_id: str | None = None


def _generate_candidates(query_name: str) -> list[tuple[str, str]]:
    """Build prioritized exact-match candidates for a query name.

    The hyphen in drug_list.yaml has two unrelated meanings:
    - Multi-word singles: 'isosorbide-mononitrate' is ONE drug,
      indexed by openFDA as 'ISOSORBIDE MONONITRATE'.
    - True combinations: 'lisinopril-hydrochlorothiazide' is TWO drugs,
      indexed as 'LISINOPRIL AND HYDROCHLOROTHIAZIDE' (and possibly with
      the components in reversed order vs. our query).

    We can't tell which is which from the name alone, so we try each shape
    in order and stop at the first openFDA hit. Single-word names use only
    the verbatim exact form — the phrase-mono fallback handles their salts.
    """
    parts = [p for p in query_name.strip().lower().split("-") if p]
    if len(parts) <= 1:
        return [("exact", query_name.strip().upper())]
    up = [p.upper() for p in parts]
    if len(up) == 2:
        return [
            ("exact-space", " ".join(up)),
            ("exact-and", " AND ".join(up)),
            ("exact-and-reversed", f"{up[1]} AND {up[0]}"),
        ]
    head, *rest = up
    rest_joined = " ".join(rest)
    return [
        ("exact-space", " ".join(up)),
        ("exact-and-pair", f"{head} AND {rest_joined}"),
        ("exact-and-pair-rev", f"{rest_joined} AND {head}"),
    ]


async def _fetch_label(
    client: httpx.AsyncClient,
    query_name: str,
    *,
    api_key: str,
) -> dict | None:
    """Try each exact-match candidate, then fall back to mono-ingredient phrase.

    Phrase fallback runs only for non-hyphenated names — the salt-form case
    (e.g., atorvastatin → 'ATORVASTATIN CALCIUM'). Hyphenated names skip it
    to avoid re-introducing combination noise.
    """
    for strategy, term in _generate_candidates(query_name):
        hit = await _search_exact(client, term, api_key=api_key)
        if hit is not None and _has_content(hit):
            log.debug("openFDA hit for %s via %s", query_name, strategy)
            return hit
    if "-" in query_name:
        parts = [p.strip().upper() for p in query_name.lower().split("-") if p.strip()]
        return await _search_phrase_combo(client, parts, api_key=api_key)
    bare = query_name.strip().upper()
    return await _search_phrase_mono(client, bare, api_key=api_key)


def purge_failed_cache() -> int:
    """Delete openFDA cache files marked 'no openFDA label'.

    The fetcher caches misses to avoid re-querying drugs that openFDA truly
    has no record of. But when the search strategy changes (as it has here),
    those cached misses are stale and need to be reset so the next fetch
    retries them. Returns the number of files removed.
    """
    cache_dir = ingestion_settings.raw_dir / "openfda"
    if not cache_dir.exists():
        return 0
    deleted = 0
    for path in cache_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("note") == "no openFDA label":
            path.unlink()
            deleted += 1
        elif not payload.get("sections"):
            # Empty sections == "match" but no usable content. Treat as stale.
            path.unlink()
            deleted += 1
    return deleted


def _auth_headers(api_key: str) -> dict[str, str] | None:
    """openFDA accepts the key as `Authorization: Basic <key>` per their docs.

    Used in preference to the api_key query param because URLs end up in logs,
    proxies, and shell history. Headers stay out of those by default.
    """
    return {"Authorization": f"Basic {api_key}"} if api_key else None


async def _search_exact(
    client: httpx.AsyncClient, term: str, *, api_key: str
) -> dict | None:
    response = await get_with_retry(
        client,
        OPENFDA_BASE,
        params={"search": f'openfda.generic_name.exact:"{term}"', "limit": 1},
        headers=_auth_headers(api_key),
        limiter=OPENFDA_RATE,
    )
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        log.warning("openFDA exact query failed for %s: %d", term, response.status_code)
        return None
    results = response.json().get("results") or []
    return results[0] if results else None


def _has_content(result: dict) -> bool:
    """A result has 'content' if at least one of the label sections we care
    about is populated. Bare matches with no prose are functionally useless."""
    return any(result.get(section) for section in LABEL_SECTIONS)


async def _search_phrase_mono(
    client: httpx.AsyncClient, term: str, *, api_key: str
) -> dict | None:
    response = await get_with_retry(
        client,
        OPENFDA_BASE,
        params={"search": f'openfda.generic_name:"{term}"', "limit": 10},
        headers=_auth_headers(api_key),
        limiter=OPENFDA_RATE,
    )
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        log.warning("openFDA phrase query failed for %s: %d", term, response.status_code)
        return None
    for result in response.json().get("results") or []:
        substance = (result.get("openfda") or {}).get("substance_name") or []
        if len(substance) != 1:
            continue
        if not _has_content(result):
            continue
        return result
    return None


async def _search_phrase_combo(
    client: httpx.AsyncClient, parts: list[str], *, api_key: str
) -> dict | None:
    """Search for a combination product by requiring each part as a substring
    of at least one substance_name. Tolerates salt-form noise (CLAVULANATE
    POTASSIUM, HYDROCODONE BITARTRATE) and component-order differences."""
    query = " AND ".join(f'openfda.generic_name:"{p}"' for p in parts)
    response = await get_with_retry(
        client,
        OPENFDA_BASE,
        params={"search": query, "limit": 10},
        headers=_auth_headers(api_key),
        limiter=OPENFDA_RATE,
    )
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        log.warning("openFDA combo query failed for %s: %d", parts, response.status_code)
        return None
    for result in response.json().get("results") or []:
        substance = (result.get("openfda") or {}).get("substance_name") or []
        upper_subs = [s.upper() for s in substance]
        if not all(any(part in sub for sub in upper_subs) for part in parts):
            continue
        if not _has_content(result):
            continue
        return result
    return None


async def resolve_one(
    client: httpx.AsyncClient,
    query_name: str,
    *,
    rxcui: str | None,
    cache_dir: Path,
    refresh: bool,
    api_key: str,
) -> OpenFDAResult:
    cache_key = rxcui if rxcui else _slug(query_name)
    cache_path = cache_dir / f"{cache_key}.json"
    if cache_path.exists() and not refresh:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        known = OpenFDAResult.__dataclass_fields__
        return OpenFDAResult(**{k: v for k, v in cached.items() if k in known})

    label = await _fetch_label(client, query_name, api_key=api_key)
    if label is None:
        result = OpenFDAResult(
            query_name=query_name,
            rxcui=rxcui,
            matched_generic_name=None,
            matched_brand_name=None,
            fetched_at=_now(),
            note="no openFDA label",
        )
    else:
        openfda_meta = label.get("openfda") or {}
        result = OpenFDAResult(
            query_name=query_name,
            rxcui=rxcui,
            matched_generic_name=_first(openfda_meta.get("generic_name")),
            matched_brand_name=_first(openfda_meta.get("brand_name")),
            sections={
                section: list(label.get(section) or [])
                for section in LABEL_SECTIONS
                if label.get(section)
            },
            fetched_at=_now(),
            document_id=label.get("id"),
        )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    return result


async def fetch_all(
    targets: list[tuple[str, str | None]],
    *,
    refresh: bool = False,
    concurrency: int = 4,
) -> list[OpenFDAResult]:
    """Fetch labels for (query_name, rxcui) pairs. rxcui may be None."""
    cache_dir = ingestion_settings.raw_dir / "openfda"
    api_key = ingestion_settings.openfda_api_key
    if not api_key:
        log.warning("OPENFDA_API_KEY not set — limited to 1,000 req/day shared IP cap.")
    semaphore = asyncio.Semaphore(concurrency)

    async with http_client() as client:

        async def bound(item: tuple[str, str | None]) -> OpenFDAResult:
            name, rxcui = item
            async with semaphore:
                return await resolve_one(
                    client,
                    name,
                    rxcui=rxcui,
                    cache_dir=cache_dir,
                    refresh=refresh,
                    api_key=api_key,
                )

        return await asyncio.gather(*(bound(t) for t in targets))


def _slug(name: str) -> str:
    return name.strip().lower().replace(" ", "-").replace("/", "-")


def _first(values: list[str] | None) -> str | None:
    if not values:
        return None
    return values[0]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
