"""
Healthcare AI V2 Admin Permissions Configuration
Permission definitions and checking logic
"""

from typing import Dict

from src.database.models_comprehensive import User
from src.security.permissions import PermissionContext, PermissionDenied, PermissionService
from src.security.permissions.adapters import build_actor_from_user

PERMISSION_CODE_MAP = {
    # view_dashboard uses legacy fallback for healthcare workers
    "manage_users": "user.create",  # Super admin - manage all users
    "manage_org_users": "user.view.org",  # Org admin - manage own org users
    "create_org_users": "user.create.org",  # Org admin - create users in org
    "manage_organizations": "organization.edit",
    # view_data_management and manage_data use legacy fallback for healthcare workers
    "view_analytics": "analytics.view",
    "manage_analytics": "analytics.manage",
    # Note: view_system, manage_system, view_live2d, view_testing, view_ai_agents, 
    # view_dashboard, view_data_management, manage_data use legacy fallback
}


def check_permission(user: User, permission: str) -> bool:
    """
    Check if user has the specified permission
    """
    if not user:
        return False

    if _is_super_admin(user):
        return True

    permission_code = PERMISSION_CODE_MAP.get(permission)
    if permission_code:
        actor = build_actor_from_user(user)
        context = PermissionContext(organization_id=getattr(user, "organization_id", None))
        try:
            return PermissionService.can(actor, permission_code, context)
        except PermissionDenied:
            # Don't return False here - fall through to legacy permissions check
            pass
        except Exception:
            # Fallback to legacy matrix if service is unavailable
            pass

    permissions = get_user_permissions(user)
    return permissions.get(permission, False)


def get_user_permissions(user: User) -> Dict[str, bool]:
    """
    Get all permissions for a user
    """
    if not user:
        return {}

    if _is_super_admin(user):
        perms = _super_admin_permissions()
        perms["is_super_admin"] = True
        perms["is_admin"] = True
        return perms

    permissions = _legacy_permissions(user)
    actor = build_actor_from_user(user)
    context = PermissionContext(organization_id=getattr(user, "organization_id", None))

    for key, permission_code in PERMISSION_CODE_MAP.items():
        try:
            PermissionService.can(actor, permission_code, context)
            permissions[key] = True
        except PermissionDenied:
            # Only set to False if legacy didn't already grant it
            if not permissions.get(key, False):
                permissions[key] = False
        except Exception:
            # Keep legacy value if service lookup fails unexpectedly
            continue

    # Add template compatibility flags
    permissions["is_super_admin"] = user.role == "super_admin" or getattr(user, "is_super_admin", False)
    permissions["is_admin"] = getattr(user, "is_admin", False)

    return permissions


def _is_super_admin(user: User) -> bool:
    role = (getattr(user, "role", "") or "").lower()
    return bool(getattr(user, "is_super_admin", False)) or role == "super_admin"


def _super_admin_permissions() -> Dict[str, bool]:
    return {
        "view_dashboard": True,
        "manage_users": True,
        "manage_organizations": True,
        "view_data_management": True,
        "manage_data": True,
        "view_ai_agents": True,
        "manage_ai_agents": True,
        "view_security": True,
        "manage_security": True,
        "view_analytics": True,
        "manage_analytics": True,
        "view_system": True,
        "manage_system": True,
        "view_live2d": True,
        "manage_live2d": True,
        "view_testing": True,
        "manage_testing": True,
        # Assessment permissions
        "view_assessment": True,
        "manage_assessment": True,
        "view_assessment_rules": True,
        "manage_assessment_rules": True,
    }


def _legacy_permissions(user: User) -> Dict[str, bool]:
    role = (getattr(user, "role", "") or "").lower()
    is_admin_flag = bool(getattr(user, "is_admin", False))

    if is_admin_flag or role == "admin":
        # Org admins: Dashboard, User Management, and Data ONLY
        return {
            "view_dashboard": True,
            "manage_users": False,  # Changed: org admins don't see ALL users
            "manage_org_users": True,  # New: but can manage their org users
            "create_org_users": True,  # New: can create users in their org
            "manage_organizations": False,  # Changed: cannot manage organizations
            "view_data_management": True,  # Can view data to improve AI
            "manage_data": True,  # Can manage data to improve AI
            "view_questionnaires": True,  # ✅ Can view and manage questionnaires
            "manage_questionnaires": True,  # ✅ Can create and edit questionnaires
            "view_ai_agents": False,  # ❌ Hidden: cannot view AI agents
            "manage_ai_agents": False,
            "view_security": False,  # ❌ Hidden: cannot view security
            "manage_security": False,
            "view_analytics": False,  # ❌ Hidden: cannot view analytics
            "manage_analytics": False,
            "view_system": False,  # ❌ Hidden: cannot view system controls
            "manage_system": False,
            "view_live2d": False,  # ❌ Hidden: cannot view Live2D
            "manage_live2d": False,  # ❌ Hidden: cannot manage Live2D
            "view_testing": False,  # ❌ Hidden: cannot view testing
            "manage_testing": False,
            # Assessment permissions - Org admins can manage rules
            "view_assessment": True,
            "manage_assessment": True,
            "view_assessment_rules": True,
            "manage_assessment_rules": True,
        }

    if role == "data_manager":
        return {
            "view_dashboard": True,
            "manage_users": False,
            "manage_organizations": False,
            "view_data_management": True,
            "manage_data": True,
            "view_ai_agents": False,
            "manage_ai_agents": False,
            "view_security": False,
            "manage_security": False,
            "view_analytics": True,
            "manage_analytics": True,
            "view_system": False,
            "manage_system": False,
            "view_live2d": False,
            "manage_live2d": False,
            "view_testing": False,
            "manage_testing": False,
        }

    if role == "medical_reviewer":
        return {
            "view_dashboard": True,
            "manage_users": False,
            "manage_organizations": False,
            "view_data_management": True,
            "manage_data": False,
            "view_ai_agents": False,
            "manage_ai_agents": False,
            "view_security": False,
            "manage_security": False,
            "view_analytics": True,
            "manage_analytics": True,
            "view_system": False,
            "manage_system": False,
            "view_live2d": False,
            "manage_live2d": False,
            "view_testing": False,
            "manage_testing": False,
        }
    
    if role in ("doctor", "nurse", "counselor", "social_worker"):
        # Healthcare staff: Can view assigned users and create new users
        return {
            "view_dashboard": True,
            "manage_users": False,  # Cannot manage ALL users (super admin only)
            "manage_org_users": True,  # ✅ Can view User Directory (scoped to assigned users)
            "create_org_users": True,  # ✅ Can create new users/patients
            "manage_organizations": False,
            "view_data_management": True,  # Can view assigned data
            "manage_data": True,  # Can manage assigned data
            "view_ai_agents": False,
            "manage_ai_agents": False,
            "view_security": False,
            "manage_security": False,
            "view_analytics": False,
            "manage_analytics": False,
            "view_system": False,
            "manage_system": False,
            "view_live2d": False,  # ❌ Step 2: Removed Live2D Studio access
            "manage_live2d": False,
            "view_testing": False,
            "manage_testing": False,
            # Assessment permissions - Staff can view and manage rules
            "view_assessment": True,
            "manage_assessment": True,
            "view_assessment_rules": True,
            "manage_assessment_rules": True,  # Social workers and counselors can add/edit rules
        }

    return {
        "view_dashboard": False,
        "manage_users": False,
        "manage_organizations": False,
        "view_data_management": False,
        "manage_data": False,
        "view_ai_agents": False,
        "manage_ai_agents": False,
        "view_security": False,
        "manage_security": False,
        "view_analytics": False,
        "manage_analytics": False,
        "view_system": False,
        "manage_system": False,
        "view_live2d": False,
        "manage_live2d": False,
        "view_testing": False,
        "manage_testing": False,
        # Assessment permissions - default user cannot manage rules
        "view_assessment": False,
        "manage_assessment": False,
        "view_assessment_rules": False,
        "manage_assessment_rules": False,
    }


def get_role_display_name(role: str) -> str:
    """
    Get display name for a role
    
    Args:
        role: Role string
        
    Returns:
        str: Display name for the role
    """
    role_names = {
        "super_admin": "Super Administrator",
        "admin": "Administrator",
        "data_manager": "Data Manager",
        "medical_reviewer": "Medical Reviewer",
        "doctor": "Doctor",
        "nurse": "Nurse",
        "social_worker": "Social Worker",
        "counselor": "Counselor",
        "user": "User",
        "patient": "Patient"
    }
    return role_names.get(role, role.title())


def get_role_description(role: str) -> str:
    """
    Get description for a role
    
    Args:
        role: Role string
        
    Returns:
        str: Description for the role
    """
    role_descriptions = {
        "super_admin": "Full system access with all administrative privileges",
        "admin": "Administrative access to most system features",
        "data_manager": "Access to data management and analytics features",
        "medical_reviewer": "Access to review medical data and analytics",
        "doctor": "Medical professional with patient care access",
        "nurse": "Nursing professional with patient care access",
        "social_worker": "Social work professional with patient support access",
        "counselor": "Counseling professional with patient support access",
        "user": "Basic user with limited system access",
        "patient": "Patient with access to personal health information"
    }
    return role_descriptions.get(role, "Standard user role")


def get_available_roles() -> Dict[str, Dict[str, str]]:
    """
    Get all available roles with their display names and descriptions
    
    Returns:
        Dict[str, Dict[str, str]]: Dictionary of role -> {name, description}
    """
    roles = [
        "super_admin", "admin", "data_manager", "medical_reviewer",
        "doctor", "nurse", "social_worker", "counselor", "user", "patient"
    ]
    
    return {
        role: {
            "name": get_role_display_name(role),
            "description": get_role_description(role)
        }
        for role in roles
    }


def can_manage_user(manager: User, target_user: User) -> bool:
    """
    Check if a user can manage another user
    
    Args:
        manager: User trying to manage
        target_user: User being managed
        
    Returns:
        bool: True if manager can manage target_user
    """
    if not manager or not target_user:
        return False
    
    # Users cannot manage themselves
    if manager.id == target_user.id:
        return False
    
    # Super admins can manage everyone
    if (getattr(manager, "is_super_admin", False) or 
        getattr(manager, "role", "").lower() == "super_admin"):
        return True
    
    # Admins can manage non-super-admin users IN THEIR ORGANIZATION
    if (getattr(manager, "is_admin", False) or 
        getattr(manager, "role", "").lower() == "admin"):
        # Cannot manage super admins
        if (getattr(target_user, "is_super_admin", False) or 
            getattr(target_user, "role", "").lower() == "super_admin"):
            return False
        # Can only manage users in same organization
        manager_org = getattr(manager, "organization_id", None)
        target_org = getattr(target_user, "organization_id", None)
        if manager_org and target_org:
            return manager_org == target_org
        return False
    
    # Others cannot manage users
    return False


def can_delete_user(manager: User, target_user: User) -> bool:
    """
    Check if a user can delete another user
    
    Args:
        manager: User trying to delete
        target_user: User being deleted
        
    Returns:
        bool: True if manager can delete target_user
    """
    if not can_manage_user(manager, target_user):
        return False
    
    # Super admins cannot be deleted
    if (getattr(target_user, "is_super_admin", False) or 
        getattr(target_user, "role", "").lower() == "super_admin"):
        return False
    
    return True
