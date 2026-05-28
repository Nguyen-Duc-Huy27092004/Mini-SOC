from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.cookies import ACCESS_COOKIE, REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.core.csrf import generate_csrf_token, validate_csrf
from app.core.database import get_db
from app.core.security import get_current_user, get_token_from_request, require_password_changed
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    UserProfile,
    WsTicketResponse,
)
from app.services import auth_service
from app.services.auth_service import (
    AuthError,
    create_session_tokens,
    create_ws_ticket,
    get_access_jti_from_token,
    hash_password,
    refresh_tokens,
    revoke_all_user_sessions,
    revoke_session_by_access_jti,
    verify_password,
)
from app.utils.audit import log_portal_action

router = APIRouter()


def _profile(user: User) -> UserProfile:
    roles: List[str] = [r.name for r in user.roles]
    return UserProfile(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        roles=roles,
        created_at=user.created_at,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request_data: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    from app.middleware.rate_limit import login_rate_limit

    await login_rate_limit(request, response)
    stmt = select(User).where(User.email == request_data.email)
    user = (await db.execute(stmt)).scalars().first()

    password_valid = False
    if user and user.hashed_password:
        try:
            password_valid = await verify_password(request_data.password, user.hashed_password)
        except Exception:
            # Invalid password hash in database
            password_valid = False

    if not user or not password_valid:
        await log_portal_action(
            db,
            action="login_failed",
            details={"email": request_data.email, "reason": "invalid_credentials"},
            request=request,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác",
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản này đã bị khóa")

    access_token, refresh_token, _, _ = await create_session_tokens(db, user)
    csrf = generate_csrf_token()
    set_auth_cookies(response, access_token, refresh_token, csrf)

    roles = [r.name for r in user.roles]
    await log_portal_action(
        db,
        action="login_success",
        details={"email": user.email, "roles": roles},
        user_id=user.id,
        request=request,
    )

    return LoginResponse(user=_profile(user), csrf_token=csrf)


@router.post("/refresh", response_model=LoginResponse)
async def refresh_session(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    validate_csrf(request)
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Thiếu refresh token")

    try:
        access_token, new_refresh, user = await refresh_tokens(db, refresh_token)
    except AuthError as exc:
        clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.message)

    csrf = generate_csrf_token()
    set_auth_cookies(response, access_token, new_refresh, csrf)
    return LoginResponse(user=_profile(user), csrf_token=csrf)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    validate_csrf(request)
    token = await get_token_from_request(request)
    if token:
        jti = await get_access_jti_from_token(token)
        if jti:
            await revoke_session_by_access_jti(db, jti)

    clear_auth_cookies(response)
    await log_portal_action(
        db,
        action="logout",
        details={"email": current_user.email, "scope": "current"},
        user_id=current_user.id,
        request=request,
    )
    return {"success": True, "detail": "Đăng xuất thành công"}


@router.post("/logout-all")
async def logout_all(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    validate_csrf(request)
    await revoke_all_user_sessions(db, current_user.id)
    clear_auth_cookies(response)
    await log_portal_action(
        db,
        action="logout",
        details={"email": current_user.email, "scope": "all"},
        user_id=current_user.id,
        request=request,
    )
    return {"success": True, "detail": "Đã đăng xuất tất cả phiên"}


@router.get("/ws-ticket", response_model=WsTicketResponse)
async def ws_ticket(
    current_user: User = Depends(require_password_changed),
) -> WsTicketResponse:
    roles = [r.name for r in current_user.roles]
    ticket = create_ws_ticket(str(current_user.id), roles)
    return WsTicketResponse(ticket=ticket, expires_in=60)


@router.post("/change-password")
async def change_password(
    request_data: ChangePasswordRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    validate_csrf(request)
    if not await verify_password(request_data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mật khẩu cũ không chính xác")

    current_user.hashed_password = await hash_password(request_data.new_password)
    current_user.must_change_password = False
    db.add(current_user)
    await revoke_all_user_sessions(db, current_user.id)
    clear_auth_cookies(response)

    await log_portal_action(
        db,
        action="change_password",
        details={"email": current_user.email},
        user_id=current_user.id,
        request=request,
    )
    return {"success": True, "detail": "Đổi mật khẩu thành công. Vui lòng đăng nhập lại."}


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)) -> UserProfile:
    return _profile(current_user)
