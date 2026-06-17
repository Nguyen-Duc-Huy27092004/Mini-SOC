"""
Zabbix Database Models.

Completely independent from Wazuh tables.
No foreign keys to wazuh_events, endpoint_inventory, or any other Wazuh model.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, Index, Integer, String, Text, Enum
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


# =========================================================================
# NEW: Asset Management
# =========================================================================

class ZabbixAsset(Base):
    """
    Asset inventory — manually managed hardware/software register.
    Independent of live Zabbix data (complementary layer).
    """
    __tablename__ = "zabbix_assets"
    __table_args__ = (
        Index("idx_zabbix_asset_hostname", "hostname"),
        Index("idx_zabbix_asset_lifecycle", "lifecycle_status"),
        Index("idx_zabbix_asset_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vendor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    purchase_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    warranty_expiration: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Active | Maintenance | End of Life
    lifecycle_status: Mapped[str] = mapped_column(String(50), nullable=False, default="Active")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# =========================================================================
# NEW: Maintenance Schedule
# =========================================================================

class ZabbixMaintenance(Base):
    """
    Preventive maintenance schedule per host/asset.
    Tracks next/last maintenance dates and generates upcoming tasks.
    """
    __tablename__ = "zabbix_maintenance"
    __table_args__ = (
        Index("idx_zabbix_maint_host", "hostname"),
        Index("idx_zabbix_maint_next_date", "next_maintenance_date"),
        Index("idx_zabbix_maint_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    # Replace Disks | Update Firmware | Windows Patches | Linux Updates |
    # Database Maintenance | Backup Verification | Security Audit | General
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, default="General")
    last_maintenance_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_maintenance_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Interval in days: 90 | 180 | 365
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    # Scheduled | Completed | Overdue | Cancelled
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="Scheduled")
    assigned_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# =========================================================================
# NEW: Server Task Recommendations
# =========================================================================

class ZabbixTask(Base):
    """
    Auto-generated task recommendations from resource/problem data.
    Can also be manually created.
    """
    __tablename__ = "zabbix_tasks"
    __table_args__ = (
        Index("idx_zabbix_task_host", "hostname"),
        Index("idx_zabbix_task_priority", "priority"),
        Index("idx_zabbix_task_status", "status"),
        Index("idx_zabbix_task_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    # Patch Required | Reboot Required | High CPU Investigation | Disk Cleanup |
    # Memory Upgrade | Security Update | Firmware Update | Backup Check
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Low | Medium | High | Critical
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="Medium")
    # Open | In Progress | Resolved | Dismissed
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="Open")
    # auto | manual
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")
    metric_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# =========================================================================
# NEW: Email Notification Log
# =========================================================================

class ZabbixNotification(Base):
    """
    Log of all email notifications sent by the system.
    """
    __tablename__ = "zabbix_notifications"
    __table_args__ = (
        Index("idx_zabbix_notif_type", "notification_type"),
        Index("idx_zabbix_notif_sent_at", "sent_at"),
        Index("idx_zabbix_notif_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # server_down | high_cpu | high_disk | high_severity | maintenance_due |
    # backup_failure | ssl_expiry | test
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    hostname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    recipients: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # comma-separated emails
    severity: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    metric_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    suggested_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # sent | failed | skipped (SMTP disabled)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sent")
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
