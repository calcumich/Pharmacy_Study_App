"""Read raw fetch caches back into the source dataclasses.

The `fetch` step writes per-drug JSON files under `data/raw/{source}/`. This
module loads them back, tolerating missing files (returning None) so the stage
step can run after a partial fetch.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from ingestion.normalize.text import make_slug
from ingestion.settings import ingestion_settings
from ingestion.sources.rxclass import ATCClass, DrugClassMapping
from ingestion.sources.rxnorm import RxNormResult
from ingestion.sources.openfda import OpenFDAResult

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DrugRawBundle:
    query_name: str
    rxnorm: RxNormResult | None
    openfda: OpenFDAResult | None
    leaf_class_ids: list[str]


def _load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        log.warning("malformed cache file %s: %s", path, exc)
        return None


def _load_rxnorm(query_name: str) -> RxNormResult | None:
    path = ingestion_settings.raw_dir / "rxnorm" / f"{make_slug(query_name)}.json"
    raw = _load_json(path)
    return RxNormResult(**raw) if isinstance(raw, dict) else None


def _load_openfda(query_name: str, rxcui: str | None) -> OpenFDAResult | None:
    cache_key = rxcui if rxcui else make_slug(query_name)
    path = ingestion_settings.raw_dir / "openfda" / f"{cache_key}.json"
    raw = _load_json(path)
    return OpenFDAResult(**raw) if isinstance(raw, dict) else None


def _load_leaf_classes(rxcui: str) -> list[str]:
    path = ingestion_settings.raw_dir / "rxclass" / "byRxcui" / f"{rxcui}.json"
    raw = _load_json(path)
    if not isinstance(raw, dict):
        return []
    return list(DrugClassMapping(**raw).leaf_class_ids)


def load_bundles(names: list[str]) -> list[DrugRawBundle]:
    bundles: list[DrugRawBundle] = []
    for name in names:
        rxnorm = _load_rxnorm(name)
        rxcui = rxnorm.rxcui if rxnorm else None
        openfda = _load_openfda(name, rxcui)
        leaf_class_ids = _load_leaf_classes(rxcui) if rxcui else []
        bundles.append(
            DrugRawBundle(
                query_name=name,
                rxnorm=rxnorm,
                openfda=openfda,
                leaf_class_ids=leaf_class_ids,
            )
        )
    return bundles


def load_class_tree() -> dict[str, ATCClass]:
    tree: dict[str, ATCClass] = {}
    graph_dir = ingestion_settings.raw_dir / "rxclass" / "classGraph"
    if not graph_dir.exists():
        return tree
    for path in sorted(graph_dir.glob("*.json")):
        raw = _load_json(path)
        if not isinstance(raw, list):
            continue
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            node = ATCClass(**entry)
            tree.setdefault(node.class_id, node)
    return tree
