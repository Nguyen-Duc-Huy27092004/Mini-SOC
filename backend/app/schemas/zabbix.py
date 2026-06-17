"""
Zabbix Pydantic Response Schemas.

All schemas represent cleaned, normalized Zabbix data.
Raw Zabbix IDs and internal fields are excluded.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# =========================================================================
# Host Schemas
# =========================================================================

class ZabbixHostSummary(BaseModel):
    """Aggregate host status counts."""
    total: int
    available: int
    unavailable: int
    unknown: int


class ZabbixHostOut(BaseModel):
    """Single host with enriched status."""
    host_id: str
    name: str
    status: str
    available: bool
    available_label: str
    ip_address: Optional[str] = None
    groups: List[str] = Field(default_factory=list)
    problem_count: int = 0
    max_severity: int = 0
    max_severity_label: str = "Not classified"


# =========================================================================
# Problem Schemas
# =========================================================================

class ZabbixProblemTag(BaseModel):
    tag: str
    value: str


class ZabbixProblemOut(BaseModel):
    """Single active problem."""
    event_id: str
    name: str
    severity: int
    severity_label: str
    severity_color: str
    acknowledged: bool
    suppressed: bool
    clock: Optional[datetime] = None
    clock_iso: Optional[str] = None
    host_name: str
    tags: List[ZabbixProblemTag] = Field(default_factory=list)


class ZabbixProblemSummary(BaseModel):
    """Aggregated problem counts by severity."""
    total: int
    by_severity: Dict[str, int] = Field(default_factory=dict)
    unacknowledged: int = 0


# =========================================================================
# Trigger Schemas
# =========================================================================

class ZabbixTriggerOut(BaseModel):
    """Single trigger with resolved host + severity info."""
    trigger_id: str
    name: str
    priority: int
    priority_label: str
    priority_color: str
    status: str
    value: int
    value_label: str
    is_problem: bool
    host_id: str
    host_name: str
    last_change: Optional[datetime] = None
    last_change_iso: Optional[str] = None


# =========================================================================
# Availability Schema
# =========================================================================

class ZabbixAvailabilitySummary(BaseModel):
    """Per-host availability status."""
    host_id: str
    host_name: str
    available: bool
    available_label: str
    available_code: int
    groups: List[str] = Field(default_factory=list)


# =========================================================================
# Resource Usage Schema
# =========================================================================

class ZabbixResourceUsage(BaseModel):
    """Per-host CPU / Memory / Disk usage percentages."""
    host_id: str
    host_name: str
    cpu_pct: Optional[float] = None
    mem_pct: Optional[float] = None
    disk_pct: Optional[float] = None
    network_in: Optional[float] = None
    network_out: Optional[float] = None


# =========================================================================
# Aggregated / Chart Schemas
# =========================================================================

class ZabbixSeverityDistribution(BaseModel):
    """Problem count per severity level."""
    severity: int
    severity_label: str
    severity_color: str
    count: int


class ZabbixTopHost(BaseModel):
    """Host ranked by number of active problems."""
    host_name: str
    problem_count: int
    max_severity: int
    max_severity_label: str
    max_severity_color: str


class ZabbixTopServer(BaseModel):
    """Top server by resource utilization."""
    host_id: str
    host_name: str
    ip_address: Optional[str] = None
    cpu_pct: Optional[float] = None
    mem_pct: Optional[float] = None
    disk_pct: Optional[float] = None
    problem_count: int = 0
    status: str = "Unknown"


class ZabbixTimelinePoint(BaseModel):
    """Problem count in a time bucket (hourly)."""
    timestamp: str
    count: int
    severity: int
    severity_label: str


class ZabbixHealthScore(BaseModel):
    """Infrastructure Health Score (0-100) with grade."""
    score: int
    grade: str  # A/B/C/D/F
    breakdown: Dict[str, Any] = Field(default_factory=dict)


# =========================================================================
# Combined Summary (used by /api/v1/zabbix/summary)
# =========================================================================

class ZabbixSummaryResponse(BaseModel):
    """Top-level summary returned by /zabbix/summary."""
    hosts: ZabbixHostSummary
    problems: ZabbixProblemSummary
    health: ZabbixHealthScore
    is_online: bool = True
    error: Optional[str] = None


# =========================================================================
# Overview Response (used by /api/v1/zabbix/overview)
# =========================================================================

class ZabbixOverviewResponse(BaseModel):
    """Extended overview including online/offline/warning/critical counts."""
    total_servers: int = 0
    online_servers: int = 0
    offline_servers: int = 0
    warning_servers: int = 0
    critical_servers: int = 0
    health_score: int = 0
    health_grade: str = "F"
    total_problems: int = 0
    critical_problems: int = 0
    disaster_problems: int = 0
    unacknowledged_problems: int = 0
    is_online: bool = True
    error: Optional[str] = None


# =========================================================================
# Charts Bundle (returned by /api/v1/zabbix/charts)
# =========================================================================

class ZabbixChartsResponse(BaseModel):
    """All chart data in a single response to minimize round-trips."""
    severity_distribution: List[ZabbixSeverityDistribution] = Field(default_factory=list)
    top_hosts: List[ZabbixTopHost] = Field(default_factory=list)
    timeline: List[ZabbixTimelinePoint] = Field(default_factory=list)
    resource_usage: List[ZabbixResourceUsage] = Field(default_factory=list)


# =========================================================================
# Asset Management Schemas
# =========================================================================

class ZabbixAssetCreate(BaseModel):
    """Create a new asset."""
    hostname: str
    ip_address: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    owner: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_date: Optional[datetime] = None
    warranty_expiration: Optional[datetime] = None
    lifecycle_status: str = "Active"
    notes: Optional[str] = None


class ZabbixAssetUpdate(BaseModel):
    """Update an existing asset (all fields optional)."""
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    owner: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_date: Optional[datetime] = None
    warranty_expiration: Optional[datetime] = None
    lifecycle_status: Optional[str] = None
    notes: Optional[str] = None


class ZabbixAssetOut(BaseModel):
    """Asset record as returned by API."""
    id: str
    hostname: str
    ip_address: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    owner: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_date: Optional[datetime] = None
    warranty_expiration: Optional[datetime] = None
    lifecycle_status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# =========================================================================
# Maintenance Schedule Schemas
# =========================================================================

class ZabbixMaintenanceCreate(BaseModel):
    """Create a new maintenance schedule entry."""
    hostname: str
    ip_address: Optional[str] = None
    task_type: str = "General"
    last_maintenance_date: Optional[datetime] = None
    next_maintenance_date: datetime
    interval_days: int = 90
    status: str = "Scheduled"
    assigned_to: Optional[str] = None
    notes: Optional[str] = None


class ZabbixMaintenanceUpdate(BaseModel):
    """Update an existing maintenance entry."""
    task_type: Optional[str] = None
    last_maintenance_date: Optional[datetime] = None
    next_maintenance_date: Optional[datetime] = None
    interval_days: Optional[int] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None


class ZabbixMaintenanceOut(BaseModel):
    """Maintenance schedule record as returned by API."""
    id: str
    hostname: str
    ip_address: Optional[str] = None
    task_type: str
    last_maintenance_date: Optional[datetime] = None
    next_maintenance_date: datetime
    interval_days: int
    status: str
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
    is_overdue: bool = False
    days_until_due: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# =========================================================================
# Task Recommendations Schemas
# =========================================================================

class ZabbixTaskOut(BaseModel):
    """Server task recommendation."""
    id: str
    hostname: str
    ip_address: Optional[str] = None
    task_type: str
    description: str
    priority: str
    status: str
    source: str
    metric_value: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ZabbixTaskUpdate(BaseModel):
    """Update task status."""
    status: Optional[str] = None
    priority: Optional[str] = None


# =========================================================================
# Notification Schemas
# =========================================================================

class ZabbixNotificationOut(BaseModel):
    """Email notification log entry."""
    id: str
    notification_type: str
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    subject: str
    message: str
    recipients: Optional[str] = None
    severity: Optional[str] = None
    metric_value: Optional[float] = None
    suggested_action: Optional[str] = None
    status: str
    error_msg: Optional[str] = None
    sent_at: datetime

    model_config = {"from_attributes": True}


class ZabbixNotificationTestRequest(BaseModel):
    """Request body for test email."""
    email: str
