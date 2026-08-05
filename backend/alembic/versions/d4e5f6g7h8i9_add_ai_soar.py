"""add ai_soar columns and chat sessions

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-08-05 10:00:00.000000

Adds:
- soar_runs.ai_analysis (JSONB)      — LLM analysis result for the run
- soar_runs.ai_confidence (Float)    — overall AI confidence score
- soar_runs.ai_threat_class (String) — AI threat classification label
- ai_chat_sessions table             — stores Conversational SOC chat history
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd4e5f6g7h8i9'
down_revision = 'c3d4e5f6g7h8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── soar_runs — add AI analysis columns ────────────────────────────────
    op.add_column(
        'soar_runs',
        sa.Column(
            'ai_analysis',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                'JSON result of LLM analysis: summary, threat_classification, '
                'recommended_actions, mitre_techniques, iocs, etc.'
            ),
        ),
    )
    op.add_column(
        'soar_runs',
        sa.Column(
            'ai_confidence',
            sa.Float(),
            nullable=True,
            comment='LLM confidence score (0.0–1.0) for the threat classification.',
        ),
    )
    op.add_column(
        'soar_runs',
        sa.Column(
            'ai_threat_class',
            sa.String(50),
            nullable=True,
            comment='AI threat classification: CRITICAL, HIGH, MEDIUM, LOW, FALSE_POSITIVE.',
        ),
    )

    # ── ai_chat_sessions — Conversational SOC ──────────────────────────────
    op.create_table(
        'ai_chat_sessions',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'title',
            sa.String(255),
            nullable=True,
            comment='Auto-generated session title from first message.',
        ),
        sa.Column(
            'messages',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='[]',
            comment=(
                'List of chat messages: '
                '[{"role": "user"|"assistant", "content": "...", "timestamp": "ISO8601"}]'
            ),
        ),
        sa.Column(
            'context',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='Optional linked context: {alert_id, incident_id, run_id}.',
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Index for fast user session lookup
    op.create_index(
        'idx_ai_chat_sessions_user_id',
        'ai_chat_sessions',
        ['user_id'],
    )
    op.create_index(
        'idx_ai_chat_sessions_updated_at',
        'ai_chat_sessions',
        ['updated_at'],
    )

    # Index for fast AI threat class filtering in soar_runs
    op.create_index(
        'idx_soar_runs_ai_threat_class',
        'soar_runs',
        ['ai_threat_class'],
    )


def downgrade() -> None:
    op.drop_index('idx_soar_runs_ai_threat_class', table_name='soar_runs')
    op.drop_index('idx_ai_chat_sessions_updated_at', table_name='ai_chat_sessions')
    op.drop_index('idx_ai_chat_sessions_user_id', table_name='ai_chat_sessions')
    op.drop_table('ai_chat_sessions')
    op.drop_column('soar_runs', 'ai_threat_class')
    op.drop_column('soar_runs', 'ai_confidence')
    op.drop_column('soar_runs', 'ai_analysis')
