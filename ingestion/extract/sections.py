"""Pull structured fields out of openFDA label section prose.

openFDA returns each labeled section (`indications_and_usage`, `mechanism_of_action`,
etc.) as an array of strings — usually one long string per section. The strings
are SPL-derived prose with section headers, subsection refs, and bullet chars
mixed in. This module cleans + splits that prose into per-drug structured fields.

Output goes into ExtractedSections, which is then merged with RxNorm/RxClass
data by the normalize step.

Trade-offs:
- Splitting is heuristic. Bulleted lists split cleanly; subsection refs
  like `( 5.2 )` also act as item delimiters because labels often place
  one ref per indication/contraindication. Comma-separated prose stays as
  a single line. The preview report will reveal where curation is needed.
- CYP and half-life extraction is regex-based — fine for explicit mentions
  ("CYP3A4", "half-life of approximately 7 hours"), misses paraphrased prose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_BULLET_CHARS = "•·●▪◆■†‡§¶–—―"

# Section headers: "1 INDICATIONS AND USAGE", "4 CONTRAINDICATIONS", etc.
# Anchor non-greedy and use a lookahead for "Capital then lowercase" — the
# first word of normal sentence prose — so we don't eat the first letter
# of the body.
_SECTION_HEADER_RE = re.compile(
    r"^\s*\d+\s+[A-Z][A-Z\s,&/-]{2,}?(?=\s[A-Z][a-z])"
)

# Known subsection labels. Restricted to a known set so we don't accidentally
# strip prose that happens to start with a title-cased phrase.
_KNOWN_SUBSECTION_LABELS = (
    "Mechanism of Action",
    "Pharmacokinetics",
    "Pharmacodynamics",
    "Clinical Pharmacology",
    "Clinical Studies",
    "Dosage and Administration",
    "Indications and Usage",
    "Contraindications",
    "Adverse Reactions",
    "Drug Interactions",
    "Warnings and Precautions",
    "Boxed Warning",
    "Absorption",
    "Distribution",
    "Metabolism",
    "Elimination",
)
_SUBSECTION_HEADER_RE = re.compile(
    r"^\s*\d+\.\d+\s+(?:"
    + "|".join(re.escape(label) for label in _KNOWN_SUBSECTION_LABELS)
    + r")\s+"
)

_REF_RE = re.compile(r"\(\s*\d+(?:\.\d+)?(?:\s*,\s*\d+(?:\.\d+)?)*\s*\)")

# Cross-reference markers like "[see Warnings and Precautions ( 5.2 )]" or just
# "[see Drug Interactions]". Strip them — they're navigation hints, not content.
_XREF_RE = re.compile(r"\[see [^\]]{1,80}\]", re.IGNORECASE)

# Combined list-item delimiter: a bullet char, a parenthesized ref like
# `( 5.2 )` or `( 4 , 7.4 )`, or a blank-line break.
_LIST_DELIM_RE = re.compile(
    rf"[{_BULLET_CHARS}]\s*"
    r"|\(\s*\d+(?:\.\d+)?(?:\s*,\s*\d+(?:\.\d+)?)*\s*\)\s*"
    r"|\n\s*\n+"
)

_WHITESPACE_RE = re.compile(r"\s+")

_CYP_RE = re.compile(r"\bCYP\s?\d[A-Z]\d+\b")
_HALF_LIFE_RE = re.compile(
    r"(?:terminal|elimination|plasma|mean)?\s*half[-\s]?life[^.;\n]{0,30}?"
    r"(\d+(?:\.\d+)?(?:\s*(?:to|-|–)\s*\d+(?:\.\d+)?)?)\s*"
    r"(hours?|hrs?|h\b|days?|d\b|minutes?|mins?)",
    re.IGNORECASE,
)


@dataclass
class ExtractedSections:
    indications: list[str] = field(default_factory=list)
    contraindications: list[str] = field(default_factory=list)
    adverse_reactions: list[str] = field(default_factory=list)
    drug_interactions_text: str | None = None
    mechanism_of_action: str | None = None
    pharmacokinetics: str | None = None
    dosing: str | None = None
    boxed_warning: str | None = None
    cyp_enzymes: list[str] = field(default_factory=list)
    half_life: str | None = None


def extract(sections: dict[str, list[str]]) -> ExtractedSections:
    moa_text = _scalar(sections.get("mechanism_of_action")) or _extract_subsection(
        sections.get("clinical_pharmacology"), "Mechanism of Action"
    )
    pk_text = _scalar(sections.get("pharmacokinetics")) or _extract_subsection(
        sections.get("clinical_pharmacology"), "Pharmacokinetics"
    )

    metabolism_source = " ".join(filter(None, [pk_text or "", moa_text or ""]))

    return ExtractedSections(
        indications=_split_list(sections.get("indications_and_usage")),
        contraindications=_split_list(sections.get("contraindications")),
        adverse_reactions=_split_list(sections.get("adverse_reactions"), cap=50),
        drug_interactions_text=_scalar(sections.get("drug_interactions")),
        mechanism_of_action=moa_text,
        pharmacokinetics=pk_text,
        dosing=_scalar(sections.get("dosage_and_administration")),
        boxed_warning=_scalar(sections.get("boxed_warning")),
        cyp_enzymes=extract_cyp_enzymes(metabolism_source),
        half_life=extract_half_life(pk_text or metabolism_source),
    )


def _split_list(raw: list[str] | None, *, cap: int = 30) -> list[str]:
    text = _join(raw)
    if not text:
        return []
    text = _strip_headers(text)
    text = _XREF_RE.sub("", text)
    chunks = _LIST_DELIM_RE.split(text)
    items = [_squash(_strip_orphan_brackets(c)) for c in chunks]
    items = [s for s in items if _is_meaningful(s)]
    return items[:cap]


def _scalar(raw: list[str] | None) -> str | None:
    text = _join(raw)
    if not text:
        return None
    text = _strip_headers(text)
    text = _XREF_RE.sub("", text)
    text = _REF_RE.sub("", text)
    text = _squash(text)
    return text or None


def _strip_orphan_brackets(text: str) -> str:
    """Splitting on refs can leave a dangling `]` from a partially-consumed
    `[see ...]` cross-ref that the xref regex missed. Drop leading punctuation."""
    return text.lstrip(" .,;:)]")


def _join(raw: list[str] | None) -> str | None:
    if not raw:
        return None
    return "\n\n".join(s for s in raw if s) or None


def _strip_headers(text: str) -> str:
    text = _SECTION_HEADER_RE.sub("", text, count=1)
    text = _SUBSECTION_HEADER_RE.sub("", text, count=1)
    return text.lstrip()


def _squash(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _is_meaningful(text: str) -> bool:
    if len(text) < 4:
        return False
    if text.lower() in {"see", "see above", "n/a", "none", "none."}:
        return False
    return any(c.isalpha() for c in text)


def _extract_subsection(raw: list[str] | None, label: str) -> str | None:
    """Pull a named subsection out of a longer composite section (e.g.,
    'Mechanism of Action' nested inside clinical_pharmacology)."""
    text = _join(raw)
    if not text:
        return None
    pattern = re.compile(
        re.escape(label) + r"\s+(.+?)(?=\s+\d+\.\d+\s+[A-Z][a-z]|\Z)",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None
    body = _REF_RE.sub("", match.group(1))
    return _squash(body) or None


def extract_cyp_enzymes(text: str) -> list[str]:
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for match in _CYP_RE.findall(text):
        normalized = match.replace(" ", "").upper()
        if normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return sorted(out)


def extract_half_life(text: str | None) -> str | None:
    if not text:
        return None
    match = _HALF_LIFE_RE.search(text)
    if not match:
        return None
    value, unit = match.group(1).strip(), match.group(2).strip().lower()
    return f"{value} {unit}"
