"""
Centralized permission checking utilities for the admin portal.

This service provides a single entry point for the rest of the codebase:

    PermissionService.can(actor, "user.create", context)

The current implementation is intentionally conservative. It supports:
  * Static permission lookups from an in-memory catalogue (until DB-backed repo is wired).
  * Organization scoping helpers.
  * Audit-friendly reason codes whenever access is denied.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Optional, Set, Tuple

from fastapi import HTTPException, status

from src.core.logging import get_logger

from .repository import load_permissions_from_db

logger = get_logger(__name__)

class PermissionDenied(HTTPException):
    """Exception raised when a permission check fails."""

    def __init__(self, message: str, reason_code: str = "permission_denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": message, "reason_code": reason_code},
        )
        self.reason_code = reason_code


class PermissionScope(str, Enum):
    """Scope selectors used by the permission catalogue."""

    GLOBAL = "global"
    ORGANIZATION = "organization"
    SELF = "self"


@dataclass(frozen=True)
class PermissionContext:
    """Context passed into permission checks."""

    organization_id: Optional[int] = None
    target_user_id: Optional[int] = None
    patient_id: Optional[int] = None
    extra: Optional[Dict[str, str]] = None


class PermissionCatalogue:
    """
    Permission catalogue source.

    Loads definitions from the database when available, otherwise falls back to the
    built-in defaults declared below.
    """

    DEFAULT_MAP: Dict[str, Tuple[Set[str], PermissionScope]] = {
        # User management
        "user.view.all": ({"super_admin", "platform_admin"}, PermissionScope.GLOBAL),
        "user.view.org": (
            {"super_admin", "platform_admin", "org_admin"},
            PermissionScope.ORGANIZATION,
        ),
        "user.create": (
            {"super_admin", "platform_admin", "org_admin"},
            PermissionScope.ORGANIZATION,
        ),
        "user.edit": (
            {"super_admin", "platform_admin", "org_admin"},
            PermissionScope.ORGANIZATION,
        ),
        "user.role.change": ({"super_admin", "platform_admin"}, PermissionScope.GLOBAL),
        "user.mfa.reset": (
            {"super_admin", "platform_admin", "org_admin"},
            PermissionScope.ORGANIZATION,
        ),
        "user.suspend": (
            {"super_admin", "platform_admin", "org_admin"},
            PermissionScope.ORGANIZATION,
        ),
        "user.delete": ({"super_admin", "platform_admin"}, PermissionScope.GLOBAL),
        # Organization management
        "organization.view": (
            {"super_admin", "platform_admin", "org_admin"},
            PermissionScope.ORGANIZATION,
        ),
        "organization.create": ({"super_admin", "platform_admin"}, PermissionScope.GLOBAL),
        "organization.edit": (
            {"super_admin", "platform_admin", "org_admin"},
            PermissionScope.ORGANIZATION,
        ),
        "organization.deactivate": ({ "super_admin", "platform_admin" }, PermissionScope.GLOBAL),
        # Patient management
        "patient.view": (
            {"super_admin", "platform_admin", "org_admin", "clinician_doctor", "clinician_nurse", "clinician_worker"},
            PermissionScope.ORGANIZATION,
        ),
        "patient.edit": (
            {"super_admin", "platform_admin", "org_admin", "clinician_doctor", "clinician_nurse"},
            PermissionScope.ORGANIZATION,
        ),
        "patient.assign": (
            {"super_admin", "platform_admin", "org_admin"},
            PermissionScope.ORGANIZATION,
        ),
        "data.view": (
            {"super_admin", "platform_admin", "data_manager", "org_admin"},
            PermissionScope.GLOBAL,
        ),
        "data.manage": (
            {"super_admin", "platform_admin", "data_manager"},
            PermissionScope.GLOBAL,
        ),
        "analytics.view": (
            {"super_admin", "platform_admin", "data_manager", "org_admin"},
            PermissionScope.GLOBAL,
        ),
        "analytics.manage": (
            {"super_admin", "platform_admin", "data_manager"},
            PermissionScope.GLOBAL,
        ),
    }

    def __init__(self, permissions: Optional[Dict[str, Tuple[Iterable[str], PermissionScope]]] = None):
        catalogue = permissions
        if catalogue is None:
            loaded = self._load_from_db()
            catalogue = loaded or self.DEFAULT_MAP

        self._map = {
            code: (set(roles), scope)
            for code, (roles, scope) in catalogue.items()
        }

    def get(self, code: str) -> Optional[Tuple[Set[str], PermissionScope]]:
        return self._map.get(code)

    @classmethod
    def _load_from_db(cls) -> Optional[Dict[str, Tuple[Iterable[str], PermissionScope]]]:
        data = load_permissions_from_db()
        if data is None:
            logger.debug("Permission catalogue: database unavailable, using defaults.")
            return None
        if not data:
            logger.debug("Permission catalogue: database returned 0 rows, using defaults.")
            return None

        catalogue: Dict[str, Tuple[Set[str], PermissionScope]] = {}
        for code, payload in data.items():
            scope = cls._normalize_scope(payload.get("scope"))
            roles = set(payload.get("roles") or [])
            if not roles:
                logger.debug("Permission catalogue: permission '%s' has no roles; skipping.", code)
                continue
            catalogue[code] = (roles, scope)
        return catalogue if catalogue else None

    @staticmethod
    def _normalize_scope(value: Optional[str]) -> PermissionScope:
        if not value:
            return PermissionScope.ORGANIZATION
        normalized = value.strip().lower()
        if normalized in {"global"}:
            return PermissionScope.GLOBAL
        if normalized in {"self", "own"}:
            return PermissionScope.SELF
        return PermissionScope.ORGANIZATION


class PermissionService:
    """
    Stateless helper that evaluates whether a given actor may perform an action.
    Actor objects must expose:
      - `id`
      - `roles`: Iterable[str] (role names)
      - `organization_ids`: Optional iterable of org IDs linked to the actor
    """

    catalogue = PermissionCatalogue()

    @classmethod
    def can(cls, actor, permission_code: str, context: Optional[PermissionContext] = None) -> bool:
        """
        Return True if the actor can perform the action described by permission_code.
        Raises PermissionDenied when the actor is not authorized.
        """
        context = context or PermissionContext()
        entry = cls.catalogue.get(permission_code)
        if not entry:
            raise PermissionDenied(
                f"Unknown permission '{permission_code}'",
                reason_code="permission_unknown",
            )

        allowed_roles, scope = entry
        actor_roles = set(getattr(actor, "roles", []) or [])

        if not actor_roles:
            raise PermissionDenied("No roles assigned to actor.", reason_code="no_roles")

        if actor_roles.isdisjoint(allowed_roles):
            raise PermissionDenied(
                "Actor does not hold required role.",
                reason_code="role_forbidden",
            )

        if scope == PermissionScope.GLOBAL:
            return True

        if scope == PermissionScope.SELF:
            target_id = context.target_user_id or context.patient_id
            if target_id and getattr(actor, "id", None) == target_id:
                return True
            raise PermissionDenied(
                "Operation restricted to the resource owner.",
                reason_code="self_scope_required",
            )

        # Organization scope validation
        if scope == PermissionScope.ORGANIZATION:
            if PermissionService._actor_has_global_role(actor_roles):
                return True

            if context.organization_id is None:
                raise PermissionDenied(
                    "Organization context required.",
                    reason_code="organization_scope_missing",
                )

            actor_orgs = set(getattr(actor, "organization_ids", []) or [])
            if context.organization_id in actor_orgs:
                return True
            raise PermissionDenied(
                "Actor is not assigned to the target organization.",
                reason_code="organization_scope_forbidden",
            )

        raise PermissionDenied("Unsupported permission scope.", reason_code="scope_not_supported")

    @staticmethod
    def _actor_has_global_role(actor_roles: Set[str]) -> bool:
        """
        Helper that returns True if the actor holds a role that should bypass org scoping.
        """
        global_roles = {"super_admin", "platform_admin"}
        return bool(actor_roles.intersection(global_roles))
