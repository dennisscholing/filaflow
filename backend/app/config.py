from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://filaflow:filaflow@db:5432/filaflow"
    secret_key: str = "change-me-before-production"
    bootstrap_admin_email: str = "admin@filaflow.local"
    bootstrap_admin_password: str = "change-me"
    public_url: str | None = None
    config_dir: Path = Path("/config")
    upload_limit_mb: int = 256
    catalog_url: str = "https://github.com/OpenPrintTag/openprinttag-database/archive/refs/heads/main.zip"
    catalog_sync_hour: int = 3
    cookie_secure: bool = False
    model_config = SettingsConfigDict(env_prefix="FILAFLOW_", env_file=".env", extra="ignore")


settings = Settings()
