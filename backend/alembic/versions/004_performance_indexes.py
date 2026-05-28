"""Performance indexes for existing columns only.

Revision ID: 004_performance_indexes
Revises: 003_incidents
Create Date: 2024-01-15 10:00:00.000000

NOTE: Indexes that depend on columns added in 005_fill_missing_columns
      (category, updated_at on incidents) are created in migration 005.
"""
from alembic import op
import sqlalchemy as sa

revision = '004_performance_indexes'
down_revision = '003_incidents'
branch_labels = None
depends_on = None


def upgrade():
    # wazuh_events — columns that already exist after 002
    op.create_index(
        'ix_wazuh_events_timestamp_severity',
        'wazuh_events',
        ['event_timestamp', 'severity'],
        postgresql_using='btree'
    )
    op.create_index(
        'ix_wazuh_events_agent_timestamp',
        'wazuh_events',
        ['agent_id', 'event_timestamp'],
        postgresql_using='btree'
    )
    op.create_index(
        'ix_wazuh_events_source_ip_timestamp',
        'wazuh_events',
        ['source_ip', 'event_timestamp'],
        postgresql_where=sa.text('source_ip IS NOT NULL'),
        postgresql_using='btree'
    )
    op.create_index(
        'ix_wazuh_events_suppressed_timestamp',
        'wazuh_events',
        ['is_suppressed', 'event_timestamp'],
        postgresql_using='btree'
    )

    # incidents — columns that already exist after 003
    op.create_index(
        'ix_incidents_correlation_key_status',
        'incidents',
        ['correlation_key', 'status'],
        postgresql_using='btree'
    )

    # sessions — already exist after 001
    op.create_index(
        'ix_sessions_user_revoked',
        'sessions',
        ['user_id', 'is_revoked'],
        postgresql_using='btree'
    )

    # portal_audit_logs — already exist after 001
    op.create_index(
        'ix_portal_audit_logs_created',
        'portal_audit_logs',
        ['created_at'],
        postgresql_using='btree'
    )


def downgrade():
    op.drop_index('ix_portal_audit_logs_created',          table_name='portal_audit_logs')
    op.drop_index('ix_sessions_user_revoked',               table_name='sessions')
    op.drop_index('ix_incidents_correlation_key_status',    table_name='incidents')
    op.drop_index('ix_wazuh_events_suppressed_timestamp',   table_name='wazuh_events')
    op.drop_index('ix_wazuh_events_source_ip_timestamp',    table_name='wazuh_events')
    op.drop_index('ix_wazuh_events_agent_timestamp',        table_name='wazuh_events')
    op.drop_index('ix_wazuh_events_timestamp_severity',     table_name='wazuh_events')
