# Why the ingestion pipeline can't share `app.config.settings`

A case study from a real bug we just fixed. The original mistake was small, but it surfaces a more general principle about how settings should be scoped to their consumer.

## The bug

In the first cut of the ingestion pipeline, `ingestion/settings.py` started like this:

```python
from app.config import settings as app_settings


class IngestionSettings:
    @property
    def openfda_api_key(self) -> str:
        return app_settings.OPENFDA_API_KEY
    ...
```

It looked sensible: ingestion needs `OPENFDA_API_KEY` and (eventually) `DATABASE_URL`. The app already has a `Settings` object that reads both from env vars. Why not reuse it?

Then this happened on first run:

```
$ python -m ingestion fetch --limit 10
Traceback (most recent call last):
  ...
  File ".../app/config.py", line 34, in <module>
    settings = Settings()
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
DATABASE_URL
  Field required [type=missing, input_value={}, input_type=dict]
```

The `fetch` command doesn't touch the database. It hits two public REST APIs. There was no reason it should care about `DATABASE_URL`. And yet it couldn't even start.

## Walking the stack

Two important details in that traceback:

1. **The crash is in `Settings()`, not in business code.** That's a side effect at module import time. Just importing `app.config` was enough to run `Settings()`, which validates every required field against the environment.
2. **`DATABASE_URL` is required because the FastAPI runtime needs it.** Look at the class:

   ```python
   class Settings(BaseSettings):
       DATABASE_URL: str          # no default — required
       SUPABASE_URL: str = ""
       SUPABASE_JWT_SECRET: str = ""
       ...
   ```

   This is correct for the API server. If the server boots without a database URL, it can't serve anything — failing fast at startup is the right call.

The mistake was assuming "ingestion needs two env vars, so does the app, let's share." That confused two different things:

- The **set of env vars** they each read happens to overlap.
- The **rules about when those vars are required** are completely different.

The API server can't run without `DATABASE_URL`. The ingestion `fetch` step can. The shared `Settings` class enforced the strictest rule for everyone — but that rule was specific to the API consumer.

## Why this is a smell, not just a syntax error

You could fix it cheaply: give `DATABASE_URL` a default of `""` in `Settings`. That works. The CLI would import cleanly. But now the *API* would boot even when there's no database configured — and silently fail to serve requests when the first query hit the connection pool. You'd have traded a loud startup error for a quiet runtime error. That's almost always a bad trade.

The underlying issue is **shared settings objects that span runtimes**. Any time two different processes (API server, batch job, migration runner, scheduled worker) read from the same `Settings` class:

- The class drifts to the union of every field anyone might need.
- The "required vs. optional" decisions get made for the most demanding caller.
- Less-demanding callers either over-configure or crash.

The cleanest model is: **each runtime owns its own settings**. Overlap is fine — they can both read `OPENFDA_API_KEY` from the same env var — but the *declaration* of what's required belongs to the consumer.

## The fix

```python
# ingestion/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv


class IngestionSettings:
    def __init__(self) -> None:
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)

    @property
    def openfda_api_key(self) -> str:
        return os.environ.get("OPENFDA_API_KEY", "")

    @property
    def database_url(self) -> str:
        return os.environ.get("DATABASE_URL", "")

    def require_database_url(self) -> str:
        url = self.database_url
        if not url:
            raise RuntimeError(
                "DATABASE_URL is not set. Add it to .env or your environment "
                "before running `python -m ingestion load`."
            )
        return url
```

Three things changed:

1. **No import of `app.config`.** Ingestion stands alone; the API's startup rules don't apply.
2. **Both vars are optional.** Missing config is allowed at import time. `fetch` and `stage` will run with neither set.
3. **The `load` step explicitly opts in to the requirement.** `require_database_url()` raises a clean error at the exact point where the missing var would matter — not three import frames deep.

This pattern shows up a lot once you start looking for it. A more general statement:

> Side effects at import time should be limited to things every consumer needs. Validation specific to one consumer belongs in that consumer's startup path, not in a shared module.

## Lesson for future modules

When adding a new batch script, scheduled job, or CLI to a project that already has a FastAPI app:

- **Don't reach for `app.config.settings`** out of convenience.
- **Read env vars directly** (or define a fresh settings class for that consumer).
- **`load_dotenv` is fine** — it's a deliberate, scoped action, not a hidden import side effect.
- **Validate at use, not at import**, for fields only some callers need.

The 30 seconds you save by reusing the existing `Settings` cost a debugging session and an architectural compromise. Cheap to avoid; expensive to undo.

## A note on the related dotenv question

The fix uses `load_dotenv` because `.env` is gitignored and worktrees don't auto-copy it. Without the explicit load, the ingestion CLI in a fresh worktree would only see process-level env vars — which on Windows usually means nothing useful for development. `load_dotenv` from `python-dotenv` is the conventional way to bridge "what's in the project folder" and "what `os.environ` knows about" without re-implementing parsing.

`pydantic-settings` does this automatically via its `env_file` config, which is what the app's `Settings` class uses. Calling `load_dotenv` directly in the ingestion module is the equivalent without the rest of the pydantic-settings machinery — appropriate because we're not validating a fixed schema, just reading two strings.
