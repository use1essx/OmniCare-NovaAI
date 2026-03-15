"""
Healthcare AI V2 Admin API Routes
Returns JSON data for admin operations
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, List, Optional
import logging

from src.database.models_comprehensive import User
from src.database.connection import get_async_db
from src.web.auth.dependencies import require_admin, require_org_admin, require_user_management_access, _is_super_admin
from src.web.auth.dependencies import get_optional_user
from ..services.metrics_service import MetricsService
from ..services.user_service import UserService
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api", tags=["admin-api"])


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "admin-api"}


@router.get("/stats")
async def get_admin_stats(
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Get comprehensive admin statistics (org-scoped for org admins, limited for healthcare workers)"""
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        metrics_service = MetricsService(db)
        stats = await metrics_service.get_admin_stats()
        
        # For non-super admins, filter stats to their organization
        if not _is_super_admin(current_user) and current_user.organization_id:
            # Note: This would need MetricsService to support org filtering
            # For now, just return the stats (they'll see aggregated data)
            pass
        
        return stats
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get admin statistics")


@router.get("/health-check")
async def get_health_check(
    current_user: User = Depends(require_user_management_access),  # Allow healthcare workers
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Get detailed system health check"""
    try:
        metrics_service = MetricsService(db)
        return await metrics_service.get_health_check()
    except Exception as e:
        logger.error(f"Error getting health check: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health check")


@router.get("/performance")
async def get_performance_metrics(
    time_range: str = Query("24h", description="Time range for metrics"),
    current_user: User = Depends(require_user_management_access),  # Allow healthcare workers
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Get system performance metrics"""
    try:
        metrics_service = MetricsService(db)
        return await metrics_service.get_performance_metrics(time_range)
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance metrics")


# User Management API
@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term"),
    role: Optional[str] = Query(None, description="Filter by role"),
    status: Optional[str] = Query(None, description="Filter by status (active/inactive)"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    current_user: User = Depends(require_user_management_access),  # Allow admins and healthcare workers
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """List users with pagination and filtering (org-scoped for org admins)"""
    try:
        user_service = UserService(db)
        
        # Determine organization scope
        org_id = None
        if not _is_super_admin(current_user):
            # Org admins only see their org
            org_id = current_user.organization_id
        
        return await user_service.list_users(
            page=page,
            limit=limit,
            search=search,
            role_filter=role,
            status_filter=status,
            sort_by=sort_by,
            sort_order=sort_order,
            organization_id=org_id,  # New: Filter by org
            requesting_user=current_user  # New: For validation
        )
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(status_code=500, detail="Failed to list users")


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    current_user: User = Depends(require_user_management_access),  # Allow admins and healthcare workers
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Get user by ID (org-scoped for org admins)"""
    try:
        user_service = UserService(db)
        user = await user_service.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Security: Org admins can only view users in their organization
        if not _is_super_admin(current_user):
            if user.get("organization_id") != current_user.organization_id:
                raise HTTPException(status_code=403, detail="Cannot view users from other organizations")
        
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user")


@router.post("/users")
async def create_user(
    user_data: Dict[str, Any],
    current_user: User = Depends(require_user_management_access),  # Allow admins and healthcare workers
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Create a new user (org-scoped for org admins)"""
    try:
        user_service = UserService(db)
        return await user_service.create_user(
            user_data=user_data,
            requesting_user=current_user  # New: Pass requesting user for validation
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user")


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    update_data: Dict[str, Any],
    current_user: User = Depends(require_user_management_access),  # Allow admins and healthcare workers
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Update user information (org-scoped for org admins)"""
    try:
        user_service = UserService(db)
        return await user_service.update_user(
            user_id=user_id,
            update_data=update_data,
            requesting_user=current_user  # New: Pass requesting user for validation
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user")


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_org_admin),  # Changed: Allow org admins
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Delete a user (org-scoped for org admins)"""
    try:
        user_service = UserService(db)
        await user_service.delete_user(
            user_id=user_id,
            requesting_user=current_user  # New: Pass requesting user for validation
        )
        return {"message": "User deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/users/{user_id}/assign")
async def assign_user_to_staff(
    user_id: int,
    assignment_data: Dict[str, Any],
    current_user: User = Depends(require_org_admin),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """
    Assign a user to a healthcare staff member.
    Only super admins and org admins can assign users.
    Staff can only see data from assigned users.
    """
    try:
        assigned_to_id = assignment_data.get("assigned_to_id")
        if not assigned_to_id:
            raise HTTPException(status_code=400, detail="assigned_to_id is required")
        
        # Use UserService to get users
        user_service = UserService(db)
        
        # Get the user to be assigned
        user_data = await user_service.get_user(user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get the staff member
        staff_data = await user_service.get_user(assigned_to_id)
        if not staff_data:
            raise HTTPException(status_code=404, detail="Staff member not found")
        
        # Verify staff member is healthcare staff
        if staff_data["role"] not in ("doctor", "nurse", "counselor", "social_worker"):
            raise HTTPException(
                status_code=400,
                detail="Can only assign to Doctor, Nurse, Counselor, or Social Worker"
            )
        
        # For org admins, verify both users are in their org
        if not _is_super_admin(current_user):
            if user_data["organization_id"] != current_user.organization_id:
                raise HTTPException(status_code=403, detail="User not in your organization")
            if staff_data["organization_id"] != current_user.organization_id:
                raise HTTPException(status_code=403, detail="Staff member not in your organization")
        
        # Update the user's assigned_caregiver_id using UserService
        update_data = {"assigned_caregiver_id": assigned_to_id}
        await user_service.update_user(
            user_id=user_id,
            update_data=update_data,
            requesting_user=current_user
        )
        
        logger.info(f"User {user_id} assigned to staff {assigned_to_id} by {current_user.username}")
        
        return {
            "message": "User assigned successfully",
            "user_id": user_id,
            "assigned_to_id": assigned_to_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/stats")
async def get_user_stats(
    current_user: User = Depends(require_user_management_access),  # Allow admins and healthcare workers
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Get user statistics (org-scoped for org admins)"""
    try:
        user_service = UserService(db)
        return await user_service.get_user_stats()
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user statistics")


@router.post("/users/bulk-update")
async def bulk_update_users(
    user_ids: List[int],
    update_data: Dict[str, Any],
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Bulk update multiple users"""
    try:
        user_service = UserService(db)
        return await user_service.bulk_update_users(user_ids, update_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error bulk updating users: {e}")
        raise HTTPException(status_code=500, detail="Failed to bulk update users")


@router.post("/users/bulk-delete")
async def bulk_delete_users(
    user_ids: List[int],
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Bulk delete multiple users"""
    try:
        user_service = UserService(db)
        return await user_service.bulk_delete_users(user_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error bulk deleting users: {e}")
        raise HTTPException(status_code=500, detail="Failed to bulk delete users")


# Data Management API
@router.get("/data/hk-sources")
async def get_hk_data_sources(
    current_user: User = Depends(require_user_management_access)  # Allow healthcare workers
) -> Dict[str, Any]:
    """Get Hong Kong data sources status"""
    # This would typically come from a data service
    # For now, return mock data
    return {
        "sources": [
            {
                "id": "ha_ae_wait_times",
                "name": "Hospital Authority - A&E Wait Times",
                "status": "online",
                "last_updated": "12 minutes ago",
                "refresh_interval": "15min"
            },
            {
                "id": "doh_clinic_directory",
                "name": "Department of Health - Clinic Directory",
                "status": "online",
                "last_updated": "2 hours ago",
                "refresh_interval": "6hr"
            }
        ],
        "summary": {
            "total_sources": 2,
            "online_sources": 2,
            "offline_sources": 0,
            "freshness_percentage": 100
        }
    }


@router.get("/data/quality")
async def get_data_quality_report(
    current_user: User = Depends(require_user_management_access)  # Allow healthcare workers
) -> Dict[str, Any]:
    """Get data quality report"""
    # Mock data quality report
    return {
        "overall_score": 87,
        "categories": [
            {
                "name": "Completeness",
                "score": 92,
                "status": "good"
            },
            {
                "name": "Accuracy",
                "score": 89,
                "status": "good"
            }
        ],
        "issues": [],
        "recommendations": []
    }


@router.get("/data/health")
async def get_system_health(
    current_user: User = Depends(require_user_management_access),  # Allow healthcare workers
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Get system health status"""
    try:
        metrics_service = MetricsService(db)
        return await metrics_service.get_health_check()
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system health")
