from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    alerts_today: int
    critical_alerts: int
    servers_under_attack: int
    agents_online: int
    agents_total: int
    attacks_blocked: int
    average_risk_score: float
    data_status: str = "available"


class TrendPoint(BaseModel):
    hour: str
    count: int


class SeverityBucket(BaseModel):
    severity: str
    count: int


class RankedServer(BaseModel):
    agent_id: str
    agent_name: str
    alert_count: int
    max_severity: str


class RankedIp(BaseModel):
    ip: str
    country: Optional[str]
    count: int
    attack_type: str


class GeoPoint(BaseModel):
    country: str
    count: int
    lat: Optional[float] = None
    lon: Optional[float] = None


class AgentStatus(BaseModel):
    agent_id: str
    agent_name: str
    status: str
    ip_address: Optional[str]
    os_name: Optional[str]
    risk_score: float
    critical_alerts: int


class MitreItem(BaseModel):
    tactic: str
    technique: str
    count: int


class AlertItemOut(BaseModel):
    id: str
    event_id: str
    timestamp: datetime
    severity: str
    category: str
    description: str
    agent_id: str
    agent_name: str
    source_ip: Optional[str]
    source_country: Optional[str]
    risk_score: float
    rule_id: str
    incident_id: Optional[str] = None


class AlertListResponse(BaseModel):
    alerts: List[AlertItemOut]
    total: int
    page: int
    page_size: int


class IncidentOut(BaseModel):
    id: str
    title: str
    description: str
    status: str
    severity: str
    correlation_type: str
    source_ip: Optional[str]
    agent_id: Optional[str]
    alert_count: int
    risk_score: float
    assigned_to_email: Optional[str]
    mitre_tactic: Optional[str]
    mitre_technique: Optional[str]
    created_at: datetime
    updated_at: datetime


class IncidentListResponse(BaseModel):
    incidents: List[IncidentOut]
    total: int
