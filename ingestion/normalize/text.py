"""Small string helpers shared across the normalize stage."""

from __future__ import annotations

_CONNECTORS = {"of", "and", "the", "in", "at", "for", "to", "by", "with", "or", "from", "on"}


def make_slug(name: str) -> str:
    """Reproduce the cache-key format used by the source fetchers.

    Must match `ingestion.sources.rxnorm._slug` and `ingestion.sources.openfda._slug`
    exactly, otherwise the cache reader will miss files on disk.
    """
    return name.strip().lower().replace(" ", "-").replace("/", "-")


def title_case_atc(name: str) -> str:
    """ATC class names come back ALL CAPS; title-case them while keeping
    common connector words lowercased (e.g. 'Agents Acting on the Renin')."""
    if not name:
        return ""
    titled = name.title()
    words = titled.split(" ")
    out: list[str] = []
    for i, word in enumerate(words):
        lower = word.lower()
        if i > 0 and lower in _CONNECTORS:
            out.append(lower)
        else:
            out.append(word)
    return " ".join(out)


def title_case_drug(name: str) -> str:
    """Title-case a drug name. Combinations stay hyphenated:
    'lisinopril-hydrochlorothiazide' -> 'Lisinopril-Hydrochlorothiazide'."""
    if not name:
        return ""
    return name.strip().title()
