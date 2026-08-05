"""
AI Analyst Service — LLM-powered security alert analysis using Google Gemini.

This service wraps the Google Generative AI SDK and provides three capabilities:
  1. analyze_alert()      — Deep analysis of a single security alert
  2. generate_playbook()  — Convert a threat description to a SOAR playbook JSON
  3. chat()               — Conversational SOC assistant with context

The service always has a fallback path:
  - If google-generativeai is not installed → ImportError is caught by callers
  - If GEMINI_API_KEY is empty → raises RuntimeError (callers fall back to simulation)
  - If Gemini API returns an error → re-raises, callers fall back to simulation

Installation:
    pip install google-generativeai>=0.8.0

Configuration (.env):
    GEMINI_API_KEY=AIzaSy...
    GEMINI_MODEL=gemini-1.5-flash   # or gemini-1.5-pro for better quality
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog
from pydantic import BaseModel

from app.core.config import settings

logger = structlog.get_logger()


# ── Data models ────────────────────────────────────────────────────────────────

class AIAnalysis(BaseModel):
    """Structured result from LLM alert analysis."""
    threat_classification: str   # CRITICAL | HIGH | MEDIUM | LOW | FALSE_POSITIVE
    confidence: float            # 0.0 – 1.0
    summary: str
    attack_narrative: str
    iocs: List[str] = []
    mitre_techniques: List[str] = []
    recommended_actions: List[Dict[str, Any]] = []
    false_positive_indicators: List[str] = []
    additional_context: str = ""


# ── System prompts ─────────────────────────────────────────────────────────────

_ALERT_ANALYSIS_PROMPT = """\
Bạn là một chuyên gia phân tích bảo mật cấp cao (Senior SOC Analyst) trong một \
Security Operations Center (SOC). Nhiệm vụ của bạn là phân tích các security alert \
và đưa ra đánh giá chuyên sâu.

Phân tích alert sau và trả về KẾT QUẢ DƯỚI DẠNG JSON THUẦN TÚY (không có markdown, \
không có code block, chỉ là JSON object):

{{
  "threat_classification": "CRITICAL|HIGH|MEDIUM|LOW|FALSE_POSITIVE",
  "confidence": <float 0.0-1.0>,
  "summary": "<Tóm tắt ngắn gọn 1-2 câu>",
  "attack_narrative": "<Giải thích chi tiết những gì đang xảy ra, tại sao nguy hiểm>",
  "iocs": ["<IP>", "<domain>", "<hash>", ...],
  "mitre_techniques": ["T1190", "T1498", ...],
  "recommended_actions": [
    {{"action": "firewall_block", "priority": 1, "reason": "<lý do>"}},
    {{"action": "notify_slack", "priority": 2, "reason": "<lý do>"}},
    {{"action": "escalate_incident", "priority": 3, "reason": "<lý do>"}},
    {{"action": "isolate_host", "priority": 4, "reason": "<lý do>"}}
  ],
  "false_positive_indicators": ["<dấu hiệu nếu đây là false positive>"],
  "additional_context": "<thông tin thêm, khuyến nghị điều tra>"
}}

Các action hợp lệ: firewall_block, notify_slack, notify_telegram, isolate_host, \
kill_process, escalate_incident, log.

Alert data:
{alert_json}

Context:
{context_json}
"""

_PLAYBOOK_GEN_PROMPT = """\
Bạn là một SOAR Engineer chuyên thiết kế security automation playbooks cho hệ thống \
Mini-SOC (FastAPI + PostgreSQL + Redis). Tạo một SOAR playbook từ mô tả sau.

Trả về JSON THUẦN TÚY theo cấu trúc này (không có markdown):
{{
  "name": "<tên ngắn gọn>",
  "description": "<mô tả chi tiết>",
  "execution_mode": "Auto|Need Approval",
  "rules": [
    {{
      "name": "<tên rule>",
      "condition_logic": "AND|OR",
      "condition_config": [
        {{"field": "<field_name>", "operator": "==|!=|>|<|>=|<=|contains", "value": "<value>"}}
      ]
    }}
  ],
  "actions": [
    {{
      "name": "<tên action>",
      "action_type": "firewall_block|notify_slack|notify_telegram|isolate_host|kill_process|escalate_incident|log|webhook",
      "step_order": <int>,
      "config": {{}}
    }}
  ]
}}

Các field hợp lệ trong condition: severity, category, rule_id, source_ip, agent_id, \
attack_type, confidence.

Mô tả threat scenario:
{description}
"""

_CHAT_SYSTEM_PROMPT = """\
Bạn là AI SOC Assistant của hệ thống Mini-SOC. Bạn hỗ trợ các SOC Analyst phân tích \
threats, thực thi SOAR actions, và trả lời câu hỏi về bảo mật.

Bạn CÓ THỂ:
- Phân tích alert, explain attack patterns, đề xuất action
- Hướng dẫn analyst điều tra incidents
- Generate SOAR playbook từ mô tả
- Trả lời câu hỏi kỹ thuật về bảo mật

Bạn KHÔNG TỰ ĐỘNG thực thi action nguy hiểm (block IP, isolate host) — \
bạn đề xuất và hỏi xác nhận trước.

Trả lời bằng tiếng Việt hoặc tiếng Anh tuỳ theo ngôn ngữ của câu hỏi.
Giữ câu trả lời súc tích, thực tế, và có cấu trúc rõ ràng.
Dùng emoji phù hợp để tăng readability.

Context hiện tại:
{context_json}
"""


# ── AI Analyst Service ─────────────────────────────────────────────────────────

class AIAnalystService:
    """
    LLM-powered security analyst backed by Google Gemini.
    All methods raise RuntimeError if Gemini is not configured.
    Callers (ai_soar.py router) catch exceptions and fall back to simulation.
    """

    def __init__(self):
        self._model = None

    def _get_model(self):
        """Lazy-initialize Gemini model. Raises if not configured."""
        if self._model is not None:
            return self._model

        import google.generativeai as genai  # ImportError if not installed

        api_key = (
            settings.GEMINI_API_KEY.get_secret_value()
            if settings.GEMINI_API_KEY
            else None
        )
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            generation_config={
                "temperature":    0.2,   # Low temperature = more deterministic JSON
                "max_output_tokens": settings.AI_MAX_TOKENS,
                "response_mime_type": "application/json",
            },
        )
        logger.info("ai_analyst_gemini_initialized", model=settings.GEMINI_MODEL)
        return self._model

    # ------------------------------------------------------------------
    # Public: Alert Analysis
    # ------------------------------------------------------------------

    async def analyze_alert(
        self,
        alert_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AIAnalysis:
        """
        Run LLM analysis on a security alert.
        Returns structured AIAnalysis. Raises on API error.
        """
        model = self._get_model()

        prompt = _ALERT_ANALYSIS_PROMPT.format(
            alert_json=json.dumps(alert_data, ensure_ascii=False, indent=2),
            context_json=json.dumps(context or {}, ensure_ascii=False, indent=2),
        )

        logger.info("ai_analyze_alert_start", severity=alert_data.get("severity"))
        response = await model.generate_content_async(prompt)
        raw = response.text.strip()

        # Parse and validate JSON response
        parsed = self._parse_json(raw)
        # Clamp confidence to [0.0, 1.0]
        parsed["confidence"] = max(0.0, min(1.0, float(parsed.get("confidence", 0.5))))

        analysis = AIAnalysis(**parsed)
        logger.info(
            "ai_analyze_alert_done",
            classification=analysis.threat_classification,
            confidence=analysis.confidence,
        )
        return analysis

    # ------------------------------------------------------------------
    # Public: Playbook Generation
    # ------------------------------------------------------------------

    async def generate_playbook(self, threat_description: str) -> Dict[str, Any]:
        """
        Generate a SOAR playbook JSON from a natural language threat description.
        Returns the raw dict (not a Pydantic model) for flexibility.
        """
        model = self._get_model()

        prompt = _PLAYBOOK_GEN_PROMPT.format(description=threat_description)

        logger.info("ai_generate_playbook_start", desc_len=len(threat_description))
        response = await model.generate_content_async(prompt)
        parsed = self._parse_json(response.text.strip())

        logger.info("ai_generate_playbook_done", name=parsed.get("name"))
        return parsed

    # ------------------------------------------------------------------
    # Public: Conversational Chat
    # ------------------------------------------------------------------

    async def chat(
        self,
        session_id: UUID,
        user_message: str,
        context: Dict[str, Any],
        user: Any = None,
        db: Any = None,
    ) -> Dict[str, Any]:
        """
        Send a message to the AI SOC assistant and get a contextual reply.
        Returns {"reply": str, "actions_executed": list}.
        """
        model = self._get_model()

        system = _CHAT_SYSTEM_PROMPT.format(
            context_json=json.dumps(context, ensure_ascii=False, indent=2)
        )
        full_prompt = f"{system}\n\nAnalyst: {user_message}\nAI:"

        logger.info("ai_chat_message", session_id=str(session_id))
        response = await model.generate_content_async(full_prompt)
        reply = response.text.strip()

        # Check if the reply requests a SOAR action execution
        actions_executed = await self._maybe_execute_actions(reply, context, db)

        return {"reply": reply, "actions_executed": actions_executed}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response. Handles cases where the model
        wraps JSON in markdown code blocks despite being told not to.
        """
        # Strip markdown code fences if present
        clean = re.sub(r"^```(?:json)?\s*", "", text.strip())
        clean = re.sub(r"\s*```$", "", clean.strip())
        try:
            return json.loads(clean)
        except json.JSONDecodeError as exc:
            logger.warning("ai_json_parse_error", raw_preview=text[:200], error=str(exc))
            raise RuntimeError(f"AI returned invalid JSON: {exc}") from exc

    @staticmethod
    async def _maybe_execute_actions(
        reply: str,
        context: Dict[str, Any],
        db: Any,
    ) -> List[Dict[str, Any]]:
        """
        Scan the AI reply for action execution markers and execute them.
        Currently a stub — Phase 4 will implement Intent Parser here.
        """
        # Placeholder — will be wired to IntentParser in Phase 4
        return []


# ── Module-level singleton ─────────────────────────────────────────────────────
ai_analyst = AIAnalystService()
