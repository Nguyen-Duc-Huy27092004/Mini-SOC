"""Enterprise auth: sessions, JWT rotation, Redis denylist, refresh reuse detection."""
from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis_client import get_redis
from app.models.user import Session, User

# Use argon2 (no 72-byte limit like bcrypt, better security)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"
TOKEN_TYPE_WS = "ws_ticket"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Synchronous password hashing (for scripts, CLI, etc.)
def hash_password_sync(password: str) -> str:
    """Synchronous password hashing - use this for scripts/CLI."""
    return pwd_context.hash(password)


# Asynchronous password hashing (for async contexts)
async def hash_password(password: str) -> str:
    return await asyncio.to_thread(pwd_context.hash, password)


async def verify_password(plain: str, hashed: str) -> bool:
    return await asyncio.to_thread(pwd_context.verify, plain, hashed)


def _secret() -> str:
    return settings.SECRET_KEY.get_secret_value()


def _encode(payload: dict) -> str:
    return jwt.encode(payload, _secret(), algorithm="HS256")


def _decode(token: str) -> dict:
    return jwt.decode(token, _secret(), algorithms=["HS256"])


async def _denylist_jti(jti: str, ttl_seconds: int) -> None:
    redis = await get_redis()
    await redis.setex(f"revoked:jti:{jti}", ttl_seconds, "1")


async def _is_jti_revoked(jti: str) -> bool:
    redis = await get_redis()
    return await redis.exists(f"revoked:jti:{jti}") > 0


async def _mark_refresh_reused(old_refresh_jti: str, user_id: uuid.UUID) -> None:
    """Store consumed refresh jti; reuse triggers full session revoke."""
    redis = await get_redis()
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis.setex(f"refresh_used:{old_refresh_jti}", ttl, str(user_id))


async def _is_refresh_reused(refresh_jti: str) -> bool:
    redis = await get_redis()
    return await redis.exists(f"refresh_used:{refresh_jti}") > 0


def _access_payload(user_id: str, roles: List[str], jti: str) -> dict:
    exp = _utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "exp": exp,
        "sub": user_id,
        "roles": roles,
        "jti": jti,
        "type": TOKEN_TYPE_ACCESS,
    }


def _refresh_payload(user_id: str, jti: str) -> dict:
    exp = _utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return {
        "exp": exp,
        "sub": user_id,
        "jti": jti,
        "type": TOKEN_TYPE_REFRESH,
    }


def create_ws_ticket(user_id: str, roles: List[str]) -> str:
    jti = str(uuid.uuid4())
    exp = _utcnow() + timedelta(seconds=settings.WS_TICKET_EXPIRE_SECONDS)
    return _encode(
        {
            "exp": exp,
            "sub": user_id,
            "roles": roles,
            "jti": jti,
            "type": TOKEN_TYPE_WS,
        }
    )


async def validate_ws_ticket(token: str) -> Tuple[str, List[str]]:
    try:
        payload = _decode(token)
    except JWTError as exc:
        raise ValueError("Invalid WS ticket") from exc
    if payload.get("type") != TOKEN_TYPE_WS:
        raise ValueError("Invalid token type")
    jti = payload.get("jti")
    if jti and await _is_jti_revoked(jti):
        raise ValueError("WS ticket revoked")
    sub = payload.get("sub")
    roles = payload.get("roles") or []
    if not sub:
        raise ValueError("Invalid subject")
    return str(sub), list(roles)


async def create_session_tokens(
    db: AsyncSession,
    user: User,
) -> Tuple[str, str, str, str]:
    """Create DB session and return (access_token, refresh_token, access_jti, refresh_jti)."""
    access_jti = str(uuid.uuid4())
    refresh_jti = str(uuid.uuid4())
    roles = [r.name for r in user.roles]
    access_token = _encode(_access_payload(str(user.id), roles, access_jti))
    refresh_token = _encode(_refresh_payload(str(user.id), refresh_jti))

    expires_at = _utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    session = Session(
        user_id=user.id,
        token_jti=access_jti,
        refresh_jti=refresh_jti,
        expires_at=expires_at,
        is_revoked=False,
    )
    db.add(session)
    await db.commit()
    return access_token, refresh_token, access_jti, refresh_jti


async def validate_access_token(db: AsyncSession, token: str) -> User:
    credentials_msg = "Không thể xác thực thông tin đăng nhập"
    try:
        payload = _decode(token)
    except JWTError:
        raise AuthError(credentials_msg)

    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise AuthError(credentials_msg)

    user_id = payload.get("sub")
    jti = payload.get("jti")
    if not user_id or not jti:
        raise AuthError(credentials_msg)

    if await _is_jti_revoked(jti):
        raise AuthError(credentials_msg)

    stmt = select(Session).where(
        Session.token_jti == jti,
        Session.is_revoked.is_(False),
        Session.expires_at > _utcnow(),
    )
    session = (await db.execute(stmt)).scalars().first()
    if not session:
        raise AuthError(credentials_msg)

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalars().first()
    if not user or not user.is_active:
        raise AuthError(credentials_msg)
    return user


async def refresh_tokens(
    db: AsyncSession,
    refresh_token: str,
) -> Tuple[str, str, User]:
    """Rotate access + refresh; detect refresh token reuse."""
    try:
        payload = _decode(refresh_token)
    except JWTError:
        raise AuthError("Refresh token không hợp lệ")

    if payload.get("type") != TOKEN_TYPE_REFRESH:
        raise AuthError("Refresh token không hợp lệ")

    user_id = payload.get("sub")
    refresh_jti = payload.get("jti")
    if not user_id or not refresh_jti:
        raise AuthError("Refresh token không hợp lệ")

    if await _is_jti_revoked(refresh_jti):
        raise AuthError("Refresh token đã bị thu hồi")

    if await _is_refresh_reused(refresh_jti):
        await revoke_all_user_sessions(db, uuid.UUID(user_id))
        raise AuthError("Phát hiện tái sử dụng refresh token — toàn bộ phiên đã bị thu hồi")

    stmt = select(Session).where(
        Session.refresh_jti == refresh_jti,
        Session.is_revoked.is_(False),
        Session.expires_at > _utcnow(),
    )
    session = (await db.execute(stmt)).scalars().first()
    if not session:
        raise AuthError("Refresh token không hợp lệ")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalars().first()
    if not user or not user.is_active:
        raise AuthError("Tài khoản không khả dụng")

    await _mark_refresh_reused(refresh_jti, user.id)
    ttl = int((session.expires_at - _utcnow()).total_seconds()) if session.expires_at else 3600
    await _denylist_jti(session.token_jti, max(ttl, 60))
    await _denylist_jti(refresh_jti, settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)

    new_access_jti = str(uuid.uuid4())
    new_refresh_jti = str(uuid.uuid4())
    roles = [r.name for r in user.roles]
    access_token = _encode(_access_payload(str(user.id), roles, new_access_jti))
    new_refresh_token = _encode(_refresh_payload(str(user.id), new_refresh_jti))

    session.token_jti = new_access_jti
    session.refresh_jti = new_refresh_jti
    db.add(session)
    await db.commit()

    return access_token, new_refresh_token, user


async def revoke_session_by_access_jti(db: AsyncSession, access_jti: str) -> None:
    stmt = select(Session).where(Session.token_jti == access_jti, Session.is_revoked.is_(False))
    session = (await db.execute(stmt)).scalars().first()
    if not session:
        return
    session.is_revoked = True
    db.add(session)
    await db.commit()
    await _denylist_jti(session.token_jti, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    await _denylist_jti(session.refresh_jti, settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)


async def revoke_all_user_sessions(db: AsyncSession, user_id: uuid.UUID) -> None:
    stmt = select(Session).where(Session.user_id == user_id, Session.is_revoked.is_(False))
    sessions = (await db.execute(stmt)).scalars().all()
    for s in sessions:
        s.is_revoked = True
        db.add(s)
        await _denylist_jti(s.token_jti, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
        await _denylist_jti(s.refresh_jti, settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)
    await db.commit()


async def get_access_jti_from_token(token: str) -> Optional[str]:
    try:
        payload = _decode(token)
        if payload.get("type") == TOKEN_TYPE_ACCESS:
            return payload.get("jti")
    except JWTError:
        return None
    return None


class AuthError(Exception):
    """Authentication failure."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
