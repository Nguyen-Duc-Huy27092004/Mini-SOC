"""
Zabbix integration service package.
Provides async client, parser, mapper, and service for Zabbix API data.
"""
from app.services.zabbix.zabbix_service import zabbix_service

__all__ = ["zabbix_service"]
