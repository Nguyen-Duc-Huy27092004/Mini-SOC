from __future__ import annotations

import ipaddress
import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$")


class ServerCreateRequest(BaseModel):
    hostname: str = Field(min_length=1, max_length=253)
    ip_address: str
    agent_id: Optional[str] = None
    os_name: str = "Linux"
    os_version: str = "Ubuntu 22.04"
    department: str = "IT Department"
    owner: str = "Admin"
    criticality: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    location: str = "Hanoi Data Center"

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, v: str) -> str:
        if not HOSTNAME_RE.match(v):
            raise ValueError("Hostname không hợp lệ")
        return v

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        ipaddress.ip_address(v)
        return v


class ServiceStatus(BaseModel):
    name: str
    status: str
    port: Optional[int] = None


class NetworkUsage(BaseModel):
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_speed_kbps: float = 0.0
    tx_speed_kbps: float = 0.0


class ServerDetail(BaseModel):
    id: str
    hostname: str
    ip_address: str
    os_name: str
    os_version: str
    uptime: int
    cpu_usage: float
    ram_usage: float
    ram_total_gb: float
    disk_usage: float
    disk_total_gb: float
    antivirus_status: str
    patch_status: str
    services: List[ServiceStatus]
    network: NetworkUsage
    status: str


class ServerSummaryResponse(BaseModel):
    servers: List[ServerDetail]
    total_count: int
    online_count: int
    offline_count: int
    data_status: str = "available"
