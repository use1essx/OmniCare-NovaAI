"""
Hierarchical Permission System for Healthcare AI
Implements role-based access control with organization and patient assignment support
"""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

from src.database.models_comprehensive import User

logger = logging.getLogger(__name__)

# =============================================================================
# Role Hierarchy Definitions
# =============================================================================

ROLE_HIERARCHY = {
    'super_admin': 100,      # Platform administrator - sees everything
    'admin': 50,             # Organization administrator - sees their org
    'doctor': 30,            # Caregiver - sees assigned patients
    'nurse': 30,             # Caregiver - sees assigned patients
    'social_worker': 30,     # Caregiver - sees assigned patients
    'counselor': 30,         # Caregiver - sees assigned patients
    'staff': 20,             # Staff - limited access
    'user': 10,              # Patient - sees only self
}

CAREGIVER_ROLES = ['doctor', 'nurse', 'social_worker', 'counselor']
ORG_ADMIN_ROLES = ['admin']
PLATFORM_ADMIN_ROLES = ['super_admin']

# =============================================================================
# Permission Check Functions
# =============================================================================

def is_super_admin(user: User) -> bool:
    """Check if user is super admin"""
    return (
        user.role == 'super_admin' or 
        getattr(user, 'is_super_admin', False)
    )

def is_org_admin(user: User) -> bool:
    """Check if user is organization admin"""
    return user.role == 'admin'

def is_caregiver(user: User) -> bool:
    """Check if user is a caregiver (doctor, nurse, social worker, counselor)"""
    return user.role in CAREGIVER_ROLES

def is_patient(user: User) -> bool:
    """Check if user is a patient/regular user"""
    return user.role == 'user'

def get_role_level(role: str) -> int:
    """Get numeric level for role"""
    return ROLE_HIERARCHY.get(role, 0)

def can_manage_user(current_user: User, target_user: User) -> bool:
    """
    Check if current_user can manage target_user
    
    Rules:
    - Super admins can manage anyone
    - Org admins can manage users in their organization
    - Caregivers can manage patients assigned to them
    - Users can only manage themselves
    """
    # Can always manage yourself
    if current_user.id == target_user.id:
        return True
    
    # Super admins can manage anyone
    if is_super_admin(current_user):
        return True
    
    # Org admins can manage users in their organization
    if is_org_admin(current_user):
        if current_user.organization_id and current_user.organization_id == target_user.organization_id:
            return True
    
    # Caregivers can manage their assigned patients
    if is_caregiver(current_user):
        if target_user.assigned_caregiver_id == current_user.id:
            return True
    
    return False

# =============================================================================
# User Filtering for Lists
# =============================================================================

async def get_accessible_user_ids(
    db: AsyncSession,
    current_user: User
) -> Optional[List[int]]:
    """
    Get list of user IDs that current_user can access.
    Returns None for super admins (can see all).
    
    Returns:
        None if user can see all users (super admin)
        List of user IDs if user has limited access
        Empty list if user can only see themselves
    """
    # Super admins see everything
    if is_super_admin(current_user):
        return None  # None means "all users"
    
    accessible_ids = set([current_user.id])  # Always see yourself
    
    # Org admins see all users in their organization
    if is_org_admin(current_user) and current_user.organization_id:
        result = await db.execute(
            text("SELECT id FROM users WHERE organization_id = :org_id"),
            {"org_id": current_user.organization_id}
        )
        for row in result:
            accessible_ids.add(row[0])
    
    # Caregivers see their assigned patients
    if is_caregiver(current_user):
        result = await db.execute(
            text("SELECT id FROM users WHERE assigned_caregiver_id = :caregiver_id"),
            {"caregiver_id": current_user.id}
        )
        for row in result:
            accessible_ids.add(row[0])
    
    return list(accessible_ids)

async def filter_users_by_access(
    db: AsyncSession,
    current_user: User,
    base_query: str = "SELECT * FROM users"
) -> str:
    """
    Modify SQL query to filter users based on current_user's access level.
    
    Args:
        db: Database session
        current_user: Current logged-in user
        base_query: Base SQL query (should select from users table)
    
    Returns:
        Modified SQL query with WHERE clause for access control
    """
    # Super admins see everything - no filtering needed
    if is_super_admin(current_user):
        return base_query
    
    accessible_ids = await get_accessible_user_ids(db, current_user)
    
    if not accessible_ids:
        # User has no access to any users - return query that returns nothing
        return f"{base_query} WHERE 1=0"
    
    # Build WHERE clause with accessible user IDs
    ids_str = ','.join(str(uid) for uid in accessible_ids)
    
    # Check if query already has WHERE clause
    if 'WHERE' in base_query.upper():
        return f"{base_query} AND users.id IN ({ids_str})"
    else:
        return f"{base_query} WHERE users.id IN ({ids_str})"

# =============================================================================
# Organization Filtering
# =============================================================================

async def get_accessible_organization_ids(
    db: AsyncSession,
    current_user: User
) -> Optional[List[int]]:
    """
    Get list of organization IDs that current_user can access.
    Returns None for super admins (can see all).
    """
    # Super admins see all organizations
    if is_super_admin(current_user):
        return None
    
    # Org admins see only their organization
    if is_org_admin(current_user) and current_user.organization_id:
        return [current_user.organization_id]
    
    # Caregivers and patients see their organization if they have one
    if current_user.organization_id:
        return [current_user.organization_id]
    
    return []

# =============================================================================
# Permission Helpers for API Endpoints
# =============================================================================

async def can_create_user_in_org(
    db: AsyncSession,
    current_user: User,
    target_org_id: Optional[int],
    target_role: str
) -> tuple[bool, Optional[str]]:
    """
    Check if current_user can create a user with target_role in target_org_id.
    
    Returns:
        (can_create: bool, error_message: Optional[str])
    """
    # Super admins can create anyone anywhere
    if is_super_admin(current_user):
        return (True, None)
    
    # Cannot create super admins
    if target_role == 'super_admin':
        return (False, "Only super admins can create super admin accounts")
    
    # Org admins can create users in their organization only
    if is_org_admin(current_user):
        if not current_user.organization_id:
            return (False, "Organization admin must belong to an organization")
        
        if target_org_id != current_user.organization_id:
            return (False, "Cannot create users in other organizations")
        
        return (True, None)
    
    # Caregivers can create patients assigned to themselves
    if is_caregiver(current_user):
        if target_role != 'user':
            return (False, "Caregivers can only create patient accounts")
        
        if target_org_id and target_org_id != current_user.organization_id:
            return (False, "Cannot create users in other organizations")
        
        return (True, None)
    
    # Regular users cannot create accounts
    return (False, "Insufficient permissions to create users")

async def can_assign_caregiver(
    db: AsyncSession,
    current_user: User,
    patient_id: int,
    caregiver_id: int
) -> tuple[bool, Optional[str]]:
    """
    Check if current_user can assign caregiver_id to patient_id.
    
    Returns:
        (can_assign: bool, error_message: Optional[str])
    """
    # Super admins can assign anyone
    if is_super_admin(current_user):
        return (True, None)
    
    # Get patient and caregiver info
    result = await db.execute(
        text("""
            SELECT id, role, organization_id, assigned_caregiver_id 
            FROM users 
            WHERE id IN (:patient_id, :caregiver_id)
        """),
        {"patient_id": patient_id, "caregiver_id": caregiver_id}
    )
    
    users = {row[0]: {"role": row[1], "org_id": row[2], "caregiver_id": row[3]} for row in result}
    
    if patient_id not in users or caregiver_id not in users:
        return (False, "Patient or caregiver not found")
    
    patient = users[patient_id]
    caregiver = users[caregiver_id]
    
    # Patient must be a 'user' role
    if patient["role"] != 'user':
        return (False, "Can only assign caregivers to patients")
    
    # Caregiver must be caregiver role
    if caregiver["role"] not in CAREGIVER_ROLES:
        return (False, "Assigned user must be a caregiver (doctor, nurse, social worker, counselor)")
    
    # Org admins can assign within their organization
    if is_org_admin(current_user):
        if patient["org_id"] != current_user.organization_id:
            return (False, "Patient not in your organization")
        if caregiver["org_id"] != current_user.organization_id:
            return (False, "Caregiver not in your organization")
        return (True, None)
    
    # Caregivers can reassign their own patients to other caregivers in same org
    if is_caregiver(current_user):
        if patient["caregiver_id"] != current_user.id:
            return (False, "Patient not assigned to you")
        if caregiver["org_id"] != current_user.organization_id:
            return (False, "Cannot assign to caregiver in different organization")
        return (True, None)
    
    return (False, "Insufficient permissions to assign caregivers")

# =============================================================================
# Export all functions
# =============================================================================

__all__ = [
    'is_super_admin',
    'is_org_admin',
    'is_caregiver',
    'is_patient',
    'get_role_level',
    'can_manage_user',
    'get_accessible_user_ids',
    'filter_users_by_access',
    'get_accessible_organization_ids',
    'can_create_user_in_org',
    'can_assign_caregiver',
    'ROLE_HIERARCHY',
    'CAREGIVER_ROLES',
    'ORG_ADMIN_ROLES',
    'PLATFORM_ADMIN_ROLES',
]

