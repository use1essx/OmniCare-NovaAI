"""
Adapters that convert database models into lightweight actors for the permission service.
"""

from types import SimpleNamespace
from typing import Iterable, Optional

from src.database.models_comprehensive import User

# Map legacy role names to the canonical PermissionService role identifiers
ROLE_TRANSLATIONS = {
    "super_admin": "super_admin",
    "admin": "platform_admin",
    "platform_admin": "platform_admin",
    "org_admin": "org_admin",
    "organization_admin": "org_admin",
    "doctor": "clinician_doctor",
    "clinician_doctor": "clinician_doctor",
    "nurse": "clinician_nurse",
    "clinician_nurse": "clinician_nurse",
    "social_worker": "clinician_worker",
    "case_worker": "clinician_worker",
    "worker": "clinician_worker",
    "clinician_worker": "clinician_worker",
    "data_manager": "data_manager",
}


def build_actor_from_user(user: User, extra_roles: Optional[Iterable[str]] = None) -> SimpleNamespace:
    """
    Convert a User ORM model into the light actor object expected by PermissionService.
    """
    roles = set(extra_roles or [])
    role = (getattr(user, "role", "") or "").lower()

    if getattr(user, "is_super_admin", False) or role == "super_admin":
        roles.add("super_admin")

    if getattr(user, "is_admin", False):
        roles.add("platform_admin")

    translated = ROLE_TRANSLATIONS.get(role)
    if translated:
        roles.add(translated)
    elif role:
        roles.add(role)

    if not roles:
        roles.add("user")

    org_id = getattr(user, "organization_id", None)
    org_ids = [org_id] if org_id else []

    return SimpleNamespace(
        id=getattr(user, "id", None),
        roles=list(roles),
        organization_ids=org_ids,
    )
