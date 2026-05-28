"""Phase 2 - Real Wazuh Integration: Add event, suppression, and risk models

Revision ID: 002_wazuh_integration
Revises: 001
Create Date: 2024-05-23 12:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "002_wazuh_integration"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add Phase 2 Wazuh integration tables."""
    
    # Create wazuh_events table
    op.create_table(
        "wazuh_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", sa.String(50), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("agent_id", sa.String(10), nullable=False),
        sa.Column("agent_name", sa.String(255), nullable=False),
        sa.Column("manager", sa.String(255), nullable=False),
        sa.Column("source_ip", sa.String(45), nullable=True),
        sa.Column("source_port", sa.Integer(), nullable=True),
        sa.Column("source_user", sa.String(255), nullable=True),
        sa.Column("dest_ip", sa.String(45), nullable=True),
        sa.Column("dest_port", sa.Integer(), nullable=True),
        sa.Column("dest_user", sa.String(255), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("rule_id", sa.String(10), nullable=False),
        sa.Column("rule_description", sa.Text(), nullable=False),
        sa.Column("rule_group", sa.String(100), nullable=False),
        sa.Column("rule_level", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("source_country", sa.String(2), nullable=True),
        sa.Column("source_city", sa.String(100), nullable=True),
        sa.Column("dest_country", sa.String(2), nullable=True),
        sa.Column("risk_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("is_suppressed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("wazuh_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_wazuh_events_event_id"),
    )
    
    # Create indexes for wazuh_events
    op.create_index("idx_event_timestamp", "wazuh_events", ["event_timestamp"], postgresql_using="brin")
    op.create_index("idx_event_agent_id", "wazuh_events", ["agent_id"])
    op.create_index("idx_event_severity", "wazuh_events", ["severity"])
    op.create_index("idx_event_suppressed", "wazuh_events", ["is_suppressed"])
    op.create_index("idx_event_rule_id", "wazuh_events", ["rule_id"])
    op.create_index("idx_event_source_ip", "wazuh_events", ["source_ip"])
    op.create_index("idx_event_dest_ip", "wazuh_events", ["dest_ip"])
    op.create_index("idx_event_created", "wazuh_events", ["created_at"])

    # Create alert_suppressions table
    op.create_table(
        "alert_suppressions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("suppression_type", sa.String(50), nullable=False),
        sa.Column("group_key", sa.String(255), nullable=False),
        sa.Column("agent_id", sa.String(10), nullable=False),
        sa.Column("rule_id", sa.String(10), nullable=False),
        sa.Column("source_ip", sa.String(45), nullable=True),
        sa.Column("dest_ip", sa.String(45), nullable=True),
        sa.Column("suppression_starts_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("suppression_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("alert_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("display_alert_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["wazuh_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["acknowledged_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Create indexes for alert_suppressions
    op.create_index("idx_suppression_agent_rule", "alert_suppressions", ["agent_id", "rule_id"])
    op.create_index("idx_suppression_expires", "alert_suppressions", ["suppression_expires_at"])
    op.create_index("idx_suppression_status", "alert_suppressions", ["status"])

    # Create event_risks table
    op.create_table(
        "event_risks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", sa.String(10), nullable=False),
        sa.Column("source_ip", sa.String(45), nullable=True),
        sa.Column("source_user", sa.String(255), nullable=True),
        sa.Column("base_risk_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("severity_factor", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("frequency_factor", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("recency_factor", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("event_risk_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("endpoint_risk_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("user_risk_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("is_critical", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_anomalous", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["wazuh_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_event_risks_event_id"),
    )
    
    # Create indexes for event_risks
    op.create_index("idx_risk_agent_id", "event_risks", ["agent_id"])
    op.create_index("idx_risk_endpoint_risk", "event_risks", ["endpoint_risk_score"])
    op.create_index("idx_risk_user_risk", "event_risks", ["user_risk_score"])

    # Create endpoint_inventory table
    op.create_table(
        "endpoint_inventory",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", sa.String(10), nullable=False),
        sa.Column("agent_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), server_default="unknown", nullable=False),
        sa.Column("last_keepalive", sa.DateTime(timezone=True), nullable=True),
        sa.Column("os_platform", sa.String(50), nullable=True),
        sa.Column("os_name", sa.String(255), nullable=True),
        sa.Column("os_version", sa.String(50), nullable=True),
        sa.Column("hostname", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("wazuh_agent_version", sa.String(20), nullable=True),
        sa.Column("node_name", sa.String(255), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("current_risk_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("critical_alert_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", name="uq_endpoint_agent_id"),
    )
    
    # Create indexes for endpoint_inventory
    op.create_index("idx_endpoint_status", "endpoint_inventory", ["status"])
    op.create_index("idx_endpoint_last_seen", "endpoint_inventory", ["last_keepalive"])


def downgrade() -> None:
    """Downgrade Phase 2 tables."""
    op.drop_table("endpoint_inventory")
    op.drop_table("event_risks")
    op.drop_table("alert_suppressions")
    op.drop_table("wazuh_events")
