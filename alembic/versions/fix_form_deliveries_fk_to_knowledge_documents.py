"""fix form_deliveries foreign key to knowledge_documents

Revision ID: fix_form_deliveries_fk_001
Revises: make_form_delivery_user_id_nullable_001
Create Date: 2026-02-28 10:00:00.000000

BUGFIX: Change form_deliveries.document_id foreign key from uploaded_documents to knowledge_documents
Root Cause: Forms are stored in knowledge_documents table, not uploaded_documents table
Impact: Allows form delivery records to be saved without foreign key constraint violations
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_form_deliveries_fk_001'
down_revision = 'make_form_delivery_user_id_nullable_001'
branch_labels = None
depends_on = None


def upgrade():
    """
    Change form_deliveries.document_id foreign key to reference knowledge_documents instead of uploaded_documents.
    
    Steps:
    1. Drop existing foreign key constraint
    2. Create new foreign key constraint referencing knowledge_documents
    """
    # Drop existing foreign key constraint
    op.drop_constraint(
        'form_deliveries_document_id_fkey',
        'form_deliveries',
        type_='foreignkey'
    )
    
    # Create new foreign key constraint referencing knowledge_documents
    op.create_foreign_key(
        'form_deliveries_document_id_fkey',
        'form_deliveries',
        'knowledge_documents',
        ['document_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    """
    Revert back to uploaded_documents foreign key (for rollback).
    
    WARNING: This may fail if there are existing records referencing knowledge_documents.
    """
    # Drop knowledge_documents foreign key
    op.drop_constraint(
        'form_deliveries_document_id_fkey',
        'form_deliveries',
        type_='foreignkey'
    )
    
    # Restore uploaded_documents foreign key
    op.create_foreign_key(
        'form_deliveries_document_id_fkey',
        'form_deliveries',
        'uploaded_documents',
        ['document_id'],
        ['id'],
        ondelete='CASCADE'
    )

