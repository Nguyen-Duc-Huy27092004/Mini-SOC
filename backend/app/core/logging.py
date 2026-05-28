"""
Centralized Logging Configuration

Production-grade structured logging:
- JSON logs for SIEM ingestion
- Async-safe contextvars
- Correlation IDs
- Secret filtering
- Structured exception handling
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import settings


# ---------------------------------------------------------------------
# Sensitive Field Filtering
# ---------------------------------------------------------------------

SENSITIVE_FIELDS = {
    "password",
    "token",
    "authorization",
    "cookie",
    "secret",
    "access_token",
    "refresh_token",
    "api_key",
}


def redact_sensitive_data(
    logger,
    method_name,
    event_dict,
):
    """
    Remove sensitive values from logs.
    """

    for key in list(event_dict.keys()):
        if key.lower() in SENSITIVE_FIELDS:
            event_dict[key] = "***REDACTED***"

    return event_dict


# ---------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------

def setup_logging() -> None:
    """
    Configure structured logging.
    """

    timestamper = structlog.processors.TimeStamper(
        fmt="iso",
        utc=True,
    )

    shared_processors = [

        # Async-safe context
        structlog.contextvars.merge_contextvars,

        # Standard metadata
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,

        # Timestamp
        timestamper,

        # Formatting helpers
        structlog.stdlib.PositionalArgumentsFormatter(),

        # Security
        redact_sensitive_data,

        # Exception formatting
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,

        # Unicode safety
        structlog.processors.UnicodeDecoder(),
    ]

    # ---------------------------------------------------------
    # Renderer
    # ---------------------------------------------------------

    if settings.ENV == "production":

        renderer = structlog.processors.JSONRenderer()

    else:

        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
        )

    # ---------------------------------------------------------
    # Structlog Config
    # ---------------------------------------------------------

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # ---------------------------------------------------------
    # Standard Logging Integration
    # ---------------------------------------------------------

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()

    # Avoid duplicate handlers
    root_logger.handlers.clear()

    root_logger.addHandler(handler)

    root_logger.setLevel(
        getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    )

    # ---------------------------------------------------------
    # Third-party Noise Reduction
    # ---------------------------------------------------------

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # ---------------------------------------------------------
    # Startup Log
    # ---------------------------------------------------------

    logger = structlog.get_logger()

    logger.info(
        "logging_initialized",
        environment=settings.ENV,
        log_level=settings.LOG_LEVEL,
    )