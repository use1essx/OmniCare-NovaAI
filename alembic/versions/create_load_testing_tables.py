"""create load testing tables

Revision ID: create_load_testing_001
Revises: fix_form_deliveries_fk_001
Create Date: 2026-02-28 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'create_load_testing_001'
down_revision = 'fix_form_deliveries_fk_001'
branch_labels = None
depends_on = None


def upgrade():
    # Create load_test_runs table
    op.create_table(
        'load_test_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('test_name', sa.String(length=255), nullable=False),
        sa.Column('environment', sa.String(length=50), nullable=False),
        
        # Configuration
        sa.Column('concurrent_users', sa.Integer(), nullable=False),
        sa.Column('messages_per_user', sa.Integer(), nullable=False),
        sa.Column('scenario_categories', postgresql.ARRAY(sa.Text()), nullable=False),
        
        # Execution
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        
        # Results summary
        sa.Column('total_messages', sa.Integer(), server_default='0', nullable=False),
        sa.Column('successful_messages', sa.Integer(), server_default='0', nullable=False),
        sa.Column('failed_messages', sa.Integer(), server_default='0', nullable=False),
        sa.Column('avg_response_time_ms', sa.Integer(), nullable=True),
        
        # Metadata
        sa.Column('config_json', postgresql.JSONB(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        
        # Foreign keys
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        
        # Check constraint
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled')",
            name='ck_load_test_runs_status'
        )
    )
    
    # Create indexes for load_test_runs
    op.create_index('idx_load_test_runs_started_at', 'load_test_runs', ['started_at'])
    op.create_index('idx_load_test_runs_status', 'load_test_runs', ['status'])
    
    # Create load_test_users table
    op.create_table(
        'load_test_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('test_run_id', sa.Integer(), nullable=False),
        sa.Column('user_index', sa.Integer(), nullable=False),
        
        # User configuration
        sa.Column('scenario_category', sa.String(length=100), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        
        # Connection
        sa.Column('session_id', sa.String(length=255), nullable=False),
        sa.Column('connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('disconnected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('connection_duration_seconds', sa.Integer(), nullable=True),
        
        # Execution
        sa.Column('messages_sent', sa.Integer(), server_default='0', nullable=False),
        sa.Column('messages_received', sa.Integer(), server_default='0', nullable=False),
        sa.Column('errors_encountered', sa.Integer(), server_default='0', nullable=False),
        
        # Status
        sa.Column('status', sa.String(length=50), nullable=False),
        
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        
        # Foreign keys
        sa.ForeignKeyConstraint(['test_run_id'], ['load_test_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        
        # Check constraint
        sa.CheckConstraint(
            "status IN ('connecting', 'active', 'completed', 'failed')",
            name='ck_load_test_users_status'
        )
    )
    
    # Create indexes for load_test_users
    op.create_index('idx_load_test_users_test_run', 'load_test_users', ['test_run_id'])
    op.create_index('idx_load_test_users_status', 'load_test_users', ['status'])
    
    # Create load_test_messages table
    op.create_table(
        'load_test_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('test_run_id', sa.Integer(), nullable=False),
        sa.Column('test_user_id', sa.Integer(), nullable=False),
        
        # Message content
        sa.Column('message_index', sa.Integer(), nullable=False),
        sa.Column('user_message', sa.Text(), nullable=False),
        sa.Column('agent_response', sa.Text(), nullable=True),
        
        # Agent information
        sa.Column('agent_name', sa.String(length=100), nullable=True),
        sa.Column('agent_type', sa.String(length=50), nullable=True),
        
        # Timing
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        
        # RAG information
        sa.Column('rag_documents', postgresql.JSONB(), nullable=True),
        sa.Column('rag_query_time_ms', sa.Integer(), nullable=True),
        
        # Document downloads
        sa.Column('download_links', postgresql.JSONB(), nullable=True),
        
        # Safety validation
        sa.Column('safety_triggered', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('risk_level', sa.String(length=20), nullable=True),
        sa.Column('risk_assessment', postgresql.JSONB(), nullable=True),
        
        # Error handling
        sa.Column('is_error', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('is_fallback', sa.Boolean(), server_default='false', nullable=False),
        
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        
        # Foreign keys
        sa.ForeignKeyConstraint(['test_run_id'], ['load_test_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['test_user_id'], ['load_test_users.id'], ondelete='CASCADE')
    )
    
    # Create indexes for load_test_messages
    op.create_index('idx_load_test_messages_test_run', 'load_test_messages', ['test_run_id'])
    op.create_index('idx_load_test_messages_user', 'load_test_messages', ['test_user_id'])
    op.create_index('idx_load_test_messages_sent_at', 'load_test_messages', ['sent_at'])
    
    # Create load_test_quality_issues table
    op.create_table(
        'load_test_quality_issues',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('test_run_id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        
        # Issue classification
        sa.Column('issue_type', sa.String(length=100), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        
        # Issue details
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('example_text', sa.Text(), nullable=True),
        
        # Quality scores
        sa.Column('clarity_score', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('completeness_score', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('appropriateness_score', sa.Numeric(precision=3, scale=2), nullable=True),
        
        # Recommendations
        sa.Column('recommendation', sa.Text(), nullable=True),
        
        # Metadata
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        
        # Foreign keys
        sa.ForeignKeyConstraint(['test_run_id'], ['load_test_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['load_test_messages.id'], ondelete='CASCADE'),
        
        # Check constraint
        sa.CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low')",
            name='ck_load_test_quality_issues_severity'
        )
    )
    
    # Create indexes for load_test_quality_issues
    op.create_index('idx_load_test_quality_issues_test_run', 'load_test_quality_issues', ['test_run_id'])
    op.create_index('idx_load_test_quality_issues_severity', 'load_test_quality_issues', ['severity'])


def downgrade():
    # Drop indexes for load_test_quality_issues
    op.drop_index('idx_load_test_quality_issues_severity', table_name='load_test_quality_issues')
    op.drop_index('idx_load_test_quality_issues_test_run', table_name='load_test_quality_issues')
    
    # Drop load_test_quality_issues table
    op.drop_table('load_test_quality_issues')
    
    # Drop indexes for load_test_messages
    op.drop_index('idx_load_test_messages_sent_at', table_name='load_test_messages')
    op.drop_index('idx_load_test_messages_user', table_name='load_test_messages')
    op.drop_index('idx_load_test_messages_test_run', table_name='load_test_messages')
    
    # Drop load_test_messages table
    op.drop_table('load_test_messages')
    
    # Drop indexes for load_test_users
    op.drop_index('idx_load_test_users_status', table_name='load_test_users')
    op.drop_index('idx_load_test_users_test_run', table_name='load_test_users')
    
    # Drop load_test_users table
    op.drop_table('load_test_users')
    
    # Drop indexes for load_test_runs
    op.drop_index('idx_load_test_runs_status', table_name='load_test_runs')
    op.drop_index('idx_load_test_runs_started_at', table_name='load_test_runs')
    
    # Drop load_test_runs table
    op.drop_table('load_test_runs')
