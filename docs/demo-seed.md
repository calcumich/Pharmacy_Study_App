# Demo Seed Dataset

The real demo app depends on curated drug data in Postgres. Alembic remains the
schema migration path; this seed is a separate content step so the dataset can
be edited, validated, and expanded without embedding clinical content in a
migration file.

Seed files:

- `data/demo_seed.json` contains the curated classes, drugs, list attributes,
  and interaction pairs.
- `scripts/seed_demo.py` validates the JSON and upserts it into Postgres.
- `scripts/db-seed-demo.ps1` is a PowerShell wrapper for the same script.

The first slice seeds 19 drugs across beta-lactams, macrolides,
fluoroquinolones, PPIs, statins, ACE inhibitors, beta blockers, and
antithrombotics. It also seeds relational drug-drug interactions so DDI cards
are non-empty.

## Mini Decision Note: Seed Strategy

This is an implementation-level decision, not a full architecture decision.
It does not introduce a new framework, service, database, auth flow, or hosting
model, so it does not need a numbered entry in `docs/decisions.md`.

**Decision.** Keep demo seed data in committed JSON and apply it with a Python
script.

**Why not Alembic data migrations?** Alembic remains the source of truth for
database structure: tables, columns, constraints, indexes, enums, and triggers.
The project has used Alembic mostly for DDL. Drug seed content is different:
mechanisms, indications, ADRs, metabolism notes, and interactions are long,
reviewed as domain content, and expected to change as the catalog grows. Putting
that content into Alembic SQL strings would be cumbersome to edit, harder to
test, and harder to review.

**Tradeoff accepted.** Applying a real database now has two separate steps:

```powershell
uv run alembic upgrade head
uv run python scripts/seed_demo.py
```

The first command makes the schema current. The second command applies curated
demo content. This is a little more operational work than a single Alembic
command, but it keeps seed content maintainable and creates a better path toward
the future ingestion pipeline.

**Production guard.** Supabase does not require the `--yes-production` flag.
The seed script requires it as a project safety guard when `APP_ENV` is
`production` or `staging`, or when `DATABASE_URL` looks like a Supabase host.
This prevents accidentally writing demo content to a cloud database just because
`.env` happens to point at Supabase.

**Interaction ordering.** `drug_interactions` stores one row per pair and the
schema enforces `drug_a_id < drug_b_id`. The JSON file uses readable drug slugs,
then the script resolves those slugs to UUIDs and sorts each pair before insert.
That means seed authors do not need to know UUID ordering, and the database
still gets canonical interaction rows.

**Current idempotency limitation.** The `drugs` table does not have a stable
`slug` column, so the script currently identifies existing drugs by `name`.
That is acceptable for this curated first slice, but it is weaker than a true
machine identifier. Display names can change or split by formulation later, for
example `metoprolol tartrate` vs `metoprolol succinate`.

**Revisit trigger.** If the seed grows into the task 15 ingestion pipeline, or
if display-name matching starts to feel brittle, consider a schema decision to
add a real `drugs.slug` column with a unique constraint. That would let seed and
ingestion code upsert with `ON CONFLICT (slug)` instead of selecting by name.

## Local Apply

Confirm `.env` points at the intended local database, then run:

```powershell
uv run alembic upgrade head
uv run python scripts/seed_demo.py
```

or:

```powershell
.\scripts\db-seed-demo.ps1
```

The script is idempotent:

- classes are upserted by `drug_classes.slug`
- drugs are selected by `drugs.name`, then inserted or updated
- list values rely on the existing `(drug_id, value)` uniqueness constraints
- interactions are stored as canonical ordered pairs and upserted by
  `(drug_a_id, drug_b_id)`

## Production Apply

Do not run this blindly against production. First confirm `DATABASE_URL` points
at the intended Supabase project. The script prints a sanitized target database
URL that omits the password.

```powershell
$env:DATABASE_URL
uv run alembic upgrade head
uv run python scripts/seed_demo.py --yes-production
```

The `--yes-production` flag is required when `APP_ENV` is `production` or
`staging`, or when the database URL looks like a Supabase host.

### Supabase Pooler And Prepared Statements

Supabase pooler URLs use PgBouncer-style pooling. With asyncpg, PgBouncer
transaction or statement pooling can conflict with asyncpg's prepared statement
cache and raise an error like:

```text
DuplicatePreparedStatementError: prepared statement "__asyncpg_stmt_1__" already exists
```

The project handles this by detecting Supabase pooler hosts ending in
`.pooler.supabase.com` and creating asyncpg connections with:

```python
statement_cache_size = 0
```

This is configured centrally in `app/db/engine.py` and used by the FastAPI app,
Alembic, and seed scripts. Direct Postgres URLs and local Docker URLs keep the
default asyncpg behavior.

## Validation

Run the tests that validate seed shape and the broader backend behavior:

```powershell
uv run pytest
```

After applying the seed, verify the API surface:

```text
GET /drug-classes
GET /drug-classes/{id}/drugs
GET /drugs/{id}
GET /study/table
```

For the deployed demo, sign in through the frontend and confirm class browsing,
drug details, table mode, and flashcard DDI cards show real data.

## Learning Notes

This seed is not a full ingestion pipeline. It is a curated baseline that fixes
the empty-demo problem and creates a data shape that can grow toward task 15.

The maintainer should be able to explain:

- why schema migration and content seeding are separate commands
- why the script refuses production-like targets without an explicit flag
- how interaction pairs are canonicalized before insert
- why drug idempotency currently depends on name lookup instead of a slug column
