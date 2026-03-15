"""
Healthcare AI V2 - pgAdmin Integration API
REST endpoints for pgAdmin authentication and management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Dict, Any, List
import logging

from src.web.auth.dependencies import require_admin
from src.web.admin.pgadmin_integration import get_pgadmin_integration, PgAdminIntegration
from src.database.models_comprehensive import User


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pgadmin", tags=["pgAdmin Integration"])


class PgAdminAuthRequest(BaseModel):
    password: str
    
    
class PgAdminSessionInfo(BaseModel):
    user_id: int
    email: str
    created_at: str
    token_preview: str


class PgAdminHealthResponse(BaseModel):
    status: str
    url: str
    response_time_ms: int = 0
    version: str = ""
    active_sessions: int = 0
    error: str = ""


@router.post("/authenticate")
async def authenticate_for_pgadmin(
    auth_request: PgAdminAuthRequest,
    current_user: User = Depends(require_admin),
    pgadmin: PgAdminIntegration = Depends(get_pgadmin_integration)
) -> Dict[str, Any]:
    """
    Authenticate user for pgAdmin access and return SSO token and redirect URL.
    
    This endpoint:
    1. Verifies the user's password
    2. Checks admin privileges
    3. Creates SSO token for pgAdmin
    4. Returns redirect URL for seamless access
    """
    try:
        auth_result = await pgadmin.authenticate_user_for_pgadmin(
            user_id=current_user.id,
            password=auth_request.password
        )
        
        logger.info(f"pgAdmin authentication successful for {current_user.email}")
        
        return {
            "success": True,
            "message": "Authentication successful",
            "sso_token": auth_result["sso_token"],
            "redirect_url": auth_result["redirect_url"],
            "expires_at": auth_result["expires_at"],
            "user_info": {
                "email": auth_result["user_info"]["email"],
                "role": auth_result["user_info"]["role"],
                "full_name": auth_result["user_info"]["full_name"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"pgAdmin authentication error for {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.get("/redirect/{sso_token}")
async def pgadmin_redirect(
    sso_token: str,
    pgadmin: PgAdminIntegration = Depends(get_pgadmin_integration)
) -> RedirectResponse:
    """
    Handle SSO redirect to pgAdmin with token validation.
    
    This endpoint validates the SSO token and redirects to pgAdmin
    if the token is valid and the user has appropriate permissions.
    """
    try:
        # Validate SSO token
        user_info = await pgadmin.validate_sso_token(sso_token)
        
        if not user_info:
            logger.warning(f"Invalid SSO token for pgAdmin redirect: {sso_token[:20]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token"
            )
        
        # Generate pgAdmin redirect URL
        redirect_url = await pgadmin.generate_pgadmin_redirect_url(user_info)
        
        logger.info(f"Redirecting {user_info['email']} to pgAdmin")
        
        return RedirectResponse(
            url=redirect_url,
            status_code=status.HTTP_302_FOUND
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"pgAdmin redirect error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Redirect failed"
        )


@router.post("/logout/{sso_token}")
async def logout_from_pgadmin(
    sso_token: str,
    current_user: User = Depends(require_admin),
    pgadmin: PgAdminIntegration = Depends(get_pgadmin_integration)
) -> Dict[str, Any]:
    """
    Logout user from pgAdmin by revoking SSO session.
    """
    try:
        success = await pgadmin.revoke_sso_session(sso_token)
        
        if success:
            logger.info(f"pgAdmin logout successful for {current_user.email}")
            return {
                "success": True,
                "message": "Successfully logged out from pgAdmin"
            }
        else:
            return {
                "success": False,
                "message": "Session not found or already expired"
            }
            
    except Exception as e:
        logger.error(f"pgAdmin logout error for {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.get("/sessions", response_model=List[PgAdminSessionInfo])
async def get_active_sessions(
    current_user: User = Depends(require_admin),
    pgadmin: PgAdminIntegration = Depends(get_pgadmin_integration)
) -> List[PgAdminSessionInfo]:
    """
    Get list of active pgAdmin sessions.
    
    Only accessible by admin users for monitoring purposes.
    """
    try:
        active_sessions = await pgadmin.get_active_pgadmin_sessions()
        
        return [
            PgAdminSessionInfo(
                user_id=session["user_id"],
                email=session["email"],
                created_at=session["created_at"],
                token_preview=session["token_preview"]
            )
            for session in active_sessions
        ]
        
    except Exception as e:
        logger.error(f"Error getting active pgAdmin sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve active sessions"
        )


@router.get("/health", response_model=PgAdminHealthResponse)
async def check_pgadmin_health(
    current_user: User = Depends(require_admin),
    pgadmin: PgAdminIntegration = Depends(get_pgadmin_integration)
) -> PgAdminHealthResponse:
    """
    Check pgAdmin service health and connectivity.
    
    Returns status information about the pgAdmin service including:
    - Service availability
    - Response time
    - Active sessions count
    - Any error information
    """
    try:
        health_info = await pgadmin.check_pgadmin_health()
        
        return PgAdminHealthResponse(
            status=health_info.get("status", "unknown"),
            url=health_info.get("url", ""),
            response_time_ms=health_info.get("response_time_ms", 0),
            version=health_info.get("version", ""),
            active_sessions=health_info.get("active_sessions", 0),
            error=health_info.get("error", "")
        )
        
    except Exception as e:
        logger.error(f"Error checking pgAdmin health: {e}")
        return PgAdminHealthResponse(
            status="error",
            url="",
            error=str(e)
        )


@router.post("/auto-setup")
async def auto_setup_servers(
    current_user: User = Depends(require_admin),
    pgadmin: PgAdminIntegration = Depends(get_pgadmin_integration)
) -> Dict[str, Any]:
    """
    Automatically setup Healthcare AI database servers in pgAdmin.
    
    This endpoint will:
    1. Check if servers already exist
    2. Create Healthcare AI database server connections
    3. Configure proper authentication
    4. Return setup status
    """
    try:
        setup_result = await pgadmin.auto_setup_healthcare_servers(current_user.email)
        
        logger.info(f"Auto-setup triggered by {current_user.email}: {setup_result['status']}")
        
        return {
            "success": setup_result["success"],
            "message": setup_result["message"],
            "servers_created": setup_result.get("servers_created", []),
            "servers_existing": setup_result.get("servers_existing", []),
            "total_servers": setup_result.get("total_servers", 0)
        }
        
    except Exception as e:
        logger.error(f"Error in auto-setup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Auto-setup failed: {str(e)}"
        )


@router.post("/cleanup-sessions")
async def cleanup_expired_sessions(
    current_user: User = Depends(require_admin),
    pgadmin: PgAdminIntegration = Depends(get_pgadmin_integration)
) -> Dict[str, Any]:
    """
    Manually trigger cleanup of expired pgAdmin sessions.
    
    This is typically run as a background task, but can be triggered manually.
    """
    try:
        await pgadmin.cleanup_expired_sessions()
        
        logger.info(f"Manual session cleanup triggered by {current_user.email}")
        
        return {
            "success": True,
            "message": "Session cleanup completed successfully"
        }
        
    except Exception as e:
        logger.error(f"Error in manual session cleanup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session cleanup failed"
        )


@router.get("/config")
async def get_pgadmin_config(
    current_user: User = Depends(require_admin),
    pgadmin: PgAdminIntegration = Depends(get_pgadmin_integration)
) -> Dict[str, Any]:
    """
    Get pgAdmin configuration information for admin interface.
    
    Returns non-sensitive configuration details for displaying
    in the admin dashboard.
    """
    try:
        config_info = {
            "pgadmin_url": pgadmin.pgadmin_url,
            "integration_enabled": True,
            "sso_enabled": True,
            "session_timeout_hours": 8,
            "supported_features": [
                "Single Sign-On",
                "Automated Database Connections",
                "Healthcare Query Templates",
                "Performance Monitoring",
                "Automated Backups",
                "Security Audit Logging"
            ]
        }
        
        return config_info
        
    except Exception as e:
        logger.error(f"Error getting pgAdmin config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve configuration"
        )
