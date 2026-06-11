"""Atomic JSON writer for staged outputs.

Writes to a `.tmp` sibling then renames into place. `Path.replace` is atomic on
both Windows and POSIX, so a crash mid-write never leaves a partially-written
target file."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ingestion.settings import ingestion_settings

log = logging.getLogger(__name__)


def wipe_staged_dir() -> None:
    """Remove every .json file in data/staged/ before a fresh stage run.

    Without this, a row set that shrinks between runs (e.g., a drug removed
    from drug_list.yaml) would leave stale rows behind in the output files."""
    staged = ingestion_settings.staged_dir
    if not staged.exists():
        staged.mkdir(parents=True, exist_ok=True)
        return
    for path in staged.glob("*.json"):
        path.unlink()
    for path in staged.glob("*.json.tmp"):
        path.unlink()


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    tmp.write_text(serialized, encoding="utf-8")
    tmp.replace(path)
    log.debug("wrote %s (%d bytes)", path, len(serialized))
