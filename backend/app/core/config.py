from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Loyalyn"
    environment: str = "production"
    database_url: str = "postgresql+asyncpg://loyalyn:change_me@db:5432/loyalyn"
    jwt_secret: str = "replace_me_with_a_long_random_secret"
    jwt_expire_minutes: int = 10080
    bootstrap_admin_email: str = "admin@loyalyn.site"
    bootstrap_admin_password: str = "ChangeMe123!"
    cors_origins: str = "http://localhost:3000,https://loyalyn.site,https://app.loyalyn.site"
    public_web_url: str = "https://app.loyalyn.site"
    notification_webhook_url: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    @property
    def cors_origin_list(self):
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

@lru_cache
def get_settings(): return Settings()
