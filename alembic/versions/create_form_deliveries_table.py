"""create form_deliveries table

Revision ID: create_form_deliveries_001
Revises: add_age_group_001
Create Date: 2026-02-26 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'create_form_deliveries_001'
down_revision = 'add_age_group_001'
branch_labels = None
depends_on = None


def upgrade():
    # Create form_deliveries table
    op.create_table(
        'form_deliveries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        
        # Delivery details
        sa.Column('delivery_method', sa.String(length=20), nullable=False),
        sa.Column('download_link', sa.Text(), nullable=False),
        sa.Column('link_expiration', sa.DateTime(timezone=True), nullable=False),
        
        # Tracking
        sa.Column('delivered_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('accessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('download_count', sa.Integer(), server_default='0', nullable=False),
        
        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        
        # Foreign keys
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['uploaded_documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        
        # Check constraint
        sa.CheckConstraint(
            "delivery_method IN ('initial', 're-request')",
            name='ck_delivery_method'
        )
    )
    
    # Create indexes
    op.create_index('idx_form_deliveries_user_conv', 'form_deliveries', ['user_id', 'conversation_id'])
    op.create_index('idx_form_deliveries_document', 'form_deliveries', ['document_id'])
    op.create_index('idx_form_deliveries_org', 'form_deliveries', ['organization_id'])
    op.create_index('idx_form_deliveries_delivered_at', 'form_deliveries', ['delivered_at'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_form_deliveries_delivered_at', table_name='form_deliveries')
    op.drop_index('idx_form_deliveries_org', table_name='form_deliveries')
    op.drop_index('idx_form_deliveries_document', table_name='form_deliveries')
    op.drop_index('idx_form_deliveries_user_conv', table_name='form_deliveries')
    
    # Drop table
    op.drop_table('form_deliveries')
