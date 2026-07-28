from functools import lru_cache
from os import getenv
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _on_vercel() -> bool:
    """Return True when running on the Vercel runtime."""
    return bool(getenv("VERCEL") or getenv("VERCEL_ENV"))


def _default_runtime_root() -> Path:
    """Writable app root: /tmp on Vercel, repo-level paths locally."""
    if _on_vercel():
        return Path("/tmp/geopipe")
    # backend/app/core/config.py → repo root (parents[3]) when developing locally
    return Path(__file__).resolve().parents[3]


_RUNTIME_ROOT = _default_runtime_root()


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GeoPipe"
    api_prefix: str = "/v1"
    database_url: str = (
        "sqlite+aiosqlite:////tmp/geopipe/geopipe.db"
        if _on_vercel()
        else "sqlite+aiosqlite:///./geopipe.db"
    )
    data_dir: Path = _RUNTIME_ROOT / "data"
    upload_dir: Path = _RUNTIME_ROOT / "uploads"
    default_crs: str = "EPSG:4326"
    max_upload_mb: int = 50
    free_request_limit: int = 10_000
    pro_request_limit: int = 1_000_000
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
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
    # Prefer the deployment URL when Vercel injects it.
    vercel_url = getenv("VERCEL_PROJECT_PRODUCTION_URL") or getenv("VERCEL_URL")
    if vercel_url and settings.public_base_url.startswith("http://127.0.0.1"):
        base = vercel_url if vercel_url.startswith("http") else f"https://{vercel_url}"
        settings.public_base_url = base
        settings.stripe_success_url = f"{base}/?billing=success"
        settings.stripe_cancel_url = f"{base}/?billing=cancel"
        if base not in settings.cors_origins:
            settings.cors_origins = [*settings.cors_origins, base]
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings
