"""add age_group to assessments

Revision ID: add_age_group_001
Revises: add_language_preference_to_assessments
Create Date: 2026-02-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_age_group_001'
down_revision = 'add_language_preference_to_assessments'
branch_labels = None
depends_on = None


def upgrade():
    # Add age_group column to assessments table
    op.add_column('assessments', sa.Column('age_group', sa.String(length=20), nullable=True))


def downgrade():
    # Remove age_group column from assessments table
    op.drop_column('assessments', 'age_group')
