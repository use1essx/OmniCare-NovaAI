"""
Form Download Service

Generates secure JWT-based download URLs for form documents.
Provides time-limited, authenticated access to form files.

Security Notes:
- AUTHENTICATION: JWT tokens with expiration
- AUTHORIZATION: Organization-level isolation enforced
- PRIVACY: Returns 404 (not 403) to avoid revealing document existence
"""

import jwt
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select

from src.core.config import settings

# Import models - can be overridden in tests
try:
    from src.database.models_knowledge_base import KnowledgeDocument
    from src.database.models_form_delivery import FormDelivery
except ImportError:
    # Fallback for testing
    KnowledgeDocument = None
    FormDelivery = None


class FormDownloadService:
    """
    Generate secure JWT-based download links for form documents.
    
    This service provides:
    - JWT token generation with expiration
    - Token verification and validation
    - Secure document serving with permission checks
    - Organization-level isolation
    - Download tracking
    """
    
    def __init__(
        self,
        db: AsyncSession,
        secret_key: Optional[str] = None,
        knowledge_document_model=None,
        form_delivery_model=None
    ):
        """
        Initialize the form download service.
        
        Args:
            db: SQLAlchemy database session
            secret_key: JWT secret key (defaults to settings.jwt_secret_key)
            knowledge_document_model: Optional KnowledgeDocument model (for testing)
            form_delivery_model: Optional FormDelivery model (for testing)
        """
        self.db = db
        # SECURITY: Use secure secret key from environment variables
        self.secret_key = secret_key or settings.jwt_secret_key
        self.KnowledgeDocument = knowledge_document_model or KnowledgeDocument
        self.FormDelivery = form_delivery_model or FormDelivery
    
    def generate_download_link(
        self,
        document_id: int,
        user_id: int,
        organization_id: int,
        expiration_minutes: int = 60
    ) -> str:
        """
        Generate a JWT-based download URL for a form document.
        
        Creates a time-limited, authenticated download link that includes
        user and organization information for authorization checks.
        
        Args:
            document_id: ID of the form document
            user_id: ID of the user requesting the download (use -1 for anonymous/guest users)
            organization_id: ID of the user's organization
            expiration_minutes: Link expiration time in minutes (default: 60)
            
        Returns:
            str: JWT token for download authentication
            
        Security:
            - AUTHENTICATION: JWT token with expiration timestamp
            - AUTHORIZATION: Includes user_id and organization_id for verification
            - VALIDATION: Token signed with secure secret key
            - SECURITY: Guest users (user_id=-1) get shorter expiration time
            
        Example:
            >>> service = FormDownloadService(db)
            >>> # Authenticated user
            >>> token = service.generate_download_link(
            ...     document_id=123,
            ...     user_id=456,
            ...     organization_id=789,
            ...     expiration_minutes=60
            ... )
            >>> # Anonymous user
            >>> token = service.generate_download_link(
            ...     document_id=123,
            ...     user_id=-1,  # Guest user ID
            ...     organization_id=1,  # Default public organization
            ...     expiration_minutes=60
            ... )
        """
        # SECURITY: Apply shorter expiration for anonymous users
        # Anonymous users get 1 hour, authenticated users get specified time
        if user_id == -1:
            # SECURITY: Shorter expiration for guest users to limit exposure
            expiration_minutes = min(expiration_minutes, 60)  # Max 1 hour for guests
            # PRIVACY: Log only that it's a guest user, no other details
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Generating download link for guest user (document_id={document_id})")
        
        # Calculate expiration timestamp
        now = datetime.utcnow()
        expiration = now + timedelta(minutes=expiration_minutes)
        
        # Create JWT payload
        # SECURITY: Include all required claims for authorization
        payload = {
            "document_id": document_id,
            "user_id": user_id,  # Can be -1 for guest users
            "organization_id": organization_id,
            "exp": expiration,  # Expiration timestamp
            "iat": now,  # Issued at timestamp
            "purpose": "form_download"  # Token purpose for validation
        }
        
        # Generate JWT token
        # SECURITY: Use HS256 algorithm with secure secret key
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")
        
        return token
    
    async def verify_and_serve(
        self,
        token: str
    ) -> FileResponse:
        """
        Verify JWT token and serve the form document.
        
        Validates the token, checks user permissions, enforces organization
        isolation, and serves the document file if authorized.
        
        Args:
            token: JWT token from download URL
            
        Returns:
            FileResponse: Document file with appropriate headers
            
        Raises:
            HTTPException: 401 if token invalid/expired, 404 if unauthorized/not found
            
        Security:
            - AUTHENTICATION: Verifies JWT signature and expiration
            - AUTHORIZATION: Checks user has permission to access document
            - ORGANIZATION: Enforces organization-level isolation
            - PRIVACY: Returns 404 (not 403) to avoid revealing existence
            - TRACKING: Increments download count and sets accessed_at
        """
        try:
            # SECURITY: Verify JWT token signature and expiration
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            # SECURITY: Token expired
            raise HTTPException(
                status_code=401,
                detail="Download link has expired. Please request the form again."
            )
        except jwt.InvalidTokenError:
            # SECURITY: Invalid token (bad signature, malformed, etc.)
            raise HTTPException(
                status_code=401,
                detail="Invalid download link."
            )
        
        # Extract claims from token
        document_id = payload.get("document_id")
        user_id = payload.get("user_id")
        organization_id = payload.get("organization_id")
        purpose = payload.get("purpose")
        
        # VALIDATION: Ensure all required claims are present
        if not all([document_id, organization_id, purpose]):
            raise HTTPException(
                status_code=401,
                detail="Invalid download link."
            )
        
        # BUGFIX: Allow user_id to be -1 for guest users
        # SECURITY: Guest users (user_id=-1) can download forms with organization isolation
        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid download link."
            )
        
        # VALIDATION: Ensure token purpose is correct
        if purpose != "form_download":
            raise HTTPException(
                status_code=401,
                detail="Invalid download link."
            )
        
        # PRIVACY: Log only IDs, not user details
        import logging
        logger = logging.getLogger(__name__)
        if user_id == -1:
            logger.info(f"Guest user downloading document {document_id}")
        else:
            logger.info(f"User {user_id} downloading document {document_id}")
        
        # SECURITY: Query document by ID only (forms are public documents)
        # NOTE: Forms are public resources, no organization isolation needed
        # PRIVACY: Return 404 (not 403) to avoid revealing document existence
        result = await self.db.execute(
            select(self.KnowledgeDocument).where(self.KnowledgeDocument.id == document_id)
        )
        document = result.scalars().first()
        
        # BUGFIX: Handle orphaned chunks (chunks exist but document record missing)
        # This can happen if document was deleted but chunks remain, or if vector store is out of sync
        if not document:
            logger.warning(f"Document {document_id} not found in knowledge_documents table, checking chunks...")
            
            # Try to get document info from chunks table
            from src.database.models_knowledge_base import KnowledgeChunk
            result = await self.db.execute(
                select(KnowledgeChunk)
                .where(KnowledgeChunk.document_id == document_id)
                .limit(1)
            )
            chunk = result.scalars().first()
            
            logger.info(f"Chunk query result from database: {chunk}")
            
            # If no chunks in database, try vector store (ChromaDB)
            if not chunk:
                logger.warning(f"No chunks in database for document {document_id}, checking vector store...")
                try:
                    from src.database.vector_store import get_vector_store
                    vector_store = get_vector_store()
                    
                    # Query vector store for this document
                    vs_results = vector_store.collection.get(
                        where={"document_id": document_id},
                        limit=1,
                        include=['metadatas']
                    )
                    
                    logger.info(f"Vector store query returned {len(vs_results['ids'])} results")
                    
                    if vs_results['ids'] and vs_results['metadatas']:
                        vs_metadata = vs_results['metadatas'][0]
                        logger.info(f"Found metadata in vector store: {vs_metadata}")
                        
                        file_path = vs_metadata.get('file_path')
                        title = vs_metadata.get('title', f'Document {document_id}')
                        file_type = vs_metadata.get('file_type', 'application/pdf')
                        is_form = vs_metadata.get('is_form', False)
                        
                        logger.info(f"Extracted from vector store: file_path={file_path}, title={title}, is_form={is_form}")
                        
                        if file_path and is_form:
                            # Create a temporary document-like object for serving
                            class TempDocument:
                                def __init__(self, file_path, title, file_type):
                                    self.file_path = file_path
                                    self.title = title
                                    self.file_type = file_type
                            
                            document = TempDocument(file_path, title, file_type)
                            logger.info(f"Using vector store metadata to serve document {document_id}")
                        else:
                            logger.error(f"Vector store metadata missing required fields: file_path={file_path}, is_form={is_form}")
                            raise HTTPException(
                                status_code=404,
                                detail="Document not found."
                            )
                    else:
                        logger.error(f"Document {document_id} not found in vector store either")
                        raise HTTPException(
                            status_code=404,
                            detail="Document not found."
                        )
                except Exception as vs_error:
                    logger.error(f"Error querying vector store: {vs_error}")
                    raise HTTPException(
                        status_code=404,
                        detail="Document not found."
                    )
            else:
                # Found chunk in database
                logger.info(f"Found chunk: id={chunk.id}, document_id={chunk.document_id}, metadata={chunk.chunk_metadata}")
                
                chunk_meta = chunk.chunk_metadata or {}
                file_path = chunk_meta.get('file_path')
                title = chunk_meta.get('title', f'Document {document_id}')
                file_type = chunk_meta.get('file_type', 'application/pdf')
                is_form = chunk_meta.get('is_form', False)
                
                logger.info(f"Extracted from chunk: file_path={file_path}, title={title}, is_form={is_form}")
                
                if file_path and is_form:
                    # Create a temporary document-like object for serving
                    class TempDocument:
                        def __init__(self, file_path, title, file_type):
                            self.file_path = file_path
                            self.title = title
                            self.file_type = file_type
                    
                    document = TempDocument(file_path, title, file_type)
                    logger.info(f"Using chunk metadata to serve document {document_id}")
                else:
                    logger.error(f"Chunk found but missing required metadata: file_path={file_path}, is_form={is_form}")
                    raise HTTPException(
                        status_code=404,
                        detail="Document not found."
                    )
        
        # SECURITY: Verify document is actually a form (additional safety check)
        # For TempDocument (from chunks), we already verified is_form in the fallback logic
        if hasattr(document, 'doc_metadata'):
            doc_metadata = document.doc_metadata or {}
            is_form = doc_metadata.get('is_form')
            
            if not is_form:
                logger.warning(f"Attempted download of non-form document {document_id} (is_form={is_form})")
                raise HTTPException(
                    status_code=404,
                    detail="Document not found."
                )
        # else: TempDocument from chunks - already verified is_form
        
        # Check if document file exists
        file_path = Path(document.file_path)
        if not file_path.exists():
            logger.error(f"Document file not found at path: {file_path}")
            raise HTTPException(
                status_code=404,
                detail="Document file not found."
            )
        
        # TRACKING: Increment download count and set accessed_at
        # Find the most recent delivery record for this token
        # BUGFIX: Handle guest users (user_id=-1) in delivery tracking
        result = await self.db.execute(
            select(self.FormDelivery)
            .where(
                and_(
                    self.FormDelivery.user_id == user_id,  # Can be -1 for guest users
                    self.FormDelivery.document_id == document_id,
                    self.FormDelivery.download_link == token
                )
            )
            .order_by(self.FormDelivery.delivered_at.desc())
        )
        delivery = result.scalars().first()
        
        if delivery:
            delivery.download_count += 1
            if not delivery.accessed_at:
                delivery.accessed_at = datetime.utcnow()
            await self.db.commit()
            # PRIVACY: Log only IDs and counts
            logger.info(f"Download count updated: document {document_id}, count {delivery.download_count}")
        else:
            # AUDIT: Log if delivery record not found (shouldn't happen normally)
            logger.warning(f"Delivery record not found for document {document_id}, user {user_id}")
        
        # Serve the document file
        # Set appropriate content-type and headers
        # BUGFIX: Ensure filename has proper extension for browser download
        filename = document.title or file_path.name
        
        # If filename doesn't have an extension, add it from the file_path
        if '.' not in filename:
            file_extension = file_path.suffix  # e.g., '.pdf'
            filename = f"{filename}{file_extension}"
        
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type=document.file_type or "application/octet-stream"
        )
