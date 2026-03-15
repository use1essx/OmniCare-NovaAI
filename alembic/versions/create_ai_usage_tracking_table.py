"""create ai_usage_tracking table

Revision ID: create_ai_usage_tracking
Revises: make_form_delivery_user_id_nullable
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'create_ai_usage_tracking'
down_revision = 'make_form_delivery_user_id_nullable'
branch_labels = None
depends_on = None


def upgrade():
    """Create ai_usage_tracking table for budget monitoring"""
    op.create_table(
        'ai_usage_tracking',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('model_tier', sa.String(length=10), nullable=False),
        sa.Column('model_id', sa.String(length=100), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False),
        sa.Column('output_tokens', sa.Integer(), nullable=False),
        sa.Column('cost_usd', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('cumulative_cost_usd', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.String(length=100), nullable=True),
        sa.Column('task_type', sa.String(length=50), nullable=True),
        sa.Column('request_id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_id')
    )
    
    # Create indexes for performance
    op.create_index('idx_ai_usage_timestamp', 'ai_usage_tracking', ['timestamp'])
    op.create_index('idx_ai_usage_cumulative', 'ai_usage_tracking', ['cumulative_cost_usd'])
    op.create_index('idx_ai_usage_user', 'ai_usage_tracking', ['user_id'])
    op.create_index('idx_ai_usage_session', 'ai_usage_tracking', ['session_id'])


def downgrade():
    """Drop ai_usage_tracking table"""
    op.drop_index('idx_ai_usage_session', table_name='ai_usage_tracking')
    op.drop_index('idx_ai_usage_user', table_name='ai_usage_tracking')
    op.drop_index('idx_ai_usage_cumulative', table_name='ai_usage_tracking')
    op.drop_index('idx_ai_usage_timestamp', table_name='ai_usage_tracking')
    op.drop_table('ai_usage_tracking')
