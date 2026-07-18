from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Loyalyn"
    app_version: str = "6.0.1"
    environment: str = "production"
    database_url: str = "postgresql+asyncpg://loyalyn:change_me@db:5432/loyalyn"
    jwt_secret: str = "replace_me_with_a_long_random_secret"
    jwt_expire_minutes: int = 30
    refresh_expire_days: int = 30
    cookie_domain: str = ".loyalyn.site"
    encryption_key: str = ""
    bootstrap_admin_email: str = "admin@loyalyn.site"
    bootstrap_admin_password: str = "ChangeMe123!"
    cors_origins: str = "http://localhost:3000,https://loyalyn.site,https://app.loyalyn.site"
    public_web_url: str = "https://app.loyalyn.site"
    public_api_url: str = "https://api.loyalyn.site"
    wallet_storage_dir: str = "/app/data/wallet"
    notification_webhook_url: str = ""
    smtp_webhook_url: str = ""
    sms_webhook_url: str = ""
    worker_poll_seconds: int = 10
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def wallet_path(self) -> Path:
        path = Path(self.wallet_storage_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
