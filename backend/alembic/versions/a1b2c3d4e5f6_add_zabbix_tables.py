"""Add Zabbix tables: zabbix_hosts, zabbix_problems, zabbix_events, zabbix_triggers, zabbix_metrics

Revision ID: a1b2c3d4e5f6
Revises: (set to your latest revision)
Create Date: 2026-06-16

This migration creates 5 new tables for Zabbix integration.
Wazuh tables are NOT modified.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '005_fill_missing_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # zabbix_hosts
    # =========================================================================
    op.create_table(
        'zabbix_hosts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('host_id', sa.String(50), nullable=False, unique=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='Monitored'),
        sa.Column('available_code', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('available_label', sa.String(30), nullable=False, server_default='Unknown'),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('groups', ARRAY(sa.String()), nullable=True),
        sa.Column('error_msg', sa.Text(), nullable=True),
        sa.Column('last_synced', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
    )
    op.create_index('idx_zabbix_host_id', 'zabbix_hosts', ['host_id'], unique=True)
    op.create_index('idx_zabbix_host_available', 'zabbix_hosts', ['available_code'])
    op.create_index('idx_zabbix_host_synced', 'zabbix_hosts', ['last_synced'])

    # =========================================================================
    # zabbix_problems
    # =========================================================================
    op.create_table(
        'zabbix_problems',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('event_id', sa.String(50), nullable=False, unique=True),
        sa.Column('object_id', sa.String(50), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('severity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('severity_label', sa.String(30), nullable=False, server_default='Not classified'),
        sa.Column('acknowledged', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('suppressed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('clock', sa.DateTime(timezone=True), nullable=True),
        sa.Column('host_name', sa.String(255), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_zabbix_problem_event_id', 'zabbix_problems', ['event_id'], unique=True)
    op.create_index('idx_zabbix_problem_severity', 'zabbix_problems', ['severity'])
    op.create_index('idx_zabbix_problem_clock', 'zabbix_problems', ['clock'])
    op.create_index('idx_zabbix_problem_synced', 'zabbix_problems', ['synced_at'])

    # =========================================================================
    # zabbix_events
    # =========================================================================
    op.create_table(
        'zabbix_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('event_id', sa.String(50), nullable=False, unique=True),
        sa.Column('object_id', sa.String(50), nullable=False),
        sa.Column('name', sa.Text(), nullable=False, server_default=''),
        sa.Column('severity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('severity_label', sa.String(30), nullable=False, server_default='Not classified'),
        sa.Column('value', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('acknowledged', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('clock', sa.DateTime(timezone=True), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_zabbix_event_id', 'zabbix_events', ['event_id'], unique=True)
    op.create_index('idx_zabbix_event_clock', 'zabbix_events', ['clock'],
                    postgresql_using='brin')
    op.create_index('idx_zabbix_event_severity', 'zabbix_events', ['severity'])

    # =========================================================================
    # zabbix_triggers
    # =========================================================================
    op.create_table(
        'zabbix_triggers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('trigger_id', sa.String(50), nullable=False, unique=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('priority_label', sa.String(30), nullable=False, server_default='Not classified'),
        sa.Column('status', sa.String(20), nullable=False, server_default='Enabled'),
        sa.Column('value', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('host_id', sa.String(50), nullable=False),
        sa.Column('host_name', sa.String(255), nullable=False, server_default=''),
        sa.Column('last_change', sa.DateTime(timezone=True), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_zabbix_trigger_id', 'zabbix_triggers', ['trigger_id'], unique=True)
    op.create_index('idx_zabbix_trigger_priority', 'zabbix_triggers', ['priority'])
    op.create_index('idx_zabbix_trigger_value', 'zabbix_triggers', ['value'])
    op.create_index('idx_zabbix_trigger_synced', 'zabbix_triggers', ['synced_at'])

    # =========================================================================
    # zabbix_metrics
    # =========================================================================
    op.create_table(
        'zabbix_metrics',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('host_id', sa.String(50), nullable=False),
        sa.Column('host_name', sa.String(255), nullable=False, server_default=''),
        sa.Column('item_id', sa.String(50), nullable=False),
        sa.Column('item_key', sa.String(255), nullable=False),
        sa.Column('item_name', sa.String(255), nullable=False, server_default=''),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('units', sa.String(50), nullable=False, server_default=''),
        sa.Column('clock', sa.DateTime(timezone=True), nullable=False),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_zabbix_metric_host_key', 'zabbix_metrics', ['host_id', 'item_key'])
    op.create_index('idx_zabbix_metric_clock', 'zabbix_metrics', ['clock'],
                    postgresql_using='brin')


def downgrade() -> None:
    # Drop in reverse order (no FK constraints across Wazuh tables)
    op.drop_table('zabbix_metrics')
    op.drop_table('zabbix_triggers')
    op.drop_table('zabbix_events')
    op.drop_table('zabbix_problems')
    op.drop_table('zabbix_hosts')
