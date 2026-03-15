"""
Form Delivery Models
Tracks form document deliveries to users in conversations
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, 
    ForeignKey, CheckConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.models_comprehensive import Base, TimestampMixin


class FormDelivery(Base):
    """
    Track form document deliveries to users in conversations.
    
    This table records when forms are delivered to users, enabling:
    - Duplicate delivery prevention
    - Re-request detection
    - Delivery history tracking
    - Audit compliance
    
    Security Notes:
    - PRIVACY: No PII stored, only IDs
    - AUDIT: All deliveries logged for compliance
    - ORGANIZATION: Isolated by organization_id
    """
    
    __tablename__ = "form_deliveries"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    # SECURITY: Organization-level isolation enforced
    # BUGFIX: user_id is nullable to support anonymous users (guest user ID = -1)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    # BUGFIX: Changed from uploaded_documents to knowledge_documents (forms are stored in knowledge_documents)
    document_id = Column(Integer, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Delivery details
    delivery_method = Column(String(20), nullable=False)  # 'initial' or 're-request'
    download_link = Column(Text, nullable=False)
    link_expiration = Column(DateTime(timezone=True), nullable=False)
    
    # Tracking
    delivered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    accessed_at = Column(DateTime(timezone=True), nullable=True)
    download_count = Column(Integer, server_default="0", nullable=False)
    
    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "delivery_method IN ('initial', 're-request')",
            name='ck_delivery_method'
        ),
        # Composite index for efficient queries
        Index('idx_form_deliveries_user_conv', 'user_id', 'conversation_id'),
        Index('idx_form_deliveries_document', 'document_id'),
        Index('idx_form_deliveries_org', 'organization_id'),
        Index('idx_form_deliveries_delivered_at', 'delivered_at'),
    )
    
    # Relationships (optional - can be added if needed)
    # user = relationship("User", foreign_keys=[user_id])
    # conversation = relationship("Conversation", foreign_keys=[conversation_id])
    # document = relationship("UploadedDocument", foreign_keys=[document_id])
    # organization = relationship("Organization", foreign_keys=[organization_id])
    
    def __repr__(self):
        return (
            f"<FormDelivery(id={self.id}, user_id={self.user_id}, "
            f"document_id={self.document_id}, method='{self.delivery_method}')>"
        )
