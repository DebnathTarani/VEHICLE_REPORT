from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_name: str = "Vehicle Report v2"
    version: str = "2.0.0"
    app_env: str = "dev"
    debug: bool = False

    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    secret_key: str = "dev-secret-change-me-in-production"

    data_dir: str = "./data"
    max_upload_mb: int = 20
    max_upload_files: int = 20
    session_ttl_hours: int = 12

    # Bootstrap admin (created on first start when users table is empty)
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str | None = None

    # Comma-separated origins for CORS (dev frontend)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Run create_all at startup (dev/test). Prod should use alembic.
    automigrate: bool = True

    # Serve frontend/dist from the app
    static_dir: str | None = None

    smtp_timeout_seconds: int = 20
    llm_timeout_seconds: int = 180

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def import_dir(self) -> str:
        import os

        return os.path.join(self.data_dir, "imports")


@lru_cache
def get_settings() -> Settings:
    return Settings()
