from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "staging"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    base_url: str = "https://staging.sokolrock.org"

    bot_token: str
    admin_telegram_ids: list[int] = Field(default_factory=list)
    bot_rate_limit_per_minute: int = 30

    database_url: str

    webhook_shared_secret: str
    yoo_kassa_webhook_ip_allowlist: str = ""

    sui_default_path_prefix: str = "/sub/"
    sui_request_timeout: int = 15

    yoo_kassa_shop_id: str
    yoo_kassa_secret_key: str
    yoo_kassa_test_mode: bool = True
    yoo_kassa_return_url: str

    crypto_provider: str = "mock"
    crypto_test_mode: bool = True
    crypto_default_rate_rub: float = 95.0

    trial_days: int = 3
    trial_grace_days: int = 1
    plan_month_price_rub: int = 100
    plan_year_price_rub: int = 1000
    subscription_expiry_notify_hours: int = 24

    domain_prod: str = "sokolrock.org"
    domain_staging: str = "staging.sokolrock.org"

    @field_validator("admin_telegram_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> list[int]:
        if isinstance(value, list):
            return [int(v) for v in value]
        if isinstance(value, str):
            if not value.strip():
                return []
            return [int(v.strip()) for v in value.split(",") if v.strip()]
        return []


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]


settings = get_settings()
