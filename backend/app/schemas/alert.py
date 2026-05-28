from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class AlertItem(BaseModel):
    id: str
    timestamp: str
    rule_id: str
    rule_level: int
    description: str
    agent_id: str
    agent_name: str
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    country: Optional[str] = None
    severity: str # critical, high, medium, low
    category: str # web, brute_force, malware, usb, powershell, system
    count: int = 1
    raw_log: Optional[Dict[str, Any]] = None
    risk_score: float = 0.0

class AlertSummaryResponse(BaseModel):
    alerts: List[AlertItem]
    total: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int

class AlertQueryParams(BaseModel):
    limit: int = 50
    offset: int = 0
    severity: Optional[str] = None
    agent_id: Optional[str] = None
    category: Optional[str] = None
    query: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
