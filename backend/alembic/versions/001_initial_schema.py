"""Initial schema with session refresh_jti and indexes.

Revision ID: 001
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(50), unique=True, nullable=False),
        sa.Column("description", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(100), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("must_change_password", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_jti", sa.String(255), unique=True, nullable=False),
        sa.Column("refresh_jti", sa.String(255), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_sessions_token_jti", "sessions", ["token_jti"])
    op.create_index("ix_sessions_refresh_jti", "sessions", ["refresh_jti"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])
    op.create_index("ix_sessions_is_revoked", "sessions", ["is_revoked"])
    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", sa.String(64)),
        sa.Column("hostname", sa.String(255), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("os_name", sa.String(100)),
        sa.Column("os_version", sa.String(100)),
        sa.Column("department", sa.String(100)),
        sa.Column("owner", sa.String(100)),
        sa.Column("criticality", sa.String(20), default="medium"),
        sa.Column("location", sa.String(255)),
        sa.Column("status", sa.String(20), default="active"),
        sa.Column("risk_score", sa.Float(), default=0.0),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "portal_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("details", postgresql.JSONB()),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_portal_audit_logs_action", "portal_audit_logs", ["action"])
    op.create_index("ix_portal_audit_logs_user_id", "portal_audit_logs", ["user_id"])
    op.create_index("ix_portal_audit_logs_created_at", "portal_audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("portal_audit_logs")
    op.drop_table("assets")
    op.drop_table("sessions")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
