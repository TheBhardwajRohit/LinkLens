from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables (and ../.env when run outside Docker)."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql://linklens:linklens@localhost:5432/linklens"
    sandbox_url: str = "http://localhost:8100"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    scan_rate_limit_per_hour: int = 20
    # Database setup and list downloads at startup. Tests turn this off.
    startup_tasks: bool = True

    # Optional keys. SecretStr keeps values out of logs and error messages.
    google_safe_browsing_api_key: SecretStr = SecretStr("")
    virustotal_api_key: SecretStr = SecretStr("")
    urlscan_api_key: SecretStr = SecretStr("")
    abusech_auth_key: SecretStr = SecretStr("")
    maxmind_account_id: str = ""
    maxmind_license_key: SecretStr = SecretStr("")
    supabase_service_role_key: SecretStr = SecretStr("")

    def configured_keys(self) -> dict[str, bool]:
        """Which optional keys are set. Names only, never values."""
        return {
            "google_safe_browsing": bool(self.google_safe_browsing_api_key.get_secret_value()),
            "virustotal": bool(self.virustotal_api_key.get_secret_value()),
            "urlscan": bool(self.urlscan_api_key.get_secret_value()),
            "abusech": bool(self.abusech_auth_key.get_secret_value()),
            "maxmind": bool(self.maxmind_account_id and self.maxmind_license_key.get_secret_value()),
            "supabase": bool(self.supabase_service_role_key.get_secret_value()),
        }

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
