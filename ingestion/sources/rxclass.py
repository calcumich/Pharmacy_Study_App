"""RxClass fetcher: pull ATC classification hierarchy for each drug.

Two-step process:
  1. /class/byRxcui?relaSource=ATC — get the leaf ATC class for each RxCUI
  2. /classGraph?classId=...&source=ATC — get the full ancestor chain so we can
     build the drug_classes tree with proper parent_id pointers.

ATC structure (5 levels):
  C        — Anatomical (1 char)
  C09      — Therapeutic subgroup (3 chars)
  C09A     — Pharmacological subgroup (4 chars)
  C09AA    — Chemical subgroup (5 chars)
  C09AA03  — Chemical substance (7 chars)

Public REST API. No auth. Cap: 20 requests/sec per IP.
Docs: https://lhncbc.nlm.nih.gov/RxNav/APIs/RxClassAPIs.html
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

RXCLASS_BASE = "https://rxnav.nlm.nih.gov/REST/rxclass"
RXCLASS_RATE = RateLimiter(rate=18, per=1.0)


@dataclass
class ATCClass:
    class_id: str
    name: str
    parent_class_id: str | None


@dataclass
class DrugClassMapping:
    query_rxcui: str
    leaf_class_ids: list[str] = field(default_factory=list)
    fetched_at: str = ""
    note: str | None = None


@dataclass
class RxClassData:
    drug_classes: dict[str, list[str]]
    class_tree: dict[str, ATCClass]


async def _fetch_drug_classes(client: httpx.AsyncClient, rxcui: str) -> DrugClassMapping:
    response = await get_with_retry(
        client,
        f"{RXCLASS_BASE}/class/byRxcui.json",
        params={"rxcui": rxcui, "relaSource": "ATC"},
        limiter=RXCLASS_RATE,
    )
    if response.status_code != 200:
        return DrugClassMapping(
            query_rxcui=rxcui, fetched_at=_now(), note=f"http {response.status_code}"
        )
    payload = response.json()
    entries = ((payload.get("rxclassDrugInfoList") or {}).get("rxclassDrugInfo")) or []
    seen: set[str] = set()
    leaf_ids: list[str] = []
    for entry in entries:
        item = entry.get("rxclassMinConceptItem") or {}
        class_id = item.get("classId")
        if class_id and class_id not in seen:
            seen.add(class_id)
            leaf_ids.append(class_id)
    return DrugClassMapping(
        query_rxcui=rxcui,
        leaf_class_ids=leaf_ids,
        fetched_at=_now(),
        note=None if leaf_ids else "no ATC class",
    )


async def _fetch_class_graph(
    client: httpx.AsyncClient, class_id: str
) -> list[ATCClass]:
    """Return all nodes in this class's graph, with parent edges resolved.

    The byRxcui endpoint uses `relaSource=ATC`, but classGraph wants the
    finer-grained classType. For ATC classes from byRxcui (relaSource=ATC),
    the classType is always `ATC1-4`. If we ever pull from other RxClass
    sources (MESH PA, MED-RT), this hardcoded value will need to vary.
    """
    response = await get_with_retry(
        client,
        f"{RXCLASS_BASE}/classGraph.json",
        params={"classId": class_id, "classType": "ATC1-4"},
        limiter=RXCLASS_RATE,
    )
    if response.status_code != 200:
        log.warning("classGraph failed for %s: %d", class_id, response.status_code)
        return []
    payload = response.json()
    graph = payload.get("rxclassGraph") or {}
    nodes = graph.get("rxclassMinConceptItem") or []
    edges = graph.get("rxclassEdge") or []

    parent_of: dict[str, str] = {}
    for edge in edges:
        child = edge.get("classId1")
        parent = edge.get("classId2")
        if child and parent:
            parent_of[child] = parent

    out: list[ATCClass] = []
    for node in nodes:
        cid = node.get("classId")
        name = (node.get("className") or "").strip()
        if not cid:
            continue
        out.append(ATCClass(class_id=cid, name=name, parent_class_id=parent_of.get(cid)))
    return out


async def _resolve_drug_classes(
    client: httpx.AsyncClient,
    rxcui: str,
    *,
    cache_dir: Path,
    refresh: bool,
) -> DrugClassMapping:
    cache_path = cache_dir / "byRxcui" / f"{rxcui}.json"
    if cache_path.exists() and not refresh:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        return DrugClassMapping(**cached)
    result = await _fetch_drug_classes(client, rxcui)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    return result


async def _resolve_class_graph(
    client: httpx.AsyncClient,
    class_id: str,
    *,
    cache_dir: Path,
    refresh: bool,
) -> list[ATCClass]:
    cache_path = cache_dir / "classGraph" / f"{class_id}.json"
    if cache_path.exists() and not refresh:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached:
            return [ATCClass(**c) for c in cached]
        # Empty cache entry — likely a prior failed fetch. Try again.
    result = await _fetch_class_graph(client, class_id)
    if result:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps([asdict(c) for c in result], indent=2), encoding="utf-8"
        )
    return result


async def fetch_all(
    rxcuis: list[str],
    *,
    refresh: bool = False,
    concurrency: int = 8,
) -> RxClassData:
    cache_dir = ingestion_settings.raw_dir / "rxclass"
    semaphore = asyncio.Semaphore(concurrency)

    async with http_client() as client:

        async def bound_drug(rxcui: str) -> DrugClassMapping:
            async with semaphore:
                return await _resolve_drug_classes(
                    client, rxcui, cache_dir=cache_dir, refresh=refresh
                )

        mappings = await asyncio.gather(*(bound_drug(r) for r in rxcuis))

        all_leaf_ids: set[str] = set()
        for m in mappings:
            all_leaf_ids.update(m.leaf_class_ids)

        async def bound_graph(cid: str) -> list[ATCClass]:
            async with semaphore:
                return await _resolve_class_graph(
                    client, cid, cache_dir=cache_dir, refresh=refresh
                )

        graphs = await asyncio.gather(*(bound_graph(cid) for cid in sorted(all_leaf_ids)))

    drug_classes: dict[str, list[str]] = {
        m.query_rxcui: list(m.leaf_class_ids) for m in mappings
    }
    class_tree: dict[str, ATCClass] = {}
    for nodes in graphs:
        for node in nodes:
            if node.class_id not in class_tree:
                class_tree[node.class_id] = node

    return RxClassData(drug_classes=drug_classes, class_tree=class_tree)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
