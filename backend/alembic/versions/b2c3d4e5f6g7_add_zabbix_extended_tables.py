"""Add Zabbix extended tables: assets, maintenance, tasks, notifications

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-17

This migration creates 4 new tables for the extended Zabbix integration.
Wazuh tables and existing Zabbix tables are NOT modified.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # zabbix_assets
    # =========================================================================
    op.create_table(
        'zabbix_assets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('hostname', sa.String(255), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('department', sa.String(255), nullable=True),
        sa.Column('owner', sa.String(255), nullable=True),
        sa.Column('vendor', sa.String(255), nullable=True),
        sa.Column('model', sa.String(255), nullable=True),
        sa.Column('serial_number', sa.String(255), nullable=True),
        sa.Column('purchase_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('warranty_expiration', sa.DateTime(timezone=True), nullable=True),
        sa.Column('lifecycle_status', sa.String(50), nullable=False, server_default='Active'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_zabbix_asset_hostname', 'zabbix_assets', ['hostname'])
    op.create_index('idx_zabbix_asset_lifecycle', 'zabbix_assets', ['lifecycle_status'])
    op.create_index('idx_zabbix_asset_created', 'zabbix_assets', ['created_at'])

    # =========================================================================
    # zabbix_maintenance
    # =========================================================================
    op.create_table(
        'zabbix_maintenance',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('hostname', sa.String(255), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('task_type', sa.String(100), nullable=False, server_default='General'),
        sa.Column('last_maintenance_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_maintenance_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('interval_days', sa.Integer(), nullable=False, server_default='90'),
        sa.Column('status', sa.String(50), nullable=False, server_default='Scheduled'),
        sa.Column('assigned_to', sa.String(255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_zabbix_maint_host', 'zabbix_maintenance', ['hostname'])
    op.create_index('idx_zabbix_maint_next_date', 'zabbix_maintenance', ['next_maintenance_date'])
    op.create_index('idx_zabbix_maint_status', 'zabbix_maintenance', ['status'])

    # =========================================================================
    # zabbix_tasks
    # =========================================================================
    op.create_table(
        'zabbix_tasks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('hostname', sa.String(255), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('task_type', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('priority', sa.String(20), nullable=False, server_default='Medium'),
        sa.Column('status', sa.String(50), nullable=False, server_default='Open'),
        sa.Column('source', sa.String(20), nullable=False, server_default='auto'),
        sa.Column('metric_value', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_zabbix_task_host', 'zabbix_tasks', ['hostname'])
    op.create_index('idx_zabbix_task_priority', 'zabbix_tasks', ['priority'])
    op.create_index('idx_zabbix_task_status', 'zabbix_tasks', ['status'])
    op.create_index('idx_zabbix_task_created', 'zabbix_tasks', ['created_at'])

    # =========================================================================
    # zabbix_notifications
    # =========================================================================
    op.create_table(
        'zabbix_notifications',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('notification_type', sa.String(50), nullable=False),
        sa.Column('hostname', sa.String(255), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('subject', sa.String(500), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('recipients', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(50), nullable=True),
        sa.Column('metric_value', sa.Float(), nullable=True),
        sa.Column('suggested_action', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='sent'),
        sa.Column('error_msg', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_zabbix_notif_type', 'zabbix_notifications', ['notification_type'])
    op.create_index('idx_zabbix_notif_sent_at', 'zabbix_notifications', ['sent_at'])
    op.create_index('idx_zabbix_notif_status', 'zabbix_notifications', ['status'])


def downgrade() -> None:
    # Drop in reverse order
    op.drop_table('zabbix_notifications')
    op.drop_table('zabbix_tasks')
    op.drop_table('zabbix_maintenance')
    op.drop_table('zabbix_assets')
