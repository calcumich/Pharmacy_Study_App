from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: Literal["local", "staging", "production"] = "local"
    AUTH_MODE: Literal["supabase", "dev"] = "supabase"
    DEV_USER_ID: str = "00000000-dead-beef-0000-000000000001"
    DATABASE_URL: str
    SUPABASE_URL: str = ""
    SUPABASE_JWT_SECRET: str = ""
    CORS_ORIGINS: str = "http://localhost:5173"
    OPENFDA_API_KEY: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def validate_auth_mode(self) -> "Settings":
        if self.AUTH_MODE == "dev" and self.APP_ENV != "local":
            raise ValueError("AUTH_MODE=dev is only allowed when APP_ENV=local")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]


settings = Settings()
