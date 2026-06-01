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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def validate_auth_mode(self) -> "Settings":
        if self.AUTH_MODE == "dev" and self.APP_ENV != "local":
            raise ValueError("AUTH_MODE=dev is only allowed when APP_ENV=local")
        return self


settings = Settings()
