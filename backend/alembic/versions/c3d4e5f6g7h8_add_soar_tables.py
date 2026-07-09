"""add soar tables

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-07-09 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c3d4e5f6g7h8'
down_revision = 'b2c3d4e5f6g7'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # soar_playbooks
    op.create_table('soar_playbooks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('execution_mode', sa.String(length=50), nullable=False, server_default='Auto'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # soar_rules
    op.create_table('soar_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('playbook_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('condition_logic', sa.String(length=50), nullable=False, server_default='AND'),
        sa.Column('condition_config', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['playbook_id'], ['soar_playbooks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # soar_actions
    op.create_table('soar_actions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('playbook_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('action_type', sa.String(length=100), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['playbook_id'], ['soar_playbooks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # soar_runs
    op.create_table('soar_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('playbook_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('trigger_source', sa.String(length=100), nullable=False),
        sa.Column('trigger_data', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='Running'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['playbook_id'], ['soar_playbooks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # soar_logs
    op.create_table('soar_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('step_order', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('request_payload', sa.JSON(), nullable=True),
        sa.Column('response_payload', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['soar_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # soar_approvals
    op.create_table('soar_approvals',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='Pending'),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decided_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['soar_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['decided_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('soar_approvals')
    op.drop_table('soar_logs')
    op.drop_table('soar_runs')
    op.drop_table('soar_actions')
    op.drop_table('soar_rules')
    op.drop_table('soar_playbooks')
