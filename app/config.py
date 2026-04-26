"""Runtime config loaded from .env / environment."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_bearer_token: str = "changeme-replace-with-long-random-string"
    data_source_mode: str = "byok"  # byok | real | mock | csv
    semrush_api_key: str = ""
    semrush_base_url: str = "https://api.semrush.com/"
    default_database: str = "us"
    semrush_pages_limit: int = 50
    semrush_keywords_limit: int = 200
    export_dir: str = "./exports"
    public_base_url: str = "http://localhost:8000"

    # BYOK (衣帽间)
    database_path: str = "./byok.db"
    key_encryption_secret: str = ""
    default_daily_quota: int = 50
    default_monthly_quota: int = 800
    validate_semrush_on_register: bool = True


settings = Settings()
