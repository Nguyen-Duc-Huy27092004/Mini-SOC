from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import (
    Field,
    SecretStr,
    computed_field,
    field_validator,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
)

ENV_TYPES = Literal[
    "development",
    "staging",
    "production",
]


def parse_json_list(value: str | list[str]) -> list[str]:

    if isinstance(value, list):
        return value

    value = value.strip()

    if not value:
        return []

    if value.startswith("["):
        return json.loads(value)

    return [x.strip() for x in value.split(",")]


class SafeEnvSettingsSource(EnvSettingsSource):
    """Custom environment source that handles empty list fields gracefully."""
    
    def decode_complex_value(
        self,
        field_name: str,
        field,
        value: str,
    ):
        """Override to handle empty strings for list fields."""
        # For list fields, handle empty strings before JSON parsing
        if hasattr(field, 'annotation') and 'list' in str(field.annotation):
            if not value or not value.strip():
                return None  # Let Pydantic use the default
        
        # For other complex types, use the default decoder
        try:
            return super().decode_complex_value(field_name, field, value)
        except json.JSONDecodeError:
            # If JSON parsing fails for list fields, return empty list
            if hasattr(field, 'annotation') and 'list' in str(field.annotation):
                return None
            raise


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
        validate_default=True,
        frozen=True,
        json_file=None,
    )
    
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """Customize settings sources to use our safe env source."""
        return (
            init_settings,
            SafeEnvSettingsSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )

    # =========================================================
    # CORE
    # =========================================================

    PROJECT_NAME: str = "Mini SOC Portal"

    ENV: ENV_TYPES = "development"

    DEBUG: bool = False

    API_V1_STR: str = "/api/v1"

    LOG_LEVEL: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ] = "INFO"

    # =========================================================
    # SECURITY
    # =========================================================

    SECRET_KEY: SecretStr

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    WS_TICKET_EXPIRE_SECONDS: int = 60

    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10

    WS_RATE_LIMIT_PER_MINUTE: int = 120

    BACKEND_CORS_ORIGINS: list[str] = Field(
        default_factory=list
    )

    # =========================================================
    # POSTGRES
    # =========================================================

    POSTGRES_SERVER: str = "db"

    POSTGRES_PORT: int = 5432

    POSTGRES_USER: str = "postgres"

    POSTGRES_PASSWORD: SecretStr

    POSTGRES_DB: str = "mini_soc"

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # =========================================================
    # REDIS
    # =========================================================

    REDIS_HOST: str = "redis"

    REDIS_PORT: int = 6379

    REDIS_PASSWORD: SecretStr | None = None

    REDIS_DB: int = 0

    # =========================================================
    # OPENSEARCH
    # =========================================================

    OPENSEARCH_HOSTS: list[str] = Field(
        default_factory=lambda: [
            "https://opensearch:9200"
        ]
    )

    OPENSEARCH_USER: str = "admin"

    OPENSEARCH_PASSWORD: SecretStr = Field(default=SecretStr("not-used"))

    OPENSEARCH_VERIFY_CERTS: bool = True

    OPENSEARCH_SSL_SHOW_WARN: bool = False

    OPENSEARCH_CA_CERTS: str | None = None

    # =========================================================
    # WAZUH
    # =========================================================

    WAZUH_API_URL: str = "https://localhost:55000"

    WAZUH_API_USER: str = "admin"

    WAZUH_API_PASSWORD: SecretStr = Field(default=SecretStr("admin"))

    # Default False because most Wazuh deployments use self-signed certificates.
    # Set to True only in production with proper CA-signed certificates.
    WAZUH_VERIFY_SSL: bool = False

    WAZUH_CA_CERTS: str | None = None

    # Default path for Wazuh alerts file (Linux). Change via env var for Windows.
    WAZUH_ALERTS_FILE: str = "/var/ossec/logs/alerts/alerts.json"

    # =========================================================
    # ZABBIX
    # =========================================================

    ZABBIX_API_URL: str = "http://localhost/zabbix/api_jsonrpc.php"

    ZABBIX_API_USER: str = "Admin"

    ZABBIX_API_PASSWORD: SecretStr = Field(default=SecretStr("zabbix"))

    # Disable SSL verification for self-signed certs (common in lab setups)
    ZABBIX_VERIFY_SSL: bool = True

    ZABBIX_TIMEOUT: int = 30

    # Set to False to completely disable Zabbix integration
    ZABBIX_ENABLED: bool = True

    # =========================================================
    # GEOIP
    # =========================================================

    GEOIP_DB_PATH: str = (
        "/usr/share/GeoIP/GeoLite2-City.mmdb"
    )

    # =========================================================
    # OBSERVABILITY
    # =========================================================

    ENABLE_SENTRY: bool = False

    SENTRY_DSN: SecretStr | None = None

    RATE_LIMIT_PER_MINUTE: int = 100

    # =========================================================
    # COOKIES
    # =========================================================

    COOKIE_SECURE: bool = False

    COOKIE_DOMAIN: str = ""

    DEFAULT_ADMIN_PASSWORD: str = "ChangeMe123!"

    # CSRF origin validation (optional, stricter security)
    CSRF_VALIDATE_ORIGIN: bool = False

    # =========================================================
    # VALIDATORS
    # =========================================================

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def validate_cors(
        cls,
        value,
    ) -> list[str]:

        if value is None:
            return []

        return parse_json_list(value)

    @field_validator("OPENSEARCH_HOSTS", mode="before")
    @classmethod
    def validate_opensearch_hosts(
        cls,
        value,
    ) -> list[str]:

        return parse_json_list(value)

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(
        cls,
        value: SecretStr,
    ) -> SecretStr:

        secret = value.get_secret_value()

        if len(secret) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters"
            )

        return value

    @field_validator("DEBUG")
    @classmethod
    def validate_debug(
        cls,
        value: bool,
        info,
    ) -> bool:

        env = info.data.get("ENV")

        if env == "production" and value:
            raise ValueError(
                "DEBUG must be False in production"
            )

        return value

    # =========================================================
    # COMPUTED
    # =========================================================

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:

        password = (
            self.POSTGRES_PASSWORD.get_secret_value()
        )

        return (
            f"postgresql+asyncpg://"
            f"{self.POSTGRES_USER}:{password}"
            f"@{self.POSTGRES_SERVER}:"
            f"{self.POSTGRES_PORT}/"
            f"{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def REDIS_URL(self) -> str:

        if self.REDIS_PASSWORD:

            password = (
                self.REDIS_PASSWORD.get_secret_value()
            )

            return (
                f"redis://:{password}"
                f"@{self.REDIS_HOST}:"
                f"{self.REDIS_PORT}/"
                f"{self.REDIS_DB}"
            )

        return (
            f"redis://{self.REDIS_HOST}:"
            f"{self.REDIS_PORT}/"
            f"{self.REDIS_DB}"
        )

    # =========================================================
    # HELPERS
    # =========================================================

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.ENV == "development"


settings = Settings()