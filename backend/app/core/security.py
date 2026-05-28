"""
Authentication & RBAC Dependencies
Production-grade FastAPI security dependencies.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Sequence

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import ACCESS_COOKIE
from app.core.database import get_db
from app.models.user import User
from app.services.auth_service import (
    AuthError,
    hash_password,
    hash_password_sync,
    verify_password,
    validate_access_token,
)

logger = structlog.get_logger()

# =========================================================
# Bearer Scheme
# =========================================================

bearer_scheme = HTTPBearer(auto_error=False)

# =========================================================
# RBAC
# =========================================================

class Role(str, Enum):
    SUPER_ADMIN = "Super Admin"
    SOC_ADMIN = "SOC Admin"
    ANALYST = "Analyst"
    VIEWER = "Viewer"


# =========================================================
# Token Extraction
# =========================================================

async def get_token_from_request(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        bearer_scheme
    ),
) -> Optional[str]:
    """
    Extract JWT from:
    1. Authorization Bearer header
    2. HttpOnly cookie fallback
    """

    if credentials:
        token = credentials.credentials

        if token and isinstance(token, str):
            return token.strip()

    cookie_token = request.cookies.get(ACCESS_COOKIE)

    if cookie_token:
        return cookie_token.strip()

    return None


# =========================================================
# Current User
# =========================================================

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        bearer_scheme
    ),
) -> User:
    """
    Validate JWT and return authenticated user.
    """

    token = await get_token_from_request(
        request=request,
        credentials=credentials,
    )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = await validate_access_token(
            db=db,
            token=token,
        )

        # Disabled/inactive account protection
        if not user.is_active:
            await logger.awarning(
                "inactive_user_login_attempt",
                user_id=user.id,
                email=user.email,
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account disabled",
            )

        return user

    except AuthError:
        await logger.awarning(
            "invalid_access_token",
            path=request.url.path,
            client=str(request.client),
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# =========================================================
# RBAC Dependency
# =========================================================

def require_roles(
    allowed_roles: Sequence[str | Role],
):
    """RBAC dependency factory — accepts role names or Role enum values."""

    allowed = {r.value if isinstance(r, Role) else r for r in allowed_roles}

    async def _checker(
        current_user: User = Depends(get_current_user),
    ) -> User:

        user_roles = {role.name for role in current_user.roles}

        if Role.SUPER_ADMIN.value in user_roles:
            return current_user

        if not user_roles.intersection(allowed):

            await logger.awarning(
                "rbac_access_denied",
                user_id=current_user.id,
                email=current_user.email,
                required_roles=list(allowed),
                user_roles=list(user_roles),
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return current_user

    return _checker


# =========================================================
# Password Rotation Enforcement
# =========================================================

async def require_password_changed(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Force password change on first login/reset.
    """

    if current_user.must_change_password:

        await logger.awarning(
            "password_change_required",
            user_id=current_user.id,
            email=current_user.email,
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required",
        )

    return current_user