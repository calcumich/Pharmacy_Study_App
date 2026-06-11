"""Generate data/staged/PREVIEW.md — human-readable staging report."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)

SCALAR_SLUGS: list[tuple[str, str]] = [
    ("moa", "Mechanism of Action"),
    ("half_life", "Half-life"),
    ("pharmacokinetics", "Pharmacokinetics"),
    ("dosing", "Dosing"),
    ("boxed_warning", "Boxed Warning"),
    ("contraindications", "Contraindications"),
]

LIST_SLUG_FILES: list[tuple[str, str, str]] = [
    ("indications", "Indications", "drug_indications.json"),
    ("adrs", "Adverse Drug Reactions", "drug_adrs.json"),
    ("metabolism", "Metabolism / CYP", "drug_metabolism.json"),
]

_TRUNC = 200


def generate_preview(staged_dir: Path) -> None:
    manifest = json.loads((staged_dir / "manifest.json").read_text(encoding="utf-8"))
    drugs = json.loads((staged_dir / "drugs.json").read_text(encoding="utf-8"))
    drug_classes = json.loads((staged_dir / "drug_classes.json").read_text(encoding="utf-8"))
    indications = json.loads((staged_dir / "drug_indications.json").read_text(encoding="utf-8"))
    adrs = json.loads((staged_dir / "drug_adrs.json").read_text(encoding="utf-8"))
    metabolism = json.loads((staged_dir / "drug_metabolism.json").read_text(encoding="utf-8"))

    lines: list[str] = []
    _header(lines, manifest)
    _counts(lines, manifest)
    _coverage(lines, drugs, indications, adrs, metabolism)
    _provenance(lines, drugs)
    _class_tree(lines, drug_classes, drugs)
    _drug_cards(lines, drugs, indications, adrs, metabolism)

    out_path = staged_dir / "PREVIEW.md"
    tmp_path = staged_dir / "PREVIEW.md.tmp"
    tmp_path.write_text("\n".join(lines), encoding="utf-8")
    tmp_path.replace(out_path)


def _header(lines: list[str], manifest: dict) -> None:
    lines += [
        "# Staged Data Preview",
        "",
        f"Generated: {manifest['generated_at']}  |  Drug list size: {manifest['drug_list_size']}",
        "",
        "Re-generate: `uv run python -m ingestion stage`",
        "",
    ]


def _counts(lines: list[str], manifest: dict) -> None:
    lines += [
        "## Counts",
        "",
        "| Table            | Rows |",
        "|------------------|------|",
    ]
    for table, n in manifest["counts"].items():
        lines.append(f"| {table:<16} | {n:>4} |")
    lines.append("")


def _coverage(
    lines: list[str],
    drugs: list[dict],
    indications: list[dict],
    adrs: list[dict],
    metabolism: list[dict],
) -> None:
    n_drugs = len(drugs)

    scalar_populated = {
        slug: sum(1 for d in drugs if d["attributes"].get(slug))
        for slug, _ in SCALAR_SLUGS
    }
    list_populated = {
        "indications": len({r["drug_name"] for r in indications}),
        "adrs": len({r["drug_name"] for r in adrs}),
        "metabolism": len({r["drug_name"] for r in metabolism}),
    }

    lines += [
        "## Attribute Coverage",
        "",
        "| Attribute              | Populated | Missing | Coverage |",
        "|------------------------|-----------|---------|----------|",
    ]
    for slug, label in SCALAR_SLUGS:
        n = scalar_populated[slug]
        pct = 100 * n / n_drugs if n_drugs else 0
        lines.append(f"| {label:<22} | {n:>9} | {n_drugs - n:>7} | {pct:>7.1f}% |")
    for slug, label, _ in LIST_SLUG_FILES:
        n = list_populated[slug]
        pct = 100 * n / n_drugs if n_drugs else 0
        lines.append(f"| {label:<22} | {n:>9} | {n_drugs - n:>7} | {pct:>7.1f}% |")
    lines.append(f"| {'Major Drug Interactions':<22} | (deferred v1)             |")
    lines.append("")


def _provenance(lines: list[str], drugs: list[dict]) -> None:
    both = rxnorm_only = openfda_only = no_sources = 0
    for d in drugs:
        src = d["attributes"].get("_sources", {})
        has_rx = bool(src.get("rxnorm"))
        has_fda = bool(src.get("openfda"))
        if has_rx and has_fda:
            both += 1
        elif has_rx:
            rxnorm_only += 1
        elif has_fda:
            openfda_only += 1
        else:
            no_sources += 1

    lines += [
        "## Source Provenance",
        "",
        "| Coverage           | Count |",
        "|--------------------|-------|",
        f"| Both (RxNorm+FDA)  | {both:>5} |",
        f"| RxNorm only        | {rxnorm_only:>5} |",
        f"| openFDA only       | {openfda_only:>5} |",
        f"| No sources         | {no_sources:>5} |",
        "",
    ]


def _class_tree(lines: list[str], drug_classes: list[dict], drugs: list[dict]) -> None:
    children: dict[str | None, list[dict]] = defaultdict(list)
    for cls in drug_classes:
        children[cls.get("parent_slug")].append(cls)
    for key in children:
        children[key].sort(key=lambda c: c["slug"])

    drug_count: dict[str, int] = defaultdict(int)
    for d in drugs:
        slug = d.get("drug_class_slug")
        if slug:
            drug_count[slug] += 1

    lines += ["## ATC Class Tree", ""]

    def _render(parent: str | None, depth: int) -> None:
        for cls in children.get(parent, []):
            indent = "  " * depth
            n = drug_count.get(cls["slug"], 0)
            note = f" ({n} drug{'s' if n != 1 else ''})" if n else ""
            lines.append(f"{indent}- **{cls['slug']}** {cls['name']}{note}")
            _render(cls["slug"], depth + 1)

    _render(None, 0)
    lines.append("")


def _drug_cards(
    lines: list[str],
    drugs: list[dict],
    indications: list[dict],
    adrs: list[dict],
    metabolism: list[dict],
) -> None:
    ind_counts: dict[str, int] = defaultdict(int)
    for r in indications:
        ind_counts[r["drug_name"]] += 1
    adr_counts: dict[str, int] = defaultdict(int)
    for r in adrs:
        adr_counts[r["drug_name"]] += 1
    met_counts: dict[str, int] = defaultdict(int)
    for r in metabolism:
        met_counts[r["drug_name"]] += 1

    lines += [f"## Drugs ({len(drugs)})", ""]

    for drug in drugs:
        name = drug["name"]
        attrs = drug["attributes"]
        src = attrs.get("_sources", {})
        rxcui = (src.get("rxnorm") or {}).get("rxcui", "—")
        doc_id = (src.get("openfda") or {}).get("document_id") or "—"
        if doc_id != "—":
            doc_id = doc_id[:8] + "…"

        lines.append(f"### {name}")
        lines.append(f"- **Generic:** {drug.get('generic_name') or 'N/A'}")
        lines.append(f"- **ATC class:** {drug.get('drug_class_slug') or 'N/A'}")
        lines.append(f"- **RxCUI:** {rxcui} · **openFDA doc:** {doc_id}")

        for slug, label in SCALAR_SLUGS:
            raw = attrs.get(slug)
            if raw:
                val = raw[:_TRUNC] + "…" if len(raw) > _TRUNC else raw
            else:
                val = "N/A"
            lines.append(f"- **{label}:** {val}")

        n_ind = ind_counts.get(name, 0)
        n_adr = adr_counts.get(name, 0)
        n_met = met_counts.get(name, 0)
        lines.append(f"- **Indications:** {n_ind} item{'s' if n_ind != 1 else ''}" if n_ind else "- **Indications:** N/A")
        lines.append(f"- **ADRs:** {n_adr} item{'s' if n_adr != 1 else ''}" if n_adr else "- **ADRs:** N/A")
        lines.append(f"- **Metabolism:** {n_met} CYP enzyme{'s' if n_met != 1 else ''}" if n_met else "- **Metabolism:** N/A")
        lines.append("")


async def append_db_diff(staged_dir: Path, db_url: str) -> None:
    """Query live DB counts and append a ## DB Comparison section to PREVIEW.md.

    Positive Δ means rows in staged not yet in DB (pre-load).
    Zero Δ means staged and DB are in sync (post-load)."""
    from sqlalchemy import text

    from ingestion.db import make_engine

    _TABLES = [
        ("attribute_types",  "attribute_types"),
        ("drug_classes",     "drug_classes"),
        ("drugs",            "drugs"),
        ("drug_indications", "drug_indications"),
        ("drug_adrs",        "drug_adrs"),
        ("drug_metabolism",  "drug_metabolism"),
    ]

    engine = make_engine(db_url)
    try:
        async with engine.connect() as conn:
            db_counts = {}
            for key, table in _TABLES:
                result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                db_counts[key] = result.scalar() or 0
    finally:
        await engine.dispose()

    manifest = json.loads((staged_dir / "manifest.json").read_text(encoding="utf-8"))
    staged_counts = manifest["counts"]
    queried_at = datetime.now(UTC).isoformat(timespec="seconds")

    lines = [
        "",
        "## DB Comparison",
        "",
        f"> Queried: {queried_at}",
        "",
        "| Table            | Staged | In DB | Δ    |",
        "|------------------|--------|-------|------|",
    ]
    for key, _ in _TABLES:
        staged = staged_counts.get(key, 0)
        in_db  = db_counts.get(key, 0)
        delta  = staged - in_db
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        lines.append(f"| {key:<16} | {staged:>6} | {in_db:>5} | {delta_str:>4} |")
    lines.append("")

    preview_path = staged_dir / "PREVIEW.md"
    with preview_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))
