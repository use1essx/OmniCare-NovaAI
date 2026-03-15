"""
Healthcare AI V2 - Authentication Handlers
Core authentication logic, JWT management, and security operations
"""

import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional

from jose import JWTError, jwt

from src.core.config import settings
from src.core.exceptions import (
    AuthenticationError,
    SecurityError,
    ValidationError,
)
from src.core.logging import get_logger, log_security_event
from src.security.auth import PasswordValidator, get_password_hash, verify_password

# Create instances for backward compatibility
password_validator = PasswordValidator()

# Ensure functions are not bound as methods (which adds implicit 'self')
# Use staticmethod wrappers so calls remain (plain_password, hashed_password)
class _PasswordHasherCompat:
    @staticmethod
    def hash_password(password: str) -> str:
        return get_password_hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return verify_password(plain_password, hashed_password)

password_hasher = _PasswordHasherCompat()
from src.database.repositories.user_repository import UserRepository, UserSessionRepository  # noqa: E402
from src.web.auth.schemas import (  # noqa: E402
    PasswordValidationResponse,
    TokenResponse,
    UserResponse,
)

logger = get_logger(__name__)


class AuthenticationHandler:
    """Main authentication handler for user login, registration, and token management"""
    
    def __init__(self):
        self.user_repo = UserRepository()
        self.session_repo = UserSessionRepository()
        self.jwt_algorithm = "HS256"
        self.access_token_expire_minutes = settings.access_token_expire_minutes
        self.refresh_token_expire_days = settings.refresh_token_expire_days
        
    def verify_token(self, token: str) -> Optional[Dict]:
        """
        Verify and decode JWT token
        
        Args:
            token: JWT token to verify
            
        Returns:
            Token payload dict if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[self.jwt_algorithm]
            )
            return payload
        except JWTError:
            return None
        
    async def authenticate_user(
        self,
        email_or_username: str,
        password: str,
        ip_address: str,
        user_agent: str,
        remember_me: bool = False
    ) -> TokenResponse:
        """
        Authenticate user with email/username and password
        
        Args:
            email_or_username: User's email or username
            password: User's password
            ip_address: Client IP address
            user_agent: Client user agent
            remember_me: Whether to extend token lifetime
            
        Returns:
            TokenResponse with access/refresh tokens and user info
            
        Raises:
            AuthenticationError: If authentication fails
            SecurityError: If account is locked or other security issues
        """
        try:
            # Determine if input is email or username
            user = None
            if "@" in email_or_username:
                user = await self.user_repo.get_by_email(email_or_username)
            else:
                user = await self.user_repo.get_by_username(email_or_username)
                
            if not user:
                await self._log_failed_login(email_or_username, ip_address, "user_not_found")
                raise AuthenticationError("Invalid credentials")
                
            # Check if account is locked
            if await self.user_repo.is_account_locked(user.id):
                await self._log_failed_login(
                    email_or_username, ip_address, "account_locked", user.id
                )
                lockout_time = user.account_locked_until
                raise SecurityError(
                    f"Account is locked until {lockout_time}",
                    context={"lockout_until": lockout_time.isoformat() if lockout_time else None}
                )
                
            # Check if account is active
            if not user.is_active:
                await self._log_failed_login(
                    email_or_username, ip_address, "account_inactive", user.id
                )
                raise AuthenticationError("Account is not active")
                
            # Verify password
            if not password_hasher.verify_password(password, user.hashed_password):
                # Increment failed login attempts
                await self.user_repo.increment_failed_attempts(user.id)
                await self._log_failed_login(
                    email_or_username, ip_address, "invalid_password", user.id
                )
                
                # Check if account should be locked
                if user.failed_login_attempts + 1 >= settings.max_login_attempts:
                    lockout_duration = timedelta(minutes=settings.account_lockout_duration_minutes)
                    await self._lock_account(user.id, lockout_duration)
                    
                raise AuthenticationError("Invalid credentials")
                
            # Reset failed attempts on successful login
            await self.user_repo.reset_failed_attempts(user.id)
            await self.user_repo.update_last_login(user.id)
            
            # Generate tokens
            access_token_expires = timedelta(
                minutes=self.access_token_expire_minutes * (7 if remember_me else 1)
            )
            refresh_token_expires = timedelta(
                days=self.refresh_token_expire_days * (4 if remember_me else 1)
            )
            
            access_token = self._create_access_token(
                user.id, user.email, user.role, access_token_expires
            )
            refresh_token = self._create_refresh_token(user.id, refresh_token_expires)
            
            # Create session record
            session_expires = datetime.utcnow() + refresh_token_expires
            await self.session_repo.create_session(
                user_id=user.id,
                session_token=access_token,
                expires_at=session_expires,
                ip_address=ip_address,
                user_agent=user_agent,
                refresh_token=refresh_token
            )
            
            # Log successful login
            log_security_event(
                event_type="user_login",
                description=f"User {user.email} logged in successfully",
                user_id=user.id,
                ip_address=ip_address,
                risk_level="low"
            )
            
            # Prepare user response
            user_response = UserResponse.model_validate(user)
            
            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=int(access_token_expires.total_seconds()),
                user=user_response
            )
            
        except (AuthenticationError, SecurityError):
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise AuthenticationError("Authentication failed")
            
    async def register_user(
        self,
        email: str,
        username: str,
        password: str,
        full_name: str,
        **kwargs
    ) -> UserResponse:
        """
        Register a new user
        
        Args:
            email: User's email address
            username: Unique username
            password: User's password
            full_name: User's full name
            **kwargs: Additional user data
            
        Returns:
            UserResponse with created user info
            
        Raises:
            ValidationError: If validation fails
            SecurityError: If user creation fails
        """
        try:
            # Check if user already exists
            existing_user = await self.user_repo.get_by_email(email)
            if existing_user:
                raise ValidationError("Email address is already registered")
                
            existing_user = await self.user_repo.get_by_username(username)
            if existing_user:
                raise ValidationError("Username is already taken")
                
            # Validate password
            user_info = {
                "email": email,
                "username": username,
                "full_name": full_name
            }
            password_validation = password_validator.validate(password, user_info)
            
            if not password_validation["is_valid"]:
                raise ValidationError(
                    "Password does not meet security requirements",
                    context={"errors": password_validation["errors"]}
                )
                
            # Hash password
            hashed_password = password_hasher.hash_password(password)
            
            # Create user
            user_data = {
                "email": email,
                "username": username.lower(),
                "hashed_password": hashed_password,
                "full_name": full_name,
                **kwargs
            }
            
            user = await self.user_repo.create(user_data)
            
            # Log user registration
            log_security_event(
                event_type="user_registration",
                description=f"New user registered: {email}",
                user_id=user.id,
                risk_level="low"
            )
            
            return UserResponse.model_validate(user)
            
        except (ValidationError, SecurityError):
            raise
        except Exception as e:
            logger.error(f"User registration error: {e}")
            raise SecurityError("User registration failed")
            
    async def refresh_token(self, refresh_token: str, ip_address: str) -> Dict:
        """
        Refresh access token using refresh token
        
        Args:
            refresh_token: Valid refresh token
            ip_address: Client IP address
            
        Returns:
            New access token and expiration info
            
        Raises:
            AuthenticationError: If refresh token is invalid
        """
        try:
            # Decode refresh token
            payload = jwt.decode(
                refresh_token,
                settings.jwt_secret_key,
                algorithms=[self.jwt_algorithm]
            )
            
            user_id = payload.get("sub")
            token_type = payload.get("type")
            
            if token_type != "refresh":
                raise AuthenticationError("Invalid token type")
                
            # Get user and session
            user = await self.user_repo.get_by_id(int(user_id))
            if not user or not user.is_active:
                raise AuthenticationError("User not found or inactive")
                
            session = await self.session_repo.get_by_field("refresh_token", refresh_token)
            if not session or not session.is_active:
                raise AuthenticationError("Invalid or expired session")
                
            # Verify session belongs to user
            if session.user_id != user.id:
                raise AuthenticationError("Token mismatch")
                
            # Generate new access token
            access_token_expires = timedelta(minutes=self.access_token_expire_minutes)
            access_token = self._create_access_token(
                user.id, user.email, user.role, access_token_expires
            )
            
            # Update session token
            await self.session_repo.update(session.id, {
                "session_token": access_token,
                "last_activity": datetime.utcnow()
            })
            
            # Log token refresh
            log_security_event(
                event_type="token_refresh",
                description=f"Access token refreshed for user {user.email}",
                user_id=user.id,
                ip_address=ip_address,
                risk_level="low"
            )
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": int(access_token_expires.total_seconds())
            }
            
        except JWTError:
            raise AuthenticationError("Invalid refresh token")
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            raise AuthenticationError("Token refresh failed")
            
    async def logout_user(
        self,
        access_token: str,
        ip_address: str,
        logout_all: bool = False
    ) -> Dict:
        """
        Logout user by revoking tokens
        
        Args:
            access_token: Current access token
            ip_address: Client IP address
            logout_all: Whether to logout from all sessions
            
        Returns:
            Logout confirmation with revoked session count
        """
        try:
            # Decode token to get user info
            payload = jwt.decode(
                access_token,
                settings.jwt_secret_key,
                algorithms=[self.jwt_algorithm]
            )
            
            user_id = int(payload.get("sub"))
            
            if logout_all:
                # Revoke all sessions for user
                revoked_count = await self.session_repo.revoke_all_sessions(user_id)
            else:
                # Revoke current session only
                session = await self.session_repo.get_by_field("session_token", access_token)
                if session:
                    await self.session_repo.revoke_session(session.id, "user_logout")
                    revoked_count = 1
                else:
                    revoked_count = 0
                    
            # Log logout
            log_security_event(
                event_type="user_logout",
                description=f"User logout - revoked {revoked_count} sessions",
                user_id=user_id,
                ip_address=ip_address,
                risk_level="low"
            )
            
            return {
                "message": "Logged out successfully",
                "revoked_sessions": revoked_count
            }
            
        except JWTError:
            raise AuthenticationError("Invalid access token")
        except Exception as e:
            logger.error(f"Logout error: {e}")
            raise AuthenticationError("Logout failed")
            
    async def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
        ip_address: str
    ) -> Dict:
        """
        Change user password
        
        Args:
            user_id: User ID
            current_password: Current password
            new_password: New password
            ip_address: Client IP address
            
        Returns:
            Success confirmation
            
        Raises:
            AuthenticationError: If current password is incorrect
            ValidationError: If new password is invalid
        """
        try:
            # Get user
            user = await self.user_repo.get_by_id(user_id)
            if not user:
                raise AuthenticationError("User not found")
                
            # Verify current password
            if not password_hasher.verify_password(current_password, user.hashed_password):
                log_security_event(
                    event_type="password_change_failed",
                    description="Incorrect current password provided",
                    user_id=user_id,
                    ip_address=ip_address,
                    risk_level="medium"
                )
                raise AuthenticationError("Current password is incorrect")
                
            # Validate new password
            user_info = {
                "email": user.email,
                "username": user.username,
                "full_name": user.full_name
            }
            password_validation = password_validator.validate(new_password, user_info)
            
            if not password_validation["is_valid"]:
                raise ValidationError(
                    "New password does not meet security requirements",
                    context={"errors": password_validation["errors"]}
                )
                
            # Hash new password
            new_hashed_password = password_hasher.hash_password(new_password)
            
            # Update password
            await self.user_repo.change_password(user_id, new_hashed_password)
            
            # Revoke all existing sessions to force re-login
            await self.session_repo.revoke_all_sessions(user_id)
            
            # Log password change
            log_security_event(
                event_type="password_changed",
                description="User password changed successfully",
                user_id=user_id,
                ip_address=ip_address,
                risk_level="medium"
            )
            
            return {"message": "Password changed successfully"}
            
        except (AuthenticationError, ValidationError):
            raise
        except Exception as e:
            logger.error(f"Password change error: {e}")
            raise SecurityError("Password change failed")
            
    def validate_password_strength(self, password: str, user_info: Optional[Dict] = None) -> PasswordValidationResponse:
        """
        Validate password strength without storing
        
        Args:
            password: Password to validate
            user_info: Optional user info for context
            
        Returns:
            PasswordValidationResponse with validation results
        """
        validation_result = password_validator.validate(password, user_info)
        
        return PasswordValidationResponse(
            is_valid=validation_result["is_valid"],
            errors=validation_result["errors"],
            strength_score=validation_result["strength_score"],
            suggestions=validation_result["suggestions"]
        )
        
    def _create_access_token(
        self,
        user_id: int,
        email: str,
        role: str,
        expires_delta: timedelta
    ) -> str:
        """Create JWT access token"""
        to_encode = {
            "sub": str(user_id),
            "email": email,
            "role": role,
            "type": "access",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + expires_delta
        }
        
        return jwt.encode(
            to_encode,
            settings.jwt_secret_key,
            algorithm=self.jwt_algorithm
        )
        
    def _create_refresh_token(self, user_id: int, expires_delta: timedelta) -> str:
        """Create JWT refresh token"""
        to_encode = {
            "sub": str(user_id),
            "type": "refresh",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + expires_delta,
            "jti": secrets.token_hex(16)  # Unique token ID
        }
        
        return jwt.encode(
            to_encode,
            settings.jwt_secret_key,
            algorithm=self.jwt_algorithm
        )
        
    async def _log_failed_login(
        self,
        identifier: str,
        ip_address: str,
        reason: str,
        user_id: Optional[int] = None
    ):
        """Log failed login attempt"""
        log_security_event(
            event_type="login_failed",
            description=f"Failed login attempt: {reason}",
            user_id=user_id,
            ip_address=ip_address,
            risk_level="medium",
            identifier=identifier,
            failure_reason=reason
        )
        
    async def _lock_account(self, user_id: int, duration: timedelta):
        """Lock user account for specified duration"""
        lockout_until = datetime.utcnow() + duration
        await self.user_repo.update(user_id, {
            "account_locked_until": lockout_until
        })
        
        log_security_event(
            event_type="account_locked",
            description=f"Account locked until {lockout_until}",
            user_id=user_id,
            risk_level="high"
        )


class TokenValidator:
    """JWT token validation and parsing utilities"""
    
    def __init__(self):
        self.jwt_algorithm = "HS256"
        
    def decode_token(self, token: str) -> Dict:
        """
        Decode and validate JWT token
        
        Args:
            token: JWT token to decode
            
        Returns:
            Token payload
            
        Raises:
            AuthenticationError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[self.jwt_algorithm]
            )
            
            # Check token type
            if payload.get("type") != "access":
                raise AuthenticationError("Invalid token type")
                
            return payload
            
        except JWTError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")
            
    def extract_user_id(self, token: str) -> int:
        """Extract user ID from token"""
        payload = self.decode_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            raise AuthenticationError("Token missing user ID")
            
        try:
            return int(user_id)
        except (ValueError, TypeError):
            raise AuthenticationError("Invalid user ID in token")
            
    def extract_user_role(self, token: str) -> str:
        """Extract user role from token"""
        payload = self.decode_token(token)
        role = payload.get("role")
        
        if not role:
            raise AuthenticationError("Token missing user role")
            
        return role
        
    def is_token_expired(self, token: str) -> bool:
        """Check if token is expired"""
        try:
            payload = self.decode_token(token)
            exp = payload.get("exp")
            
            if not exp:
                return True
                
            return datetime.utcnow().timestamp() > exp
            
        except AuthenticationError:
            return True



# PermissionChecker retired in favor of centralized PermissionService
# Create global instances
auth_handler = AuthenticationHandler()
token_validator = TokenValidator()

# Export handlers
__all__ = [
    "AuthenticationHandler",
    "TokenValidator",
    "auth_handler",
    "token_validator",
]
