from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

from app.services.ddos_engine import DDoSEngine

router = APIRouter()

# Global engine instance
ddos_engine = DDoSEngine(auto_block_enabled=True)

class DDoSMitigateRequest(BaseModel):
    source_ip: str = Field(..., example="198.51.100.42", description="Target IP address to block or unblock")
    operation: str = Field("block", example="block", description="Mitigation operation: 'block' or 'unblock'")
    reason: str = Field("Manual SOC Analyst Action", description="Reason for mitigation")

class DDoSStatusResponse(BaseModel):
    auto_block_enabled: bool
    blocked_count: int
    blocked_ips: Dict[str, Any]

@router.get("/status", response_model=DDoSStatusResponse)
async def get_ddos_status():
    """Get current Anti-DDoS engine mitigation status and list of blocked IPs"""
    blocked_ips = ddos_engine.get_blocked_ips()
    return DDoSStatusResponse(
        auto_block_enabled=ddos_engine.auto_block_enabled,
        blocked_count=len(blocked_ips),
        blocked_ips=blocked_ips
    )

@router.post("/mitigate")
async def execute_manual_mitigation(req: DDoSMitigateRequest):
    """
    Manual 1-Click SOC Analyst Action to block or unblock an IP address at Firewall layer.
    """
    if req.operation not in ("block", "unblock"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Operation must be 'block' or 'unblock'")

    result = await ddos_engine.manual_mitigate(
        source_ip=req.source_ip,
        operation=req.operation,
        reason=req.reason
    )

    if not result.is_ddos and result.action_taken == "FAILED":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.message)

    return {
        "status": "success",
        "operation": req.operation,
        "source_ip": req.source_ip,
        "action_taken": result.action_taken,
        "message": result.message
    }
