"""Fill all missing columns to match current models.

Revision ID: 005_fill_missing_columns
Revises: 004_performance_indexes
Create Date: 2026-05-27

Adds every column that exists in the SQLAlchemy models but is absent from
the database (detected by check_db.py).  All new columns are nullable /
have server-side defaults so existing rows are not broken.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005_fill_missing_columns"
down_revision = "004_performance_indexes"  # noqa: E501
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ------------------------------------------------------------------ #
    # assets — 12 missing columns                                         #
    # ------------------------------------------------------------------ #
    with op.batch_alter_table("assets") as batch_op:
        batch_op.add_column(sa.Column("os_version",  sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("owner",       sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("location",    sa.String(100), nullable=True))
        batch_op.add_column(sa.Column(
            "status",
            sa.String(20),
            server_default="active",
            nullable=False,
        ))
        batch_op.add_column(sa.Column("mac_address", sa.String(32),  nullable=True))
        batch_op.add_column(sa.Column("fqdn",        sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("domain",      sa.String(255), nullable=True))
        batch_op.add_column(sa.Column(
            "asset_type",
            sa.String(30),
            server_default="server",
            nullable=False,
        ))
        batch_op.add_column(sa.Column("source",      sa.String(50),  nullable=True))
        batch_op.add_column(sa.Column("last_seen",   sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ))
        batch_op.add_column(sa.Column("deleted_at",  sa.DateTime(timezone=True), nullable=True))

    # ------------------------------------------------------------------ #
    # wazuh_events — 12 missing columns                                   #
    # ------------------------------------------------------------------ #
    with op.batch_alter_table("wazuh_events") as batch_op:
        batch_op.add_column(sa.Column(
            "manager",
            sa.String(255),
            server_default="unknown",
            nullable=False,
        ))
        batch_op.add_column(sa.Column("source_port",    sa.Integer(),    nullable=True))
        batch_op.add_column(sa.Column("source_user",    sa.String(255),  nullable=True))
        batch_op.add_column(sa.Column("dest_port",      sa.Integer(),    nullable=True))
        batch_op.add_column(sa.Column("dest_user",      sa.String(255),  nullable=True))
        batch_op.add_column(sa.Column(
            "rule_group",
            sa.String(100),
            server_default="",
            nullable=False,
        ))
        batch_op.add_column(sa.Column(
            "rule_level",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ))
        batch_op.add_column(sa.Column(
            "message",
            sa.Text(),
            server_default="",
            nullable=False,
        ))
        batch_op.add_column(sa.Column(
            "category",
            sa.String(50),
            server_default="system",
            nullable=False,
        ))
        batch_op.add_column(sa.Column("source_country", sa.String(2),   nullable=True))
        batch_op.add_column(sa.Column("source_city",    sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("dest_country",   sa.String(2),   nullable=True))

    # Index on new columns used by queries
    op.create_index(
        "idx_event_source_user",
        "wazuh_events",
        ["source_user"],
        postgresql_where=sa.text("source_user IS NOT NULL"),
    )
    op.create_index("idx_event_category", "wazuh_events", ["category"])

    # ------------------------------------------------------------------ #
    # alert_suppressions — 9 missing columns                              #
    # ------------------------------------------------------------------ #
    with op.batch_alter_table("alert_suppressions") as batch_op:
        batch_op.add_column(sa.Column(
            "rule_id",
            sa.String(10),
            server_default="",
            nullable=False,
        ))
        batch_op.add_column(sa.Column("source_ip",           sa.String(45),  nullable=True))
        batch_op.add_column(sa.Column("dest_ip",             sa.String(45),  nullable=True))
        batch_op.add_column(sa.Column(
            "suppression_starts_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ))
        batch_op.add_column(sa.Column(
            "alert_count",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ))
        batch_op.add_column(sa.Column(
            "display_alert_count",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ))
        batch_op.add_column(sa.Column("acknowledged_at",     sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column(
            "acknowledged_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ))
        batch_op.add_column(sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ))

    # ------------------------------------------------------------------ #
    # event_risks — 7 missing columns                                     #
    # ------------------------------------------------------------------ #
    with op.batch_alter_table("event_risks") as batch_op:
        batch_op.add_column(sa.Column(
            "agent_id",
            sa.String(10),
            server_default="000",
            nullable=False,
        ))
        batch_op.add_column(sa.Column("source_ip",       sa.String(45),  nullable=True))
        batch_op.add_column(sa.Column("source_user",     sa.String(255), nullable=True))
        batch_op.add_column(sa.Column(
            "recency_factor",
            sa.Float(),
            server_default="1.0",
            nullable=False,
        ))
        batch_op.add_column(sa.Column(
            "user_risk_score",
            sa.Float(),
            server_default="0.0",
            nullable=False,
        ))
        batch_op.add_column(sa.Column(
            "is_anomalous",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ))
        batch_op.add_column(sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ))

    # ------------------------------------------------------------------ #
    # endpoint_inventory — 6 missing columns                              #
    # ------------------------------------------------------------------ #
    with op.batch_alter_table("endpoint_inventory") as batch_op:
        batch_op.add_column(sa.Column("last_keepalive",       sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("os_name",              sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("os_version",           sa.String(50),  nullable=True))
        batch_op.add_column(sa.Column("wazuh_agent_version",  sa.String(20),  nullable=True))
        batch_op.add_column(sa.Column("node_name",            sa.String(255), nullable=True))
        batch_op.add_column(sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ))

    # ------------------------------------------------------------------ #
    # incidents — 11 missing columns                                      #
    # ------------------------------------------------------------------ #
    with op.batch_alter_table("incidents") as batch_op:
        batch_op.add_column(sa.Column(
            "correlation_type",
            sa.String(50),
            server_default="manual",
            nullable=False,
        ))
        batch_op.add_column(sa.Column("source_ip",          sa.String(45), nullable=True))
        batch_op.add_column(sa.Column("rule_id",            sa.String(10), nullable=True))
        batch_op.add_column(sa.Column("category",           sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("mitre_tactic",       sa.String(80), nullable=True))
        batch_op.add_column(sa.Column("mitre_technique",    sa.String(80), nullable=True))
        batch_op.add_column(sa.Column(
            "alert_count",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ))
        batch_op.add_column(sa.Column("acknowledged_at",    sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column(
            "acknowledged_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ))
        batch_op.add_column(sa.Column("resolved_at",        sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ))

    # ------------------------------------------------------------------ #
    # incident_timeline — 1 missing column                                #
    # ------------------------------------------------------------------ #
    with op.batch_alter_table("incident_timeline") as batch_op:
        batch_op.add_column(sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ))

    # ------------------------------------------------------------------ #
    # Indexes that depend on columns added above                          #
    # ------------------------------------------------------------------ #
    op.create_index(
        'ix_wazuh_events_category_timestamp',
        'wazuh_events',
        ['category', 'event_timestamp'],
        postgresql_using='btree',
    )
    op.create_index(
        'ix_incidents_status_updated',
        'incidents',
        ['status', 'updated_at'],
        postgresql_using='btree',
    )

    # ------------------------------------------------------------------ #
    # Seed required roles if not present                                  #
    # ------------------------------------------------------------------ #
    op.execute("""
        INSERT INTO roles (id, name, description, created_at)
        VALUES
            (gen_random_uuid(), 'Super Admin',  'Full system access',              now()),
            (gen_random_uuid(), 'SOC Analyst',  'Alert triage and investigation',  now()),
            (gen_random_uuid(), 'IT Admin',     'Infrastructure management',       now()),
            (gen_random_uuid(), 'Manager',      'Read-only executive view',        now()),
            (gen_random_uuid(), 'Auditor',      'Audit log access',                now())
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade() -> None:
    # new indexes
    op.drop_index('ix_incidents_status_updated',        table_name='incidents')
    op.drop_index('ix_wazuh_events_category_timestamp', table_name='wazuh_events')

    # incident_timeline
    with op.batch_alter_table("incident_timeline") as batch_op:
        batch_op.drop_column("details")

    # incidents
    for col in [
        "metadata_json", "resolved_at", "acknowledged_by_id", "acknowledged_at",
        "alert_count", "mitre_technique", "mitre_tactic", "category",
        "rule_id", "source_ip", "correlation_type",
    ]:
        with op.batch_alter_table("incidents") as batch_op:
            batch_op.drop_column(col)

    # endpoint_inventory
    for col in ["metadata", "node_name", "wazuh_agent_version", "os_version", "os_name", "last_keepalive"]:
        with op.batch_alter_table("endpoint_inventory") as batch_op:
            batch_op.drop_column(col)

    # event_risks
    for col in ["updated_at", "is_anomalous", "user_risk_score", "recency_factor", "source_user", "source_ip", "agent_id"]:
        with op.batch_alter_table("event_risks") as batch_op:
            batch_op.drop_column(col)

    # alert_suppressions
    for col in ["updated_at", "acknowledged_by_id", "acknowledged_at", "display_alert_count",
                "alert_count", "suppression_starts_at", "dest_ip", "source_ip", "rule_id"]:
        with op.batch_alter_table("alert_suppressions") as batch_op:
            batch_op.drop_column(col)

    # wazuh_events
    op.drop_index("idx_event_category", table_name="wazuh_events")
    op.drop_index("idx_event_source_user", table_name="wazuh_events")
    for col in ["dest_country", "source_city", "source_country", "category", "message",
                "rule_level", "rule_group", "dest_user", "dest_port", "source_user",
                "source_port", "manager"]:
        with op.batch_alter_table("wazuh_events") as batch_op:
            batch_op.drop_column(col)

    # assets
    for col in ["deleted_at", "updated_at", "last_seen", "source", "asset_type",
                "domain", "fqdn", "mac_address", "status", "location", "owner", "os_version"]:
        with op.batch_alter_table("assets") as batch_op:
            batch_op.drop_column(col)
