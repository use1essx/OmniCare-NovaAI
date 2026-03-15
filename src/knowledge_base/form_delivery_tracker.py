"""
Form Delivery Tracker Service

Tracks form document deliveries to users in conversations.
Enables duplicate delivery prevention and delivery history tracking.

Security Notes:
- ORGANIZATION: All queries enforce organization-level isolation
- PRIVACY: Audit logs contain only IDs, no PII/PHI
- AUDIT: All deliveries logged for compliance
"""

import json
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select

# Import models - can be overridden in tests
try:
    from src.database.models_form_delivery import FormDelivery
    from src.database.models_comprehensive import AuditLog
except ImportError:
    # Fallback for testing
    FormDelivery = None
    AuditLog = None


class FormDeliveryTracker:
    """
    Track form document deliveries to users in conversations.
    
    This service provides:
    - Delivery recording with audit logging
    - Duplicate delivery detection
    - Delivery history queries
    - Organization-level isolation
    
    Implementation Note:
    - Uses async SQLAlchemy for compatibility with AsyncSession
    - All database operations use async/await patterns
    """
    
    def __init__(self, db: AsyncSession, form_delivery_model=None, audit_log_model=None):
        """
        Initialize the form delivery tracker.
        
        Args:
            db: SQLAlchemy async database session
            form_delivery_model: Optional FormDelivery model (for testing)
            audit_log_model: Optional AuditLog model (for testing)
        """
        self.db = db
        self.FormDelivery = form_delivery_model or FormDelivery
        self.AuditLog = audit_log_model or AuditLog
    
    async def record_delivery(
        self,
        user_id: int,
        conversation_id: int,
        document_id: int,
        delivery_method: str,
        organization_id: int,
        download_link: str,
        link_expiration: datetime
    ) -> int:
        """
        Record a form delivery event.
        
        Creates a delivery record and audit log entry for compliance.
        
        Args:
            user_id: ID of the user receiving the form (use -1 for anonymous/guest users)
            conversation_id: ID of the conversation
            document_id: ID of the form document
            delivery_method: "initial" or "re-request"
            organization_id: ID of the organization (for isolation)
            download_link: Generated download URL
            link_expiration: Expiration timestamp for the download link
            
        Returns:
            int: ID of the created delivery record
            
        Security:
            - ORGANIZATION: Enforces organization-level isolation
            - AUDIT: Creates audit log without PII
            - VALIDATION: Validates delivery_method values
            - SECURITY: Guest users (user_id=-1) are tracked separately
            
        Note:
            This method is declared async for compatibility with async callers,
            but uses synchronous database operations internally. This is correct
            for short database operations that don't significantly block the event loop.
        """
        # VALIDATION: Ensure delivery_method is valid
        if delivery_method not in ("initial", "re-request"):
            raise ValueError(f"Invalid delivery_method: {delivery_method}. Must be 'initial' or 're-request'")
        
        # PRIVACY: Log only IDs, not user details
        import logging
        logger = logging.getLogger(__name__)
        if user_id == -1:
            logger.info(f"Recording form delivery for guest user: document {document_id}")
        else:
            logger.info(f"Recording form delivery for user {user_id}: document {document_id}")
        
        # Create delivery record
        # SECURITY: Organization-level isolation enforced via organization_id
        # BUGFIX: Allow user_id=-1 for guest users
        delivery = self.FormDelivery(
            user_id=user_id,  # Can be -1 for guest users
            conversation_id=conversation_id,
            document_id=document_id,
            organization_id=organization_id,
            delivery_method=delivery_method,
            download_link=download_link,
            link_expiration=link_expiration,
            delivered_at=datetime.utcnow(),  # Set explicitly for SQLite compatibility
            created_at=datetime.utcnow()
        )
        
        self.db.add(delivery)
        await self.db.flush()  # Get the ID without committing
        
        # AUDIT: Create audit log entry
        # PRIVACY: Log only IDs, no PII/PHI
        target_details_dict = {
            "conversation_id": conversation_id,
            "document_id": document_id,
            "delivery_method": delivery_method,
            "organization_id": organization_id,
            "is_guest_user": user_id == -1  # Flag for anonymous deliveries
        }
        
        # Convert to JSON string for SQLite compatibility in tests
        target_details_str = json.dumps(target_details_dict)
        
        audit_log = self.AuditLog(
            event_type="form_delivered",
            event_category="knowledge_base",
            event_description=f"Form document delivered to {'guest user' if user_id == -1 else 'user'} in conversation (method: {delivery_method})",
            user_id=user_id if user_id != -1 else None,  # NULL for guest users in audit log
            target_type="form_document",
            target_id=str(document_id),
            target_details=target_details_str,
            result="success",
            severity_level="info",
            security_impact="low"
        )
        
        self.db.add(audit_log)
        await self.db.commit()
        
        return delivery.id
    
    async def was_delivered(
        self,
        user_id: int,
        conversation_id: int,
        document_id: int
    ) -> Optional[Dict]:
        """
        Check if a form was delivered in this conversation.
        
        Args:
            user_id: ID of the user (can be -1 for guest users)
            conversation_id: ID of the conversation
            document_id: ID of the form document
            
        Returns:
            Optional[Dict]: Delivery details if found, None otherwise
            Contains: id, delivered_at, delivery_method, download_link
            
        Security:
            - ORGANIZATION: Implicitly isolated by user_id + conversation_id
            - SECURITY: Guest users (user_id=-1) are tracked separately
        """
        # SECURITY: Query filtered by user_id, conversation_id, document_id
        # Organization isolation is implicit through conversation ownership
        # BUGFIX: Handle guest users (user_id=-1)
        result = await self.db.execute(
            select(self.FormDelivery)
            .where(
                and_(
                    self.FormDelivery.user_id == user_id,  # Can be -1 for guest users
                    self.FormDelivery.conversation_id == conversation_id,
                    self.FormDelivery.document_id == document_id
                )
            )
            .order_by(self.FormDelivery.delivered_at.desc())
        )
        delivery = result.scalars().first()
        
        if not delivery:
            return None
        
        return {
            "id": delivery.id,
            "delivered_at": delivery.delivered_at,
            "delivery_method": delivery.delivery_method,
            "download_link": delivery.download_link,
            "link_expiration": delivery.link_expiration,
            "download_count": delivery.download_count
        }
    
    async def get_delivery_history(
        self,
        user_id: int,
        conversation_id: int,
        organization_id: int
    ) -> List[Dict]:
        """
        Get all forms delivered in this conversation.
        
        Args:
            user_id: ID of the user (can be -1 for guest users)
            conversation_id: ID of the conversation
            organization_id: ID of the organization (for isolation)
            
        Returns:
            List[Dict]: List of delivery records with details
            Each dict contains: id, document_id, delivered_at, delivery_method
            
        Security:
            - ORGANIZATION: Explicitly filters by organization_id
            - SECURITY: Guest users (user_id=-1) are tracked separately
        """
        # SECURITY: Organization-level isolation enforced
        # BUGFIX: Handle guest users (user_id=-1)
        result = await self.db.execute(
            select(self.FormDelivery)
            .where(
                and_(
                    self.FormDelivery.user_id == user_id,  # Can be -1 for guest users
                    self.FormDelivery.conversation_id == conversation_id,
                    self.FormDelivery.organization_id == organization_id
                )
            )
            .order_by(self.FormDelivery.delivered_at.desc())
        )
        deliveries = result.scalars().all()
        
        return [
            {
                "id": delivery.id,
                "document_id": delivery.document_id,
                "delivered_at": delivery.delivered_at,
                "delivery_method": delivery.delivery_method,
                "download_link": delivery.download_link,
                "link_expiration": delivery.link_expiration,
                "download_count": delivery.download_count,
                "accessed_at": delivery.accessed_at
            }
            for delivery in deliveries
        ]
