from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GeoPipe"
    api_prefix: str = "/v1"
    database_url: str = "sqlite+aiosqlite:///./geopipe.db"
    data_dir: Path = Path(__file__).resolve().parents[3] / "data"
    upload_dir: Path = Path(__file__).resolve().parents[3] / "uploads"
    default_crs: str = "EPSG:4326"
    max_upload_mb: int = 50
    free_request_limit: int = 10_000
    pro_request_limit: int = 1_000_000
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Spatial stores: geopackage | duckdb | spatialite | postgis
    spatial_backend: str = "geopackage"
    postgis_url: str | None = None
    # Public base URL used in agent connector snippets
    public_base_url: str = "http://127.0.0.1:8000"
    mcp_server_name: str = "geopipe"
    # Auth
    jwt_secret: str = "geopipe-dev-secret-change-me-32b!"
    jwt_expire_hours: int = 72
    auth_required: bool = False
    # Stripe (optional — without keys, local /billing/dev-upgrade works)
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_pro: str | None = None
    stripe_success_url: str = "http://localhost:5173/?billing=success"
    stripe_cancel_url: str = "http://localhost:5173/?billing=cancel"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings
