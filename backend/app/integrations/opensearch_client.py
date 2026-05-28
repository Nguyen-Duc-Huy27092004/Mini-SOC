"""
Shared Async OpenSearch Client
Production-grade OpenSearch connection manager.
"""

from __future__ import annotations

from typing import Optional

import structlog
from opensearchpy import AsyncOpenSearch
from opensearchpy.exceptions import (
    ConnectionError as OpenSearchConnectionError,
    TransportError,
)

from app.core.config import settings
from app.core.metrics import (
    OS_QUERY_ERRORS,
)

logger = structlog.get_logger()

# =========================================================
# Globals
# =========================================================

_opensearch_client: Optional[AsyncOpenSearch] = None

# =========================================================
# Internal Factory
# =========================================================

async def _create_client() -> AsyncOpenSearch:
    """
    Create and validate OpenSearch client.
    """

    client = AsyncOpenSearch(
        hosts=settings.OPENSEARCH_HOSTS,

        http_auth=(
            settings.OPENSEARCH_USER,
            settings.OPENSEARCH_PASSWORD.get_secret_value(),
        ),

        use_ssl=True,

        verify_certs=settings.OPENSEARCH_VERIFY_CERTS,

        ssl_show_warn=settings.OPENSEARCH_SSL_SHOW_WARN,

        timeout=30,

        max_retries=3,
        retry_on_timeout=True,

        pool_maxsize=25,

        http_compress=True,
    )

    # Validate connectivity
    health = await client.cluster.health()

    await logger.ainfo(
        "opensearch_connected",
        cluster_name=health.get("cluster_name"),
        status=health.get("status"),
    )

    return client


# =========================================================
# Public Accessor
# =========================================================

async def get_opensearch_client() -> AsyncOpenSearch:
    """
    Return shared OpenSearch client.

    Auto-recovers from dropped connections.
    """

    global _opensearch_client

    if _opensearch_client is None:

        try:
            _opensearch_client = await _create_client()

        except Exception:
            await logger.aerror(
                "opensearch_initialization_failed",
                exc_info=True,
            )
            raise

    # Health check existing client
    try:
        await _opensearch_client.ping()

    except Exception:

        await logger.awarning(
            "opensearch_connection_lost_reconnecting"
        )

        try:
            await close_opensearch_client()

            _opensearch_client = await _create_client()

        except Exception:
            await logger.aerror(
                "opensearch_reconnect_failed",
                exc_info=True,
            )
            raise

    return _opensearch_client


# =========================================================
# Shutdown
# =========================================================

async def close_opensearch_client() -> None:
    """
    Gracefully close OpenSearch connections.
    """

    global _opensearch_client

    if _opensearch_client is not None:

        try:
            await _opensearch_client.close()

            await logger.ainfo(
                "opensearch_closed"
            )

        except Exception:
            await logger.aerror(
                "opensearch_close_error",
                exc_info=True,
            )

        finally:
            _opensearch_client = None


# =========================================================
# Healthcheck
# =========================================================

async def opensearch_healthcheck() -> bool:
    """
    Lightweight OpenSearch healthcheck.
    """

    try:
        client = await get_opensearch_client()

        result = await client.ping()

        return bool(result)

    except Exception:
        return False


# =========================================================
# Safe Query Wrapper
# =========================================================

async def safe_opensearch_query(
    operation: str,
    query_coro,
):
    """
    Execute OpenSearch query safely with metrics/logging.
    """

    try:
        return await query_coro

    except (
        OpenSearchConnectionError,
        TransportError,
    ) as exc:

        OS_QUERY_ERRORS.labels(
            operation=operation,
        ).inc()

        await logger.aerror(
            "opensearch_query_failed",
            operation=operation,
            error=str(exc),
            exc_info=True,
        )

        raise