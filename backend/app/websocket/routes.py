"""Authenticated WebSocket endpoint."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.services.auth_service import validate_ws_ticket
from app.websocket.manager import manager

logger = structlog.get_logger()
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    ticket = websocket.query_params.get("ticket")
    if not ticket:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing ticket")
        return

    try:
        user_id, roles = await validate_ws_ticket(ticket)
    except ValueError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid ticket")
        return

    if not await manager.check_ws_rate(user_id):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Rate limit exceeded")
        return

    client_id = await manager.connect(websocket, user_id, roles)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as exc:
        await logger.aerror("ws_error", error=str(exc))
        manager.disconnect(client_id)
