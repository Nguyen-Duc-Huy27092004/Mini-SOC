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

    SECRET_KEY: SecretStr = Field(
        default=SecretStr("default_mini_soc_secure_secret_key_minimum_32_chars")
    )

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(
        cls,
        value,
    ) -> SecretStr:

        if isinstance(value, SecretStr):
            secret = value.get_secret_value()
        else:
            secret = str(value or "")

        if not secret or len(secret) < 32:
            secret = "default_mini_soc_secure_secret_key_minimum_32_chars"

        return SecretStr(secret)

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

    POSTGRES_PASSWORD: SecretStr = Field(
        default=SecretStr("SocSecurePass123!")
    )

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
    # EMAIL NOTIFICATIONS (Zabbix alerting)
    # =========================================================

    SMTP_HOST: str = "smtp.gmail.com"

    SMTP_PORT: int = 587

    SMTP_USER: str = ""

    SMTP_PASSWORD: SecretStr = Field(default=SecretStr(""))

    SMTP_FROM: str = ""

    # Set to True to enable email sending
    NOTIFICATION_ENABLED: bool = False

    # Comma-separated list of recipient emails
    NOTIFICATION_TO_EMAILS: list[str] = Field(default_factory=list)

    # CPU threshold for high CPU notifications (%)
    NOTIFICATION_CPU_THRESHOLD: float = 90.0

    # Disk threshold for high disk notifications (%)
    NOTIFICATION_DISK_THRESHOLD: float = 90.0

    # Days before maintenance to send notification
    NOTIFICATION_MAINTENANCE_DAYS_AHEAD: int = 7

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
    # FIREWALL API
    # =========================================================

    # REST API endpoint of the firewall appliance (iptables API, pfSense, FortiGate, etc.)
    # If not configured, SOAR will use fallback simulation mode.
    FIREWALL_API_URL: str = "http://localhost:8080/api/v1/firewall"

    FIREWALL_API_TOKEN: SecretStr = Field(default=SecretStr("mock-token"))

    # =========================================================
    # AI-SOAR — Google Gemini LLM Integration
    # =========================================================

    # Google Gemini API key. Get from https://aistudio.google.com/
    # Leave empty to run in offline/simulation mode.
    GEMINI_API_KEY: SecretStr | None = None

    # Gemini model to use. Flash is fast & cheap; Pro is more capable.
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Master switch for AI-SOAR features (analysis, triage, chat, playbook gen)
    AI_SOAR_ENABLED: bool = True

    # Minimum AI confidence to act on a classification (0.0 – 1.0).
    # Below this threshold, the alert is passed to human review.
    AI_TRIAGE_CONFIDENCE_THRESHOLD: float = 0.70

    # If True, AI can suppress false-positive alerts automatically
    # when confidence >= AI_TRIAGE_CONFIDENCE_THRESHOLD.
    AI_AUTO_SUPPRESS_FP: bool = False

    # Maximum tokens for AI alert analysis response
    AI_MAX_TOKENS: int = 2048

    # =========================================================
    # SLACK NOTIFICATIONS
    # =========================================================

    # Slack Incoming Webhook URL.
    # Create at: https://api.slack.com/messaging/webhooks
    SLACK_WEBHOOK_URL: SecretStr | None = None

    # Default Slack channel for alert notifications (e.g. #soc-alerts)
    SLACK_CHANNEL: str = "#soc-alerts"

    # Slack Bot Token for interactive message callbacks (approve/reject playbooks)
    SLACK_BOT_TOKEN: SecretStr | None = None

    # Slack Signing Secret for webhook signature verification
    SLACK_SIGNING_SECRET: SecretStr | None = None

    # =========================================================
    # TELEGRAM NOTIFICATIONS
    # =========================================================

    # Telegram Bot Token. Get from @BotFather.
    TELEGRAM_BOT_TOKEN: SecretStr | None = None

    # Telegram Chat ID to send alerts to (group or channel).
    # Use negative IDs for groups, e.g. -100123456789
    TELEGRAM_CHAT_ID: str = ""

    # =========================================================
    # DDOS ENGINE — Redis Persistence
    # =========================================================

    # Redis key prefix for persisting blocked IPs across restarts
    DDOS_REDIS_KEY_PREFIX: str = "ddos:blocked"

    # Default TTL for blocked IPs in Redis (seconds). Default 24h.
    DDOS_BLOCK_TTL_SECONDS: int = 86400

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

        if self.REDIS_PASSWORD and self.REDIS_PASSWORD.get_secret_value().strip():

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