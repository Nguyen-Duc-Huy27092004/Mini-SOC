"""
Webhooks Router — Handles inbound callbacks from external services.

Currently supports:
  - POST /webhooks/slack/action  — Slack Interactive Message callbacks
    (Approve/Reject SOAR playbook from Slack button click)

Security:
  Each incoming Slack request is verified with HMAC-SHA256 using the
  SLACK_SIGNING_SECRET. Requests with invalid signatures are rejected with 403.
  If SLACK_SIGNING_SECRET is not configured, verification is skipped
  (development mode only).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings

router = APIRouter()


# ── Slack signature verification ──────────────────────────────────────────────

async def _verify_slack_signature(request: Request) -> bytes:
    """
    Verify Slack request signature (HMAC-SHA256).
    See: https://api.slack.com/authentication/verifying-requests-from-slack
    Raises HTTP 403 if verification fails.
    Returns the raw request body bytes.
    """
    body = await request.body()

    signing_secret = (
        settings.SLACK_SIGNING_SECRET.get_secret_value()
        if settings.SLACK_SIGNING_SECRET
        else None
    )

    if not signing_secret:
        # Development mode — skip verification
        return body

    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    slack_sig  = request.headers.get("X-Slack-Signature", "")

    # Reject stale requests (> 5 min old) to prevent replay attacks
    try:
        if abs(time.time() - float(timestamp)) > 300:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Stale request.")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid timestamp.")

    sig_base = f"v0:{timestamp}:{body.decode('utf-8', errors='replace')}"
    expected = "v0=" + hmac.new(
        signing_secret.encode(),
        sig_base.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, slack_sig):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Slack signature.")

    return body


# ── Slack Interactive Message callback ────────────────────────────────────────

@router.post("/slack/action", summary="Receive Slack interactive message callbacks")
async def slack_action_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handles button-click callbacks from Slack interactive messages.

    Expected action IDs (from Slack message blocks):
      - soar_approve_<run_id>  → Approve the SOAR run
      - soar_reject_<run_id>   → Reject the SOAR run

    Slack sends the payload as application/x-www-form-urlencoded
    with a 'payload' field containing JSON.
    """
    body = await _verify_slack_signature(request)

    # Parse Slack payload (form-encoded JSON)
    try:
        form_data = await request.form()
        payload_str = form_data.get("payload", "")
        payload = json.loads(payload_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Slack payload.")

    # Extract the clicked action
    actions = payload.get("actions", [])
    if not actions:
        return {"text": "No action found."}

    action      = actions[0]
    action_id   = action.get("action_id", "")
    user_name   = payload.get("user", {}).get("name", "Unknown")

    # Parse action_id: format is "soar_approve_<run_id>" or "soar_reject_<run_id>"
    if action_id.startswith("soar_approve_"):
        run_id_str = action_id.removeprefix("soar_approve_")
        decision   = "Approved"
    elif action_id.startswith("soar_reject_"):
        run_id_str = action_id.removeprefix("soar_reject_")
        decision   = "Rejected"
    else:
        return {"text": f"Unknown action: {action_id}"}

    try:
        run_id = uuid.UUID(run_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid run_id: {run_id_str}")

    # Apply the decision — reuse the existing approval logic
    from app.models.soar import SoarApproval, SoarRun
    from sqlalchemy import select
    import datetime

    stmt = select(SoarApproval).where(SoarApproval.run_id == run_id)
    approval = (await db.execute(stmt)).scalars().first()

    if not approval:
        return {"text": f"No pending approval found for run {run_id}."}

    if approval.status != "Pending":
        return {"text": f"Approval already {approval.status}."}

    approval.status     = decision
    approval.decided_at = datetime.datetime.now(datetime.timezone.utc)
    # Note: decided_by_id can't be set from Slack without a user mapping table
    await db.commit()

    if decision == "Approved":
        run = await db.get(SoarRun, run_id)
        if run:
            from app.soar.playbook_engine import PlaybookEngine
            import asyncio
            engine = PlaybookEngine(db)
            asyncio.create_task(engine.execute_run(run.id, None, run.trigger_data))

    import structlog
    structlog.get_logger().info(
        "soar_slack_approval_decision",
        run_id=str(run_id),
        decision=decision,
        slack_user=user_name,
    )

    # Return a Slack response message to update the original message
    return {
        "replace_original": True,
        "text": (
            f"{'✅' if decision == 'Approved' else '❌'} "
            f"SOAR Run `{run_id}` **{decision}** by @{user_name}"
        ),
    }
