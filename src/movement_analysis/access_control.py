"""
Healthcare AI V2 - Movement Analysis Access Control
Assignment-based access control for movement analysis history and data
"""

import logging
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models_comprehensive import User
from .models import Assessment

logger = logging.getLogger(__name__)


def is_super_admin(user: User) -> bool:
    """Check if user is a super admin"""
    return (
        getattr(user, "is_super_admin", False) or 
        (getattr(user, "role", "") or "").lower() == "super_admin"
    )


def is_org_admin(user: User) -> bool:
    """Check if user is an organization admin"""
    if is_super_admin(user):
        return True
    return (
        getattr(user, "is_admin", False) and 
        getattr(user, "organization_id", None) is not None
    )


def is_healthcare_staff(user: User) -> bool:
    """Check if user is healthcare staff (can have assigned patients)"""
    role = (getattr(user, "role", "") or "").lower()
    return role in ("doctor", "nurse", "counselor", "social_worker")


async def can_view_assessment(
    current_user: User,
    assessment: Assessment,
    db: AsyncSession
) -> bool:
    """
    Check if current user can view a specific assessment
    
    Access Rules:
    1. User can view their own assessments
    2. Super admin can view all assessments
    3. Org admin can view assessments within their organization
    4. Assigned staff can view assessments of users assigned to them
    
    Args:
        current_user: The user requesting access
        assessment: The assessment to check access for
        db: Database session
        
    Returns:
        True if access is allowed, False otherwise
    """
    if not current_user or not assessment:
        return False
    
    # Rule 1: User can view their own assessments
    if current_user.id == assessment.user_id:
        logger.debug(f"Access granted: User {current_user.id} viewing own assessment {assessment.id}")
        return True
    
    # Rule 2: Super admin can view all
    if is_super_admin(current_user):
        logger.debug(f"Access granted: Super admin {current_user.id} viewing assessment {assessment.id}")
        return True
    
    # Rule 3: Org admin can view assessments within their organization
    if is_org_admin(current_user):
        if current_user.organization_id == assessment.organization_id:
            logger.debug(f"Access granted: Org admin {current_user.id} viewing org assessment {assessment.id}")
            return True
    
    # Rule 4: Assigned staff can view assessments of users assigned to them
    if is_healthcare_staff(current_user):
        # Get the assessment owner
        from src.database.repositories.user_repository import UserRepository
        user_repo = UserRepository()
        target_user = await user_repo.get_by_id(assessment.user_id)
        
        if target_user:
            # Check if current user is the assigned caregiver
            assigned_caregiver_id = getattr(target_user, "assigned_caregiver_id", None)
            if assigned_caregiver_id == current_user.id:
                logger.debug(f"Access granted: Assigned staff {current_user.id} viewing assessment {assessment.id}")
                return True
            
            # Also check assigned_to_id for backward compatibility
            assigned_to_id = getattr(target_user, "assigned_to_id", None)
            if assigned_to_id == current_user.id:
                logger.debug(f"Access granted: Assigned staff {current_user.id} viewing assessment {assessment.id}")
                return True
    
    logger.debug(f"Access denied: User {current_user.id} cannot view assessment {assessment.id}")
    return False


async def can_view_user_assessments(
    current_user: User,
    target_user_id: int,
    db: AsyncSession
) -> bool:
    """
    Check if current user can view assessments for a specific user
    
    Args:
        current_user: The user requesting access
        target_user_id: ID of the user whose assessments are being accessed
        db: Database session
        
    Returns:
        True if access is allowed, False otherwise
    """
    if not current_user:
        return False
    
    # User can view their own assessments
    if current_user.id == target_user_id:
        return True
    
    # Super admin can view all
    if is_super_admin(current_user):
        return True
    
    # Get target user to check organization and assignment
    from src.database.repositories.user_repository import UserRepository
    user_repo = UserRepository()
    target_user = await user_repo.get_by_id(target_user_id)
    
    if not target_user:
        return False
    
    # Org admin can view users in their organization
    if is_org_admin(current_user):
        target_org_id = getattr(target_user, "organization_id", None)
        if current_user.organization_id == target_org_id:
            return True
    
    # Healthcare staff can view assigned users
    if is_healthcare_staff(current_user):
        assigned_caregiver_id = getattr(target_user, "assigned_caregiver_id", None)
        assigned_to_id = getattr(target_user, "assigned_to_id", None)
        
        if assigned_caregiver_id == current_user.id or assigned_to_id == current_user.id:
            return True
    
    return False


def get_assessment_query_filter(
    current_user: User,
    base_query,
    user_model: type = User
):
    """
    Apply access control filters to an assessment query
    
    This function adds WHERE clauses to filter assessments based on user's access level.
    
    Args:
        current_user: The user making the query
        base_query: SQLAlchemy query to filter
        user_model: User model class (for joins)
        
    Returns:
        Filtered query
    """
    from .models import Assessment
    
    # Super admin sees everything
    if is_super_admin(current_user):
        return base_query
    
    # Org admin sees their organization's assessments
    if is_org_admin(current_user):
        return base_query.where(Assessment.organization_id == current_user.organization_id)
    
    # Healthcare staff sees their own + assigned users' assessments
    if is_healthcare_staff(current_user):
        # This requires a more complex query with a subquery for assigned users
        from sqlalchemy import or_
        
        # Get IDs of users assigned to this staff member
        assigned_users_subquery = (
            select(User.id)
            .where(
                or_(
                    User.assigned_caregiver_id == current_user.id,
                    User.assigned_to_id == current_user.id
                )
            )
        )
        
        return base_query.where(
            or_(
                Assessment.user_id == current_user.id,  # Own assessments
                Assessment.user_id.in_(assigned_users_subquery)  # Assigned users' assessments
            )
        )
    
    # Regular users only see their own assessments
    return base_query.where(Assessment.user_id == current_user.id)


def can_manage_assessment_rules(user: User) -> bool:
    """
    Check if user can create/edit/delete assessment rules
    
    Allowed roles:
    - Super admin
    - Org admin
    - Social worker
    - Counselor
    
    Args:
        user: User to check
        
    Returns:
        True if user can manage rules
    """
    if not user:
        return False
    
    if is_super_admin(user):
        return True
    
    if is_org_admin(user):
        return True
    
    role = (getattr(user, "role", "") or "").lower()
    return role in ("social_worker", "counselor")


def can_view_staff_report(user: User, assessment: Assessment) -> bool:
    """
    Check if user can view the staff/professional report for an assessment
    
    Staff report is only visible to:
    - Super admin
    - Org admin (within their org)
    - Healthcare staff (for assigned users or their own assessments)
    
    Args:
        user: User requesting access
        assessment: Assessment to check
        
    Returns:
        True if user can view staff report
    """
    if not user or not assessment:
        return False
    
    # Super admin always sees staff view
    if is_super_admin(user):
        return True
    
    # Org admin sees staff view for their org
    if is_org_admin(user):
        return user.organization_id == assessment.organization_id
    
    # Healthcare staff sees staff view
    if is_healthcare_staff(user):
        return True
    
    # Regular users/parents don't see staff view
    return False


async def get_accessible_user_ids(
    current_user: User,
    db: AsyncSession
) -> Optional[List[int]]:
    """
    Get list of user IDs whose assessments the current user can access
    
    Returns None if user can access all (super admin)
    Returns list of specific user IDs for scoped access
    
    Args:
        current_user: User requesting access
        db: Database session
        
    Returns:
        None for full access, or list of accessible user IDs
    """
    # Super admin can access all
    if is_super_admin(current_user):
        return None
    
    accessible_ids = [current_user.id]  # Always include self
    
    # Org admin can access all users in their org
    if is_org_admin(current_user) and current_user.organization_id:
        result = await db.execute(
            select(User.id).where(User.organization_id == current_user.organization_id)
        )
        org_user_ids = [row[0] for row in result.fetchall()]
        accessible_ids.extend(org_user_ids)
    
    # Healthcare staff can access assigned users
    elif is_healthcare_staff(current_user):
        from sqlalchemy import or_
        result = await db.execute(
            select(User.id).where(
                or_(
                    User.assigned_caregiver_id == current_user.id,
                    User.assigned_to_id == current_user.id
                )
            )
        )
        assigned_user_ids = [row[0] for row in result.fetchall()]
        accessible_ids.extend(assigned_user_ids)
    
    return list(set(accessible_ids))  # Remove duplicates

