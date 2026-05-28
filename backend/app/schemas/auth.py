from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, computed_field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=12)


class UserProfile(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    is_active: bool
    must_change_password: bool
    roles: List[str]
    created_at: datetime

    # Frontend expects a `username` field — derived from email prefix
    @computed_field  # type: ignore[misc]
    @property
    def username(self) -> str:
        return self.email.split("@")[0]

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    user: UserProfile
    csrf_token: str


class WsTicketResponse(BaseModel):
    ticket: str
    expires_in: int
