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
    # assets — missing columns not in 001                                #
    # ------------------------------------------------------------------ #
    with op.batch_alter_table("assets") as batch_op:
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

    # Index on new columns used by queries
    op.create_index(
        "idx_event_source_user",
        "wazuh_events",
        ["source_user"],
        postgresql_where=sa.text("source_user IS NOT NULL"),
    )
    op.create_index("idx_event_category", "wazuh_events", ["category"])

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

    # wazuh_events
    op.drop_index("idx_event_category", table_name="wazuh_events")
    op.drop_index("idx_event_source_user", table_name="wazuh_events")

    # assets
    for col in ["deleted_at", "updated_at", "last_seen", "source", "asset_type",
                "domain", "fqdn", "mac_address"]:
        with op.batch_alter_table("assets") as batch_op:
            batch_op.drop_column(col)
