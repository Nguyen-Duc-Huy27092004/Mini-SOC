from __future__ import annotations

from app.services.base_provider import BaseDataProvider
from app.services.wazuh_data_provider import WazuhDataProvider

_provider: WazuhDataProvider | None = None


def get_data_provider() -> BaseDataProvider:
    """Single provider: PostgreSQL / Wazuh events only."""
    global _provider
    if _provider is None:
        _provider = WazuhDataProvider()
    return _provider
