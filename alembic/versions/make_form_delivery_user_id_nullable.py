"""make form_delivery user_id nullable for anonymous users

Revision ID: make_user_id_nullable_001
Revises: create_form_deliveries_001
Create Date: 2026-02-26 16:00:00.000000

This migration makes the user_id column in form_deliveries table nullable
to support anonymous user form delivery. Anonymous users will use a special
guest user ID (-1) for tracking purposes.

Security Notes:
- SECURITY: Anonymous users can access public forms with guest user ID
- AUDIT: All deliveries (including anonymous) are logged for compliance
- ORGANIZATION: Organization isolation still enforced via organization_id
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'make_user_id_nullable_001'
down_revision = 'create_form_deliveries_001'
branch_labels = None
depends_on = None


def upgrade():
    """
    Make user_id nullable in form_deliveries table.
    
    This allows form delivery records for anonymous users (guest user ID = -1).
    The foreign key constraint is modified to allow NULL values.
    """
    # Drop the existing foreign key constraint
    # SECURITY: We'll recreate it with nullable=True to allow guest users
    op.drop_constraint('form_deliveries_user_id_fkey', 'form_deliveries', type_='foreignkey')
    
    # Alter the column to be nullable
    # BUGFIX: Allow NULL user_id for anonymous user form deliveries
    op.alter_column(
        'form_deliveries',
        'user_id',
        existing_type=sa.Integer(),
        nullable=True
    )
    
    # Recreate the foreign key constraint with nullable=True
    # SECURITY: Foreign key still enforces referential integrity for authenticated users
    op.create_foreign_key(
        'form_deliveries_user_id_fkey',
        'form_deliveries',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    """
    Revert user_id to non-nullable.
    
    WARNING: This will fail if there are any form_delivery records with NULL user_id.
    You must delete or update those records before downgrading.
    """
    # Drop the foreign key constraint
    op.drop_constraint('form_deliveries_user_id_fkey', 'form_deliveries', type_='foreignkey')
    
    # Alter the column back to non-nullable
    # WARNING: This will fail if there are NULL values
    op.alter_column(
        'form_deliveries',
        'user_id',
        existing_type=sa.Integer(),
        nullable=False
    )
    
    # Recreate the foreign key constraint with nullable=False
    op.create_foreign_key(
        'form_deliveries_user_id_fkey',
        'form_deliveries',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'
    )
