"""
Healthcare AI V2 - Enhanced Custom Exception Hierarchy
======================================================

Comprehensive exception classes for all subsystems.

Features:
- Structured error context with logging
- Machine-readable error codes
- User-friendly messages
- HTTP status code mapping
- Original error wrapping
"""

from typing import Any, Dict, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# BASE EXCEPTION
# ============================================================================

class HealthcareAIException(Exception):
    """
    Enhanced base exception for Healthcare AI V2.

    All custom exceptions inherit from this base class.
    Provides structured error context, logging, and HTTP mapping.
    """

    # Default values (overridden in subclasses)
    error_code: str = "HEALTHCARE_AI_ERROR"
    http_status_code: int = 500
    user_message: str = "An unexpected error occurred. Please try again."

    def __init__(
        self,
        message: str,
        *,
        error_code: Optional[str] = None,
        http_status_code: Optional[int] = None,
        user_message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
        # Legacy compatibility
        detail: Optional[str] = None,
        status_code: Optional[int] = None,
        error_type: Optional[str] = None
    ):
        """
        Initialize exception with structured context.

        Args:
            message: Internal error message (for logging)
            error_code: Machine-readable error code
            http_status_code: HTTP status code for API responses
            user_message: User-friendly error message
            context: Additional error context (user_id, session_id, etc.)
            original_error: Original exception if wrapping another error

            # Legacy parameters for backward compatibility:
            detail: Legacy parameter (maps to message)
            status_code: Legacy parameter (maps to http_status_code)
            error_type: Legacy parameter (maps to error_code)
        """
        # Handle legacy parameters
        if detail:
            message = detail
        if status_code:
            http_status_code = status_code
        if error_type:
            error_code = error_type

        super().__init__(message)

        self.message = message
        self.detail = message  # For backward compatibility
        self.error_code = error_code or self.__class__.error_code
        self.http_status_code = http_status_code or self.__class__.http_status_code
        self.status_code = self.http_status_code  # For backward compatibility
        self.error_type = self.error_code  # For backward compatibility
        self.user_message = user_message or self.__class__.user_message
        self.context = context or {}
        self.original_error = original_error
        self.timestamp = datetime.now(timezone.utc)

        # Log the error
        self._log_error()

    def _log_error(self):
        """Log error with full context"""
        log_data = {
            "error_code": self.error_code,
            "error_message": self.message,  # Changed from 'message' to avoid conflict
            "user_message": self.user_message,
            "context": self.context,
            "timestamp": self.timestamp.isoformat()
        }

        if self.original_error:
            log_data["original_error"] = str(self.original_error)
            log_data["original_error_type"] = type(self.original_error).__name__

        logger.error(
            f"[{self.error_code}] {self.message}",
            extra=log_data,
            exc_info=self.original_error is not None
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        result = {
            "error": True,
            "error_code": self.error_code,
            "message": self.user_message,
            "timestamp": self.timestamp.isoformat()
        }

        # Include context in development (filter sensitive data in production)
        if self.context:
            result["context"] = self.context

        return result


# ============================================================================
# AGENT SUBSYSTEM EXCEPTIONS
# ============================================================================

class AgentProcessingError(HealthcareAIException):
    """Exception raised during agent processing"""
    error_code = "AGENT_PROCESSING_ERROR"
    http_status_code = 500
    user_message = "Unable to process your request. Please try rephrasing your question."


class AgentNotFoundError(AgentProcessingError):
    """Exception raised when agent cannot be found"""
    error_code = "AGENT_NOT_FOUND"
    http_status_code = 500
    user_message = "The requested agent is not available. Please try again."


class AgentRoutingError(AgentProcessingError):
    """Exception raised during agent routing"""
    error_code = "AGENT_ROUTING_ERROR"
    http_status_code = 500
    user_message = "Unable to determine the appropriate response agent."


class AgentTimeoutError(AgentProcessingError):
    """Exception raised when agent processing times out"""
    error_code = "AGENT_TIMEOUT"
    http_status_code = 504
    user_message = "Request processing took too long. Please try again with a simpler question."


class EmotionMappingError(AgentProcessingError):
    """Exception raised during emotion mapping"""
    error_code = "EMOTION_MAPPING_ERROR"
    http_status_code = 500
    user_message = "Unable to generate appropriate response emotion."


# Legacy compatibility
class AgentError(AgentProcessingError):
    """Legacy agent error (use AgentProcessingError instead)"""
    pass


# ============================================================================
# WEBSOCKET SUBSYSTEM EXCEPTIONS
# ============================================================================

class WebSocketError(HealthcareAIException):
    """Base exception for WebSocket-related errors"""
    error_code = "WEBSOCKET_ERROR"
    http_status_code = 500
    user_message = "Connection error occurred. Please refresh and try again."


class WebSocketConnectionError(WebSocketError):
    """Exception raised during WebSocket connection"""
    error_code = "WEBSOCKET_CONNECTION_ERROR"
    http_status_code = 503
    user_message = "Unable to establish connection. Please check your network and try again."


class WebSocketSessionNotFoundError(WebSocketError):
    """Exception raised when session cannot be found"""
    error_code = "WEBSOCKET_SESSION_NOT_FOUND"
    http_status_code = 404
    user_message = "Session not found. Please reconnect."


class WebSocketRateLimitError(WebSocketError):
    """Exception raised when rate limit is exceeded"""
    error_code = "WEBSOCKET_RATE_LIMIT"
    http_status_code = 429
    user_message = "Too many requests. Please wait a moment before sending another message."


class WebSocketAuthenticationError(WebSocketError):
    """Exception raised during WebSocket authentication"""
    error_code = "WEBSOCKET_AUTH_ERROR"
    http_status_code = 401
    user_message = "Authentication failed. Please log in again."


class WebSocketMessageError(WebSocketError):
    """Exception raised during message processing"""
    error_code = "WEBSOCKET_MESSAGE_ERROR"
    http_status_code = 400
    user_message = "Invalid message format. Please try again."


# ============================================================================
# DATABASE SUBSYSTEM EXCEPTIONS
# ============================================================================

class DatabaseError(HealthcareAIException):
    """Base exception for database-related errors (enhanced)"""
    error_code = "DATABASE_ERROR"
    http_status_code = 500
    user_message = "Database error occurred. Please try again later."


class DatabaseConnectionError(DatabaseError):
    """Exception raised when database connection fails"""
    error_code = "DATABASE_CONNECTION_ERROR"
    http_status_code = 503
    user_message = "Unable to connect to database. Please try again later."


class DatabaseQueryError(DatabaseError):
    """Exception raised during database query execution"""
    error_code = "DATABASE_QUERY_ERROR"
    http_status_code = 500
    user_message = "Database query failed. Please try again."


class DatabaseRecordNotFoundError(DatabaseError):
    """Exception raised when database record is not found"""
    error_code = "DATABASE_RECORD_NOT_FOUND"
    http_status_code = 404
    user_message = "The requested record was not found."


class DatabaseIntegrityError(DatabaseError):
    """Exception raised on database integrity constraint violation"""
    error_code = "DATABASE_INTEGRITY_ERROR"
    http_status_code = 409
    user_message = "Data integrity error. The operation conflicts with existing data."


# ============================================================================
# AUTHENTICATION SUBSYSTEM EXCEPTIONS
# ============================================================================

class AuthenticationError(HealthcareAIException):
    """Base exception for authentication-related errors (enhanced)"""
    error_code = "AUTHENTICATION_ERROR"
    http_status_code = 401
    user_message = "Authentication failed. Please log in again."


class InvalidCredentialsError(AuthenticationError):
    """Exception raised when credentials are invalid"""
    error_code = "INVALID_CREDENTIALS"
    http_status_code = 401
    user_message = "Invalid username or password."


class TokenExpiredError(AuthenticationError):
    """Exception raised when JWT token has expired"""
    error_code = "TOKEN_EXPIRED"
    http_status_code = 401
    user_message = "Your session has expired. Please log in again."


class TokenInvalidError(AuthenticationError):
    """Exception raised when JWT token is invalid"""
    error_code = "TOKEN_INVALID"
    http_status_code = 401
    user_message = "Invalid authentication token. Please log in again."


class UserNotFoundError(AuthenticationError):
    """Exception raised when user is not found"""
    error_code = "USER_NOT_FOUND"
    http_status_code = 404
    user_message = "User account not found."


class UserInactiveError(AuthenticationError):
    """Exception raised when user account is inactive"""
    error_code = "USER_INACTIVE"
    http_status_code = 403
    user_message = "Your account is inactive. Please contact support."


# ============================================================================
# AUTHORIZATION SUBSYSTEM EXCEPTIONS
# ============================================================================

class AuthorizationError(HealthcareAIException):
    """Base exception for authorization-related errors (enhanced)"""
    error_code = "AUTHORIZATION_ERROR"
    http_status_code = 403
    user_message = "You don't have permission to perform this action."


class InsufficientPermissionsError(AuthorizationError):
    """Exception raised when user lacks required permissions"""
    error_code = "INSUFFICIENT_PERMISSIONS"
    http_status_code = 403
    user_message = "You don't have sufficient permissions for this operation."


class OrganizationAccessDeniedError(AuthorizationError):
    """Exception raised when user cannot access organization resource"""
    error_code = "ORGANIZATION_ACCESS_DENIED"
    http_status_code = 403
    user_message = "You don't have access to this organization's resources."


# ============================================================================
# VALIDATION SUBSYSTEM EXCEPTIONS
# ============================================================================

class ValidationError(HealthcareAIException):
    """Base exception for validation-related errors (enhanced)"""
    error_code = "VALIDATION_ERROR"
    http_status_code = 422  # Changed from 400 to 422 (Unprocessable Entity)
    user_message = "Input validation failed. Please check your input and try again."


class InputSanitizationError(ValidationError):
    """Exception raised during input sanitization"""
    error_code = "INPUT_SANITIZATION_ERROR"
    http_status_code = 400
    user_message = "Input contains invalid or unsafe content."


class InputTooLongError(ValidationError):
    """Exception raised when input exceeds maximum length"""
    error_code = "INPUT_TOO_LONG"
    http_status_code = 400
    user_message = "Input is too long. Please shorten your message and try again."


class InvalidInputFormatError(ValidationError):
    """Exception raised when input format is invalid"""
    error_code = "INVALID_INPUT_FORMAT"
    http_status_code = 400
    user_message = "Invalid input format. Please check your input and try again."


class MissingRequiredFieldError(ValidationError):
    """Exception raised when required field is missing"""
    error_code = "MISSING_REQUIRED_FIELD"
    http_status_code = 400
    user_message = "Required field is missing. Please provide all required information."


# ============================================================================
# RATE LIMITING EXCEPTIONS
# ============================================================================

class RateLimitError(HealthcareAIException):
    """Base exception for rate limiting (enhanced)"""
    error_code = "RATE_LIMIT_ERROR"
    http_status_code = 429
    user_message = "Too many requests. Please wait a moment before trying again."


class UserRateLimitError(RateLimitError):
    """Exception raised when user rate limit is exceeded"""
    error_code = "USER_RATE_LIMIT"
    http_status_code = 429
    user_message = "You've made too many requests. Please wait before trying again."


class IPRateLimitError(RateLimitError):
    """Exception raised when IP rate limit is exceeded"""
    error_code = "IP_RATE_LIMIT"
    http_status_code = 429
    user_message = "Too many requests from your network. Please try again later."


# ============================================================================
# AI SERVICE EXCEPTIONS
# ============================================================================

class AIServiceError(HealthcareAIException):
    """Base exception for AI service errors"""
    error_code = "AI_SERVICE_ERROR"
    http_status_code = 500
    user_message = "AI service error. Please try again later."


class AIModelNotAvailableError(AIServiceError):
    """Exception raised when AI model is not available"""
    error_code = "AI_MODEL_NOT_AVAILABLE"
    http_status_code = 503
    user_message = "AI model is currently unavailable. Please try again later."


class AIResponseError(AIServiceError):
    """Exception raised when AI response generation fails"""
    error_code = "AI_RESPONSE_ERROR"
    http_status_code = 500
    user_message = "Unable to generate response. Please try rephrasing your question."


class AITimeoutError(AIServiceError):
    """Exception raised when AI request times out"""
    error_code = "AI_TIMEOUT"
    http_status_code = 504
    user_message = "AI response took too long. Please try again."


class BudgetExceededError(AIServiceError):
    """Exception raised when AI budget limit is exceeded"""
    error_code = "BUDGET_EXCEEDED"
    http_status_code = 429
    user_message = "AI service budget limit reached. Please contact administrator."


# ============================================================================
# SAFETY VALIDATION EXCEPTIONS
# ============================================================================

class SafetyValidationError(HealthcareAIException):
    """Base exception for safety validation"""
    error_code = "SAFETY_VALIDATION_ERROR"
    http_status_code = 500
    user_message = "Safety validation error occurred."


class UnsafeContentDetectedError(SafetyValidationError):
    """Exception raised when unsafe content is detected"""
    error_code = "UNSAFE_CONTENT_DETECTED"
    http_status_code = 400
    user_message = "Your request contains content that cannot be processed for safety reasons."


class EmergencySituationError(SafetyValidationError):
    """Exception raised when emergency situation is detected"""
    error_code = "EMERGENCY_SITUATION"
    http_status_code = 200  # Not an error, but needs special handling
    user_message = "Emergency situation detected. Connecting to emergency services."


# ============================================================================
# LIVE2D INTEGRATION EXCEPTIONS
# ============================================================================

class Live2DIntegrationError(HealthcareAIException):
    """Base exception for Live2D integration errors"""
    error_code = "LIVE2D_INTEGRATION_ERROR"
    http_status_code = 500
    user_message = "Live2D avatar error. The system will continue without avatar animations."


class Live2DModelLoadError(Live2DIntegrationError):
    """Exception raised when Live2D model fails to load"""
    error_code = "LIVE2D_MODEL_LOAD_ERROR"
    http_status_code = 500
    user_message = "Unable to load avatar model. Continuing in text-only mode."


class Live2DAnimationError(Live2DIntegrationError):
    """Exception raised when Live2D animation fails"""
    error_code = "LIVE2D_ANIMATION_ERROR"
    http_status_code = 500
    user_message = "Avatar animation error. Text responses will continue normally."


# ============================================================================
# LEGACY EXCEPTIONS (for backward compatibility)
# ============================================================================

class NotFoundError(DatabaseRecordNotFoundError):
    """Legacy NotFoundError (use DatabaseRecordNotFoundError instead)"""
    pass


class ConflictError(DatabaseIntegrityError):
    """Legacy ConflictError (use DatabaseIntegrityError instead)"""
    pass


class ExternalAPIError(AIServiceError):
    """Legacy ExternalAPIError (use AIServiceError instead)"""
    def __init__(self, detail: str, service: str, context: Optional[Dict[str, Any]] = None):
        context = context or {}
        context["service"] = service
        super().__init__(message=detail, context=context)


class FileProcessingError(ValidationError):
    """Legacy FileProcessingError (use ValidationError instead)"""
    def __init__(self, detail: str, filename: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        context = context or {}
        if filename:
            context["filename"] = filename
        super().__init__(message=detail, context=context)


class SecurityError(AuthorizationError):
    """Legacy SecurityError (use AuthorizationError instead)"""
    pass


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def handle_exception(exc: Exception, context: Optional[Dict[str, Any]] = None) -> HealthcareAIException:
    """
    Convert any exception to a HealthcareAIException with context.

    Args:
        exc: Original exception
        context: Additional context (user_id, session_id, etc.)

    Returns:
        HealthcareAIException or subclass
    """
    # If already a HealthcareAIException, just add context
    if isinstance(exc, HealthcareAIException):
        if context:
            exc.context.update(context)
        return exc

    # Wrap other exceptions
    return HealthcareAIException(
        message=str(exc),
        context=context,
        original_error=exc
    )


def log_exception(exc: Exception, context: Optional[Dict[str, Any]] = None):
    """
    Log exception with context.

    Args:
        exc: Exception to log
        context: Additional context
    """
    if isinstance(exc, HealthcareAIException):
        # Already logged in __init__
        return

    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
        extra={"context": context or {}},
        exc_info=True
    )
