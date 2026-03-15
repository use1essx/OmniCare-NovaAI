"""
Healthcare AI V2 - Authentication Dependencies
FastAPI dependencies for authentication and authorization
"""

from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.exceptions import AuthenticationError
from src.core.logging import get_logger
from src.database.models_comprehensive import User, UserSession
from src.database.repositories.user_repository import UserRepository, UserSessionRepository
from src.web.auth.handlers import token_validator
from src.security.permissions import PermissionContext, PermissionDenied, PermissionService
from src.security.permissions.adapters import build_actor_from_user

logger = get_logger(__name__)

# HTTP Bearer token security scheme
security = HTTPBearer(
    scheme_name="Bearer Token",
    description="JWT Bearer token for authentication",
    auto_error=False
)

# Repository instances
user_repo = UserRepository()
session_repo = UserSessionRepository()

# Role hierarchy and legacy permission mapping (fallback when PermissionService not available)
ROLE_HIERARCHY = {
    "user": 1,
    "medical_reviewer": 2,
    "data_manager": 3,
    "admin": 4,
    "super_admin": 5,
}

ROLE_PERMISSIONS = {
    "user": {"view_own_conversations", "create_conversations", "view_hk_data"},
    "medical_reviewer": {
        "view_conversations",
        "review_documents",
        "approve_medical_content",
        "view_agent_performance",
    },
    "data_manager": {
        "upload_documents",
        "manage_hk_data",
        "view_system_metrics",
        "export_data",
    },
    "admin": {
        "manage_users",
        "view_audit_logs",
        "manage_system_settings",
        "view_all_data",
    },
    "super_admin": {
        "manage_admins",
        "system_administration",
        "security_management",
        "full_access",
    },
}


def has_role_level(user_role: str, required_role: str) -> bool:
    user_level = ROLE_HIERARCHY.get((user_role or "").lower(), 0)
    required_level = ROLE_HIERARCHY.get((required_role or "").lower(), 0)
    return user_level >= required_level


def has_permission(user_role: str, required_permission: str) -> bool:
    role = (user_role or "").lower()
    if role == "super_admin":
        return True
    permissions = ROLE_PERMISSIONS.get(role, set())
    if required_permission in permissions:
        return True
    user_level = ROLE_HIERARCHY.get(role, 0)
    for candidate_role, level in ROLE_HIERARCHY.items():
        if level < user_level and required_permission in ROLE_PERMISSIONS.get(candidate_role, set()):
            return True
    return False


def can_access_resource(
    user_role: str,
    resource: str,
    action: str,
    resource_owner_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> bool:
    permission = f"{action}_{resource}"
    if has_permission(user_role, permission):
        return True
    if (
        resource_owner_id
        and user_id
        and resource_owner_id == user_id
        and has_permission(user_role, f"{action}_own_{resource}")
    ):
        return True
    return False


async def get_token_from_header(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """
    Extract JWT token from Authorization header
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        JWT token string
        
    Raises:
        HTTPException: If token is missing or invalid format
    """
    token = credentials.credentials if credentials and credentials.credentials else None
    
    if not token:
        token = request.cookies.get("access_token") or request.cookies.get("auth_token")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token


async def get_current_user(
    request: Request,
    token: str = Depends(get_token_from_header)
) -> User:
    """
    Get current authenticated user from JWT token
    
    Args:
        request: FastAPI request object
        token: JWT access token
        
    Returns:
        Current authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Validate and decode token
        payload = token_validator.decode_token(token)
        user_id = int(payload.get("sub"))
        
        # Get user from database
        user = await user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Check if account is locked
        if await user_repo.is_account_locked(user.id):
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is temporarily locked",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Verify session exists and is active
        session = await session_repo.get_by_field("session_token", token)
        if not session or not session.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Update session activity
        await session_repo.update_activity(session.id)
        
        # Store user in request state for logging
        request.state.current_user = user
        request.state.current_session = session
        
        return user
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(request: Request) -> Optional[User]:
    """
    Get current user if authenticated, otherwise return None.
    This allows endpoints to work for both authenticated and anonymous users.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Current authenticated user or None
    """
    try:
        # Try to get authorization header
        auth_header = request.headers.get("authorization")
        token = None
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        
        # Fallback to cookies if header missing
        if not token:
            token = request.cookies.get("access_token") or request.cookies.get("auth_token")
        
        if not token:
            return None
            
        # Try to validate token and get user
        payload = token_validator.decode_token(token)
        user_id = int(payload.get("sub"))
        
        user = await user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            return None
            
        # Check if account is locked
        if await user_repo.is_account_locked(user.id):
            return None
        
        # Ensure session is still active
        session = await session_repo.get_by_field("session_token", token)
        if not session or not session.is_active:
            return None
            
        # Store user in request state for logging
        request.state.current_user = user
        request.state.current_session = session
        
        return user
        
    except Exception as e:
        # Log the error but don't fail - return None for anonymous access
        logger.debug(f"Optional authentication failed: {e}")
        return None


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user (additional verification)
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current active user
        
    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is not active"
        )
    
    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get current verified user
    
    Args:
        current_user: Current active user
        
    Returns:
        Current verified user
        
    Raises:
        HTTPException: If user is not verified
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required"
        )
    
    return current_user


async def get_optional_user_v2(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[User]:
    """
    Get current user if authenticated, otherwise None (Deprecated - use get_optional_user instead)
    
    Args:
        request: FastAPI request object
        credentials: Optional HTTP authorization credentials
        
    Returns:
        Current user if authenticated, None otherwise
    """
    # Try Bearer token first
    if credentials and credentials.credentials:
        try:
            return await get_current_user(request, credentials.credentials)
        except HTTPException:
            pass
    
    # Fallback to cookie auth
    try:
        token = request.cookies.get("access_token") or request.cookies.get("auth_token")
        if token:
            return await get_current_user(request, token)
    except HTTPException:
        pass
    
    return None


# Role-based dependencies
def require_role(required_role: str):
    """
    Create dependency that requires specific role or higher
    
    Args:
        required_role: Minimum required role
        
    Returns:
        FastAPI dependency function
    """
    async def role_dependency(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        if not has_role_level(current_user.role, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role} role or higher"
            )
        return current_user
    
    return role_dependency


def require_permission(required_permission: str):
    """
    Create dependency that requires specific permission
    
    Args:
        required_permission: Required permission
        
    Returns:
        FastAPI dependency function
    """
    async def permission_dependency(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        if not has_permission(current_user.role, required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {required_permission}"
            )
        return current_user
    
    return permission_dependency


def require_permission_code(permission_code: str, require_org_context: bool = True):
    """
    Enforce a PermissionService permission code within FastAPI dependencies.
    """

    async def permission_dependency(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        actor = build_actor_from_user(current_user)
        organization_id = getattr(current_user, "organization_id", None) if require_org_context else None
        context = PermissionContext(organization_id=organization_id)
        try:
            PermissionService.can(actor, permission_code, context)
        except PermissionDenied as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        return current_user

    return permission_dependency


def require_resource_access(resource: str, action: str):
    """
    Create dependency that checks resource access permissions
    
    Args:
        resource: Resource name
        action: Action to perform
        
    Returns:
        FastAPI dependency function
    """
    async def resource_dependency(
        request: Request,
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        # Extract resource owner ID from path parameters if available
        resource_owner_id = None
        if hasattr(request, "path_params"):
            resource_owner_id = request.path_params.get("user_id")
            if resource_owner_id:
                try:
                    resource_owner_id = int(resource_owner_id)
                except (ValueError, TypeError):
                    resource_owner_id = None
        
        # Check access permission
        has_access = can_access_resource(
            user_role=current_user.role,
            resource=resource,
            action=action,
            resource_owner_id=resource_owner_id,
            user_id=current_user.id
        )
        
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot {action} {resource}"
            )
            
        return current_user
    
    return resource_dependency


# Specific role dependencies (commonly used)
require_admin = require_role("admin")
require_medical_reviewer = require_role("medical_reviewer")
require_data_manager = require_role("data_manager")
require_super_admin = require_role("super_admin")


async def require_org_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Require user to be either super admin or organization admin.
    Organization admins can only manage their own organization.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current user if they have org admin or super admin access
        
    Raises:
        HTTPException: If user lacks admin privileges or organization membership
    """
    # Super admins have full access
    if (getattr(current_user, "is_super_admin", False) or 
        (current_user.role or "").lower() == "super_admin"):
        return current_user
    
    # Check if user is org admin
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to manage users"
        )
    
    # Org admins must have an organization
    if not getattr(current_user, "organization_id", None):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization membership required. Please contact system administrator."
        )
    
    return current_user


async def require_user_management_access(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Require user to have access to user management.
    Allows: super admins, org admins, and healthcare workers (doctor, nurse, counselor, social_worker).
    Healthcare workers get scoped access to assigned patients only.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current user if they have user management access
        
    Raises:
        HTTPException: If user lacks user management privileges
    """
    import logging
    logger = logging.getLogger(__name__)
    
    user_role = (getattr(current_user, "role", "") or "").lower()
    is_super = getattr(current_user, "is_super_admin", False)
    is_admin = getattr(current_user, "is_admin", False)
    org_id = getattr(current_user, "organization_id", None)
    
    logger.info(f"🔍 require_user_management_access check: user={current_user.username}, role={user_role}, is_super={is_super}, is_admin={is_admin}, org_id={org_id}")
    
    # Super admins have full access
    if (is_super or user_role == "super_admin"):
        logger.info("✅ Access granted - Super Admin")
        return current_user
    
    # Org admins have organization-scoped access
    if is_admin:
        if not org_id:
            logger.warning("❌ Access denied - Org admin without organization")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization membership required. Please contact system administrator."
            )
        logger.info(f"✅ Access granted - Org Admin (org_id={org_id})")
        return current_user
    
    # Healthcare workers have scoped access to assigned patients
    if user_role in ("doctor", "nurse", "counselor", "social_worker"):
        if not org_id:
            logger.warning("❌ Access denied - Healthcare worker without organization")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization membership required. Please contact system administrator."
            )
        logger.info(f"✅ Access granted - Healthcare Worker (role={user_role}, org_id={org_id})")
        return current_user
    
    # All other users are denied
    logger.warning(f"❌ Access denied - Insufficient permissions (role={user_role})")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions to access user management"
    )


def _is_super_admin(user: User) -> bool:
    """Helper to check if user is super admin"""
    return (getattr(user, "is_super_admin", False) or 
            (getattr(user, "role", "") or "").lower() == "super_admin")

# Specific permission dependencies
require_view_users = require_permission("view_users")
require_manage_users = require_permission("manage_users")
require_view_conversations = require_permission("view_conversations")
require_moderate_conversations = require_permission("moderate_conversations")
require_upload_documents = require_permission("upload_documents")
require_review_documents = require_permission("review_documents")
require_approve_documents = require_permission("approve_documents")
require_view_audit_logs = require_permission("view_audit_logs")
require_manage_system = require_permission("manage_system")


async def get_current_session(
    request: Request,
    current_user: User = Depends(get_current_user)
) -> UserSession:
    """
    Get current user session
    
    Args:
        request: FastAPI request object
        current_user: Current authenticated user
        
    Returns:
        Current user session
        
    Raises:
        HTTPException: If session not found
    """
    if hasattr(request.state, "current_session"):
        return request.state.current_session
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session not found"
    )


async def validate_session_ownership(
    session_id: int,
    current_user: User = Depends(get_current_user)
) -> UserSession:
    """
    Validate that current user owns the specified session
    
    Args:
        session_id: Session ID to validate
        current_user: Current authenticated user
        
    Returns:
        User session if owned by current user
        
    Raises:
        HTTPException: If session not found or not owned by user
    """
    session = await session_repo.get_by_id(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
        
    if session.user_id == current_user.id:
        return session

    target_user = await user_repo.get_by_id(session.user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session owner not found"
        )

    actor = build_actor_from_user(current_user)
    context = PermissionContext(
        organization_id=getattr(target_user, "organization_id", None),
        target_user_id=target_user.id,
    )

    try:
        PermissionService.can(actor, "user.edit", context)
        return session
    except PermissionDenied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other user's session"
        ) from None


async def validate_user_ownership(
    user_id: int,
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Validate that current user can access specified user
    
    Args:
        user_id: User ID to validate access for
        current_user: Current authenticated user
        
    Returns:
        Target user if access is allowed
        
    Raises:
        HTTPException: If access is denied
    """
    # Users can always access their own data
    if user_id == current_user.id:
        return current_user

    target_user = await user_repo.get_by_id(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    actor = build_actor_from_user(current_user)

    # First, see if actor has global view access
    try:
        PermissionService.can(actor, "user.view.all", PermissionContext())
        return target_user
    except PermissionDenied:
        pass

    # Fall back to organization-scoped visibility
    target_org_id = getattr(target_user, "organization_id", None)
    context = PermissionContext(
        organization_id=target_org_id,
        target_user_id=target_user.id
    )
    try:
        PermissionService.can(actor, "user.view.org", context)
        return target_user
    except PermissionDenied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other user's data"
        ) from None


# Rate limiting dependency
class RateLimitChecker:
    """Rate limiting dependency"""
    
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # In production, use Redis
        
    def __call__(self, request: Request) -> None:
        """
        Check rate limit for request
        
        Args:
            request: FastAPI request object
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        # Get client identifier (IP address)
        client_ip = self._get_client_ip(request)
        now = datetime.utcnow()
        
        # Clean old requests (simplified in-memory implementation)
        if client_ip in self.requests:
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip]
                if (now - req_time).total_seconds() < self.window_seconds
            ]
        else:
            self.requests[client_ip] = []
            
        # Check rate limit
        if len(self.requests[client_ip]) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now.timestamp()) + self.window_seconds)
                }
            )
            
        # Record request
        self.requests[client_ip].append(now)
        
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request"""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
            
        forwarded = request.headers.get("X-Real-IP")
        if forwarded:
            return forwarded
            
        return request.client.host if request.client else "unknown"


# Rate limiting instances for different endpoints
auth_rate_limit = RateLimitChecker(max_requests=5, window_seconds=60)  # 5 auth attempts per minute
api_rate_limit = RateLimitChecker(max_requests=100, window_seconds=60)  # 100 API calls per minute
upload_rate_limit = RateLimitChecker(max_requests=10, window_seconds=300)  # 10 uploads per 5 minutes


# Export dependencies
__all__ = [
    # Core dependencies
    "get_token_from_header",
    "get_current_user",
    "get_current_active_user",
    "get_current_verified_user",
    "get_optional_user",
    "get_current_session",
    
    # Role dependencies
    "require_role",
    "require_admin",
    "require_medical_reviewer",
    "require_data_manager",
    "require_super_admin",
    "require_org_admin",
    
    # Permission dependencies
    "require_permission",
    "require_permission_code",
    "require_resource_access",
    "require_view_users",
    "require_manage_users",
    "require_view_conversations",
    "require_moderate_conversations",
    "require_upload_documents",
    "require_review_documents",
    "require_approve_documents",
    "require_view_audit_logs",
    "require_manage_system",
    
    # Validation dependencies
    "validate_session_ownership",
    "validate_user_ownership",
    
    # Rate limiting
    "RateLimitChecker",
    "auth_rate_limit",
    "api_rate_limit",
    "upload_rate_limit",
    
    # Helper functions
    "_is_super_admin",
]
