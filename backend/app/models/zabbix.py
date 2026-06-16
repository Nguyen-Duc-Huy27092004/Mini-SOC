"""
Zabbix Database Models.

Completely independent from Wazuh tables.
No foreign keys to wazuh_events, endpoint_inventory, or any other Wazuh model.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, Index, Integer, String, Text
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ZabbixHost(Base):
    """
    Snapshot of Zabbix monitored hosts.
    Updated via sync_to_db() in ZabbixService.
    """
    __tablename__ = "zabbix_hosts"
    __table_args__ = (
        Index("idx_zabbix_host_id", "host_id", unique=True),
        Index("idx_zabbix_host_available", "available_code"),
        Index("idx_zabbix_host_synced", "last_synced"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    host_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="Monitored")
    available_code: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_label: Mapped[str] = mapped_column(String(30), nullable=False, default="Unknown")
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Stored as PostgreSQL text array
    groups: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)

    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    last_synced: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )


class ZabbixProblem(Base):
    """
    Snapshot of active Zabbix problems.
    Refreshed on each sync cycle.
    """
    __tablename__ = "zabbix_problems"
    __table_args__ = (
        Index("idx_zabbix_problem_event_id", "event_id", unique=True),
        Index("idx_zabbix_problem_severity", "severity"),
        Index("idx_zabbix_problem_clock", "clock"),
        Index("idx_zabbix_problem_synced", "synced_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    object_id: Mapped[str] = mapped_column(String(50), nullable=False)  # trigger/item id
    name: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    severity_label: Mapped[str] = mapped_column(String(30), nullable=False, default="Not classified")
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    suppressed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    clock: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    host_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )


class ZabbixEvent(Base):
    """
    Historical Zabbix events (trigger state changes).
    """
    __tablename__ = "zabbix_events"
    __table_args__ = (
        Index("idx_zabbix_event_id", "event_id", unique=True),
        Index("idx_zabbix_event_clock", "clock", postgresql_using="brin"),
        Index("idx_zabbix_event_severity", "severity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    object_id: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    severity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    severity_label: Mapped[str] = mapped_column(String(30), nullable=False, default="Not classified")
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0=OK 1=Problem
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    clock: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )


class ZabbixTrigger(Base):
    """
    Snapshot of Zabbix trigger states.
    """
    __tablename__ = "zabbix_triggers"
    __table_args__ = (
        Index("idx_zabbix_trigger_id", "trigger_id", unique=True),
        Index("idx_zabbix_trigger_priority", "priority"),
        Index("idx_zabbix_trigger_value", "value"),
        Index("idx_zabbix_trigger_synced", "synced_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trigger_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    priority_label: Mapped[str] = mapped_column(String(30), nullable=False, default="Not classified")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Enabled")
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0=OK 1=Problem
    host_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    host_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    last_change: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )


class ZabbixMetric(Base):
    """
    Time-series metric snapshots (CPU, memory, disk values).
    Stored from item.get lastvalue at each sync.
    Older than 7 days can be pruned.
    """
    __tablename__ = "zabbix_metrics"
    __table_args__ = (
        Index("idx_zabbix_metric_host_key", "host_id", "item_key"),
        Index("idx_zabbix_metric_clock", "clock", postgresql_using="brin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    host_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    host_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    item_id: Mapped[str] = mapped_column(String(50), nullable=False)
    item_key: Mapped[str] = mapped_column(String(255), nullable=False)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    units: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    clock: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
