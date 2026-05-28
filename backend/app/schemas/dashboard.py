from typing import List, Dict, Any
from pydantic import BaseModel

class StatItem(BaseModel):
    label: str
    value: Any
    change_percentage: float
    status: str # ok, warning, critical

class SecurityScore(BaseModel):
    score: float
    level: str # Excellent, Good, Fair, Poor
    last_updated: str

class TimelineItem(BaseModel):
    timestamp: str
    count: int
    severity: str # critical, high, medium, low

class TopAttacker(BaseModel):
    ip: str
    country: str
    count: int
    attack_type: str

class DashboardOverview(BaseModel):
    data_status: str = "available"  # available | degraded | unavailable
    security_score: SecurityScore
    total_servers: int
    agents_online: int
    agents_offline: int
    critical_alerts: int
    high_alerts: int
    backup_status: str # OK, Canh bao, Loi
    endpoint_count: int
    top_attackers: List[TopAttacker]
    attack_timeline: List[TimelineItem]
    alert_distribution_severity: Dict[str, int] # critical, high, medium, low
