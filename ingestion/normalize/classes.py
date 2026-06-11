"""Build drug_classes rows from the ATC graph, topologically ordered."""

from __future__ import annotations

import logging
from collections import defaultdict, deque

from ingestion.normalize.text import title_case_atc
from ingestion.sources.rxclass import ATCClass

log = logging.getLogger(__name__)


def build_drug_class_rows(tree: dict[str, ATCClass]) -> list[dict]:
    """Return one row per unique class_id, parents before children.

    Kahn's algorithm: repeatedly drain nodes with no remaining unresolved
    parent. Ties broken alphabetically by class_id for deterministic output.
    Orphans (parent_class_id set but parent missing from the tree) are
    promoted to roots so the loader can still ingest them.
    """
    indegree: dict[str, int] = defaultdict(int)
    children_of: dict[str, list[str]] = defaultdict(list)
    orphans: list[str] = []

    for class_id, node in tree.items():
        parent = node.parent_class_id
        if parent is None:
            continue
        if parent not in tree:
            orphans.append(class_id)
            continue
        indegree[class_id] += 1
        children_of[parent].append(class_id)

    ready: deque[str] = deque(
        sorted(cid for cid in tree if indegree[cid] == 0)
    )
    ordered: list[str] = []
    while ready:
        cid = ready.popleft()
        ordered.append(cid)
        for child in sorted(children_of[cid]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)

    if len(ordered) != len(tree):
        unresolved = set(tree) - set(ordered)
        log.warning("topo sort left %d classes unresolved (cycle?): %s",
                    len(unresolved), sorted(unresolved)[:5])
        ordered.extend(sorted(unresolved))

    if orphans:
        log.warning("class graph has %d orphans (parent missing): %s",
                    len(orphans), sorted(orphans)[:5])

    return [
        {
            "slug": tree[cid].class_id,
            "name": title_case_atc(tree[cid].name),
            "parent_slug": tree[cid].parent_class_id if tree[cid].parent_class_id in tree else None,
            "description": None,
        }
        for cid in ordered
    ]
