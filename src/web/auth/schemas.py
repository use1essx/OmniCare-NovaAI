"""
Healthcare AI V2 - Authentication Schemas
Pydantic models for authentication requests and responses
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    """User registration request schema"""
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    password: str = Field(..., min_length=8, max_length=128, description="Password")
    full_name: str = Field(..., min_length=2, max_length=255, description="Full name")
    department: Optional[str] = Field(None, max_length=100, description="Department")
    license_number: Optional[str] = Field(None, max_length=100, description="Professional license number")
    organization: Optional[str] = Field(None, max_length=255, description="Organization")
    language_preference: str = Field(default="en", description="Preferred language")
    timezone: str = Field(default="Asia/Hong_Kong", description="User timezone")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format"""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, hyphens, and underscores")
        if v.startswith(("-", "_")) or v.endswith(("-", "_")):
            raise ValueError("Username cannot start or end with hyphens or underscores")
        return v.lower()

    @field_validator("language_preference")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validate language preference"""
        allowed_languages = ["en", "zh-HK"]  # Only English and Cantonese (Hong Kong)
        if v not in allowed_languages:
            raise ValueError(f"Language must be one of: {allowed_languages}")
        return v


class UserLoginRequest(BaseModel):
    """User login request schema"""
    email_or_username: str = Field(..., description="Email address or username")
    password: str = Field(..., description="Password")
    remember_me: bool = Field(default=False, description="Remember login for extended period")


class TokenRefreshRequest(BaseModel):
    """Token refresh request schema"""
    refresh_token: str = Field(..., description="Valid refresh token")


class ChangePasswordRequest(BaseModel):
    """Change password request schema"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    confirm_password: str = Field(..., description="Confirm new password")

    @field_validator("confirm_password")
    @classmethod
    def validate_password_match(cls, v: str, info) -> str:
        """Validate password confirmation matches"""
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError("Password confirmation does not match")
        return v


class TwoFactorSetupRequest(BaseModel):
    """Two-factor authentication setup request"""
    secret: str = Field(..., description="2FA secret key")
    verification_code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")


class TwoFactorVerifyRequest(BaseModel):
    """Two-factor authentication verification request"""
    verification_code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")


class UserResponse(BaseModel):
    """User response schema"""
    id: int
    email: str
    username: str
    full_name: Optional[str] = None
    role: str
    department: Optional[str] = None
    license_number: Optional[str] = None
    organization: Optional[str] = None
    is_active: bool
    is_verified: bool
    is_admin: bool
    language_preference: Optional[str] = "en"
    timezone: Optional[str] = "Asia/Hong_Kong"
    notification_preferences: Optional[Dict] = None
    health_profile: Optional[Dict] = None
    last_login: Optional[datetime] = None
    created_at: datetime
    two_factor_enabled: Optional[bool] = False

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user: UserResponse = Field(..., description="User information")


class TokenRefreshResponse(BaseModel):
    """Token refresh response schema"""
    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")


class LogoutResponse(BaseModel):
    """Logout response schema"""
    message: str = Field(..., description="Logout confirmation message")
    revoked_sessions: int = Field(..., description="Number of sessions revoked")


class UserPermissionResponse(BaseModel):
    """User permission response schema"""
    name: str
    description: Optional[str] = None
    category: str
    resource: str
    action: str


class UserSessionResponse(BaseModel):
    """User session response schema"""
    id: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    last_activity: Optional[datetime] = None
    is_active: bool
    device_info: Optional[Dict] = None

    class Config:
        from_attributes = True


class AuthStatusResponse(BaseModel):
    """Authentication status response"""
    authenticated: bool
    user: Optional[UserResponse] = None
    permissions: List[UserPermissionResponse] = []
    session: Optional[UserSessionResponse] = None
    requires_2fa: bool = False


class PasswordValidationResponse(BaseModel):
    """Password validation response"""
    is_valid: bool
    errors: List[str] = []
    strength_score: int = Field(..., ge=0, le=100, description="Password strength score (0-100)")
    suggestions: List[str] = []


class SecurityEventResponse(BaseModel):
    """Security event response"""
    event_type: str
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool
    details: Optional[Dict] = None


class AccountSecurityResponse(BaseModel):
    """Account security information response"""
    account_locked: bool
    lockout_expires: Optional[datetime] = None
    failed_attempts: int
    last_login: Optional[datetime] = None
    recent_events: List[SecurityEventResponse] = []
    active_sessions: List[UserSessionResponse] = []
    two_factor_enabled: bool


class TwoFactorSetupResponse(BaseModel):
    """Two-factor setup response"""
    qr_code_url: str = Field(..., description="QR code URL for authenticator apps")
    secret_key: str = Field(..., description="Secret key for manual entry")
    backup_codes: List[str] = Field(..., description="One-time backup codes")


class ApiKeyResponse(BaseModel):
    """API key response schema"""
    key_id: str
    api_key: str
    name: str
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    created_at: datetime


class ErrorResponse(BaseModel):
    """Standard error response schema"""
    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Error type/code")
    details: Optional[Dict] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


# Request/Response models for batch operations
class BulkUserRequest(BaseModel):
    """Bulk user operations request"""
    user_ids: List[int] = Field(..., min_items=1, max_items=100, description="List of user IDs")
    action: str = Field(..., description="Action to perform")
    parameters: Optional[Dict] = Field(None, description="Action parameters")


class BulkUserResponse(BaseModel):
    """Bulk user operations response"""
    total_requested: int
    successful: int
    failed: int
    errors: List[str] = []
    details: List[Dict] = []


# Validation schemas
class PasswordPolicyResponse(BaseModel):
    """Password policy information"""
    min_length: int
    require_uppercase: bool
    require_lowercase: bool
    require_numbers: bool
    require_special_chars: bool
    forbidden_patterns: List[str]
    expiry_days: Optional[int] = None


class RateLimitResponse(BaseModel):
    """Rate limit information"""
    limit: int
    remaining: int
    reset_time: datetime
    retry_after: Optional[int] = None


# WebSocket authentication schemas
class WebSocketAuthRequest(BaseModel):
    """WebSocket authentication request"""
    token: str = Field(..., description="JWT access token")
    channel: str = Field(..., description="Channel to subscribe to")


class WebSocketAuthResponse(BaseModel):
    """WebSocket authentication response"""
    authenticated: bool
    user_id: Optional[int] = None
    channels: List[str] = []
    error: Optional[str] = None


# Export all schemas
__all__ = [
    # Request schemas
    "UserRegisterRequest",
    "UserLoginRequest", 
    "TokenRefreshRequest",
    "ChangePasswordRequest",
    "TwoFactorSetupRequest",
    "TwoFactorVerifyRequest",
    "BulkUserRequest",
    "WebSocketAuthRequest",
    
    # Response schemas
    "UserResponse",
    "TokenResponse",
    "TokenRefreshResponse", 
    "LogoutResponse",
    "UserPermissionResponse",
    "UserSessionResponse",
    "AuthStatusResponse",
    "PasswordValidationResponse",
    "SecurityEventResponse",
    "AccountSecurityResponse",
    "TwoFactorSetupResponse",
    "ApiKeyResponse",
    "ErrorResponse",
    "BulkUserResponse",
    "PasswordPolicyResponse",
    "RateLimitResponse",
    "WebSocketAuthResponse",
]
