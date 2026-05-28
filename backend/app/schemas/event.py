"""Event and Alert Schemas for API Responses"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class EventSourceSchema(BaseModel):
    """Source information in an event"""
    ip: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None


class EventDestinationSchema(BaseModel):
    """Destination information in an event"""
    ip: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None


class EventAgentSchema(BaseModel):
    """Agent information in an event"""
    id: str
    name: str


class EventRuleSchema(BaseModel):
    """Rule information in an event"""
    id: str
    description: str
    level: int
    group: str


class WazuhEventSchema(BaseModel):
    """
    Normalized Wazuh Event for API responses.
    
    Single source of truth for all event data.
    """
    event_id: str
    timestamp: datetime = Field(alias="event_timestamp")
    agent: EventAgentSchema
    severity: str = Field(description="critical, high, medium, low")
    risk_score: float
    rule: EventRuleSchema
    message: str
    category: str
    source: EventSourceSchema
    destination: EventDestinationSchema
    is_suppressed: bool
    
    class Config:
        from_attributes = True


class AlertSuppressionSchema(BaseModel):
    """Alert Suppression Summary"""
    id: str
    suppression_type: str  # deduplication, burst_grouping, repeated_attack, thresholding
    agent_id: str
    rule_id: str
    alert_count: int
    display_alert_count: int
    status: str  # active, acknowledged, expired, resolved
    group_key: str
    suppression_expires_at: datetime
    acknowledged_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class EndpointRiskSchema(BaseModel):
    """Endpoint Risk Summary"""
    agent_id: str
    agent_name: str
    status: str  # active, disconnected, never_connected
    current_risk_score: float  # 0-100
    critical_alert_count: int
    last_keepalive: Optional[datetime] = None
    os_name: Optional[str] = None
    ip_address: Optional[str] = None
    
    class Config:
        from_attributes = True


class DashboardStatsSchema(BaseModel):
    """Dashboard Statistics"""
    total_alerts_today: int
    critical_alerts_today: int
    total_endpoints: int
    active_endpoints: int
    endpoints_with_risk: int
    avg_endpoint_risk: float
    top_rule_id: Optional[str] = None
    top_rule_count: int = 0


class AlertTimelineEntrySchema(BaseModel):
    """Alert Timeline Entry"""
    timestamp: datetime
    count: int
    severity: str
    
    class Config:
        from_attributes = True


class AlertListResponseSchema(BaseModel):
    """Paginated alert list response"""
    total: int
    page: int
    page_size: int
    alerts: List[WazuhEventSchema]


class EndpointListResponseSchema(BaseModel):
    """Paginated endpoint list response"""
    total: int
    page: int
    page_size: int
    endpoints: List[EndpointRiskSchema]


class RealtimeEventWsSchema(BaseModel):
    """
    WebSocket event message schema.
    
    Sent to connected clients in real-time.
    """
    event_type: str = "alert"  # alert, metric, control
    event_id: str
    timestamp: datetime
    data: WazuhEventSchema
    server_time: datetime = Field(default_factory=datetime.utcnow)


class WsHeartbeatSchema(BaseModel):
    """WebSocket heartbeat message"""
    event_type: str = "heartbeat"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    server_time: datetime = Field(default_factory=datetime.utcnow)
