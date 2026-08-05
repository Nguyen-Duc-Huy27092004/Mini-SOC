"""
AI-SOAR API Router — LLM-powered security analysis endpoints.

Endpoints:
  POST /ai/analyze-alert          — Analyze a specific alert with Gemini LLM
  GET  /ai/runs/{run_id}/analysis — Retrieve saved AI analysis for a SOAR run
  POST /ai/generate-playbook      — AI generates a SOAR playbook from description
  POST /ai/chat                   — Conversational SOC interface
  GET  /ai/chat/sessions          — List user's chat sessions
  GET  /ai/chat/sessions/{id}     — Get chat session history

All endpoints require authentication. AI analysis is async and may take 1-5s.
When GEMINI_API_KEY is not configured, endpoints return a structured
simulation response so the frontend can still demonstrate the UI.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.models.user import User

logger = structlog.get_logger()
router = APIRouter()


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class AnalyzeAlertRequest(BaseModel):
    alert_id: Optional[uuid.UUID] = Field(None, description="UUID of WazuhEvent to analyse")
    alert_data: Optional[Dict[str, Any]] = Field(
        None, description="Raw alert dict (if alert_id not provided)"
    )


class GeneratePlaybookRequest(BaseModel):
    threat_description: str = Field(
        ...,
        min_length=10,
        description=(
            "Natural language description of the threat scenario. "
            "E.g. 'Auto-block IPs after 5 failed SSH logins in 60 seconds'"
        ),
    )
    auto_deploy: bool = Field(False, description="If True, deploy the generated playbook immediately")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: Optional[uuid.UUID] = Field(None, description="Resume existing session")
    context: Optional[Dict[str, Any]] = Field(
        None, description="Optional linked context: {alert_id, incident_id, run_id}"
    )


class AIAnalysisResponse(BaseModel):
    threat_classification: str
    confidence: float
    summary: str
    attack_narrative: str
    iocs: List[str]
    mitre_techniques: List[str]
    recommended_actions: List[Dict[str, Any]]
    false_positive_indicators: List[str]
    additional_context: str
    simulation_mode: bool = False


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    reply: str
    actions_executed: List[Dict[str, Any]] = []
    simulation_mode: bool = False


# ── Helper: load AI analyst lazily ────────────────────────────────────────────

def _get_ai_analyst():
    """Lazy import to avoid startup errors when google-generativeai is not installed."""
    try:
        from app.services.ai_analyst import ai_analyst
        return ai_analyst
    except ImportError:
        return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/analyze-alert",
    response_model=AIAnalysisResponse,
    summary="Analyze a security alert with AI",
)
async def analyze_alert(
    req: AnalyzeAlertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AIAnalysisResponse:
    """
    Submit a Wazuh alert (by ID or raw dict) for LLM-powered analysis.
    Returns threat classification, MITRE mapping, recommended SOAR actions, and more.
    """
    alert_data: Dict[str, Any] = {}

    if req.alert_id:
        from app.models.event import WazuhEvent
        event = await db.get(WazuhEvent, req.alert_id)
        if not event:
            raise HTTPException(status_code=404, detail=f"Alert {req.alert_id} not found.")
        alert_data = {
            "event_id": event.event_id,
            "severity":  event.severity,
            "category":  event.category,
            "rule_id":   event.rule_id,
            "rule_description": event.rule_description,
            "source_ip": event.source_ip,
            "agent_id":  event.agent_id,
            "source_user": event.source_user,
            "raw_log":   event.raw_log,
        }
    elif req.alert_data:
        alert_data = req.alert_data
    else:
        raise HTTPException(status_code=400, detail="Provide either alert_id or alert_data.")

    analyst = _get_ai_analyst()
    if analyst and settings.AI_SOAR_ENABLED:
        try:
            result = await analyst.analyze_alert(alert_data)
            return AIAnalysisResponse(**result.model_dump(), simulation_mode=False)
        except Exception as exc:
            logger.warning("ai_analyze_alert_error", error=str(exc))
            # Fall through to simulation

    # Simulation mode (no API key or error)
    return _simulate_analysis(alert_data)


@router.get(
    "/runs/{run_id}/analysis",
    response_model=Optional[AIAnalysisResponse],
    summary="Get saved AI analysis for a SOAR run",
)
async def get_run_analysis(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Optional[AIAnalysisResponse]:
    """Retrieve the AI analysis that was saved when a SOAR run executed."""
    from app.models.soar import SoarRun
    run = await db.get(SoarRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="SOAR run not found.")
    if not run.ai_analysis:
        return None
    return AIAnalysisResponse(**run.ai_analysis, simulation_mode=False)


@router.post(
    "/generate-playbook",
    summary="Generate a SOAR playbook from a natural language description",
)
async def generate_playbook(
    req: GeneratePlaybookRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Describe a threat scenario in natural language and get a ready-to-deploy
    SOAR playbook JSON back. Optionally auto-deploy it.
    """
    analyst = _get_ai_analyst()
    if analyst and settings.AI_SOAR_ENABLED:
        try:
            playbook_data = await analyst.generate_playbook(req.threat_description)

            if req.auto_deploy:
                from app.models.soar import SoarPlaybook, SoarRule, SoarAction
                pb = SoarPlaybook(
                    name=playbook_data.get("name", "AI Generated Playbook"),
                    description=playbook_data.get("description", req.threat_description),
                    is_active=True,
                    execution_mode=playbook_data.get("execution_mode", "Need Approval"),
                )
                db.add(pb)
                await db.commit()
                await db.refresh(pb)

                for r in playbook_data.get("rules", []):
                    db.add(SoarRule(playbook_id=pb.id, **r))
                for a in playbook_data.get("actions", []):
                    db.add(SoarAction(playbook_id=pb.id, **a))
                await db.commit()

                return {
                    "playbook": playbook_data,
                    "deployed": True,
                    "playbook_id": str(pb.id),
                    "simulation_mode": False,
                }

            return {"playbook": playbook_data, "deployed": False, "simulation_mode": False}

        except Exception as exc:
            logger.warning("ai_generate_playbook_error", error=str(exc))

    # Simulation mode
    return _simulate_playbook(req.threat_description)


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Conversational SOC — chat with the AI security assistant",
)
async def ai_chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ChatResponse:
    """
    Send a message to the AI SOC assistant. It understands security context
    and can execute SOAR actions on your behalf (with confirmation).

    Example commands:
      - "Block IP 198.51.100.45"
      - "Show me all critical alerts from the last hour"
      - "Create a playbook for SSH brute force"
      - "What's the risk score of agent web-server-01?"
    """
    session_id = req.session_id or uuid.uuid4()

    analyst = _get_ai_analyst()
    if analyst and settings.AI_SOAR_ENABLED:
        try:
            result = await analyst.chat(
                session_id=session_id,
                user_message=req.message,
                context=req.context or {},
                user=current_user,
                db=db,
            )
            return ChatResponse(
                session_id=session_id,
                reply=result["reply"],
                actions_executed=result.get("actions_executed", []),
                simulation_mode=False,
            )
        except Exception as exc:
            logger.warning("ai_chat_error", error=str(exc))

    # Simulation mode
    return ChatResponse(
        session_id=session_id,
        reply=_simulate_chat_reply(req.message),
        actions_executed=[],
        simulation_mode=True,
    )


@router.get(
    "/status",
    summary="Check AI-SOAR engine status",
)
async def ai_status(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Returns the current AI-SOAR configuration status."""
    has_gemini = bool(
        settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.get_secret_value()
    )
    has_slack    = bool(settings.SLACK_WEBHOOK_URL)
    has_telegram = bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)

    return {
        "ai_soar_enabled":   settings.AI_SOAR_ENABLED,
        "gemini_configured": has_gemini,
        "gemini_model":      settings.GEMINI_MODEL,
        "slack_configured":  has_slack,
        "telegram_configured": has_telegram,
        "auto_suppress_fp":  settings.AI_AUTO_SUPPRESS_FP,
        "confidence_threshold": settings.AI_TRIAGE_CONFIDENCE_THRESHOLD,
        "mode": "live" if has_gemini else "simulation",
    }


# ── Simulation helpers (used when Gemini API not configured) ──────────────────

def _simulate_analysis(alert_data: Dict[str, Any]) -> AIAnalysisResponse:
    """Return a realistic-looking simulated analysis for demo/dev mode."""
    severity    = str(alert_data.get("severity", "medium")).lower()
    attack_type = str(alert_data.get("attack_type", alert_data.get("category", "UNKNOWN")))
    source_ip   = str(alert_data.get("source_ip", "N/A"))

    return AIAnalysisResponse(
        threat_classification="HIGH" if severity in ("critical", "high") else "MEDIUM",
        confidence=0.87,
        summary=f"[SIMULATION] Suspicious {attack_type} activity detected from {source_ip}.",
        attack_narrative=(
            f"The source IP {source_ip} has been flagged for {attack_type} behaviour. "
            "This analysis is running in SIMULATION mode — configure GEMINI_API_KEY "
            "in your .env for real AI-powered insights."
        ),
        iocs=[source_ip] if source_ip != "N/A" else [],
        mitre_techniques=["T1190", "T1498"],
        recommended_actions=[
            {"action": "firewall_block", "priority": 1, "reason": "Block attacking IP immediately"},
            {"action": "notify_slack",   "priority": 2, "reason": "Alert SOC team"},
            {"action": "escalate_incident", "priority": 3, "reason": "Open incident for tracking"},
        ],
        false_positive_indicators=["If IP belongs to a known scanner/CDN"],
        additional_context="Set GEMINI_API_KEY to enable real AI analysis.",
        simulation_mode=True,
    )


def _simulate_playbook(description: str) -> Dict[str, Any]:
    return {
        "playbook": {
            "name": f"AI Generated: {description[:60]}",
            "description": description,
            "execution_mode": "Need Approval",
            "rules": [
                {
                    "name": "Trigger condition",
                    "condition_logic": "AND",
                    "condition_config": [
                        {"field": "severity", "operator": "==", "value": "high"}
                    ],
                }
            ],
            "actions": [
                {"name": "Block attacker", "action_type": "firewall_block",
                 "step_order": 1, "config": {"ip": "{{source_ip}}", "operation": "block"}},
                {"name": "Notify team", "action_type": "notify_slack",
                 "step_order": 2, "config": {"message_template": "Alert from {{source_ip}}"}},
            ],
        },
        "deployed": False,
        "simulation_mode": True,
        "note": "Set GEMINI_API_KEY to generate real AI-crafted playbooks.",
    }


def _simulate_chat_reply(message: str) -> str:
    msg = message.lower()
    if "block" in msg:
        return (
            "🔒 [SIMULATION] Tôi hiểu bạn muốn block một IP. "
            "Trong chế độ live, tôi sẽ thực thi SOAR firewall_block action ngay lập tức. "
            "Hãy cấu hình GEMINI_API_KEY để kích hoạt tính năng này."
        )
    if "playbook" in msg:
        return (
            "📋 [SIMULATION] Tôi có thể tạo playbook từ mô tả của bạn. "
            "Sử dụng endpoint POST /ai/generate-playbook với threat_description. "
            "Cấu hình GEMINI_API_KEY để nhận playbook thực sự từ AI."
        )
    return (
        f"🤖 [SIMULATION MODE] Câu hỏi nhận được: '{message}'. "
        "AI-SOAR đang chạy ở chế độ mô phỏng. "
        "Cấu hình GEMINI_API_KEY trong file .env để bật chế độ AI thực."
    )
