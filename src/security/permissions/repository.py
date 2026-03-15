"""
Repository helpers for loading permission catalogue data from the database.
"""

from collections import defaultdict
from typing import Dict, Optional, Set

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.core.logging import get_logger
from src.database.connection import get_sync_session

logger = get_logger(__name__)


def load_permissions_from_db() -> Optional[Dict[str, Dict[str, object]]]:
    """
    Attempt to load permission definitions from the database.

    Returns:
        Mapping of permission code -> {"scope": str, "roles": set[str]}
        None when the data source is unavailable (e.g. tables not migrated yet).
    """
    try:
        with get_sync_session() as session:
            rows = session.execute(
                text(
                    """
                    SELECT
                        p.code AS permission_code,
                        COALESCE(p.scope, 'organization') AS scope,
                        r.name AS role_name
                    FROM permissions p
                    JOIN role_permissions rp ON rp.permission_id = p.id
                    JOIN roles r ON r.id = rp.role_id
                    """
                )
            ).fetchall()
    except (SQLAlchemyError, RuntimeError) as exc:
        logger.debug("Permission catalogue load skipped: %s", exc)
        return None

    if not rows:
        return {}

    catalogue: Dict[str, Dict[str, object]] = defaultdict(lambda: {"scope": "organization", "roles": set()})
    for row in rows:
        code = row.permission_code
        scope = row.scope
        role = row.role_name
        entry = catalogue[code]
        entry["scope"] = scope
        roles: Set[str] = entry["roles"]  # type: ignore[assignment]
        roles.add(role)

    return catalogue
