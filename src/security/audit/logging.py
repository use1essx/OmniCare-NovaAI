"""
Audit logging utilities.

This module provides a lightweight audit logger that can be wired into FastAPI routes
and service functions. It is intentionally minimal until the database persistence
layer lands.
"""

from __future__ import annotations

import functools
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("security.audit")


@dataclass
class AuditEvent:
    action: str
    actor_id: Optional[int]
    target_type: str
    target_id: Optional[str] = None
    organization_id: Optional[int] = None
    status: str = "success"
    reason_code: Optional[str] = None
    diff: Optional[Dict[str, Any]] = field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


class AuditLogger:
    """
    Lightweight logger that records audit events. For now we emit to standard logging;
    once the audit_log table is ready we can persist there.
    """

    @staticmethod
    def record(event: AuditEvent) -> None:
        payload = {
            "action": event.action,
            "actor_id": event.actor_id,
            "target_type": event.target_type,
            "target_id": event.target_id,
            "organization_id": event.organization_id,
            "status": event.status,
            "reason_code": event.reason_code,
            "created_at": event.created_at.isoformat(),
            "diff": event.diff,
            "metadata": event.metadata,
        }
        logger.info("AUDIT %s", payload)


def audit_action(action: str, extract_context: Optional[Callable[..., AuditEvent]] = None):
    """
    Decorator used to emit audit logs around privileged operations.

    Example:

        @audit_action("user.update")
        async def update_user(actor, user, payload):
            ...
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            event = None
            try:
                result = await func(*args, **kwargs)
                event = _build_event(action, args, kwargs, result, extract_context)
                event.status = "success"
                return result
            except Exception as exc:  # pragma: no cover - re-raise after logging
                event = _build_event(action, args, kwargs, None, extract_context)
                event.status = "error"
                event.reason_code = getattr(exc, "reason_code", None)
                AuditLogger.record(event)
                raise
            finally:
                if event and event.status == "success":
                    AuditLogger.record(event)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            event = None
            try:
                result = func(*args, **kwargs)
                event = _build_event(action, args, kwargs, result, extract_context)
                event.status = "success"
                return result
            except Exception as exc:  # pragma: no cover - re-raise after logging
                event = _build_event(action, args, kwargs, None, extract_context)
                event.status = "error"
                event.reason_code = getattr(exc, "reason_code", None)
                AuditLogger.record(event)
                raise
            finally:
                if event and event.status == "success":
                    AuditLogger.record(event)

        # Choose wrapper based on coroutine status
        return async_wrapper if _is_coroutine(func) else sync_wrapper

    return decorator


def _build_event(
    action: str,
    args,
    kwargs,
    result,
    extractor: Optional[Callable[..., AuditEvent]],
) -> AuditEvent:
    if extractor:
        return extractor(action=action, args=args, kwargs=kwargs, result=result)
    actor = kwargs.get("actor") or (args[0] if args else None)
    actor_id = getattr(actor, "id", None)
    organization_id = getattr(actor, "organization_id", None)
    return AuditEvent(
        action=action,
        actor_id=actor_id,
        target_type="unknown",
        organization_id=organization_id,
        metadata={"auto_extracted": True},
    )


def _is_coroutine(func: Callable) -> bool:
    return hasattr(func, "__code__") and func.__code__.co_flags & 0x80
