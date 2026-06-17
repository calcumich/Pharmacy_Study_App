# Ingestion And Drug-Class Browser Status

Date: 2026-06-17

This note records the current state of the ingestion/class-browser work in a
more narrative form than the git log. It is not a handover prompt or a final
architecture decision.

## What Prompted This

The class browser was showing many drug classes that had no studyable drugs
under them. That made the UI feel broken: a user could click through several
levels of drug categories and land on an empty leaf.

The confusing part was that the ingestion pipeline is driven by generic drug
names. At first glance, if classes are discovered from drugs, it seems like
there should not be empty classes. The investigation showed that the pipeline
stores more source taxonomy than it ultimately assigns to drugs.

## Current Mental Model

The ingestion pipeline is catalog-seeded, not taxonomy-discovery-driven.

It starts from `ingestion/drug_list.yaml`, resolves those names through RxNorm,
uses RxClass to find ATC classifications, fetches openFDA label text, stages
normalized JSON under `data/staged/`, and then loads staged rows into Postgres.

Classes can still be empty because RxClass can expose multiple class leaves and
ancestor graphs, while each normalized `drugs` row currently chooses one final
class assignment. So `drug_classes` can include taxonomy branches observed from
source data even when no drug ends up assigned to that branch.

## Changes Made

`GET /drug-classes` now filters out classes with zero descendant drugs. This is
backend filtering because those nodes are not actionable study choices; sending
them to the frontend only creates noise and extra work.

The response now includes:

- `direct_drug_count`
- `descendant_drug_count`

Parent classes with zero direct drugs are still returned if they have descendant
drugs. Direct assignment is not very meaningful in this hierarchy: a drug a few
levels down still belongs to the parent class for study purposes.

A DB-backed report script was added:

```powershell
uv run python scripts\report_empty_drug_classes.py
```

It reports hidden empty class branches from the current database. This is an
admin/operator diagnostic, not learner-facing UI.

A dedicated ingestion doc was also added:

```text
docs/ingestion.md
```

It includes a Mermaid diagram of the current pipeline, explains why empty
classes can exist, and records expansion options.

## Idempotency Status

Repeated ingestion runs are mostly resilient for the same curated drug list:

- raw fetches are cached unless `--refresh` is used
- `attribute_types` upsert by `slug`
- `drug_classes` upsert by `slug`
- list-shaped attributes are delete-then-insert for staged drugs
- `drugs` are updated when the staged display `name` matches an existing row

The weak point is drug identity. The `drugs` table does not currently have a
stable `slug`, `rxcui`, or other unique external identifier. The loader matches
existing drugs by display `name`, which is workable for a curated list but can
produce duplicates if the same real drug later stages under a different display
name.

RxCUI is probably the right next identity anchor for this app, with the caveat
that RxNorm concepts exist at multiple levels: ingredient, clinical drug,
branded drug, multi-ingredient product, and so on. If we add `drugs.rxcui`, we
should also think about storing the RxNorm term type (`tty`) so we know what
kind of concept a row represents.

## Expansion Direction

The current recommendation is to keep the existing curated-name pipeline and
use ClinCalc DrugStats Top 300 to drive the next expansion batch.

Near-term flow:

1. Take candidates from ClinCalc DrugStats Top 300.
2. Normalize them into this repo's `drug_list.yaml` naming style.
3. Manually review combinations, salts, insulins, devices, and ambiguous names.
4. Add a small batch, probably 25-50 names.
5. Run fetch and stage.
6. Review `data/staged/PREVIEW.md`.
7. Run the empty-class report.
8. Load only after the staged data looks useful.

AHRQ MEPS Prescribed Medicines data is noted as a possible later expansion
source. It is more official/public-data-oriented, but likely requires more
processing before it becomes useful as candidate generic names.

## Open Questions

- Should `drugs` get a stable `rxcui` column with a non-null unique constraint
  once backfilled, or should it start nullable with a partial unique index?
- Which RxNorm concept levels should count as a canonical study drug?
- Should multi-ingredient products be first-class drugs, or should the app
  prefer single ingredients except for especially common combinations?
- Should the ingestion candidate list remain manually edited YAML, or should we
  add a generated candidate-review artifact before touching `drug_list.yaml`?
- When an admin screen exists, should the empty-class report become an
  authenticated admin endpoint?

## Validation Notes

Focused drug-class tree tests passed after the filtering change:

```powershell
uv run pytest tests\test_unit_tree_builder.py
```

The frontend build also passed after updating the `DrugClassNode` type:

```powershell
npm run build
```

The full backend test suite had one unrelated existing failure in
`tests/test_smoke_api.py`: the smoke test expects six attribute types, while the
current seeded attribute list includes additional scalar attributes such as
`pharmacokinetics`.
