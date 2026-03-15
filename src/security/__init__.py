"""
Healthcare AI V2 - Security Module
Consolidated security components for authentication, monitoring, and protection
"""

from .auth import (
    PasswordValidator,
    InputSanitizer,
    SecurityTokenGenerator,
    IPValidator,
    SecurityHeaders,
    get_password_hash,
    verify_password,
    BCRYPT_ROUNDS
)

from .api import (
    APIKeyManager,
    log_api_operation
)

from .middleware import (
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
    EnhancedCORSMiddleware,
    RequestSizeMiddleware,
    SecurityAuditMiddleware
)

from .permissions import (
    PermissionService,
    PermissionDenied,
    PermissionContext
)

from .audit import (
    AuditEvent,
    AuditLogger,
    audit_action
)

__all__ = [
    # Authentication & Validation
    'PasswordValidator',
    'InputSanitizer',
    'SecurityTokenGenerator',
    'IPValidator',
    'SecurityHeaders',
    'get_password_hash',
    'verify_password',
    'BCRYPT_ROUNDS',
    
    # API Security
    'APIKeyManager',
    'log_api_operation',
    
    # Middleware
    'SecurityHeadersMiddleware',
    'RequestLoggingMiddleware',
    'EnhancedCORSMiddleware',
    'RequestSizeMiddleware',
    'SecurityAuditMiddleware',

    # Permissions
    'PermissionService',
    'PermissionDenied',
    'PermissionContext',

    # Audit
    'AuditEvent',
    'AuditLogger',
    'audit_action',
]
