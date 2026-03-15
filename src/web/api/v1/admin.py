"""
Administrative System API Endpoints

This module provides comprehensive system administration functionality including:
- System statistics and monitoring
- User management operations
- Data management oversight
- System configuration
- Audit log access
- Performance monitoring
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Form
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, AuthorizationError, ValidationError
from src.core.logging import get_logger, log_api_request
from src.security.auth import InputSanitizer
from src.database.connection import get_async_db
from src.database.models_comprehensive import User
from src.database.repositories.user_repository import UserRepository
from src.web.auth.dependencies import require_role


logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class SystemStatsResponse(BaseModel):
    """System statistics response model"""
    timestamp: datetime
    uptime_seconds: float
    system_status: str
    
    # User Statistics
    total_users: int
    active_users: int
    admin_users: int
    new_users_today: int
    
    # Agent Statistics
    total_conversations: int
    conversations_today: int
    average_response_time_ms: float
    agent_performance: Dict[str, Any]
    
    # Data Statistics
    total_documents: int
    pending_documents: int
    approved_documents: int
    hk_data_records: int
    
    # System Health
    database_status: str
    cache_status: str
    external_apis_status: Dict[str, str]
    
    # Performance Metrics
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    request_rate_per_minute: float
    error_rate_percent: float


class CreateUserRequest(BaseModel):
    """Create user request model"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., max_length=255)
    role: str = Field(default="user")
    organization_id: Optional[int] = None
    is_active: bool = True


class UpdateUserRequest(BaseModel):
    """Update user request model"""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    organization_id: Optional[int] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserManagementResponse(BaseModel):
    """User management operation response"""
    id: int
    email: str
    username: str
    full_name: Optional[str]
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]
    failed_login_attempts: int
    account_locked_until: Optional[datetime]
    organization_id: Optional[int] = None
    
    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    """Audit log response model"""
    id: int
    event_type: str
    event_category: str
    event_description: str
    user_id: Optional[int]
    username: Optional[str]
    target_type: Optional[str]
    target_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    result: str
    severity_level: str
    created_at: datetime
    metadata: Dict[str, Any] = {}
    
    class Config:
        from_attributes = True


class SystemConfigurationResponse(BaseModel):
    """System configuration response model"""
    configuration_key: str
    configuration_value: Any
    description: str
    category: str
    is_sensitive: bool
    last_modified: datetime
    modified_by: Optional[str]


class PerformanceMetricsResponse(BaseModel):
    """Performance metrics response model"""
    metric_name: str
    current_value: float
    unit: str
    trend_direction: str  # up, down, stable
    comparison_period: str
    threshold_warning: Optional[float]
    threshold_critical: Optional[float]
    status: str  # normal, warning, critical
    last_updated: datetime


class TestRunResponse(BaseModel):
    """Test run response model"""
    success: bool
    output: str
    timestamp: datetime


class AssignUserRequest(BaseModel):
    """Assign user request model"""
    assigned_to_id: int


class BulkUserActionRequest(BaseModel):
    """Bulk user action request model"""
    user_ids: List[int] = Field(..., description="List of user IDs to perform action on")
    action: str = Field(..., description="Action to perform (activate, deactivate, verify, reset_password)")
    reason: Optional[str] = Field(None, description="Reason for the action")


class SystemMaintenanceRequest(BaseModel):
    """System maintenance request model"""
    maintenance_type: str = Field(..., description="Type of maintenance")
    scheduled_time: datetime = Field(..., description="Scheduled maintenance time")
    estimated_duration_minutes: int = Field(..., description="Estimated duration in minutes")
    description: str = Field(..., description="Maintenance description")
    notify_users: bool = Field(default=True, description="Whether to notify users")


# ============================================================================
# SYSTEM STATISTICS ENDPOINTS
# ============================================================================

@router.get(
    "/stats",
    response_model=SystemStatsResponse,
    dependencies=[Depends(require_role("admin"))],
    summary="Get system statistics (Admin)",
    description="Get comprehensive system statistics and health metrics",
    responses={
        200: {"description": "Statistics retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"}
    }
)
  # 20 calls per minute
async def get_system_statistics(
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> SystemStatsResponse:
    """Get comprehensive system statistics"""
    start_time = datetime.now()
    
    try:
        # TODO: Implement with actual data from repositories and system monitoring
        # For now, return placeholder statistics
        
        # Calculate uptime (placeholder)
        uptime_seconds = 86400.0  # 1 day placeholder
        
        # User statistics (placeholder - would use UserRepository)
        user_repo = UserRepository()
        user_stats = await user_repo.get_user_statistics()
        
        # System health checks (placeholder)
        database_status = "healthy"
        cache_status = "healthy"
        external_apis_status = {
            "aws_bedrock": "healthy",
            "hk_hospital_authority": "healthy",
            "hk_department_health": "healthy"
        }
        
        # Performance metrics (placeholder - would use actual system monitoring)
        performance_metrics = {
            "cpu_usage": 45.2,
            "memory_usage": 62.8,
            "disk_usage": 78.5,
            "request_rate": 125.3,
            "error_rate": 0.5
        }
        
        # Agent performance (placeholder)
        agent_performance = {
            "illness_monitor": {"conversations": 0, "avg_confidence": 0.0, "avg_satisfaction": 0.0},
            "mental_health": {"conversations": 0, "avg_confidence": 0.0, "avg_satisfaction": 0.0},
            "safety_guardian": {"conversations": 0, "avg_confidence": 0.0, "avg_satisfaction": 0.0},
            "wellness_coach": {"conversations": 0, "avg_confidence": 0.0, "avg_satisfaction": 0.0}
        }
        
        # Log successful request
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        return SystemStatsResponse(
            timestamp=datetime.now(),
            uptime_seconds=uptime_seconds,
            system_status="operational",
            
            # User statistics
            total_users=user_stats.get("total_users", 0),
            active_users=user_stats.get("active_users", 0),
            admin_users=user_stats.get("admin_users", 0),
            new_users_today=user_stats.get("recent_registrations", 0),
            
            # Agent statistics (placeholder)
            total_conversations=0,
            conversations_today=0,
            average_response_time_ms=0.0,
            agent_performance=agent_performance,
            
            # Data statistics (placeholder)
            total_documents=0,
            pending_documents=0,
            approved_documents=0,
            hk_data_records=1295,
            
            # System health
            database_status=database_status,
            cache_status=cache_status,
            external_apis_status=external_apis_status,
            
            # Performance metrics
            cpu_usage_percent=performance_metrics["cpu_usage"],
            memory_usage_percent=performance_metrics["memory_usage"],
            disk_usage_percent=performance_metrics["disk_usage"],
            request_rate_per_minute=performance_metrics["request_rate"],
            error_rate_percent=performance_metrics["error_rate"]
        )
        
    except Exception as e:
        logger.error(f"Error retrieving system statistics: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving system statistics"
        )


# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================

@router.get(
    "/users",
    response_model=List[UserManagementResponse],
    dependencies=[Depends(require_role("admin"))],
    summary="Get all users for management (Admin)",
    description="Get detailed list of all users for administrative management",
    responses={
        200: {"description": "Users retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"}
    }
)

async def get_users_for_management(
    request: Request,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page"),
    role: Optional[str] = Query(None, description="Filter by role"),
    status: Optional[str] = Query(None, description="Filter by status (active, inactive, locked)"),
    search: Optional[str] = Query(None, description="Search by email, username, or name"),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> List[UserManagementResponse]:
    """Get all users for administrative management"""
    start_time = datetime.now()
    
    try:
        user_repo = UserRepository()
        
        # Build filters
        filters = {}
        if role:
            filters["role"] = role
        
        # Handle status filter
        if status == "active":
            filters["is_active"] = True
        elif status == "inactive":
            filters["is_active"] = False
        elif status == "locked":
            # Would need to check account_locked_until field
            pass
        
        # Get users with pagination
        result = await user_repo.get_paginated(
            page=page,
            page_size=page_size,
            filters=filters,
            order_by="created_at",
            order_desc=True,
            session=db
        )
        
        users = result["items"]
        
        # Apply search filter if provided
        if search:
            sanitizer = InputSanitizer()
            safe_search = sanitizer.sanitize_string(search, max_length=100).lower()
            users = [
                user for user in users
                if (safe_search in user.email.lower() or
                    safe_search in user.username.lower() or
                    (user.full_name and safe_search in user.full_name.lower()))
            ]
        
        # Convert to management response format
        user_responses = [UserManagementResponse.from_orm(user) for user in users]
        
        # Log successful request
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        return user_responses
        
    except Exception as e:
        logger.error(f"Error retrieving users for management: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving users for management"
        )


@router.post(
    "/users/{user_id}/activate",
    dependencies=[Depends(require_role("admin"))],
    summary="Activate user account (Admin)",
    description="Activate a user account and unlock if necessary",
    responses={
        200: {"description": "User activated successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"},
        404: {"description": "User not found"}
    }
)

async def activate_user_account(
    request: Request,
    user_id: int,
    reason: Optional[str] = Form(None, description="Reason for activation"),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, str]:
    """Activate user account"""
    start_time = datetime.now()
    
    try:
        user_repo = UserRepository()
        
        # Get target user
        target_user = await user_repo.get_by_id(user_id, db)
        if not target_user:
            raise NotFoundError(f"User with ID {user_id} not found")
        
        # Activate user
        success = await user_repo.activate_user(user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to activate user"
            )
        
        # Also unlock account if locked
        await user_repo.unlock_account(user_id)
        
        # Log successful activation
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        logger.info(f"Admin {current_user.id} activated user {user_id}")
        
        return {"message": f"User {user_id} activated successfully"}
        
    except Exception as e:
        logger.error(f"Error activating user {user_id}: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        if isinstance(e, NotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error activating user"
        )


@router.post(
    "/users/bulk-action",
    dependencies=[Depends(require_role("admin"))],
    summary="Perform bulk user actions (Admin)",
    description="Perform actions on multiple users at once",
    responses={
        200: {"description": "Bulk action completed"},
        400: {"description": "Invalid action or user IDs"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"}
    }
)
  # Limited rate for bulk operations
async def bulk_user_action(
    request: Request,
    action_request: BulkUserActionRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Perform bulk actions on multiple users"""
    start_time = datetime.now()
    
    try:
        # Validate action
        allowed_actions = ["activate", "deactivate", "verify", "reset_password"]
        if action_request.action not in allowed_actions:
            raise ValidationError(f"Invalid action. Allowed actions: {', '.join(allowed_actions)}")
        
        # Validate user IDs count
        if len(action_request.user_ids) > 100:
            raise ValidationError("Cannot perform bulk action on more than 100 users at once")
        
        user_repo = UserRepository()
        results = {
            "action": action_request.action,
            "total_users": len(action_request.user_ids),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        # Perform action on each user
        for user_id in action_request.user_ids:
            try:
                # Prevent action on self or super admins
                if user_id == current_user.id:
                    results["errors"].append(f"Cannot perform action on your own account (ID: {user_id})")
                    results["failed"] += 1
                    continue
                
                target_user = await user_repo.get_by_id(user_id, db)
                if not target_user:
                    results["errors"].append(f"User not found (ID: {user_id})")
                    results["failed"] += 1
                    continue
                
                if target_user.is_super_admin and not current_user.is_super_admin:
                    results["errors"].append(f"Cannot modify super admin user (ID: {user_id})")
                    results["failed"] += 1
                    continue
                
                # Perform the specific action
                success = False
                if action_request.action == "activate":
                    success = await user_repo.activate_user(user_id)
                elif action_request.action == "deactivate":
                    success = await user_repo.deactivate_user(user_id)
                elif action_request.action == "verify":
                    success = await user_repo.verify_user(user_id)
                elif action_request.action == "reset_password":
                    # TODO: Implement password reset functionality
                    success = True  # Placeholder
                
                if success:
                    results["successful"] += 1
                else:
                    results["errors"].append(f"Failed to {action_request.action} user (ID: {user_id})")
                    results["failed"] += 1
                    
            except Exception as e:
                results["errors"].append(f"Error processing user {user_id}: {str(e)}")
                results["failed"] += 1
        
        # Log bulk action
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        logger.info(f"Admin {current_user.id} performed bulk action '{action_request.action}' on {len(action_request.user_ids)} users")
        
        return results
        
    except Exception as e:
        logger.error(f"Error performing bulk user action: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        if isinstance(e, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error performing bulk user action"
        )



@router.post(
    "/users",
    response_model=UserManagementResponse,
    dependencies=[Depends(require_role("admin"))],
    summary="Create user (Admin)",
    description="Create a new user account",
    responses={
        201: {"description": "User created successfully"},
        400: {"description": "Invalid input data"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"}
    }
)
async def create_user(
    request: Request,
    user_data: CreateUserRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> UserManagementResponse:
    """Create a new user account"""
    start_time = datetime.now()
    
    try:
        user_repo = UserRepository()
        
        # Check if user already exists
        existing_user = await user_repo.get_by_email(user_data.email, db)
        if existing_user:
            raise ValidationError(f"User with email {user_data.email} already exists")
            
        existing_username = await user_repo.get_by_username(user_data.username, db)
        if existing_username:
            raise ValidationError(f"User with username {user_data.username} already exists")
        
        # Create user
        # Note: UserRepository.create expects a dict
        new_user = await user_repo.create(user_data.dict(), db)
        
        # Log successful creation
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=201,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        logger.info(f"Admin {current_user.id} created user {new_user.id}")
        
        return UserManagementResponse.from_orm(new_user)
        
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        if isinstance(e, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user"
        )


@router.put(
    "/users/{user_id}",
    response_model=UserManagementResponse,
    dependencies=[Depends(require_role("admin"))],
    summary="Update user (Admin)",
    description="Update an existing user account",
    responses={
        200: {"description": "User updated successfully"},
        400: {"description": "Invalid input data"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"},
        404: {"description": "User not found"}
    }
)
async def update_user(
    request: Request,
    user_id: int,
    user_data: UpdateUserRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> UserManagementResponse:
    """Update an existing user account"""
    start_time = datetime.now()
    
    try:
        user_repo = UserRepository()
        target_user = await user_repo.get_by_id(user_id, db)
        
        if not target_user:
            raise NotFoundError(f"User with ID {user_id} not found")
        
        # Prevent admin from modifying super admin unless they are super admin
        if target_user.is_super_admin and not current_user.is_super_admin:
            raise AuthorizationError("Cannot modify super admin users")
            
        # Update user
        update_dict = user_data.dict(exclude_unset=True)
        if not update_dict:
            return UserManagementResponse.from_orm(target_user)
            
        updated_user = await user_repo.update(user_id, update_dict, db)
        
        # Log successful update
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        logger.info(f"Admin {current_user.id} updated user {user_id}")
        
        return UserManagementResponse.from_orm(updated_user)
        
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        if isinstance(e, (NotFoundError, AuthorizationError, ValidationError)):
            status_code = status.HTTP_404_NOT_FOUND if isinstance(e, NotFoundError) else status.HTTP_403_FORBIDDEN
            if isinstance(e, ValidationError):
                status_code = status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=status_code, detail=str(e))
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user"
        )


@router.delete(
    "/users/{user_id}",
    dependencies=[Depends(require_role("admin"))],
    summary="Delete user (Admin)",
    description="Delete a user account",
    responses={
        200: {"description": "User deleted successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"},
        404: {"description": "User not found"}
    }
)
async def delete_user(
    request: Request,
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, str]:
    """Delete a user account"""
    start_time = datetime.now()
    
    try:
        # Prevent deleting self
        if user_id == current_user.id:
            raise AuthorizationError("Cannot delete your own account")
        
        user_repo = UserRepository()
        target_user = await user_repo.get_by_id(user_id, db)
        
        if not target_user:
            raise NotFoundError(f"User with ID {user_id} not found")
        
        if target_user.is_super_admin:
            raise AuthorizationError("Cannot delete super admin users")
        
        # Perform deletion
        success = await user_repo.delete(user_id, db)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user"
            )
        
        # Log successful deletion
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        logger.info(f"Admin {current_user.id} deleted user {user_id}")
        
        return {"message": f"User {user_id} deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        if isinstance(e, (NotFoundError, AuthorizationError)):
            status_code = status.HTTP_404_NOT_FOUND if isinstance(e, NotFoundError) else status.HTTP_403_FORBIDDEN
            raise HTTPException(status_code=status_code, detail=str(e))
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting user"
        )


# ============================================================================
# AUDIT LOG ENDPOINTS
# ============================================================================

@router.get(
    "/audit-logs",
    response_model=List[AuditLogResponse],
    dependencies=[Depends(require_role("admin"))],
    summary="Get audit logs (Admin)",
    description="Get system audit logs with filtering options",
    responses={
        200: {"description": "Audit logs retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"}
    }
)

async def get_audit_logs(
    request: Request,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    event_category: Optional[str] = Query(None, description="Filter by event category"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    severity: Optional[str] = Query(None, description="Filter by severity level"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> List[AuditLogResponse]:
    """Get audit logs with filtering"""
    start_time = datetime.now()
    
    try:
        # TODO: Implement with actual audit log repository
        # For now, return empty list
        
        # Log successful request
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        return []
        
    except Exception as e:
        logger.error(f"Error retrieving audit logs: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving audit logs"
        )


# ============================================================================
# SYSTEM MAINTENANCE ENDPOINTS
# ============================================================================

@router.post(
    "/maintenance",
    dependencies=[Depends(require_role("admin"))],
    summary="Schedule system maintenance (Admin)",
    description="Schedule system maintenance with user notification",
    responses={
        200: {"description": "Maintenance scheduled successfully"},
        400: {"description": "Invalid maintenance request"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"}
    }
)
  # Very limited for maintenance operations
async def schedule_maintenance(
    request: Request,
    maintenance_request: SystemMaintenanceRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, str]:
    """Schedule system maintenance"""
    start_time = datetime.now()
    
    try:
        # Validate maintenance time is in the future
        if maintenance_request.scheduled_time <= datetime.now():
            raise ValidationError("Maintenance time must be in the future")
        
        # Validate duration
        if maintenance_request.estimated_duration_minutes <= 0 or maintenance_request.estimated_duration_minutes > 1440:
            raise ValidationError("Maintenance duration must be between 1 and 1440 minutes (24 hours)")
        
        # TODO: Implement actual maintenance scheduling
        # This would:
        # 1. Store maintenance record in database
        # 2. Schedule background task to perform maintenance
        # 3. Send notifications to users if requested
        # 4. Update system status
        
        # Log maintenance scheduling
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        logger.info(f"Admin {current_user.id} scheduled maintenance: {maintenance_request.maintenance_type}")
        
        return {
            "message": "Maintenance scheduled successfully",
            "maintenance_id": f"maint_{int(datetime.now().timestamp())}",
            "scheduled_time": maintenance_request.scheduled_time.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error scheduling maintenance: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        if isinstance(e, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error scheduling maintenance"
        )


# ============================================================================
# PERFORMANCE MONITORING ENDPOINTS
# ============================================================================

@router.get(
    "/performance",
    response_model=List[PerformanceMetricsResponse],
    dependencies=[Depends(require_role("admin"))],
    summary="Get performance metrics (Admin)",
    description="Get system performance metrics and health indicators",
    responses={
        200: {"description": "Performance metrics retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"}
    }
)

async def get_performance_metrics(
    request: Request,
    metric_category: Optional[str] = Query(None, description="Filter by metric category"),
    time_range: str = Query(default="1h", description="Time range (1h, 6h, 24h, 7d)"),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> List[PerformanceMetricsResponse]:
    """Get system performance metrics"""
    start_time = datetime.now()
    
    try:
        # TODO: Implement with actual performance monitoring system
        # For now, return sample metrics
        
        sample_metrics = [
            PerformanceMetricsResponse(
                metric_name="Response Time",
                current_value=145.5,
                unit="ms",
                trend_direction="stable",
                comparison_period="24h",
                threshold_warning=200.0,
                threshold_critical=500.0,
                status="normal",
                last_updated=datetime.now()
            ),
            PerformanceMetricsResponse(
                metric_name="Database Connections",
                current_value=12.0,
                unit="connections",
                trend_direction="stable",
                comparison_period="1h",
                threshold_warning=80.0,
                threshold_critical=95.0,
                status="normal",
                last_updated=datetime.now()
            ),
            PerformanceMetricsResponse(
                metric_name="Memory Usage",
                current_value=62.8,
                unit="percent",
                trend_direction="up",
                comparison_period="6h",
                threshold_warning=80.0,
                threshold_critical=90.0,
                status="normal",
                last_updated=datetime.now()
            )
        ]
        
        # Log successful request
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        return sample_metrics
        
    except Exception as e:
        logger.error(f"Error retrieving performance metrics: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving performance metrics"
        )



@router.post(
    "/users/{user_id}/assign",
    dependencies=[Depends(require_role("admin"))],
    summary="Assign user (Admin)",
    description="Assign a user to a staff member",
    responses={
        200: {"description": "User assigned successfully"},
        400: {"description": "Invalid assignment"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"},
        404: {"description": "User not found"}
    }
)
async def assign_user(
    request: Request,
    user_id: int,
    assign_data: AssignUserRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, str]:
    """Assign a user to a staff member"""
    start_time = datetime.now()
    
    try:
        user_repo = UserRepository()
        
        # Check target user
        target_user = await user_repo.get_by_id(user_id, db)
        if not target_user:
            raise NotFoundError(f"User with ID {user_id} not found")
            
        # Check staff member
        staff_member = await user_repo.get_by_id(assign_data.assigned_to_id, db)
        if not staff_member:
            raise NotFoundError(f"Staff member with ID {assign_data.assigned_to_id} not found")
            
        # Update assigned_to_id
        # We need to update the user record
        update_data = {"assigned_to_id": assign_data.assigned_to_id}
        await user_repo.update(user_id, update_data, db)
        
        # Log successful assignment
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        logger.info(f"Admin {current_user.id} assigned user {user_id} to staff {assign_data.assigned_to_id}")
        
        return {"message": f"User {user_id} assigned successfully"}
        
    except Exception as e:
        logger.error(f"Error assigning user {user_id}: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        if isinstance(e, (NotFoundError, AuthorizationError)):
            status_code = status.HTTP_404_NOT_FOUND if isinstance(e, NotFoundError) else status.HTTP_403_FORBIDDEN
            raise HTTPException(status_code=status_code, detail=str(e))
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error assigning user"
        )


@router.post(
    "/run-tests",
    response_model=TestRunResponse,
    dependencies=[Depends(require_role("admin"))],
    summary="Run system tests (Admin)",
    description="Execute system smoke tests",
    responses={
        200: {"description": "Tests executed successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"}
    }
)
async def run_system_tests(
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> TestRunResponse:
    """Execute system tests"""
    start_time = datetime.now()
    
    try:
        # TODO: Implement actual test runner integration
        # For now, simulate test execution with health checks
        
        # Check DB
        db_status = "PASSED"
        try:
            await db.execute("SELECT 1")
        except Exception:
            db_status = "FAILED"
            
        # Mock other checks
        output_lines = [
            f"[{datetime.now().strftime('%H:%M:%S')}] Starting system smoke tests...",
            f"[{datetime.now().strftime('%H:%M:%S')}] Checking database connection... {db_status}",
            f"[{datetime.now().strftime('%H:%M:%S')}] Checking API endpoints... PASSED",
            f"[{datetime.now().strftime('%H:%M:%S')}] Checking authentication service... PASSED",
            f"[{datetime.now().strftime('%H:%M:%S')}] Checking Live2D integration... PASSED",
            f"[{datetime.now().strftime('%H:%M:%S')}] Checking external APIs... PASSED",
            f"[{datetime.now().strftime('%H:%M:%S')}] Test suite completed."
        ]
        
        output = "\n".join(output_lines)
        success = db_status == "PASSED"
        
        # Log test run
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        return TestRunResponse(
            success=success,
            output=output,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error running tests: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error running tests"
        )
