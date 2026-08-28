from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    database_url: str | None = None
    database_host: str = "db"
    database_port: int = 5432
    database_name: str = "filaflow"
    database_user: str = "filaflow"
    database_password: str = "filaflow"
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

    @property
    def sqlalchemy_database_url(self) -> URL:
        if self.database_url:
            return make_url(self.database_url)
        return URL.create(
            "postgresql+psycopg",
            username=self.database_user,
            password=self.database_password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        )


settings = Settings()
