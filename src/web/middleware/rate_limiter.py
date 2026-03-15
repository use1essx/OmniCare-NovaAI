"""
Healthcare AI V2 - Sophisticated Rate Limiting System
Advanced rate limiting with user-specific limits, sliding windows, and abuse detection
"""

import time
import json
import hashlib
from typing import Dict, List, Optional, Tuple, Any, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from enum import Enum

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

from src.core.config import settings
from src.core.logging import get_logger, log_security_event


class LimitType(Enum):
    """Rate limit types"""
    PER_SECOND = "per_second"
    PER_MINUTE = "per_minute"
    PER_HOUR = "per_hour"
    PER_DAY = "per_day"
    BURST = "burst"
    SLIDING_WINDOW = "sliding_window"


class ClientType(Enum):
    """Client types for different rate limits"""
    ANONYMOUS = "anonymous"
    AUTHENTICATED = "authenticated"
    ADMIN = "admin"
    MEDICAL_REVIEWER = "medical_reviewer"
    API_KEY = "api_key"
    BOT = "bot"


@dataclass
class RateLimit:
    """Rate limit configuration"""
    limit_type: LimitType
    max_requests: int
    window_seconds: int
    burst_allowance: int = 0
    penalty_multiplier: float = 1.0
    
    def __post_init__(self):
        if self.burst_allowance == 0:
            self.burst_allowance = max(1, self.max_requests // 10)


@dataclass
class RateLimitState:
    """Current rate limit state for a client"""
    client_id: str
    current_count: int
    window_start: float
    last_request: float
    burst_used: int = 0
    violations: int = 0
    penalty_until: Optional[float] = None
    
    def is_penalized(self) -> bool:
        """Check if client is currently penalized"""
        return self.penalty_until and time.time() < self.penalty_until


class AdvancedRateLimiter:
    """Advanced rate limiting system with Redis backend"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.redis_client: Optional[redis.Redis] = None
        
        # Fallback in-memory storage
        self._memory_store: Dict[str, RateLimitState] = {}
        
        # Rate limit configurations by endpoint pattern and client type
        self.rate_limits = self._configure_rate_limits()
        
        # Sliding window tracking
        self.sliding_windows: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Abuse detection thresholds
        self.abuse_threshold = 5  # violations before temporary ban
        self.abuse_penalty_minutes = 30
        
    def _configure_rate_limits(self) -> Dict[str, Dict[ClientType, List[RateLimit]]]:
        """Configure rate limits for different endpoints and client types"""
        return {
            "/api/v1/auth/login": {
                ClientType.ANONYMOUS: [
                    RateLimit(LimitType.PER_MINUTE, 5, 60),
                    RateLimit(LimitType.PER_HOUR, 20, 3600),
                    RateLimit(LimitType.BURST, 3, 10)
                ],
                ClientType.AUTHENTICATED: [
                    RateLimit(LimitType.PER_MINUTE, 10, 60),
                    RateLimit(LimitType.PER_HOUR, 50, 3600)
                ]
            },
            "/api/v1/auth/register": {
                ClientType.ANONYMOUS: [
                    RateLimit(LimitType.PER_MINUTE, 2, 60),
                    RateLimit(LimitType.PER_HOUR, 5, 3600),
                    RateLimit(LimitType.PER_DAY, 10, 86400)
                ]
            },
            "/api/v1/chat": {
                ClientType.ANONYMOUS: [
                    RateLimit(LimitType.PER_MINUTE, 10, 60),
                    RateLimit(LimitType.PER_HOUR, 100, 3600),
                    RateLimit(LimitType.SLIDING_WINDOW, 20, 300)  # 20 requests in 5 minutes
                ],
                ClientType.AUTHENTICATED: [
                    RateLimit(LimitType.PER_MINUTE, 30, 60),
                    RateLimit(LimitType.PER_HOUR, 500, 3600),
                    RateLimit(LimitType.SLIDING_WINDOW, 50, 300)
                ],
                ClientType.ADMIN: [
                    RateLimit(LimitType.PER_MINUTE, 100, 60),
                    RateLimit(LimitType.PER_HOUR, 2000, 3600)
                ]
            },
            "/api/v1/upload": {
                ClientType.AUTHENTICATED: [
                    RateLimit(LimitType.PER_MINUTE, 5, 60),
                    RateLimit(LimitType.PER_HOUR, 20, 3600),
                    RateLimit(LimitType.PER_DAY, 100, 86400)
                ],
                ClientType.ADMIN: [
                    RateLimit(LimitType.PER_MINUTE, 20, 60),
                    RateLimit(LimitType.PER_HOUR, 200, 3600)
                ]
            },
            "/api/v1/admin": {
                ClientType.ADMIN: [
                    RateLimit(LimitType.PER_MINUTE, 50, 60),
                    RateLimit(LimitType.PER_HOUR, 1000, 3600)
                ]
            },
            # Default limits for unspecified endpoints
            "default": {
                ClientType.ANONYMOUS: [
                    RateLimit(LimitType.PER_MINUTE, 20, 60),
                    RateLimit(LimitType.PER_HOUR, 200, 3600),
                    RateLimit(LimitType.SLIDING_WINDOW, 30, 300)
                ],
                ClientType.AUTHENTICATED: [
                    RateLimit(LimitType.PER_MINUTE, 60, 60),
                    RateLimit(LimitType.PER_HOUR, 1000, 3600),
                    RateLimit(LimitType.SLIDING_WINDOW, 100, 300)
                ],
                ClientType.ADMIN: [
                    RateLimit(LimitType.PER_MINUTE, 200, 60),
                    RateLimit(LimitType.PER_HOUR, 5000, 3600)
                ],
                ClientType.BOT: [
                    RateLimit(LimitType.PER_MINUTE, 2, 60),
                    RateLimit(LimitType.PER_HOUR, 10, 3600)
                ]
            }
        }
    
    async def initialize(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url_str,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            await self.redis_client.ping()
            self.logger.info("Rate limiter connected to Redis")
        except Exception as e:
            self.logger.warning(f"Redis unavailable for rate limiting: {e}")
            self.redis_client = None
    
    async def check_rate_limit(
        self,
        client_id: str,
        endpoint: str,
        client_type: ClientType,
        user_id: Optional[int] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request should be rate limited
        
        Returns:
            (allowed, limit_info)
        """
        try:
            # Get applicable rate limits
            rate_limits = self._get_rate_limits(endpoint, client_type)
            
            if not rate_limits:
                return True, {}
            
            current_time = time.time()
            limit_info = {}
            
            # Check each rate limit
            for rate_limit in rate_limits:
                allowed, info = await self._check_single_limit(
                    client_id, rate_limit, current_time, endpoint
                )
                
                if not allowed:
                    # Log rate limit violation
                    await self._log_rate_limit_violation(
                        client_id, endpoint, rate_limit, info, user_id
                    )
                    
                    # Update abuse tracking
                    await self._track_abuse(client_id, endpoint)
                    
                    return False, info
                
                # Collect limit info for headers
                limit_info.update(info)
            
            # Record successful request
            await self._record_request(client_id, endpoint, current_time)
            
            return True, limit_info
            
        except Exception as e:
            self.logger.error(f"Error checking rate limit: {e}")
            # Fail open - allow request on error
            return True, {}
    
    async def _check_single_limit(
        self,
        client_id: str,
        rate_limit: RateLimit,
        current_time: float,
        endpoint: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check a single rate limit"""
        key = f"rate_limit:{client_id}:{endpoint}:{rate_limit.limit_type.value}"
        
        if rate_limit.limit_type == LimitType.SLIDING_WINDOW:
            return await self._check_sliding_window(
                client_id, rate_limit, current_time, endpoint
            )
        
        # Get current state
        state = await self._get_rate_limit_state(key, client_id)
        
        # Check if in penalty period
        if state.is_penalized():
            return False, {
                "error": "Rate limit exceeded - temporary penalty",
                "retry_after": int(state.penalty_until - current_time),
                "limit": rate_limit.max_requests,
                "window": rate_limit.window_seconds
            }
        
        # Reset window if expired
        if current_time - state.window_start >= rate_limit.window_seconds:
            state.window_start = current_time
            state.current_count = 0
            state.burst_used = 0
        
        # Check burst allowance for rapid requests
        if rate_limit.limit_type == LimitType.BURST:
            time_since_last = current_time - state.last_request
            if time_since_last < 1.0:  # Less than 1 second
                if state.burst_used >= rate_limit.burst_allowance:
                    return False, {
                        "error": "Burst limit exceeded",
                        "retry_after": 1,
                        "limit": rate_limit.burst_allowance,
                        "window": "burst"
                    }
                state.burst_used += 1
        
        # Check main limit
        if state.current_count >= rate_limit.max_requests:
            return False, {
                "error": "Rate limit exceeded",
                "retry_after": int(rate_limit.window_seconds - (current_time - state.window_start)),
                "limit": rate_limit.max_requests,
                "window": rate_limit.window_seconds,
                "current": state.current_count
            }
        
        # Update state
        state.current_count += 1
        state.last_request = current_time
        
        # Store updated state
        await self._store_rate_limit_state(key, state)
        
        return True, {
            "limit": rate_limit.max_requests,
            "remaining": rate_limit.max_requests - state.current_count,
            "window": rate_limit.window_seconds,
            "reset_time": int(state.window_start + rate_limit.window_seconds)
        }
    
    async def _check_sliding_window(
        self,
        client_id: str,
        rate_limit: RateLimit,
        current_time: float,
        endpoint: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check sliding window rate limit"""
        window_key = f"sliding:{client_id}:{endpoint}"
        
        # Get request timestamps from sliding window
        if self.redis_client:
            # Redis-based sliding window
            pipe = self.redis_client.pipeline()
            
            # Remove old requests outside window
            cutoff_time = current_time - rate_limit.window_seconds
            pipe.zremrangebyscore(window_key, 0, cutoff_time)
            
            # Count current requests in window
            pipe.zcard(window_key)
            
            # Add current request
            pipe.zadd(window_key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(window_key, rate_limit.window_seconds + 60)
            
            results = await pipe.execute()
            current_count = results[1]
        else:
            # Memory-based sliding window
            timestamps = self.sliding_windows[window_key]
            cutoff_time = current_time - rate_limit.window_seconds
            
            # Remove old timestamps
            while timestamps and timestamps[0] < cutoff_time:
                timestamps.popleft()
            
            current_count = len(timestamps)
            timestamps.append(current_time)
        
        if current_count >= rate_limit.max_requests:
            return False, {
                "error": "Sliding window rate limit exceeded",
                "retry_after": 60,  # Suggest retry in 1 minute
                "limit": rate_limit.max_requests,
                "window": rate_limit.window_seconds,
                "current": current_count
            }
        
        return True, {
            "limit": rate_limit.max_requests,
            "remaining": rate_limit.max_requests - current_count,
            "window": rate_limit.window_seconds,
            "window_type": "sliding"
        }
    
    async def _get_rate_limit_state(self, key: str, client_id: str) -> RateLimitState:
        """Get rate limit state from storage"""
        if self.redis_client:
            try:
                data = await self.redis_client.get(key)
                if data:
                    state_dict = json.loads(data)
                    return RateLimitState(**state_dict)
            except Exception as e:
                self.logger.warning(f"Error getting rate limit state from Redis: {e}")
        
        # Fallback to memory
        return self._memory_store.get(key, RateLimitState(
            client_id=client_id,
            current_count=0,
            window_start=time.time(),
            last_request=0
        ))
    
    async def _store_rate_limit_state(self, key: str, state: RateLimitState):
        """Store rate limit state"""
        if self.redis_client:
            try:
                data = json.dumps(asdict(state))
                await self.redis_client.setex(key, 3600, data)  # 1 hour TTL
                return
            except Exception as e:
                self.logger.warning(f"Error storing rate limit state to Redis: {e}")
        
        # Fallback to memory
        self._memory_store[key] = state
    
    async def _track_abuse(self, client_id: str, endpoint: str):
        """Track rate limit abuse for potential penalties"""
        abuse_key = f"abuse:{client_id}"
        time.time()
        
        try:
            if self.redis_client:
                # Increment abuse counter
                count = await self.redis_client.incr(abuse_key)
                await self.redis_client.expire(abuse_key, 3600)  # 1 hour window
            else:
                # Memory-based tracking
                if not hasattr(self, '_abuse_tracking'):
                    self._abuse_tracking = {}
                self._abuse_tracking[abuse_key] = self._abuse_tracking.get(abuse_key, 0) + 1
                count = self._abuse_tracking[abuse_key]
            
            # Apply penalty if threshold exceeded
            if count >= self.abuse_threshold:
                await self._apply_penalty(client_id, self.abuse_penalty_minutes * 60)
                
                # Log security event
                log_security_event(
                    event_type="rate_limit_abuse",
                    description=f"Rate limit abuse detected for client {client_id}",
                    ip_address=client_id.split(":")[0] if ":" in client_id else client_id,
                    risk_level="high",
                    event_details={
                        "client_id": client_id,
                        "endpoint": endpoint,
                        "violation_count": count,
                        "penalty_minutes": self.abuse_penalty_minutes
                    }
                )
                
        except Exception as e:
            self.logger.error(f"Error tracking abuse: {e}")
    
    async def _apply_penalty(self, client_id: str, penalty_seconds: int):
        """Apply penalty to abusive client"""
        penalty_key = f"penalty:{client_id}"
        penalty_until = time.time() + penalty_seconds
        
        try:
            if self.redis_client:
                await self.redis_client.setex(
                    penalty_key, 
                    penalty_seconds, 
                    str(penalty_until)
                )
            else:
                # Update all rate limit states for this client
                for key, state in self._memory_store.items():
                    if state.client_id == client_id:
                        state.penalty_until = penalty_until
                        
        except Exception as e:
            self.logger.error(f"Error applying penalty: {e}")
    
    async def _record_request(self, client_id: str, endpoint: str, timestamp: float):
        """Record successful request for analytics"""
        try:
            # Store in Redis for analytics
            if self.redis_client:
                analytics_key = f"analytics:requests:{datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d-%H')}"
                await self.redis_client.hincrby(analytics_key, f"{client_id}:{endpoint}", 1)
                await self.redis_client.expire(analytics_key, 7 * 86400)  # 7 days
                
        except Exception as e:
            self.logger.warning(f"Error recording request analytics: {e}")
    
    async def _log_rate_limit_violation(
        self,
        client_id: str,
        endpoint: str,
        rate_limit: RateLimit,
        limit_info: Dict,
        user_id: Optional[int] = None
    ):
        """Log rate limit violation"""
        log_security_event(
            event_type="rate_limit_exceeded",
            description=f"Rate limit exceeded for {endpoint}",
            ip_address=client_id.split(":")[0] if ":" in client_id else client_id,
            user_id=user_id,
            risk_level="medium",
            event_details={
                "client_id": client_id,
                "endpoint": endpoint,
                "limit_type": rate_limit.limit_type.value,
                "max_requests": rate_limit.max_requests,
                "window_seconds": rate_limit.window_seconds,
                "limit_info": limit_info
            }
        )
    
    def _get_rate_limits(self, endpoint: str, client_type: ClientType) -> List[RateLimit]:
        """Get applicable rate limits for endpoint and client type"""
        # Try exact endpoint match first
        if endpoint in self.rate_limits:
            return self.rate_limits[endpoint].get(client_type, [])
        
        # Try pattern matching
        for pattern, limits in self.rate_limits.items():
            if pattern != "default" and self._endpoint_matches_pattern(endpoint, pattern):
                return limits.get(client_type, [])
        
        # Fall back to default limits
        return self.rate_limits["default"].get(client_type, [])
    
    def _endpoint_matches_pattern(self, endpoint: str, pattern: str) -> bool:
        """Check if endpoint matches pattern"""
        # Simple pattern matching - can be enhanced with regex
        if pattern.endswith("*"):
            return endpoint.startswith(pattern[:-1])
        
        if "*" in pattern:
            parts = pattern.split("*")
            return endpoint.startswith(parts[0]) and endpoint.endswith(parts[-1])
        
        return endpoint == pattern
    
    async def get_rate_limit_status(self, client_id: str) -> Dict[str, Any]:
        """Get current rate limit status for client"""
        status = {
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat(),
            "limits": {},
            "penalties": {}
        }
        
        try:
            # Check for active penalties
            penalty_key = f"penalty:{client_id}"
            if self.redis_client:
                penalty_until = await self.redis_client.get(penalty_key)
                if penalty_until:
                    status["penalties"]["active"] = True
                    status["penalties"]["until"] = float(penalty_until)
            
            # Get current limit states
            if self.redis_client:
                keys = await self.redis_client.keys(f"rate_limit:{client_id}:*")
                for key in keys:
                    data = await self.redis_client.get(key)
                    if data:
                        state = json.loads(data)
                        endpoint = key.split(":")[2]
                        limit_type = key.split(":")[3]
                        status["limits"][f"{endpoint}:{limit_type}"] = state
            
        except Exception as e:
            self.logger.error(f"Error getting rate limit status: {e}")
            status["error"] = str(e)
        
        return status


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = get_logger(__name__)
        self.rate_limiter = AdvancedRateLimiter()
        
        # Bot detection patterns
        self.bot_patterns = [
            "bot", "crawler", "spider", "scraper", "scanner"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for certain paths
        skip_paths = ["/health", "/docs", "/openapi.json", "/favicon.ico"]
        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)
        
        try:
            # Determine client type and ID
            client_type, client_id, user_id = await self._identify_client(request)
            
            # Check rate limits
            allowed, limit_info = await self.rate_limiter.check_rate_limit(
                client_id=client_id,
                endpoint=request.url.path,
                client_type=client_type,
                user_id=user_id
            )
            
            if not allowed:
                # Rate limit exceeded
                response = JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "message": limit_info.get("error", "Too many requests"),
                        "retry_after": limit_info.get("retry_after", 60)
                    }
                )
                
                # Add rate limit headers
                self._add_rate_limit_headers(response, limit_info)
                return response
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers to successful responses
            self._add_rate_limit_headers(response, limit_info)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Rate limiting error: {e}")
            # Fail open - allow request on error
            return await call_next(request)
    
    async def _identify_client(self, request: Request) -> Tuple[ClientType, str, Optional[int]]:
        """Identify client type and generate client ID"""
        user_id = None
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        # Check for authenticated user
        if hasattr(request.state, 'user') and request.state.user:
            user = request.state.user
            user_id = user.id
            
            if getattr(user, 'is_admin', False):
                client_type = ClientType.ADMIN
            elif getattr(user, 'role', '') == 'medical_reviewer':
                client_type = ClientType.MEDICAL_REVIEWER
            else:
                client_type = ClientType.AUTHENTICATED
            
            client_id = f"user:{user_id}:{client_ip}"
        
        # Check for API key authentication
        elif "authorization" in request.headers:
            auth_header = request.headers["authorization"]
            if auth_header.startswith("Bearer "):
                # This is likely an API key or JWT token
                token_hash = hashlib.sha256(auth_header.encode()).hexdigest()[:16]
                client_type = ClientType.API_KEY
                client_id = f"api:{token_hash}:{client_ip}"
            else:
                client_type = ClientType.ANONYMOUS
                client_id = f"anon:{client_ip}"
        
        # Check for bot/crawler
        elif any(pattern in user_agent.lower() for pattern in self.bot_patterns):
            client_type = ClientType.BOT
            client_id = f"bot:{client_ip}:{hashlib.md5(user_agent.encode()).hexdigest()[:8]}"
        
        # Anonymous user
        else:
            client_type = ClientType.ANONYMOUS
            client_id = f"anon:{client_ip}"
        
        return client_type, client_id, user_id
    
    def _add_rate_limit_headers(self, response: Response, limit_info: Dict[str, Any]):
        """Add rate limit headers to response"""
        if "limit" in limit_info:
            response.headers["X-RateLimit-Limit"] = str(limit_info["limit"])
        
        if "remaining" in limit_info:
            response.headers["X-RateLimit-Remaining"] = str(limit_info["remaining"])
        
        if "reset_time" in limit_info:
            response.headers["X-RateLimit-Reset"] = str(limit_info["reset_time"])
        
        if "window" in limit_info:
            response.headers["X-RateLimit-Window"] = str(limit_info["window"])
        
        if "retry_after" in limit_info:
            response.headers["Retry-After"] = str(limit_info["retry_after"])
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        # Check X-Forwarded-For header
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Direct connection
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"


# Global rate limiter instance
rate_limiter = AdvancedRateLimiter()


async def initialize_rate_limiter():
    """Initialize the global rate limiter"""
    await rate_limiter.initialize()


# Convenience functions

async def check_rate_limit(
    client_id: str,
    endpoint: str,
    client_type: ClientType,
    user_id: Optional[int] = None
) -> Tuple[bool, Dict[str, Any]]:
    """Check rate limit for specific client and endpoint"""
    return await rate_limiter.check_rate_limit(client_id, endpoint, client_type, user_id)


async def get_rate_limit_status(client_id: str) -> Dict[str, Any]:
    """Get rate limit status for client"""
    return await rate_limiter.get_rate_limit_status(client_id)
