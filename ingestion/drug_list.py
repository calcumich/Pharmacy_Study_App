from pathlib import Path

import yaml

from ingestion.settings import ingestion_settings


def load_drug_names(path: Path | None = None) -> list[str]:
    target = path or ingestion_settings.drug_list_path
    if not target.exists():
        raise FileNotFoundError(
            f"Drug list not found at {target}. Create it with one generic name per list entry."
        )
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    drugs = raw.get("drugs", [])
    if not isinstance(drugs, list):
        raise ValueError(f"{target}: expected a 'drugs:' list at the top level.")
    cleaned: list[str] = []
    seen: set[str] = set()
    for entry in drugs:
        if not isinstance(entry, str):
            raise ValueError(f"{target}: every drug entry must be a string, got {entry!r}.")
        name = entry.strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        cleaned.append(name)
    return cleaned
