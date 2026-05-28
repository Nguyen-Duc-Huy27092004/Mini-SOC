"""Incident workflow tables.

Revision ID: 003_incidents
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_incidents"
down_revision = "002_wazuh_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), server_default="open", nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("correlation_key", sa.String(255), nullable=False),
        sa.Column("correlation_type", sa.String(50), nullable=False),
        sa.Column("source_ip", sa.String(45)),
        sa.Column("agent_id", sa.String(10)),
        sa.Column("rule_id", sa.String(10)),
        sa.Column("category", sa.String(50)),
        sa.Column("mitre_tactic", sa.String(80)),
        sa.Column("mitre_technique", sa.String(80)),
        sa.Column("alert_count", sa.Integer(), server_default="1"),
        sa.Column("risk_score", sa.Float(), server_default="0"),
        sa.Column("assigned_to_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("metadata_json", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_incident_status", "incidents", ["status"])
    op.create_index("idx_incident_severity", "incidents", ["severity"])
    op.create_index("idx_incident_created", "incidents", ["created_at"])
    op.create_index("idx_incident_correlation", "incidents", ["correlation_key"])

    op.create_table(
        "incident_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_incident_comments_incident", "incident_comments", ["incident_id"])

    op.create_table(
        "alert_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wazuh_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_alert_assignments_incident", "alert_assignments", ["incident_id"])
    op.create_index("idx_alert_assignments_event", "alert_assignments", ["event_id"], unique=True)

    op.create_table(
        "incident_timeline",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("details", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_incident_timeline_incident", "incident_timeline", ["incident_id"])


def downgrade() -> None:
    op.drop_table("incident_timeline")
    op.drop_table("alert_assignments")
    op.drop_table("incident_comments")
    op.drop_table("incidents")
