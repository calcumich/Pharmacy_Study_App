"""
Seed the database with the mock data from frontend/src/api/mock.ts.

Inserts drug classes, drugs, and their list-type attributes (indications,
ADRs, metabolism). Attribute type IDs are looked up from the DB by slug —
do not hardcode them.

Usage:
    DATABASE_URL=postgresql+asyncpg://app:secret@localhost:5433/pharmdb \
        python scripts/seed_mock_data.py

Safe to run multiple times: uses INSERT ... ON CONFLICT DO NOTHING throughout.
"""

import asyncio
import os
import sys
import uuid

from dotenv import load_dotenv
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Allow imports from the project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.models.drugs import Drug, DrugClass, DrugIndication, DrugAdr, DrugMetabolism

load_dotenv(override=True)

DATABASE_URL = os.environ["DATABASE_URL"]

# ── Class tree ────────────────────────────────────────────────────────────────
#
# Structure mirrors DRUG_CLASSES in mock.ts.
# Each entry: (slug, name, description, parent_slug | None)

CLASSES = [
    ("cardiovascular",  "Cardiovascular",  "Drugs acting on the heart and vasculature", None),
    ("beta-blockers",   "Beta-Blockers",   "Competitive antagonists of β-adrenoceptors",  "cardiovascular"),
    ("ace-inhibitors",  "ACE Inhibitors",  "Inhibit angiotensin-converting enzyme",        "cardiovascular"),
    ("statins",         "Statins",         "HMG-CoA reductase inhibitors",                "cardiovascular"),
    ("antibiotics",     "Antibiotics",     "Antimicrobial agents",                        None),
    ("beta-lactams",    "Beta-Lactams",    "Contain a β-lactam ring; inhibit cell-wall synthesis", "antibiotics"),
    ("penicillins",     "Penicillins",     "Natural and semi-synthetic penicillin derivatives",    "beta-lactams"),
]

# ── Drug data ─────────────────────────────────────────────────────────────────
#
# Each entry:
# {
#   "name": str,
#   "generic_name": str,
#   "class_slug": str,
#   "attributes": dict,        # stored as JSONB (scalar fields: moa, half_life)
#   "indications": list[str],
#   "adrs": list[str],
#   "metabolism": list[str],
# }

DRUGS = [
    {
        "name": "Metoprolol",
        "generic_name": "metoprolol tartrate/succinate",
        "class_slug": "beta-blockers",
        "attributes": {
            "moa": "Selective β1-adrenoceptor antagonist; reduces heart rate and myocardial oxygen demand without significant β2 blockade at therapeutic doses",
            "half_life": "3–7 h (tartrate IR); 12–22 h (succinate XR)",
        },
        "indications": [
            "Hypertension",
            "Stable angina pectoris",
            "Heart failure (HFrEF)",
            "Post-MI secondary prevention",
            "Atrial fibrillation (rate control)",
        ],
        "adrs": [
            "Bradycardia",
            "Fatigue / lethargy",
            "Cold extremities",
            "Hypotension",
            "Bronchospasm (high doses)",
            "Impaired glucose tolerance",
        ],
        "metabolism": [
            "CYP2D6 (major substrate)",
            "Extensive hepatic first-pass",
            "Active metabolites: α-hydroxymetoprolol",
        ],
    },
    {
        "name": "Atenolol",
        "generic_name": "atenolol",
        "class_slug": "beta-blockers",
        "attributes": {
            "moa": "Selective β1-adrenoceptor antagonist; hydrophilic — does not cross BBB readily",
            "half_life": "6–7 h",
        },
        "indications": [
            "Hypertension",
            "Angina pectoris",
            "Post-MI secondary prevention",
        ],
        "adrs": [
            "Bradycardia",
            "Fatigue",
            "Cold extremities",
            "Rebound hypertension on abrupt withdrawal",
        ],
        "metabolism": [
            "Minimal hepatic metabolism",
            "Renally excreted unchanged (~50%)",
            "Dose-adjust in renal impairment",
        ],
    },
    {
        "name": "Carvedilol",
        "generic_name": "carvedilol",
        "class_slug": "beta-blockers",
        "attributes": {
            "moa": "Non-selective β1/β2-blocker + α1-blocker; vasodilation via α1 blockade reduces afterload",
            "half_life": "7–10 h",
        },
        "indications": [
            "Heart failure (HFrEF)",
            "Hypertension",
            "Post-MI LV dysfunction",
        ],
        "adrs": [
            "Dizziness / orthostatic hypotension (α1 blockade)",
            "Fatigue",
            "Bradycardia",
            "Weight gain",
        ],
        "metabolism": [
            "CYP2D6 and CYP2C9 (major)",
            "Extensive hepatic first-pass (~85%)",
            "Stereoselective metabolism",
        ],
    },
    {
        "name": "Lisinopril",
        "generic_name": "lisinopril",
        "class_slug": "ace-inhibitors",
        "attributes": {
            "moa": "Competitive inhibitor of ACE; prevents conversion of angiotensin I → II; reduces aldosterone secretion and bradykinin degradation",
            "half_life": "12 h",
        },
        "indications": [
            "Hypertension",
            "Heart failure",
            "Post-MI",
            "Diabetic nephropathy",
        ],
        "adrs": [
            "Dry cough (bradykinin)",
            "Angioedema (rare, serious)",
            "Hyperkalemia",
            "Fetotoxicity (CI in pregnancy)",
            "First-dose hypotension",
        ],
        "metabolism": [
            "Not hepatically metabolised (active drug, not prodrug)",
            "Renally excreted unchanged",
            "Dose-adjust in renal impairment",
        ],
    },
    {
        "name": "Ramipril",
        "generic_name": "ramipril",
        "class_slug": "ace-inhibitors",
        "attributes": {
            "moa": "Prodrug; hydrolysed to ramiprilat, a high-affinity ACE inhibitor with long tissue-binding duration",
            "half_life": "13–17 h (ramiprilat)",
        },
        "indications": [
            "Hypertension",
            "Heart failure",
            "Post-MI",
            "CV risk reduction (HOPE trial)",
            "Diabetic nephropathy",
        ],
        "adrs": [
            "Dry cough",
            "Angioedema",
            "Hyperkalemia",
            "Teratogenicity",
            "Renal impairment (bilateral RAS)",
        ],
        "metabolism": [
            "Hepatic esterases → ramiprilat (active)",
            "CYP minor role",
            "Renal excretion",
        ],
    },
    {
        "name": "Atorvastatin",
        "generic_name": "atorvastatin calcium",
        "class_slug": "statins",
        "attributes": {
            "moa": "Competitive HMG-CoA reductase inhibitor; reduces hepatic cholesterol synthesis → upregulates LDL-R → increased LDL clearance",
            "half_life": "14 h (active metabolites up to 20–30 h)",
        },
        "indications": [
            "Primary hypercholesterolaemia",
            "Combined hyperlipidaemia",
            "CV risk reduction (primary & secondary prevention)",
            "Familial hypercholesterolaemia",
        ],
        "adrs": [
            "Myalgia / myopathy",
            "Rhabdomyolysis (rare)",
            "Elevated transaminases",
            "New-onset diabetes",
            "Headache",
        ],
        "metabolism": [
            "CYP3A4 (major substrate)",
            "Active metabolites (ortho- and para-OH atorvastatin)",
            "Biliary excretion",
            "Substrate for OATP1B1",
        ],
    },
    {
        "name": "Amoxicillin",
        "generic_name": "amoxicillin trihydrate",
        "class_slug": "penicillins",
        "attributes": {
            "moa": "Aminopenicillin; binds PBPs → inhibits peptidoglycan cross-linking → bactericidal; extended spectrum vs. gram-negatives vs. ampicillin",
            "half_life": "1–1.5 h",
        },
        "indications": [
            "Otitis media",
            "Community-acquired pneumonia",
            "Streptococcal pharyngitis",
            "UTI (susceptible organisms)",
            "H. pylori eradication (triple therapy)",
        ],
        "adrs": [
            "Diarrhoea / GI upset",
            "Maculopapular rash",
            "Hypersensitivity / anaphylaxis",
            "C. difficile colitis",
            "Antibiotic-associated diarrhoea",
        ],
        "metabolism": [
            "Minimal hepatic metabolism",
            "Primarily renal excretion (tubular secretion)",
            "Probenecid increases levels",
        ],
    },
]


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # ── 1. Insert drug classes in dependency order ────────────────────────
        print("Seeding drug classes…")
        class_id_by_slug: dict[str, uuid.UUID] = {}

        for slug, name, description, parent_slug in CLASSES:
            parent_id = class_id_by_slug.get(parent_slug) if parent_slug else None

            result = await session.execute(
                text("""
                    INSERT INTO drug_classes (name, slug, description, parent_id)
                    VALUES (:name, :slug, :description, :parent_id)
                    ON CONFLICT (slug) DO NOTHING
                    RETURNING id
                """),
                {"name": name, "slug": slug, "description": description, "parent_id": parent_id},
            )
            row = result.fetchone()

            if row:
                class_id_by_slug[slug] = row[0]
                print(f"  inserted  {name}")
            else:
                # Already exists — look up the id.
                existing = await session.execute(
                    text("SELECT id FROM drug_classes WHERE slug = :slug"),
                    {"slug": slug},
                )
                class_id_by_slug[slug] = existing.scalar_one()
                print(f"  exists    {name}")

        # ── 2. Insert drugs ───────────────────────────────────────────────────
        print("\nSeeding drugs…")
        drug_id_by_name: dict[str, uuid.UUID] = {}

        for d in DRUGS:
            class_id = class_id_by_slug[d["class_slug"]]

            result = await session.execute(
                text("""
                    INSERT INTO drugs (name, generic_name, drug_class_id, attributes)
                    VALUES (:name, :generic_name, :drug_class_id, CAST(:attributes AS jsonb))
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """),
                {
                    "name": d["name"],
                    "generic_name": d["generic_name"],
                    "drug_class_id": class_id,
                    "attributes": __import__("json").dumps(d["attributes"]),
                },
            )
            row = result.fetchone()

            if row:
                drug_id_by_name[d["name"]] = row[0]
                print(f"  inserted  {d['name']}")
            else:
                existing = await session.execute(
                    text("SELECT id FROM drugs WHERE name = :name"),
                    {"name": d["name"]},
                )
                drug_id_by_name[d["name"]] = existing.scalar_one()
                print(f"  exists    {d['name']}")

        # ── 3. Insert list-type attributes ────────────────────────────────────
        print("\nSeeding indications, ADRs, metabolism…")

        for d in DRUGS:
            drug_id = drug_id_by_name[d["name"]]

            for value in d["indications"]:
                await session.execute(
                    text("""
                        INSERT INTO drug_indications (drug_id, value)
                        VALUES (:drug_id, :value)
                        ON CONFLICT (drug_id, value) DO NOTHING
                    """),
                    {"drug_id": drug_id, "value": value},
                )

            for value in d["adrs"]:
                await session.execute(
                    text("""
                        INSERT INTO drug_adrs (drug_id, value)
                        VALUES (:drug_id, :value)
                        ON CONFLICT (drug_id, value) DO NOTHING
                    """),
                    {"drug_id": drug_id, "value": value},
                )

            for value in d["metabolism"]:
                await session.execute(
                    text("""
                        INSERT INTO drug_metabolism (drug_id, value)
                        VALUES (:drug_id, :value)
                        ON CONFLICT (drug_id, value) DO NOTHING
                    """),
                    {"drug_id": drug_id, "value": value},
                )

        await session.commit()

    await engine.dispose()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
