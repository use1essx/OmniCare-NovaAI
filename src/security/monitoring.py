"""
Healthcare AI V2 - Real-time Security Monitoring System
Advanced threat detection and security event monitoring
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from enum import Enum
import redis.asyncio as redis

from src.core.config import settings
from src.core.logging import get_logger, log_security_event


class ThreatLevel(Enum):
    """Security threat levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventType(Enum):
    """Security event types"""
    FAILED_LOGIN = "failed_login"
    MULTIPLE_IPS = "multiple_ips"
    RAPID_REQUESTS = "rapid_requests"
    SUSPICIOUS_PATTERN = "suspicious_pattern"
    BRUTE_FORCE = "brute_force"
    IP_BLOCKED = "ip_blocked"
    UNUSUAL_ACTIVITY = "unusual_activity"
    GEOGRAPHIC_ANOMALY = "geographic_anomaly"
    API_ABUSE = "api_abuse"
    MALICIOUS_PAYLOAD = "malicious_payload"


@dataclass
class SecurityEvent:
    """Security event data structure"""
    event_id: str
    event_type: EventType
    threat_level: ThreatLevel
    timestamp: datetime
    source_ip: str
    user_id: Optional[int] = None
    username: Optional[str] = None
    user_agent: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    payload_size: Optional[int] = None
    details: Optional[Dict] = None
    action_taken: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['threat_level'] = self.threat_level.value
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class IPProfile:
    """IP address behavioral profile"""
    ip: str
    first_seen: datetime
    last_seen: datetime
    request_count: int = 0
    failed_logins: int = 0
    successful_logins: int = 0
    endpoints_accessed: Set[str] = None
    user_agents: Set[str] = None
    countries: Set[str] = None
    blocked_until: Optional[datetime] = None
    threat_score: float = 0.0
    
    def __post_init__(self):
        if self.endpoints_accessed is None:
            self.endpoints_accessed = set()
        if self.user_agents is None:
            self.user_agents = set()
        if self.countries is None:
            self.countries = set()


class SecurityMonitor:
    """Real-time security monitoring and threat detection system"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.redis_client: Optional[redis.Redis] = None
        
        # Monitoring thresholds
        self.failed_login_threshold = 5
        self.rapid_request_threshold = 50  # requests per minute
        self.brute_force_threshold = 10  # failed logins in 5 minutes
        self.ip_switch_threshold = 3  # different IPs for same user in 1 hour
        
        # Time windows
        self.login_window = timedelta(minutes=5)
        self.rapid_request_window = timedelta(minutes=1)
        self.ip_tracking_window = timedelta(hours=1)
        
        # In-memory tracking (fallback if Redis unavailable)
        self.ip_profiles: Dict[str, IPProfile] = {}
        self.user_ip_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=10))
        self.blocked_ips: Set[str] = set()
        self.recent_events: deque = deque(maxlen=1000)
        
        # Geographic data (simplified)
        self.suspicious_countries = {"CN", "RU", "KP", "IR"}  # Configurable
        
    async def initialize(self):
        """Initialize Redis connection and load existing data"""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url_str,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            await self.redis_client.ping()
            self.logger.info("Security monitor connected to Redis")
            
            # Load blocked IPs from Redis
            blocked_ips = await self.redis_client.smembers("security:blocked_ips")
            self.blocked_ips.update(blocked_ips)
            
        except Exception as e:
            self.logger.warning(f"Redis unavailable for security monitoring: {e}")
            self.redis_client = None
    
    async def track_request(
        self,
        ip: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        endpoint: str = "",
        method: str = "",
        user_agent: str = "",
        payload_size: int = 0,
        success: bool = True
    ) -> List[SecurityEvent]:
        """Track incoming request and detect threats"""
        events = []
        current_time = datetime.utcnow()
        
        try:
            # Update IP profile
            await self._update_ip_profile(ip, endpoint, user_agent, current_time)
            
            # Track user IP history
            if user_id:
                await self._track_user_ip(user_id, ip, current_time)
            
            # Check for various threats
            events.extend(await self._check_blocked_ip(ip))
            events.extend(await self._check_rapid_requests(ip, current_time))
            events.extend(await self._check_multiple_ips(user_id, current_time))
            events.extend(await self._check_suspicious_patterns(ip, endpoint, user_agent))
            events.extend(await self._check_payload_anomalies(payload_size, endpoint))
            
            # Track failed authentication
            if not success and "auth" in endpoint:
                events.extend(await self._track_failed_login(ip, user_id, username, current_time))
            
            # Process and store events
            for event in events:
                await self._process_security_event(event)
                
        except Exception as e:
            self.logger.error(f"Error tracking request: {e}")
            
        return events
    
    async def track_login_attempt(
        self,
        ip: str,
        identifier: str,  # email or username
        success: bool,
        user_id: Optional[int] = None,
        user_agent: str = ""
    ) -> List[SecurityEvent]:
        """Track login attempts for brute force detection"""
        events = []
        current_time = datetime.utcnow()
        
        try:
            key = f"security:login_attempts:{ip}"
            
            if self.redis_client:
                # Increment attempt counter
                await self.redis_client.incr(key)
                await self.redis_client.expire(key, int(self.login_window.total_seconds()))
                
                # Get current count
                attempt_count = int(await self.redis_client.get(key) or 0)
            else:
                # Fallback to memory tracking
                attempt_count = self._increment_memory_counter(f"login:{ip}", self.login_window)
            
            if not success:
                # Check for brute force attack
                if attempt_count >= self.brute_force_threshold:
                    event = SecurityEvent(
                        event_id=self._generate_event_id(),
                        event_type=EventType.BRUTE_FORCE,
                        threat_level=ThreatLevel.HIGH,
                        timestamp=current_time,
                        source_ip=ip,
                        user_id=user_id,
                        username=identifier,
                        user_agent=user_agent,
                        details={
                            "attempt_count": attempt_count,
                            "time_window": str(self.login_window)
                        }
                    )
                    events.append(event)
                    
                    # Block IP temporarily
                    await self._block_ip_temporarily(ip, timedelta(hours=1))
                
                elif attempt_count >= self.failed_login_threshold:
                    event = SecurityEvent(
                        event_id=self._generate_event_id(),
                        event_type=EventType.FAILED_LOGIN,
                        threat_level=ThreatLevel.MEDIUM,
                        timestamp=current_time,
                        source_ip=ip,
                        user_id=user_id,
                        username=identifier,
                        user_agent=user_agent,
                        details={
                            "attempt_count": attempt_count,
                            "threshold": self.failed_login_threshold
                        }
                    )
                    events.append(event)
            
            # Process events
            for event in events:
                await self._process_security_event(event)
                
        except Exception as e:
            self.logger.error(f"Error tracking login attempt: {e}")
            
        return events
    
    async def is_ip_blocked(self, ip: str) -> Tuple[bool, Optional[datetime]]:
        """Check if IP is currently blocked"""
        try:
            if ip in self.blocked_ips:
                return True, None
            
            if self.redis_client:
                blocked_until = await self.redis_client.get(f"security:blocked:{ip}")
                if blocked_until:
                    unblock_time = datetime.fromisoformat(blocked_until)
                    if datetime.utcnow() < unblock_time:
                        return True, unblock_time
                    else:
                        # Expired block, remove it
                        await self.redis_client.delete(f"security:blocked:{ip}")
                        self.blocked_ips.discard(ip)
            
            return False, None
            
        except Exception as e:
            self.logger.error(f"Error checking IP block status: {e}")
            return False, None
    
    async def block_ip(self, ip: str, duration: timedelta, reason: str = "Security violation"):
        """Block IP address for specified duration"""
        try:
            unblock_time = datetime.utcnow() + duration
            self.blocked_ips.add(ip)
            
            if self.redis_client:
                await self.redis_client.set(
                    f"security:blocked:{ip}",
                    unblock_time.isoformat(),
                    ex=int(duration.total_seconds())
                )
                await self.redis_client.sadd("security:blocked_ips", ip)
            
            # Log security event
            event = SecurityEvent(
                event_id=self._generate_event_id(),
                event_type=EventType.IP_BLOCKED,
                threat_level=ThreatLevel.HIGH,
                timestamp=datetime.utcnow(),
                source_ip=ip,
                details={
                    "reason": reason,
                    "duration_minutes": int(duration.total_seconds() / 60),
                    "unblock_time": unblock_time.isoformat()
                },
                action_taken="IP blocked"
            )
            
            await self._process_security_event(event)
            self.logger.warning(f"IP {ip} blocked for {duration}: {reason}")
            
        except Exception as e:
            self.logger.error(f"Error blocking IP {ip}: {e}")
    
    async def unblock_ip(self, ip: str):
        """Manually unblock IP address"""
        try:
            self.blocked_ips.discard(ip)
            
            if self.redis_client:
                await self.redis_client.delete(f"security:blocked:{ip}")
                await self.redis_client.srem("security:blocked_ips", ip)
            
            self.logger.info(f"IP {ip} manually unblocked")
            
        except Exception as e:
            self.logger.error(f"Error unblocking IP {ip}: {e}")
    
    async def get_security_dashboard(self) -> Dict:
        """Get security dashboard data"""
        try:
            current_time = datetime.utcnow()
            last_hour = current_time - timedelta(hours=1)
            last_day = current_time - timedelta(days=1)
            
            # Count recent events by type and severity
            recent_events = [e for e in self.recent_events if e.timestamp > last_hour]
            
            event_counts = defaultdict(int)
            threat_counts = defaultdict(int)
            
            for event in recent_events:
                event_counts[event.event_type.value] += 1
                threat_counts[event.threat_level.value] += 1
            
            dashboard = {
                "timestamp": current_time.isoformat(),
                "summary": {
                    "blocked_ips": len(self.blocked_ips),
                    "events_last_hour": len(recent_events),
                    "events_last_day": len([e for e in self.recent_events if e.timestamp > last_day]),
                    "critical_alerts": threat_counts.get("critical", 0),
                    "high_alerts": threat_counts.get("high", 0)
                },
                "event_types": dict(event_counts),
                "threat_levels": dict(threat_counts),
                "top_blocked_ips": list(self.blocked_ips)[:10],
                "recent_events": [event.to_dict() for event in list(recent_events)[-20:]]
            }
            
            # Add Redis-based stats if available
            if self.redis_client:
                try:
                    dashboard["redis_stats"] = await self._get_redis_security_stats()
                except Exception as e:
                    self.logger.warning(f"Failed to get Redis stats: {e}")
            
            return dashboard
            
        except Exception as e:
            self.logger.error(f"Error generating security dashboard: {e}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}
    
    # Private methods
    
    async def _update_ip_profile(self, ip: str, endpoint: str, user_agent: str, timestamp: datetime):
        """Update IP profile with request information"""
        if ip not in self.ip_profiles:
            self.ip_profiles[ip] = IPProfile(
                ip=ip,
                first_seen=timestamp,
                last_seen=timestamp,
                endpoints_accessed=set(),
                user_agents=set(),
                countries=set()
            )
        
        profile = self.ip_profiles[ip]
        profile.last_seen = timestamp
        profile.request_count += 1
        profile.endpoints_accessed.add(endpoint)
        profile.user_agents.add(user_agent[:100])  # Limit size
        
        # Calculate basic threat score
        profile.threat_score = self._calculate_threat_score(profile)
    
    async def _track_user_ip(self, user_id: int, ip: str, timestamp: datetime):
        """Track IP addresses used by user"""
        user_ips = self.user_ip_history[user_id]
        user_ips.append((ip, timestamp))
    
    async def _check_blocked_ip(self, ip: str) -> List[SecurityEvent]:
        """Check if IP is in blocked list"""
        blocked, unblock_time = await self.is_ip_blocked(ip)
        if blocked:
            return [SecurityEvent(
                event_id=self._generate_event_id(),
                event_type=EventType.IP_BLOCKED,
                threat_level=ThreatLevel.HIGH,
                timestamp=datetime.utcnow(),
                source_ip=ip,
                details={"unblock_time": unblock_time.isoformat() if unblock_time else None},
                action_taken="Request blocked"
            )]
        return []
    
    async def _check_rapid_requests(self, ip: str, timestamp: datetime) -> List[SecurityEvent]:
        """Check for rapid fire requests"""
        key = f"security:requests:{ip}"
        
        try:
            if self.redis_client:
                count = await self.redis_client.incr(key)
                if count == 1:
                    await self.redis_client.expire(key, int(self.rapid_request_window.total_seconds()))
            else:
                count = self._increment_memory_counter(f"requests:{ip}", self.rapid_request_window)
            
            if count > self.rapid_request_threshold:
                return [SecurityEvent(
                    event_id=self._generate_event_id(),
                    event_type=EventType.RAPID_REQUESTS,
                    threat_level=ThreatLevel.MEDIUM,
                    timestamp=timestamp,
                    source_ip=ip,
                    details={
                        "request_count": count,
                        "threshold": self.rapid_request_threshold,
                        "time_window": str(self.rapid_request_window)
                    }
                )]
                
        except Exception as e:
            self.logger.error(f"Error checking rapid requests: {e}")
            
        return []
    
    async def _check_multiple_ips(self, user_id: Optional[int], timestamp: datetime) -> List[SecurityEvent]:
        """Check for user accessing from multiple IPs"""
        if not user_id:
            return []
        
        try:
            cutoff_time = timestamp - self.ip_tracking_window
            recent_ips = [
                ip for ip, ts in self.user_ip_history[user_id]
                if ts > cutoff_time
            ]
            
            unique_ips = set(recent_ips)
            
            if len(unique_ips) > self.ip_switch_threshold:
                return [SecurityEvent(
                    event_id=self._generate_event_id(),
                    event_type=EventType.MULTIPLE_IPS,
                    threat_level=ThreatLevel.MEDIUM,
                    timestamp=timestamp,
                    source_ip=recent_ips[-1] if recent_ips else "",
                    user_id=user_id,
                    details={
                        "ip_count": len(unique_ips),
                        "ips": list(unique_ips),
                        "threshold": self.ip_switch_threshold,
                        "time_window": str(self.ip_tracking_window)
                    }
                )]
                
        except Exception as e:
            self.logger.error(f"Error checking multiple IPs: {e}")
            
        return []
    
    async def _check_suspicious_patterns(self, ip: str, endpoint: str, user_agent: str) -> List[SecurityEvent]:
        """Check for suspicious request patterns"""
        events = []
        
        try:
            # Check for suspicious endpoints
            suspicious_endpoints = [
                "/admin", "/.env", "/config", "/wp-admin", "/phpmyadmin",
                "/.git", "/backup", "/sql", "/database"
            ]
            
            if any(suspicious in endpoint.lower() for suspicious in suspicious_endpoints):
                events.append(SecurityEvent(
                    event_id=self._generate_event_id(),
                    event_type=EventType.SUSPICIOUS_PATTERN,
                    threat_level=ThreatLevel.MEDIUM,
                    timestamp=datetime.utcnow(),
                    source_ip=ip,
                    endpoint=endpoint,
                    user_agent=user_agent,
                    details={"pattern": "suspicious_endpoint", "endpoint": endpoint}
                ))
            
            # Check for bot-like user agents
            bot_patterns = ["bot", "crawler", "spider", "scraper", "scanner"]
            if any(pattern in user_agent.lower() for pattern in bot_patterns):
                events.append(SecurityEvent(
                    event_id=self._generate_event_id(),
                    event_type=EventType.SUSPICIOUS_PATTERN,
                    threat_level=ThreatLevel.LOW,
                    timestamp=datetime.utcnow(),
                    source_ip=ip,
                    endpoint=endpoint,
                    user_agent=user_agent,
                    details={"pattern": "bot_user_agent", "user_agent": user_agent}
                ))
            
        except Exception as e:
            self.logger.error(f"Error checking suspicious patterns: {e}")
            
        return events
    
    async def _check_payload_anomalies(self, payload_size: int, endpoint: str) -> List[SecurityEvent]:
        """Check for unusual payload sizes"""
        events = []
        
        try:
            # Define normal payload size limits by endpoint type
            size_limits = {
                "upload": 50 * 1024 * 1024,  # 50MB
                "api": 1024 * 1024,          # 1MB
                "auth": 10 * 1024,           # 10KB
                "default": 100 * 1024        # 100KB
            }
            
            endpoint_type = "default"
            if "upload" in endpoint:
                endpoint_type = "upload"
            elif "api" in endpoint:
                endpoint_type = "api"
            elif "auth" in endpoint:
                endpoint_type = "auth"
            
            limit = size_limits[endpoint_type]
            
            if payload_size > limit:
                threat_level = ThreatLevel.HIGH if payload_size > limit * 10 else ThreatLevel.MEDIUM
                
                events.append(SecurityEvent(
                    event_id=self._generate_event_id(),
                    event_type=EventType.API_ABUSE,
                    threat_level=threat_level,
                    timestamp=datetime.utcnow(),
                    source_ip="",  # Will be filled by caller
                    endpoint=endpoint,
                    payload_size=payload_size,
                    details={
                        "payload_size": payload_size,
                        "limit": limit,
                        "endpoint_type": endpoint_type
                    }
                ))
                
        except Exception as e:
            self.logger.error(f"Error checking payload anomalies: {e}")
            
        return events
    
    async def _track_failed_login(
        self,
        ip: str,
        user_id: Optional[int],
        username: Optional[str],
        timestamp: datetime
    ) -> List[SecurityEvent]:
        """Track failed login attempts"""
        events = []
        
        try:
            # Update IP profile
            if ip in self.ip_profiles:
                self.ip_profiles[ip].failed_logins += 1
            
            # Check for patterns that suggest automated attacks
            key = f"security:failed_login_user:{username or 'unknown'}"
            
            if self.redis_client:
                count = await self.redis_client.incr(key)
                await self.redis_client.expire(key, 3600)  # 1 hour window
            else:
                count = self._increment_memory_counter(f"failed_user:{username}", timedelta(hours=1))
            
            if count > 5:  # Multiple failed attempts on same user
                events.append(SecurityEvent(
                    event_id=self._generate_event_id(),
                    event_type=EventType.FAILED_LOGIN,
                    threat_level=ThreatLevel.MEDIUM,
                    timestamp=timestamp,
                    source_ip=ip,
                    user_id=user_id,
                    username=username,
                    details={
                        "failed_attempts": count,
                        "target_user": username
                    }
                ))
                
        except Exception as e:
            self.logger.error(f"Error tracking failed login: {e}")
            
        return events
    
    async def _block_ip_temporarily(self, ip: str, duration: timedelta):
        """Block IP for temporary duration"""
        await self.block_ip(ip, duration, "Automated block due to suspicious activity")
    
    async def _process_security_event(self, event: SecurityEvent):
        """Process and store security event"""
        try:
            # Add to recent events
            self.recent_events.append(event)
            
            # Log to application logs
            log_security_event(
                event_type=event.event_type.value,
                description=f"Security event: {event.event_type.value}",
                ip_address=event.source_ip,
                risk_level=event.threat_level.value,
                user_id=event.user_id,
                event_details=event.details
            )
            
            # Store in Redis for persistence
            if self.redis_client:
                await self.redis_client.lpush(
                    "security:events",
                    json.dumps(event.to_dict())
                )
                await self.redis_client.ltrim("security:events", 0, 9999)  # Keep last 10k events
            
            # Send alerts for high/critical threats
            if event.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
                await self._send_alert(event)
                
        except Exception as e:
            self.logger.error(f"Error processing security event: {e}")
    
    async def _send_alert(self, event: SecurityEvent):
        """Send alert for high-priority security events"""
        try:
            alert_message = f"SECURITY ALERT: {event.event_type.value} from {event.source_ip}"
            
            # Log critical alert
            self.logger.critical(
                f"{alert_message} - Threat Level: {event.threat_level.value}",
                extra={"security_event": event.to_dict()}
            )
            
            # Here you could integrate with external alerting systems:
            # - Send email notifications
            # - Push to Slack/Discord
            # - Trigger PagerDuty/OpsGenie
            # - Send SMS alerts
            
        except Exception as e:
            self.logger.error(f"Error sending security alert: {e}")
    
    def _calculate_threat_score(self, profile: IPProfile) -> float:
        """Calculate threat score for IP profile"""
        score = 0.0
        
        # High request volume
        if profile.request_count > 1000:
            score += 20
        elif profile.request_count > 500:
            score += 10
        
        # High failure rate
        if profile.failed_logins > 0:
            failure_rate = profile.failed_logins / max(profile.request_count, 1)
            score += failure_rate * 30
        
        # Many different endpoints
        if len(profile.endpoints_accessed) > 20:
            score += 15
        
        # Multiple user agents (possible bot)
        if len(profile.user_agents) > 5:
            score += 10
        
        # Suspicious countries
        if profile.countries.intersection(self.suspicious_countries):
            score += 25
        
        return min(score, 100.0)  # Cap at 100
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        return f"se_{int(time.time() * 1000)}_{hash(time.time()) % 10000:04d}"
    
    def _increment_memory_counter(self, key: str, window: timedelta) -> int:
        """Fallback memory-based counter when Redis unavailable"""
        # Simple in-memory implementation (not persistent)
        # In production, you'd want a more sophisticated approach
        current_time = time.time()
        window_seconds = window.total_seconds()
        
        if not hasattr(self, '_memory_counters'):
            self._memory_counters = {}
        
        if key not in self._memory_counters:
            self._memory_counters[key] = []
        
        # Clean old entries
        self._memory_counters[key] = [
            timestamp for timestamp in self._memory_counters[key]
            if current_time - timestamp < window_seconds
        ]
        
        # Add current request
        self._memory_counters[key].append(current_time)
        
        return len(self._memory_counters[key])
    
    async def _get_redis_security_stats(self) -> Dict:
        """Get security statistics from Redis"""
        stats = {}
        
        try:
            # Get blocked IPs count
            stats["blocked_ips_redis"] = await self.redis_client.scard("security:blocked_ips")
            
            # Get recent events count
            stats["stored_events"] = await self.redis_client.llen("security:events")
            
            # Get active rate limits
            rate_limit_keys = await self.redis_client.keys("security:requests:*")
            stats["active_rate_limits"] = len(rate_limit_keys)
            
        except Exception as e:
            self.logger.warning(f"Error getting Redis security stats: {e}")
            
        return stats


# Global security monitor instance
security_monitor = SecurityMonitor()


async def initialize_security_monitor():
    """Initialize the global security monitor"""
    await security_monitor.initialize()


# Convenience functions for use in middleware

async def track_request_security(
    ip: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    endpoint: str = "",
    method: str = "",
    user_agent: str = "",
    payload_size: int = 0,
    success: bool = True
) -> List[SecurityEvent]:
    """Track request for security monitoring"""
    return await security_monitor.track_request(
        ip=ip,
        user_id=user_id,
        username=username,
        endpoint=endpoint,
        method=method,
        user_agent=user_agent,
        payload_size=payload_size,
        success=success
    )


async def track_login_security(
    ip: str,
    identifier: str,
    success: bool,
    user_id: Optional[int] = None,
    user_agent: str = ""
) -> List[SecurityEvent]:
    """Track login attempt for security monitoring"""
    return await security_monitor.track_login_attempt(
        ip=ip,
        identifier=identifier,
        success=success,
        user_id=user_id,
        user_agent=user_agent
    )


async def check_ip_blocked(ip: str) -> Tuple[bool, Optional[datetime]]:
    """Check if IP is blocked"""
    return await security_monitor.is_ip_blocked(ip)


async def block_ip_address(ip: str, duration: timedelta, reason: str = "Security violation"):
    """Block IP address"""
    await security_monitor.block_ip(ip, duration, reason)
