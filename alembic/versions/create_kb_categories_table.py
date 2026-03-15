"""create kb_categories table

Revision ID: create_kb_categories
Revises: make_form_delivery_user_id_nullable
Create Date: 2026-03-11 05:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'create_kb_categories'
down_revision = 'make_form_delivery_user_id_nullable'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create kb_categories table
    op.create_table(
        'kb_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name_en', sa.String(length=255), nullable=False),
        sa.Column('name_zh', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('description_en', sa.Text(), nullable=True),
        sa.Column('description_zh', sa.Text(), nullable=True),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['parent_id'], ['kb_categories.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('slug', 'level', name='uq_kb_categories_slug_level')
    )
    
    # Create indexes for kb_categories
    op.create_index('ix_kb_categories_slug', 'kb_categories', ['slug'])
    op.create_index('ix_kb_categories_level', 'kb_categories', ['level'])
    op.create_index('ix_kb_categories_parent_id', 'kb_categories', ['parent_id'])
    
    # Create document_category_tags table
    op.create_table(
        'document_category_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['uploaded_documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['kb_categories.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('document_id', 'category_id', name='uq_document_category_tags')
    )
    
    # Create indexes for document_category_tags
    op.create_index('ix_document_category_tags_document_id', 'document_category_tags', ['document_id'])
    op.create_index('ix_document_category_tags_category_id', 'document_category_tags', ['category_id'])


def downgrade() -> None:
    # Drop document_category_tags table
    op.drop_index('ix_document_category_tags_category_id', table_name='document_category_tags')
    op.drop_index('ix_document_category_tags_document_id', table_name='document_category_tags')
    op.drop_table('document_category_tags')
    
    # Drop kb_categories indexes
    op.drop_index('ix_kb_categories_parent_id', table_name='kb_categories')
    op.drop_index('ix_kb_categories_level', table_name='kb_categories')
    op.drop_index('ix_kb_categories_slug', table_name='kb_categories')
    
    # Drop kb_categories table
    op.drop_table('kb_categories')
