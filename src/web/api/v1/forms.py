"""
Form Download API Endpoints

Provides secure JWT-based download endpoints for form documents.
Public endpoint - authentication via JWT token in URL.

Security Notes:
- AUTHENTICATION: JWT token in path parameter
- AUTHORIZATION: Organization-level isolation enforced in service layer
- PRIVACY: Returns 404 (not 403) to avoid revealing document existence
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import get_async_db
from src.knowledge_base.form_download_service import FormDownloadService
from src.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/forms/download/{token}")
async def download_form(
    token: str,
    db: AsyncSession = Depends(get_async_db)
) -> FileResponse:
    """
    Download a form document using a secure JWT token.
    
    This is a public endpoint - authentication is provided by the JWT token itself.
    The token contains user_id, document_id, organization_id, and expiration.
    
    Args:
        token: JWT token from download URL (path parameter)
        db: Database session (injected)
        
    Returns:
        FileResponse: Form document file with appropriate headers
        
    Raises:
        HTTPException: 
            - 401 if token is invalid or expired
            - 404 if document not found or user lacks permission
            
    Security:
        - AUTHENTICATION: JWT token verified in FormDownloadService
        - AUTHORIZATION: Organization isolation enforced
        - PRIVACY: Returns 404 (not 403) to avoid revealing existence
        - TRACKING: Download count incremented, accessed_at timestamp set
        
    Example:
        GET /api/v1/forms/download/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
        
    Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
    """
    try:
        # SECURITY: All validation and authorization handled by FormDownloadService
        # - JWT signature verification
        # - Expiration check
        # - Organization isolation
        # - Permission verification
        service = FormDownloadService(db)
        
        # PRIVACY: Service returns 404 (not 403) for unauthorized access
        file_response = await service.verify_and_serve(token)
        
        # AUDIT: Download tracking handled in service layer
        logger.info(f"Form download successful via token")
        
        return file_response
        
    except HTTPException:
        # Re-raise HTTP exceptions from service layer
        raise
    except Exception as e:
        # PRIVACY: Don't expose internal errors
        logger.error(f"Form download failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to download form document"
        )
