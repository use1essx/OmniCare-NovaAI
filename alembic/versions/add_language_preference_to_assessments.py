"""Add language_preference to assessments

Revision ID: add_lang_pref_001
Revises: 
Create Date: 2026-02-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_lang_pref_001'
down_revision = None  # Update this to the latest revision ID
branch_labels = None
depends_on = None


def upgrade():
    """Add language_preference column to assessments table"""
    # Add column with default value 'en'
    op.add_column('assessments', 
        sa.Column('language_preference', sa.String(length=10), nullable=False, server_default='en')
    )
    
    # Remove server_default after adding (best practice)
    op.alter_column('assessments', 'language_preference', server_default=None)


def downgrade():
    """Remove language_preference column from assessments table"""
    op.drop_column('assessments', 'language_preference')
