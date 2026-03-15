"""
Healthcare AI V2 - Advanced Security Middleware
Content security, input validation, and threat detection middleware
"""

import re
import json
import time
from typing import Dict, Any, Callable
from urllib.parse import unquote

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.logging import get_logger, log_security_event
from src.security.monitoring import (
    track_request_security, 
    check_ip_blocked
)


class ContentSecurityMiddleware(BaseHTTPMiddleware):
    """Content Security Policy and security headers middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = get_logger(__name__)
        
        # CSP directives for healthcare application
        self.csp_directives = {
            "default-src": "'self'",
            "script-src": "'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.tailwindcss.com",
            "style-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com https://cdnjs.cloudflare.com",
            "img-src": "'self' data: https: blob:",
            "font-src": "'self' https://fonts.gstatic.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
            "connect-src": "'self'",
            "media-src": "'self' blob:",
            "object-src": "'none'",
            "frame-src": "'none'",
            "frame-ancestors": "'none'",
            "form-action": "'self'",
            "base-uri": "'self'",
            "upgrade-insecure-requests": "",
        }
        
        # Security headers
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": (
                "geolocation=(), microphone=(self), camera=(), "
                "payment=(), usb=(), magnetometer=(), gyroscope=(), "
                "accelerometer=(), ambient-light-sensor=()"
            ),
            "X-Permitted-Cross-Domain-Policies": "none",
            "Cross-Origin-Embedder-Policy": "require-corp",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin"
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Apply security headers to response
        response = await call_next(request)
        
        # Add CSP header
        csp_header = "; ".join([
            f"{directive} {value}" if value else directive
            for directive, value in self.csp_directives.items()
        ])
        response.headers["Content-Security-Policy"] = csp_header
        
        # Add other security headers
        for header, value in self.security_headers.items():
            response.headers[header] = value
        
        # Add custom healthcare security headers
        response.headers["X-Healthcare-API"] = "v2.0"
        response.headers["X-Content-Security"] = "enforced"
        
        return response


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Advanced input validation and sanitization middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = get_logger(__name__)
        
        # Malicious patterns for detection
        self.sql_injection_patterns = [
            r"(\bunion\b.*\bselect\b)",
            r"(\bselect\b.*\bfrom\b)",
            r"(\binsert\b.*\binto\b)",
            r"(\bupdate\b.*\bset\b)",
            r"(\bdelete\b.*\bfrom\b)",
            r"(\bdrop\b.*\btable\b)",
            r"(\balter\b.*\btable\b)",
            r"(--|\#|/\*|\*/)",
            r"(\bor\b.*=.*\bor\b)",
            r"(\band\b.*=.*\band\b)",
            r"('.*'.*=.*'.*')",
            r"(\bexec\b|\bexecute\b)",
            r"(\bsp_\w+)",
            r"(\bxp_\w+)"
        ]
        
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
            r"onclick\s*=",
            r"onmouseover\s*=",
            r"onfocus\s*=",
            r"onblur\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"<applet[^>]*>",
            r"<meta[^>]*>",
            r"<link[^>]*>",
            r"eval\s*\(",
            r"expression\s*\("
        ]
        
        self.command_injection_patterns = [
            r";\s*(rm|del|format|fdisk)",
            r";\s*(cat|type|more|less)",
            r";\s*(ps|netstat|whoami|id)",
            r";\s*(wget|curl|nc|telnet)",
            r"\|\s*(rm|del|format)",
            r"&&\s*(rm|del|format)",
            r"`.*`",
            r"\$\(.*\)",
            r">\s*/dev/null",
            r"2>&1"
        ]
        
        self.path_traversal_patterns = [
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e%2f",
            r"%2e%2e%5c",
            r"..%2f",
            r"..%5c",
            r"%252e%252e%252f"
        ]
        
        # File upload validation
        self.allowed_file_extensions = {
            '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.txt', '.doc', '.docx', 
            '.xls', '.xlsx', '.csv', '.zip', '.json'
        }
        
        self.dangerous_file_extensions = {
            '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js', 
            '.jar', '.ps1', '.sh', '.php', '.asp', '.aspx', '.jsp'
        }
        
        # Compile patterns for performance
        self.compiled_patterns = {
            'sql': [re.compile(pattern, re.IGNORECASE) for pattern in self.sql_injection_patterns],
            'xss': [re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in self.xss_patterns],
            'cmd': [re.compile(pattern, re.IGNORECASE) for pattern in self.command_injection_patterns],
            'path': [re.compile(pattern, re.IGNORECASE) for pattern in self.path_traversal_patterns]
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        client_ip = self._get_client_ip(request)
        
        try:
            # Check if IP is blocked
            is_blocked, unblock_time = await check_ip_blocked(client_ip)
            if is_blocked:
                self.logger.warning(f"Blocked IP {client_ip} attempted access")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied from this IP address"
                )
            
            # Validate request
            await self._validate_request(request)
            
            # Process request
            response = await call_next(request)
            
            # Track successful request
            await track_request_security(
                ip=client_ip,
                endpoint=str(request.url.path),
                method=request.method,
                user_agent=request.headers.get("user-agent", ""),
                payload_size=self._get_content_length(request),
                success=True
            )
            
            processing_time = int((time.time() - start_time) * 1000)
            
            # Add security context to response
            response.headers["X-Request-ID"] = getattr(request.state, 'request_id', 'unknown')
            response.headers["X-Processing-Time"] = str(processing_time)
            
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            self.logger.error(f"Input validation error: {e}")
            
            # Track failed request
            await track_request_security(
                ip=client_ip,
                endpoint=str(request.url.path),
                method=request.method,
                user_agent=request.headers.get("user-agent", ""),
                success=False
            )
            
            # Return generic error to avoid information disclosure
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Invalid request", "request_id": getattr(request.state, 'request_id', 'unknown')}
            )
    
    async def _validate_request(self, request: Request):
        """Comprehensive request validation"""
        # Validate URL and query parameters
        await self._validate_url(request)
        
        # Validate headers
        await self._validate_headers(request)
        
        # Validate body if present
        if request.method in ['POST', 'PUT', 'PATCH']:
            await self._validate_body(request)
        
        # Check for file uploads
        if "multipart/form-data" in request.headers.get("content-type", ""):
            await self._validate_file_upload(request)
    
    async def _validate_url(self, request: Request):
        """Validate URL path and query parameters"""
        path = str(request.url.path)
        query = str(request.url.query)
        
        # Check path traversal attempts
        if self._detect_patterns(path, 'path'):
            await self._log_security_violation(
                request, "path_traversal", 
                {"path": path, "pattern": "path_traversal"}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid path format"
            )
        
        # Check for suspicious query parameters
        if query:
            decoded_query = unquote(query)
            
            for pattern_type in ['sql', 'xss', 'cmd']:
                if self._detect_patterns(decoded_query, pattern_type):
                    await self._log_security_violation(
                        request, f"{pattern_type}_injection",
                        {"query": decoded_query[:200], "pattern": pattern_type}
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid query parameters"
                    )
        
        # Check URL length
        if len(str(request.url)) > 2048:
            await self._log_security_violation(
                request, "oversized_url",
                {"url_length": len(str(request.url))}
            )
            raise HTTPException(
                status_code=status.HTTP_414_URI_TOO_LONG,
                detail="URL too long"
            )
    
    async def _validate_headers(self, request: Request):
        """Validate HTTP headers"""
        headers = request.headers
        
        # Check for malicious headers
        dangerous_headers = ['x-forwarded-for', 'x-real-ip', 'x-originating-ip']
        for header in dangerous_headers:
            if header in headers:
                value = headers[header]
                if self._detect_patterns(value, 'xss') or self._detect_patterns(value, 'cmd'):
                    await self._log_security_violation(
                        request, "malicious_header",
                        {"header": header, "value": value[:100]}
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid header value"
                    )
        
        # Validate User-Agent
        user_agent = headers.get("user-agent", "")
        if len(user_agent) > 512:
            await self._log_security_violation(
                request, "oversized_user_agent",
                {"user_agent_length": len(user_agent)}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user agent"
            )
        
        # Check for suspicious user agents
        suspicious_ua_patterns = [
            r"sqlmap", r"nmap", r"masscan", r"nessus", r"openvas",
            r"nikto", r"dirb", r"dirbuster", r"gobuster", r"wfuzz"
        ]
        
        for pattern in suspicious_ua_patterns:
            if re.search(pattern, user_agent, re.IGNORECASE):
                await self._log_security_violation(
                    request, "suspicious_user_agent",
                    {"user_agent": user_agent, "pattern": pattern}
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
    
    async def _validate_body(self, request: Request):
        """Validate request body"""
        try:
            content_type = request.headers.get("content-type", "")
            content_length = self._get_content_length(request)
            
            # Check content length
            max_size = 10 * 1024 * 1024  # 10MB default
            if "upload" in str(request.url.path):
                max_size = 50 * 1024 * 1024  # 50MB for uploads
            
            if content_length > max_size:
                await self._log_security_violation(
                    request, "oversized_payload",
                    {"content_length": content_length, "max_size": max_size}
                )
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Payload too large"
                )
            
            # Read and validate body content for JSON/form data
            if "application/json" in content_type:
                body = await request.body()
                if body:
                    try:
                        # Parse JSON to validate structure
                        json_data = json.loads(body)
                        await self._validate_json_content(request, json_data)
                    except json.JSONDecodeError:
                        await self._log_security_violation(
                            request, "invalid_json",
                            {"content_type": content_type}
                        )
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid JSON format"
                        )
            
            elif "application/x-www-form-urlencoded" in content_type:
                # Validate form data
                body = await request.body()
                if body:
                    form_data = body.decode('utf-8', errors='ignore')
                    await self._validate_form_data(request, form_data)
                    
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error validating request body: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request body"
            )
    
    async def _validate_json_content(self, request: Request, json_data: Any):
        """Validate JSON content for malicious patterns"""
        json_str = json.dumps(json_data)
        
        # Check for injection patterns in JSON values
        for pattern_type in ['sql', 'xss', 'cmd']:
            if self._detect_patterns(json_str, pattern_type):
                await self._log_security_violation(
                    request, f"{pattern_type}_in_json",
                    {"pattern": pattern_type, "content_preview": json_str[:200]}
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid content in request"
                )
        
        # Check for deeply nested objects (potential DoS)
        if self._check_json_depth(json_data) > 10:
            await self._log_security_violation(
                request, "deep_json_nesting",
                {"depth": self._check_json_depth(json_data)}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="JSON structure too complex"
            )
    
    async def _validate_form_data(self, request: Request, form_data: str):
        """Validate form data for malicious patterns"""
        decoded_data = unquote(form_data)
        
        for pattern_type in ['sql', 'xss', 'cmd']:
            if self._detect_patterns(decoded_data, pattern_type):
                await self._log_security_violation(
                    request, f"{pattern_type}_in_form",
                    {"pattern": pattern_type, "content_preview": decoded_data[:200]}
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid form data"
                )
    
    async def _validate_file_upload(self, request: Request):
        """Validate file upload requests"""
        content_type = request.headers.get("content-type", "")
        
        if "multipart/form-data" not in content_type:
            return
        
        # This is a simplified validation - in practice, you'd parse the multipart data
        # and validate each file's content type, extension, and content
        
        # Check for suspicious boundary patterns
        if "boundary=" in content_type:
            boundary = content_type.split("boundary=")[1].split(";")[0].strip()
            if len(boundary) > 256 or self._detect_patterns(boundary, 'xss'):
                await self._log_security_violation(
                    request, "malicious_boundary",
                    {"boundary": boundary[:100]}
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid upload format"
                )
    
    def _detect_patterns(self, text: str, pattern_type: str) -> bool:
        """Detect malicious patterns in text"""
        if not text or pattern_type not in self.compiled_patterns:
            return False
        
        patterns = self.compiled_patterns[pattern_type]
        return any(pattern.search(text) for pattern in patterns)
    
    def _check_json_depth(self, obj: Any, depth: int = 0) -> int:
        """Check JSON nesting depth"""
        if depth > 15:  # Prevent infinite recursion
            return depth
        
        if isinstance(obj, dict):
            return max([self._check_json_depth(v, depth + 1) for v in obj.values()] + [depth])
        elif isinstance(obj, list):
            return max([self._check_json_depth(item, depth + 1) for item in obj] + [depth])
        else:
            return depth
    
    def _get_content_length(self, request: Request) -> int:
        """Get content length from request"""
        try:
            return int(request.headers.get("content-length", 0))
        except (ValueError, TypeError):
            return 0
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address with proxy support"""
        # Check X-Forwarded-For header (be careful with this in production)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain
            ip = forwarded_for.split(",")[0].strip()
            return ip
        
        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fall back to direct connection IP
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
    
    async def _log_security_violation(self, request: Request, violation_type: str, details: Dict):
        """Log security violation"""
        client_ip = self._get_client_ip(request)
        
        log_security_event(
            event_type=violation_type,
            description=f"Security violation: {violation_type}",
            ip_address=client_ip,
            risk_level="high",
            event_details={
                "url": str(request.url),
                "method": request.method,
                "user_agent": request.headers.get("user-agent", ""),
                "violation_details": details
            }
        )


class AntiAutomationMiddleware(BaseHTTPMiddleware):
    """Anti-automation and bot detection middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = get_logger(__name__)
        
        # Bot detection patterns
        self.bot_patterns = [
            r"bot", r"crawler", r"spider", r"scraper", r"scanner",
            r"curl", r"wget", r"httpclient", r"python-requests",
            r"postman", r"insomnia", r"http", r"fetch"
        ]
        
        # Suspicious behavior thresholds
        self.request_burst_threshold = 20  # requests in 10 seconds
        self.user_agent_rotation_threshold = 5  # different UAs in 1 minute
        
        # Compile patterns
        self.compiled_bot_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.bot_patterns
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        try:
            # Skip certain endpoints from bot detection
            skip_paths = ["/health", "/docs", "/openapi.json", "/favicon.ico"]
            if any(request.url.path.startswith(path) for path in skip_paths):
                return await call_next(request)
            
            # Check for bot patterns in User-Agent
            if self._is_likely_bot(user_agent):
                # Allow some legitimate bots but log them
                legitimate_bots = ["googlebot", "bingbot", "slurp", "duckduckbot"]
                if not any(bot in user_agent.lower() for bot in legitimate_bots):
                    await self._handle_bot_detection(request, "user_agent_bot", user_agent)
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"error": "Automated requests not allowed"}
                    )
            
            # Check for missing or suspicious headers
            await self._check_request_headers(request)
            
            # Check for automation patterns
            await self._check_automation_patterns(request)
            
            response = await call_next(request)
            
            # Add anti-automation headers
            response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet"
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Anti-automation middleware error: {e}")
            return await call_next(request)
    
    def _is_likely_bot(self, user_agent: str) -> bool:
        """Check if user agent indicates a bot"""
        if not user_agent or len(user_agent) < 10:
            return True
        
        return any(pattern.search(user_agent) for pattern in self.compiled_bot_patterns)
    
    async def _check_request_headers(self, request: Request):
        """Check for missing or suspicious headers that indicate automation"""
        headers = request.headers
        
        # Check for missing common browser headers
        common_headers = ["accept", "accept-encoding", "accept-language"]
        missing_headers = [h for h in common_headers if h not in headers]
        
        if len(missing_headers) >= 2:
            await self._handle_bot_detection(
                request, "missing_headers", 
                {"missing": missing_headers}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request headers"
            )
        
        # Check for suspicious header combinations
        accept_header = headers.get("accept", "")
        if accept_header == "*/*" and "browser" not in headers.get("user-agent", "").lower():
            await self._handle_bot_detection(
                request, "suspicious_accept_header",
                {"accept": accept_header}
            )
    
    async def _check_automation_patterns(self, request: Request):
        """Check for automation behavioral patterns"""
        client_ip = self._get_client_ip(request)
        
        # Check request timing patterns (this would need Redis for proper implementation)
        # For now, we'll use a simplified in-memory approach
        
        # Check for rapid sequential requests
        current_time = time.time()
        if not hasattr(self, '_request_times'):
            self._request_times = {}
        
        if client_ip not in self._request_times:
            self._request_times[client_ip] = []
        
        # Clean old entries and add current request
        self._request_times[client_ip] = [
            t for t in self._request_times[client_ip] 
            if current_time - t < 10  # 10 second window
        ]
        self._request_times[client_ip].append(current_time)
        
        # Check for burst of requests
        if len(self._request_times[client_ip]) > self.request_burst_threshold:
            await self._handle_bot_detection(
                request, "request_burst",
                {"requests_in_10s": len(self._request_times[client_ip])}
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests"
            )
    
    async def _handle_bot_detection(self, request: Request, detection_type: str, details: Any):
        """Handle detected bot/automation"""
        client_ip = self._get_client_ip(request)
        
        log_security_event(
            event_type="bot_detection",
            description=f"Bot/automation detected: {detection_type}",
            ip_address=client_ip,
            risk_level="medium",
            event_details={
                "detection_type": detection_type,
                "details": details,
                "url": str(request.url),
                "user_agent": request.headers.get("user-agent", "")
            }
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"


class FileUploadSecurityMiddleware(BaseHTTPMiddleware):
    """File upload security validation middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = get_logger(__name__)
        
        # File type validation
        self.allowed_mime_types = {
            'application/pdf',
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
            'text/plain', 'text/csv',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/zip',
            'application/json'
        }
        
        self.dangerous_mime_types = {
            'application/x-executable',
            'application/x-msdownload',
            'application/x-msdos-program',
            'application/x-msi',
            'application/x-sh',
            'application/x-csh',
            'text/x-script',
            'application/javascript',
            'text/javascript',
            'application/x-php',
            'text/x-php'
        }
        
        # File signature validation (magic numbers)
        self.file_signatures = {
            b'\x25\x50\x44\x46': 'pdf',         # PDF
            b'\xFF\xD8\xFF': 'jpeg',            # JPEG
            b'\x89\x50\x4E\x47': 'png',         # PNG
            b'\x47\x49\x46\x38': 'gif',         # GIF
            b'\x50\x4B\x03\x04': 'zip',         # ZIP/Office
            b'\xD0\xCF\x11\xE0': 'ole',         # OLE (Office)
        }
        
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only process file upload requests
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("multipart/form-data"):
            return await call_next(request)
        
        try:
            await self._validate_file_upload(request)
            return await call_next(request)
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"File upload validation error: {e}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "File validation failed"}
            )
    
    async def _validate_file_upload(self, request: Request):
        """Validate file upload security"""
        # Check content length
        content_length = int(request.headers.get("content-length", 0))
        if content_length > self.max_file_size:
            await self._log_upload_violation(
                request, "oversized_file",
                {"size": content_length, "max": self.max_file_size}
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File too large"
            )
        
        # In a real implementation, you would:
        # 1. Parse the multipart data
        # 2. Check file signatures against declared MIME types
        # 3. Scan file content for malicious patterns
        # 4. Validate file names for path traversal
        # 5. Check for embedded executables in documents
        
        # For now, we'll do basic validation
        await self._validate_multipart_headers(request)
    
    async def _validate_multipart_headers(self, request: Request):
        """Validate multipart form headers"""
        content_type = request.headers.get("content-type", "")
        
        # Extract boundary
        if "boundary=" not in content_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid multipart format"
            )
        
        boundary = content_type.split("boundary=")[1]
        
        # Validate boundary format
        if len(boundary) > 256 or not re.match(r'^[a-zA-Z0-9\-_=+/]+$', boundary):
            await self._log_upload_violation(
                request, "invalid_boundary",
                {"boundary": boundary[:100]}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid upload boundary"
            )
    
    async def _log_upload_violation(self, request: Request, violation_type: str, details: Dict):
        """Log file upload security violation"""
        client_ip = self._get_client_ip(request)
        
        log_security_event(
            event_type="file_upload_violation",
            description=f"File upload violation: {violation_type}",
            ip_address=client_ip,
            risk_level="medium",
            event_details={
                "violation_type": violation_type,
                "details": details,
                "url": str(request.url),
                "user_agent": request.headers.get("user-agent", "")
            }
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
