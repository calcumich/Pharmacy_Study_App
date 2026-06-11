"""Standalone settings for the ingestion pipeline.

Deliberately does NOT import app.config — ingestion is a batch job with
different requirements than the FastAPI runtime. It needs OPENFDA_API_KEY
(for openFDA polite-use limits) and DATABASE_URL (only for the `load` step).
Importing app.config would force every CLI invocation to satisfy the app's
required settings (e.g., DATABASE_URL) even for offline `fetch` runs.
"""

from __future__ import annotations

import os
from functools import cached_property
from pathlib import Path

from dotenv import load_dotenv


class IngestionSettings:
    def __init__(self) -> None:
        env_path = self._discover_repo_root() / ".env"
        if env_path.exists():
            load_dotenv(env_path)

    def _discover_repo_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    @cached_property
    def repo_root(self) -> Path:
        return self._discover_repo_root()

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

    @cached_property
    def data_dir(self) -> Path:
        return self.repo_root / "data"

    @cached_property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @cached_property
    def staged_dir(self) -> Path:
        return self.data_dir / "staged"

    @cached_property
    def drug_list_path(self) -> Path:
        return self.repo_root / "ingestion" / "drug_list.yaml"


ingestion_settings = IngestionSettings()
