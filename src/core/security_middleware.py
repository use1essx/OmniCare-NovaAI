"""
Healthcare AI V2 - Security Middleware
Enhanced security headers and middleware for production deployment
"""

from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add comprehensive security headers to all HTTP responses
    """
    
    def __init__(self, app, enable_hsts: bool = False):
        super().__init__(app)
        self.enable_hsts = enable_hsts
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Security Headers
        security_headers = {
            # Prevent MIME type sniffing
            "X-Content-Type-Options": "nosniff",
            
            # Prevent clickjacking
            "X-Frame-Options": "DENY",
            
            # XSS Protection (legacy but still useful)
            "X-XSS-Protection": "1; mode=block",
            
            # Content Security Policy
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.tailwindcss.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
                "img-src 'self' data: blob:; "
                "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "connect-src 'self' http://localhost:8790 ws://localhost:8790; "
                "media-src 'self' blob:; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            ),
            
            # Referrer Policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Permissions Policy
            "Permissions-Policy": (
                "camera=(), microphone=(self), geolocation=(), "
                "payment=(), usb=(), magnetometer=(), gyroscope=()"
            ),
            
            # Remove server information
            "Server": "Healthcare-AI-V2"
        }
        
        # Add HSTS header for HTTPS (only in production)
        if self.enable_hsts and request.url.scheme == "https":
            security_headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        # Apply all security headers
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Enhanced request logging for security monitoring
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Log request details
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log response details
        logger.info(
            f"Request: {request.method} {request.url.path} | "
            f"Status: {response.status_code} | "
            f"Time: {process_time:.3f}s | "
            f"IP: {client_ip} | "
            f"UA: {user_agent[:50]}..."
        )
        
        # Add processing time header
        response.headers["X-Process-Time"] = str(process_time)
        
        return response


class EnhancedCORSMiddleware(BaseHTTPMiddleware):
    """
    Enhanced CORS middleware with stricter controls
    """
    
    def __init__(self, app, allowed_origins: list = None, allowed_methods: list = None):
        super().__init__(app)
        self.allowed_origins = allowed_origins or [
            "http://localhost:3000",
            "http://localhost:8000",
            "http://localhost:8080",
            "https://healthcare-ai.com"  # Add your production domain
        ]
        self.allowed_methods = allowed_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        origin = request.headers.get("origin")
        
        # Handle preflight requests
        if request.method == "OPTIONS":
            response = Response()
        else:
            response = await call_next(request)
        
        # Apply CORS headers if origin is allowed
        if origin in self.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allowed_methods)
            response.headers["Access-Control-Allow-Headers"] = (
                "Authorization, Content-Type, Accept, Origin, User-Agent, "
                "Cache-Control, Keep-Alive, X-Requested-With"
            )
        
        return response


class RequestSizeMiddleware(BaseHTTPMiddleware):
    """
    Limit request size to prevent DoS attacks
    """
    
    def __init__(self, app, max_size: int = 10 * 1024 * 1024):  # 10MB default
        super().__init__(app)
        self.max_size = max_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check Content-Length header
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            logger.warning(f"Request size {content_length} exceeds limit {self.max_size}")
            return Response(
                content="Request too large",
                status_code=413,
                headers={"Content-Type": "text/plain"}
            )
        
        return await call_next(request)


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    """
    Security audit logging for suspicious activities
    """
    
    SUSPICIOUS_PATTERNS = [
        "union select", "drop table", "exec(", "eval(", 
        "<script", "javascript:", "data:text/html",
        "../", "..\\", "/etc/passwd", "cmd.exe"
    ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check for suspicious patterns in URL and headers
        url_path = str(request.url.path).lower()
        query_params = str(request.url.query).lower()
        user_agent = request.headers.get("user-agent", "").lower()
        
        suspicious_found = []
        for pattern in self.SUSPICIOUS_PATTERNS:
            if (pattern in url_path or 
                pattern in query_params or 
                pattern in user_agent):
                suspicious_found.append(pattern)
        
        if suspicious_found:
            client_ip = request.client.host if request.client else "unknown"
            logger.warning(
                f"SECURITY ALERT: Suspicious patterns detected | "
                f"IP: {client_ip} | "
                f"Path: {request.url.path} | "
                f"Patterns: {suspicious_found} | "
                f"UA: {request.headers.get('user-agent', 'unknown')}"
            )
        
        return await call_next(request)
