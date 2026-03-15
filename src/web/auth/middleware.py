"""
Healthcare AI V2 - Authentication Middleware
Middleware for authentication, authorization, and security
"""

import time
from datetime import datetime, timedelta
from typing import Callable, List, Optional

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.exceptions import AuthenticationError, AuthorizationError
from src.core.logging import get_logger, log_security_event
from src.security.auth import IPValidator, SecurityHeaders
from src.database.repositories.user_repository import UserRepository, UserSessionRepository
from src.web.auth.handlers import token_validator

logger = get_logger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for protected routes
    
    Automatically validates JWT tokens for protected endpoints and
    injects user information into request state.
    """
    
    def __init__(self, app, protected_paths: Optional[List[str]] = None):
        super().__init__(app)
        self.user_repo = UserRepository()
        self.session_repo = UserSessionRepository()
        
        # Default protected paths
        self.protected_paths = protected_paths or [
            "/api/v1/agents",
            "/api/v1/conversations", 
            "/api/v1/data",
            "/api/v1/admin",
            "/api/v1/users"
        ]
        
        # Paths that are always public
        self.public_paths = [
            "/",
            "/health",
            "/docs",
            "/openapi.json",
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
            "/api/v1/auth/password-policy"
        ]
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through authentication middleware"""
        start_time = time.time()
        
        try:
            # Check if path requires authentication
            if self._is_protected_path(request.url.path):
                await self._authenticate_request(request)
                
            # Process request
            response = await call_next(request)
            
            # Add security headers
            self._add_security_headers(response)
            
            # Log request if user is authenticated
            if hasattr(request.state, "current_user"):
                processing_time = int((time.time() - start_time) * 1000)
                await self._log_authenticated_request(request, response, processing_time)
                
            return response
            
        except AuthenticationError as e:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": str(e),
                    "error_type": "authentication_error",
                    "timestamp": datetime.utcnow().isoformat()
                },
                headers={"WWW-Authenticate": "Bearer"}
            )
        except AuthorizationError as e:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": str(e),
                    "error_type": "authorization_error",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Authentication middleware error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal server error",
                    "error_type": "middleware_error",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
    def _is_protected_path(self, path: str) -> bool:
        """Check if path requires authentication"""
        # Check public paths first
        for public_path in self.public_paths:
            if path.startswith(public_path):
                return False
                
        # Check protected paths
        for protected_path in self.protected_paths:
            if path.startswith(protected_path):
                return True
                
        return False
        
    async def _authenticate_request(self, request: Request):
        """Authenticate request and inject user information"""
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise AuthenticationError("Missing or invalid authorization header")
            
        token = auth_header.split(" ")[1]
        
        # Validate token
        payload = token_validator.decode_token(token)
        user_id = int(payload.get("sub"))
        
        # Get user from database
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AuthenticationError("User not found")
            
        # Check if user is active
        if not user.is_active:
            raise AuthenticationError("User account is disabled")
            
        # Check if account is locked
        if await self.user_repo.is_account_locked(user.id):
            raise AuthenticationError("Account is temporarily locked")
            
        # Verify session exists and is active
        session = await self.session_repo.get_by_field("session_token", token)
        if not session or not session.is_active:
            raise AuthenticationError("Invalid or expired session")
            
        # Update session activity
        await self.session_repo.update_activity(session.id)
        
        # Inject user and session into request state
        request.state.current_user = user
        request.state.current_session = session
        request.state.user_id = user.id
        request.state.user_role = user.role
        
    def _add_security_headers(self, response: Response):
        """Add security headers to response"""
        security_headers = SecurityHeaders.get_security_headers()
        for header, value in security_headers.items():
            response.headers[header] = value
            
    async def _log_authenticated_request(
        self, 
        request: Request, 
        response: Response, 
        processing_time: int
    ):
        """Log authenticated request for audit purposes"""
        if hasattr(request.state, "current_user"):
            user = request.state.current_user
            
            # Log API request
            log_data = {
                "user_id": user.id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "processing_time_ms": processing_time,
                "ip_address": self._get_client_ip(request),
                "user_agent": request.headers.get("User-Agent", "")
            }
            
            # Determine risk level based on status code and path
            if response.status_code >= 400:
                pass
            if request.url.path.startswith("/api/v1/admin"):
                pass
                
            logger.info(f"API request: {request.method} {request.url.path}", extra=log_data)
            
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
            
        forwarded = request.headers.get("X-Real-IP")
        if forwarded:
            return forwarded
            
        return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware with Redis-like in-memory storage
    
    Implements rate limiting per IP address and per user for different
    endpoint categories.
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.requests = {}  # In production, use Redis
        
        # Rate limits for different endpoint types
        self.rate_limits = {
            "auth": {"max_requests": 5, "window_seconds": 60},      # Auth endpoints
            "api": {"max_requests": 100, "window_seconds": 60},     # Regular API
            "upload": {"max_requests": 10, "window_seconds": 300},  # File uploads
            "admin": {"max_requests": 50, "window_seconds": 60},    # Admin endpoints
        }
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through rate limiting middleware"""
        try:
            # Determine rate limit category
            category = self._get_rate_limit_category(request.url.path)
            
            if category:
                # Check rate limit
                client_id = self._get_client_identifier(request)
                await self._check_rate_limit(client_id, category, request)
                
            # Process request
            response = await call_next(request)
            
            # Record successful request
            if category:
                await self._record_request(client_id, category)
                
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rate limit middleware error: {e}")
            return await call_next(request)
            
    def _get_rate_limit_category(self, path: str) -> Optional[str]:
        """Determine rate limit category for path"""
        if path.startswith("/api/v1/auth"):
            return "auth"
        elif path.startswith("/api/v1/admin"):
            return "admin"
        elif "/upload" in path:
            return "upload"
        elif path.startswith("/api/v1"):
            return "api"
        return None
        
    def _get_client_identifier(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Use user ID if authenticated, otherwise IP
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"
        else:
            client_ip = self._get_client_ip(request)
            return f"ip:{client_ip}"
            
    async def _check_rate_limit(self, client_id: str, category: str, request: Request):
        """Check if client has exceeded rate limit"""
        limit_config = self.rate_limits[category]
        max_requests = limit_config["max_requests"]
        window_seconds = limit_config["window_seconds"]
        
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window_seconds)
        
        # Get client request history
        if client_id not in self.requests:
            self.requests[client_id] = {}
        if category not in self.requests[client_id]:
            self.requests[client_id][category] = []
            
        request_times = self.requests[client_id][category]
        
        # Remove old requests
        request_times[:] = [
            req_time for req_time in request_times 
            if req_time > window_start
        ]
        
        # Check limit
        if len(request_times) >= max_requests:
            # Calculate reset time
            oldest_request = min(request_times) if request_times else now
            reset_time = oldest_request + timedelta(seconds=window_seconds)
            retry_after = int((reset_time - now).total_seconds())
            
            # Log rate limit violation
            await self._log_rate_limit_violation(client_id, category, request)
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_time.timestamp())),
                    "Retry-After": str(retry_after)
                }
            )
            
    async def _record_request(self, client_id: str, category: str):
        """Record successful request"""
        now = datetime.utcnow()
        if client_id not in self.requests:
            self.requests[client_id] = {}
        if category not in self.requests[client_id]:
            self.requests[client_id][category] = []
            
        self.requests[client_id][category].append(now)
        
    async def _log_rate_limit_violation(
        self, 
        client_id: str, 
        category: str, 
        request: Request
    ):
        """Log rate limit violation"""
        log_security_event(
            event_type="rate_limit_exceeded",
            description=f"Rate limit exceeded for {category} endpoints",
            ip_address=self._get_client_ip(request),
            risk_level="medium",
            client_id=client_id,
            category=category,
            path=request.url.path
        )
        
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
            
        forwarded = request.headers.get("X-Real-IP")
        if forwarded:
            return forwarded
            
        return request.client.host if request.client else "unknown"


class IPSecurityMiddleware(BaseHTTPMiddleware):
    """
    IP-based security middleware
    
    Blocks suspicious IP addresses and logs security events.
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.blocked_ips = set()  # In production, use Redis/database
        self.suspicious_activities = {}  # Track suspicious patterns
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through IP security middleware"""
        client_ip = self._get_client_ip(request)
        
        try:
            # Validate IP address
            IPValidator.validate_ip(client_ip)
            
            # Check if IP is blocked
            if client_ip in self.blocked_ips:
                await self._log_blocked_ip_attempt(client_ip, request)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied from this IP address"
                )
                
            # Check for suspicious patterns
            await self._check_suspicious_activity(client_ip, request)
            
            # Process request
            response = await call_next(request)
            
            # Update activity tracking
            await self._update_activity_tracking(client_ip, request, response)
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"IP security middleware error: {e}")
            return await call_next(request)
            
    async def _check_suspicious_activity(self, client_ip: str, request: Request):
        """Check for suspicious activity patterns"""
        now = datetime.utcnow()
        
        # Initialize tracking for new IPs
        if client_ip not in self.suspicious_activities:
            self.suspicious_activities[client_ip] = {
                "failed_auth_attempts": [],
                "suspicious_paths": [],
                "rapid_requests": [],
                "last_request": None
            }
            
        activity = self.suspicious_activities[client_ip]
        
        # Check for rapid requests (potential DDoS)
        if activity["last_request"]:
            time_diff = (now - activity["last_request"]).total_seconds()
            if time_diff < 0.1:  # Less than 100ms between requests
                activity["rapid_requests"].append(now)
                
                # Check if too many rapid requests
                recent_rapid = [
                    req for req in activity["rapid_requests"]
                    if (now - req).total_seconds() < 60
                ]
                
                if len(recent_rapid) > 50:  # More than 50 rapid requests per minute
                    await self._handle_suspicious_activity(
                        client_ip, "rapid_requests", request
                    )
                    
        activity["last_request"] = now
        
        # Check for suspicious paths
        suspicious_patterns = [
            "/admin", "/.env", "/config", "/backup",
            "/wp-admin", "/phpmyadmin", "/api/v1/admin"
        ]
        
        path = request.url.path
        for pattern in suspicious_patterns:
            if pattern in path.lower():
                activity["suspicious_paths"].append((now, path))
                
                # Check frequency of suspicious path access
                recent_suspicious = [
                    entry for entry in activity["suspicious_paths"]
                    if (now - entry[0]).total_seconds() < 300  # 5 minutes
                ]
                
                if len(recent_suspicious) > 5:
                    await self._handle_suspicious_activity(
                        client_ip, "suspicious_paths", request
                    )
                    
    async def _handle_suspicious_activity(
        self, 
        client_ip: str, 
        activity_type: str, 
        request: Request
    ):
        """Handle detected suspicious activity"""
        # Log security event
        log_security_event(
            event_type="suspicious_activity",
            description=f"Suspicious {activity_type} detected from IP {client_ip}",
            ip_address=client_ip,
            risk_level="high",
            activity_type=activity_type,
            path=request.url.path
        )
        
        # For demo purposes, just log. In production, might block IP temporarily
        logger.warning(f"Suspicious {activity_type} from IP {client_ip}")
        
    async def _update_activity_tracking(
        self, 
        client_ip: str, 
        request: Request, 
        response: Response
    ):
        """Update activity tracking for IP"""
        # Track failed authentication attempts
        if (request.url.path.startswith("/api/v1/auth") and 
            response.status_code in [401, 403]):
            
            if client_ip in self.suspicious_activities:
                now = datetime.utcnow()
                self.suspicious_activities[client_ip]["failed_auth_attempts"].append(now)
                
                # Check for too many failed auth attempts
                recent_failures = [
                    attempt for attempt in 
                    self.suspicious_activities[client_ip]["failed_auth_attempts"]
                    if (now - attempt).total_seconds() < 300  # 5 minutes
                ]
                
                if len(recent_failures) > 10:  # More than 10 failures in 5 minutes
                    await self._handle_suspicious_activity(
                        client_ip, "failed_auth_attempts", request
                    )
                    
    async def _log_blocked_ip_attempt(self, client_ip: str, request: Request):
        """Log attempt from blocked IP"""
        log_security_event(
            event_type="blocked_ip_attempt",
            description=f"Access attempt from blocked IP {client_ip}",
            ip_address=client_ip,
            risk_level="high",
            path=request.url.path
        )
        
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
            
        forwarded = request.headers.get("X-Real-IP")
        if forwarded:
            return forwarded
            
        return request.client.host if request.client else "unknown"


class SessionTimeoutMiddleware(BaseHTTPMiddleware):
    """
    Session timeout middleware
    
    Automatically expires sessions based on inactivity and maximum lifetime.
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.session_repo = UserSessionRepository()
        self.max_session_lifetime = timedelta(days=7)  # Maximum session lifetime
        self.inactivity_timeout = timedelta(minutes=30)  # Inactivity timeout
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through session timeout middleware"""
        try:
            # Check session timeout for authenticated requests
            if hasattr(request.state, "current_session"):
                session = request.state.current_session
                await self._check_session_timeout(session)
                
            return await call_next(request)
            
        except Exception as e:
            logger.error(f"Session timeout middleware error: {e}")
            return await call_next(request)
            
    async def _check_session_timeout(self, session):
        """Check if session has timed out"""
        now = datetime.utcnow()
        
        # Check maximum lifetime
        if session.created_at and (now - session.created_at) > self.max_session_lifetime:
            await self.session_repo.revoke_session(
                session.id, "session_lifetime_exceeded"
            )
            raise AuthenticationError("Session has exceeded maximum lifetime")
            
        # Check inactivity timeout
        last_activity = session.last_activity or session.created_at
        if last_activity and (now - last_activity) > self.inactivity_timeout:
            await self.session_repo.revoke_session(
                session.id, "session_inactivity_timeout"
            )
            raise AuthenticationError("Session has timed out due to inactivity")


# Export middleware classes
__all__ = [
    "AuthenticationMiddleware",
    "RateLimitMiddleware", 
    "IPSecurityMiddleware",
    "SessionTimeoutMiddleware",
]
