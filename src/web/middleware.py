"""
Healthcare AI V2 - Middleware Components
Custom middleware for security, logging, and request handling
"""

import time
import uuid
from typing import Callable, Dict
import asyncio
from collections import defaultdict

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.config import settings
from src.core.logging import get_logger, log_api_request, log_security_event

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        path = request.url.path or ""
        # Treat root path and /live2d paths as Live2D app
        is_live2d_route = "/live2d" in path or path == "/" or path == "/index.html"
        
        if settings.enable_live2d_security_headers:
            # Allow microphone for Live2D routes (voice chat feature)
            if is_live2d_route:
                response.headers["Permissions-Policy"] = settings.live2d_permissions_policy
            else:
                response.headers["Permissions-Policy"] = settings.default_permissions_policy
            
            # Content Security Policy (needed even in dev when tunneling through preview domains)
            apply_csp = settings.live2d_enable_csp and (is_live2d_route or settings.is_production)
            if apply_csp:
                connect_sources = ["'self'"]
                connect_sources.extend(settings.live2d_connect_sources or [])
                # Deduplicate while preserving order
                seen = set()
                deduped_sources = []
                for source in connect_sources:
                    normalized = source.strip()
                    if not normalized:
                        continue
                    if normalized not in seen:
                        seen.add(normalized)
                        deduped_sources.append(normalized)
                connect_src_value = " ".join(deduped_sources)
                
                csp = (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.tailwindcss.com; "
                    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
                    "img-src 'self' data: https:; "
                    "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                    f"connect-src {connect_src_value}; "
                    "media-src 'self' blob:; "
                    "frame-ancestors 'none';"
                )
                response.headers["Content-Security-Policy"] = csp
        
        # HTTPS enforcement in production
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log all API requests and responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Get client information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        # Log request start
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_ip": client_ip,
                "user_agent": user_agent
            }
        )
        
        try:
            response = await call_next(request)
            
            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            # Log API request
            log_api_request(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                ip_address=client_ip,
                request_id=request_id
            )
            
            return response
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": client_ip,
                    "response_time_ms": response_time_ms,
                    "error": str(e)
                },
                exc_info=True
            )
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers (when behind proxy)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to direct connection
        if request.client:
            return request.client.host
        
        return "unknown"


class BasicRateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware with Redis-like in-memory storage"""
    
    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.requests: Dict[str, list] = defaultdict(list)
        self._cleanup_task = None
        
        # Start cleanup task
        if not self._cleanup_task:
            import asyncio
            self._cleanup_task = asyncio.create_task(self._cleanup_old_requests())
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks and static files
        if request.url.path in ["/health", "/"] or request.url.path.startswith("/static"):
            return await call_next(request)
        
        # Get client identifier
        client_ip = self._get_client_ip(request)
        client_key = f"rate_limit:{client_ip}"
        
        # Check rate limit
        current_time = time.time()
        
        # Clean old requests for this client
        self.requests[client_key] = [
            req_time for req_time in self.requests[client_key]
            if current_time - req_time < self.period
        ]
        
        # Check if rate limit exceeded
        if len(self.requests[client_key]) >= self.calls:
            log_security_event(
                event_type="rate_limit_exceeded",
                description=f"Rate limit exceeded for IP: {client_ip}",
                ip_address=client_ip,
                risk_level="medium",
                requests_count=len(self.requests[client_key]),
                limit=self.calls,
                period=self.period
            )
            
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "error_type": "rate_limit_error",
                    "message": f"Too many requests. Limit: {self.calls} requests per {self.period} seconds",
                    "retry_after": self.period
                },
                headers={"Retry-After": str(self.period)}
            )
        
        # Add current request
        self.requests[client_key].append(current_time)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = max(0, self.calls - len(self.requests[client_key]))
        response.headers["X-RateLimit-Limit"] = str(self.calls)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(current_time + self.period))
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        if request.client:
            return request.client.host
        
        return "unknown"
    
    async def _cleanup_old_requests(self):
        """Periodically cleanup old request records"""
        while True:
            try:
                await asyncio.sleep(self.period)
                current_time = time.time()
                
                # Clean up old requests
                for client_key in list(self.requests.keys()):
                    self.requests[client_key] = [
                        req_time for req_time in self.requests[client_key]
                        if current_time - req_time < self.period
                    ]
                    
                    # Remove empty entries
                    if not self.requests[client_key]:
                        del self.requests[client_key]
                        
            except Exception as e:
                logger.error(f"Error in rate limit cleanup: {e}")


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Global error handling middleware"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
            
        except Exception as e:
            # Log the error
            logger.error(
                f"Unhandled exception in {request.method} {request.url.path}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": dict(request.query_params),
                    "client_ip": self._get_client_ip(request),
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            
            # Return generic error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "error_type": "internal_error",
                    "message": "An unexpected error occurred. Please try again later.",
                    "request_id": getattr(request.state, 'request_id', None)
                }
            )
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        if request.client:
            return request.client.host
        
        return "unknown"


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Add cache control headers based on endpoint"""
    
    def __init__(self, app):
        super().__init__(app)
        
        # Cache control rules
        self.cache_rules = {
            "/static": "public, max-age=31536000",  # 1 year for static files
            "/api/v1/health": "no-cache, no-store, must-revalidate",
            "/api/v1/hk-data": "public, max-age=1800",  # 30 minutes for HK data
            "/docs": "public, max-age=3600",  # 1 hour for docs
            "/openapi.json": "public, max-age=3600",
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Apply cache control based on path
        path = request.url.path
        
        for rule_path, cache_control in self.cache_rules.items():
            if path.startswith(rule_path):
                response.headers["Cache-Control"] = cache_control
                break
        else:
            # Default cache control for API endpoints
            if path.startswith("/api/"):
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            else:
                response.headers["Cache-Control"] = "public, max-age=300"  # 5 minutes
        
        return response
