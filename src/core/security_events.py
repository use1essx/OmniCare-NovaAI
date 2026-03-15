"""
Healthcare AI V2 - Security Event Tracking and Alerting System
Comprehensive security event management with real-time alerts and notifications
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
try:
    from email.mime.text import MIMEText as MimeText
    from email.mime.multipart import MIMEMultipart as MimeMultipart
    from email.mime.base import MIMEBase as MimeBase
    from email import encoders
except ImportError:
    # Fallback for different Python versions
    try:
        from email.mime.text import MIMEText as MimeText
        from email.mime.multipart import MIMEMultipart as MimeMultipart  
        from email.mime.base import MIMEBase as MimeBase
        from email import encoders
    except ImportError:
        # If email modules not available, define dummy classes
        class MimeText:
            def __init__(self, *args, **kwargs): pass
        class MimeMultipart:
            def __init__(self, *args, **kwargs): pass
            def attach(self, *args, **kwargs): pass
            def __setitem__(self, *args, **kwargs): pass
        class MimeBase:
            def __init__(self, *args, **kwargs): pass
        class encoders:
            @staticmethod
            def encode_base64(*args, **kwargs): pass
try:
    import aiosmtplib
    SMTP_AVAILABLE = True
except ImportError:
    SMTP_AVAILABLE = False
    class aiosmtplib:
        @staticmethod
        async def send(*args, **kwargs):
            raise RuntimeError("aiosmtplib not available - install with: pip install aiosmtplib")

try:
    import httpx
    HTTP_AVAILABLE = True
except ImportError:
    HTTP_AVAILABLE = False
    class httpx:
        class AsyncClient:
            def __init__(self, *args, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def post(self, *args, **kwargs):
                raise RuntimeError("httpx not available - install with: pip install httpx")
import redis.asyncio as redis

from src.core.config import settings
from src.core.logging import get_logger, log_security_event
from src.database.connection import get_async_session
from src.database.models_comprehensive import AuditLog


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertChannel(Enum):
    """Alert delivery channels"""
    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"
    WEBHOOK = "webhook"
    DATABASE = "database"
    LOG = "log"


class EventCategory(Enum):
    """Security event categories"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    SYSTEM_SECURITY = "system_security"
    NETWORK_SECURITY = "network_security"
    MALWARE_DETECTION = "malware_detection"
    COMPLIANCE = "compliance"
    INCIDENT_RESPONSE = "incident_response"


@dataclass
class SecurityAlert:
    """Security alert data structure"""
    alert_id: str
    title: str
    description: str
    level: AlertLevel
    category: EventCategory
    timestamp: datetime
    source_ip: Optional[str] = None
    user_id: Optional[int] = None
    affected_resources: List[str] = None
    technical_details: Dict[str, Any] = None
    recommended_actions: List[str] = None
    alert_channels: List[AlertChannel] = None
    
    def __post_init__(self):
        if self.affected_resources is None:
            self.affected_resources = []
        if self.technical_details is None:
            self.technical_details = {}
        if self.recommended_actions is None:
            self.recommended_actions = []
        if self.alert_channels is None:
            self.alert_channels = [AlertChannel.LOG, AlertChannel.DATABASE]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['level'] = self.level.value
        data['category'] = self.category.value
        data['timestamp'] = self.timestamp.isoformat()
        data['alert_channels'] = [channel.value for channel in self.alert_channels]
        return data


@dataclass
class AlertRule:
    """Alert rule configuration"""
    rule_id: str
    name: str
    description: str
    event_pattern: str  # Pattern to match events
    threshold: int = 1  # Number of events to trigger alert
    time_window: int = 300  # Time window in seconds
    alert_level: AlertLevel = AlertLevel.WARNING
    alert_channels: List[AlertChannel] = None
    enabled: bool = True
    
    def __post_init__(self):
        if self.alert_channels is None:
            self.alert_channels = [AlertChannel.LOG]


class SecurityEventTracker:
    """Central security event tracking and alerting system"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.redis_client: Optional[redis.Redis] = None
        
        # Alert rules configuration
        self.alert_rules = self._configure_default_rules()
        
        # Alert handlers
        self.alert_handlers = {
            AlertChannel.EMAIL: self._send_email_alert,
            AlertChannel.SMS: self._send_sms_alert,
            AlertChannel.SLACK: self._send_slack_alert,
            AlertChannel.WEBHOOK: self._send_webhook_alert,
            AlertChannel.DATABASE: self._store_alert_in_database,
            AlertChannel.LOG: self._log_alert
        }
        
        # Event aggregation for complex alerts
        self.event_counters = {}
        self.alert_suppressions = {}  # Prevent duplicate alerts
        
        # Notification settings
        self.notification_settings = {
            'email': {
                'smtp_server': getattr(settings, 'smtp_server', 'localhost'),
                'smtp_port': getattr(settings, 'smtp_port', 587),
                'smtp_username': getattr(settings, 'smtp_username', ''),
                'smtp_password': getattr(settings, 'smtp_password', ''),
                'from_email': getattr(settings, 'alert_from_email', 'security@healthcare-ai.com'),
                'admin_emails': getattr(settings, 'admin_emails', ['admin@healthcare-ai.com'])
            },
            'slack': {
                'webhook_url': getattr(settings, 'slack_webhook_url', ''),
                'channel': getattr(settings, 'slack_channel', '#security-alerts')
            },
            'webhook': {
                'urls': getattr(settings, 'alert_webhook_urls', [])
            }
        }
    
    async def initialize(self):
        """Initialize the security event tracker"""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url_str,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            await self.redis_client.ping()
            self.logger.info("Security event tracker connected to Redis")
        except Exception as e:
            self.logger.warning(f"Redis unavailable for security events: {e}")
            self.redis_client = None
    
    async def track_event(
        self,
        event_type: str,
        description: str,
        level: AlertLevel = AlertLevel.INFO,
        category: EventCategory = EventCategory.SYSTEM_SECURITY,
        user_id: Optional[int] = None,
        source_ip: Optional[str] = None,
        technical_details: Dict[str, Any] = None,
        affected_resources: List[str] = None
    ):
        """Track a security event and check for alert conditions"""
        try:
            # Create event record
            event_data = {
                'event_type': event_type,
                'description': description,
                'level': level.value,
                'category': category.value,
                'timestamp': datetime.utcnow().isoformat(),
                'user_id': user_id,
                'source_ip': source_ip,
                'technical_details': technical_details or {},
                'affected_resources': affected_resources or []
            }
            
            # Store event
            await self._store_event(event_data)
            
            # Check alert rules
            await self._check_alert_rules(event_data)
            
            # Log the event
            log_security_event(
                event_type=event_type,
                description=description,
                user_id=user_id,
                ip_address=source_ip,
                risk_level=level.value,
                event_details=technical_details
            )
            
        except Exception as e:
            self.logger.error(f"Error tracking security event: {e}")
    
    async def create_alert(
        self,
        title: str,
        description: str,
        level: AlertLevel,
        category: EventCategory,
        source_ip: Optional[str] = None,
        user_id: Optional[int] = None,
        technical_details: Dict[str, Any] = None,
        recommended_actions: List[str] = None,
        alert_channels: List[AlertChannel] = None
    ) -> SecurityAlert:
        """Create and process a security alert"""
        try:
            alert = SecurityAlert(
                alert_id=self._generate_alert_id(),
                title=title,
                description=description,
                level=level,
                category=category,
                timestamp=datetime.utcnow(),
                source_ip=source_ip,
                user_id=user_id,
                technical_details=technical_details or {},
                recommended_actions=recommended_actions or [],
                alert_channels=alert_channels or self._get_default_channels(level)
            )
            
            # Check for alert suppression
            if await self._should_suppress_alert(alert):
                self.logger.debug(f"Alert suppressed: {alert.title}")
                return alert
            
            # Process alert through configured channels
            await self._process_alert(alert)
            
            # Record alert suppression
            await self._record_alert_suppression(alert)
            
            return alert
            
        except Exception as e:
            self.logger.error(f"Error creating security alert: {e}")
            raise
    
    async def _store_event(self, event_data: Dict[str, Any]):
        """Store security event"""
        try:
            # Store in Redis for real-time access
            if self.redis_client:
                event_key = f"security_events:{datetime.utcnow().strftime('%Y-%m-%d')}"
                await self.redis_client.lpush(event_key, json.dumps(event_data))
                await self.redis_client.expire(event_key, 7 * 86400)  # Keep for 7 days
            
            # Store in database for long-term retention
            async with get_async_session() as session:
                audit_log = AuditLog(
                    event_type=event_data['event_type'],
                    event_category=event_data['category'],
                    event_description=event_data['description'],
                    user_id=event_data.get('user_id'),
                    ip_address=event_data.get('source_ip'),
                    severity_level=event_data['level'],
                    old_values=event_data.get('technical_details', {}),
                    result='success'
                )
                session.add(audit_log)
                await session.commit()
                
        except Exception as e:
            self.logger.error(f"Error storing security event: {e}")
    
    async def _check_alert_rules(self, event_data: Dict[str, Any]):
        """Check if event triggers any alert rules"""
        try:
            for rule in self.alert_rules.values():
                if not rule.enabled:
                    continue
                
                # Check if event matches rule pattern
                if await self._event_matches_rule(event_data, rule):
                    # Increment counter for this rule
                    await self._increment_rule_counter(rule.rule_id, event_data)
                    
                    # Check if threshold is reached
                    count = await self._get_rule_counter(rule.rule_id, rule.time_window)
                    if count >= rule.threshold:
                        await self._trigger_rule_alert(rule, event_data, count)
                        
        except Exception as e:
            self.logger.error(f"Error checking alert rules: {e}")
    
    async def _event_matches_rule(self, event_data: Dict[str, Any], rule: AlertRule) -> bool:
        """Check if event matches alert rule pattern"""
        try:
            # Simple pattern matching - can be enhanced with regex or complex logic
            pattern = rule.event_pattern.lower()
            event_type = event_data['event_type'].lower()
            description = event_data['description'].lower()
            
            return pattern in event_type or pattern in description
            
        except Exception:
            return False
    
    async def _increment_rule_counter(self, rule_id: str, event_data: Dict[str, Any]):
        """Increment counter for alert rule"""
        try:
            if self.redis_client:
                counter_key = f"alert_rule_counter:{rule_id}"
                timestamp = time.time()
                
                # Add timestamp to sorted set
                await self.redis_client.zadd(counter_key, {str(timestamp): timestamp})
                
                # Set expiration
                await self.redis_client.expire(counter_key, 3600)  # 1 hour
            else:
                # Fallback to memory
                if rule_id not in self.event_counters:
                    self.event_counters[rule_id] = []
                self.event_counters[rule_id].append(time.time())
                
        except Exception as e:
            self.logger.error(f"Error incrementing rule counter: {e}")
    
    async def _get_rule_counter(self, rule_id: str, time_window: int) -> int:
        """Get current count for alert rule within time window"""
        try:
            current_time = time.time()
            cutoff_time = current_time - time_window
            
            if self.redis_client:
                counter_key = f"alert_rule_counter:{rule_id}"
                
                # Remove old entries
                await self.redis_client.zremrangebyscore(counter_key, 0, cutoff_time)
                
                # Count remaining entries
                count = await self.redis_client.zcard(counter_key)
                return count
            else:
                # Fallback to memory
                if rule_id not in self.event_counters:
                    return 0
                
                # Filter by time window
                recent_events = [
                    timestamp for timestamp in self.event_counters[rule_id]
                    if timestamp > cutoff_time
                ]
                self.event_counters[rule_id] = recent_events
                return len(recent_events)
                
        except Exception as e:
            self.logger.error(f"Error getting rule counter: {e}")
            return 0
    
    async def _trigger_rule_alert(self, rule: AlertRule, event_data: Dict[str, Any], count: int):
        """Trigger alert for rule"""
        try:
            # Create alert
            alert = SecurityAlert(
                alert_id=self._generate_alert_id(),
                title=f"Security Rule Triggered: {rule.name}",
                description=f"{rule.description} (Triggered {count} times in {rule.time_window} seconds)",
                level=rule.alert_level,
                category=EventCategory.INCIDENT_RESPONSE,
                timestamp=datetime.utcnow(),
                source_ip=event_data.get('source_ip'),
                user_id=event_data.get('user_id'),
                technical_details={
                    'rule_id': rule.rule_id,
                    'trigger_count': count,
                    'time_window': rule.time_window,
                    'last_event': event_data
                },
                recommended_actions=[
                    f"Investigate {rule.name} pattern",
                    "Review recent security events",
                    "Check system logs for anomalies"
                ],
                alert_channels=rule.alert_channels
            )
            
            await self._process_alert(alert)
            
            # Reset counter after alert
            await self._reset_rule_counter(rule.rule_id)
            
        except Exception as e:
            self.logger.error(f"Error triggering rule alert: {e}")
    
    async def _reset_rule_counter(self, rule_id: str):
        """Reset counter for alert rule"""
        try:
            if self.redis_client:
                counter_key = f"alert_rule_counter:{rule_id}"
                await self.redis_client.delete(counter_key)
            else:
                self.event_counters.pop(rule_id, None)
                
        except Exception as e:
            self.logger.error(f"Error resetting rule counter: {e}")
    
    async def _should_suppress_alert(self, alert: SecurityAlert) -> bool:
        """Check if alert should be suppressed to avoid spam"""
        try:
            # Create suppression key based on alert type and source
            suppression_key = f"{alert.category.value}:{alert.level.value}:{alert.source_ip or 'unknown'}"
            
            if self.redis_client:
                exists = await self.redis_client.exists(f"alert_suppression:{suppression_key}")
                return bool(exists)
            else:
                # Memory-based suppression
                return suppression_key in self.alert_suppressions
                
        except Exception as e:
            self.logger.error(f"Error checking alert suppression: {e}")
            return False
    
    async def _record_alert_suppression(self, alert: SecurityAlert):
        """Record alert suppression to prevent duplicates"""
        try:
            suppression_key = f"{alert.category.value}:{alert.level.value}:{alert.source_ip or 'unknown'}"
            
            # Suppression duration based on alert level
            suppression_duration = {
                AlertLevel.INFO: 300,      # 5 minutes
                AlertLevel.WARNING: 600,   # 10 minutes
                AlertLevel.ERROR: 1800,    # 30 minutes
                AlertLevel.CRITICAL: 3600, # 1 hour
                AlertLevel.EMERGENCY: 300  # 5 minutes (shorter for emergencies)
            }
            
            duration = suppression_duration.get(alert.level, 600)
            
            if self.redis_client:
                await self.redis_client.setex(
                    f"alert_suppression:{suppression_key}",
                    duration,
                    alert.alert_id
                )
            else:
                self.alert_suppressions[suppression_key] = time.time() + duration
                
        except Exception as e:
            self.logger.error(f"Error recording alert suppression: {e}")
    
    async def _process_alert(self, alert: SecurityAlert):
        """Process alert through configured channels"""
        try:
            tasks = []
            
            for channel in alert.alert_channels:
                if channel in self.alert_handlers:
                    task = self.alert_handlers[channel](alert)
                    tasks.append(task)
            
            # Execute all alert handlers concurrently
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                
        except Exception as e:
            self.logger.error(f"Error processing alert: {e}")
    
    async def _send_email_alert(self, alert: SecurityAlert):
        """Send email alert"""
        try:
            if not self.notification_settings['email']['admin_emails']:
                return
            
            subject = f"[Healthcare AI Security] {alert.level.value.upper()}: {alert.title}"
            
            body = f"""
Security Alert Details:

Title: {alert.title}
Level: {alert.level.value.upper()}
Category: {alert.category.value}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

Description:
{alert.description}

Technical Details:
{json.dumps(alert.technical_details, indent=2)}

Recommended Actions:
{chr(10).join('- ' + action for action in alert.recommended_actions)}

Alert ID: {alert.alert_id}
Source IP: {alert.source_ip or 'Unknown'}
User ID: {alert.user_id or 'N/A'}

This is an automated security alert from Healthcare AI V2.
"""
            
            # Send email using aiosmtplib
            message = MimeMultipart()
            message['From'] = self.notification_settings['email']['from_email']
            message['To'] = ', '.join(self.notification_settings['email']['admin_emails'])
            message['Subject'] = subject
            
            message.attach(MimeText(body, 'plain'))
            
            smtp_settings = self.notification_settings['email']
            
            await aiosmtplib.send(
                message,
                hostname=smtp_settings['smtp_server'],
                port=smtp_settings['smtp_port'],
                username=smtp_settings['smtp_username'],
                password=smtp_settings['smtp_password'],
                use_tls=True
            )
            
            self.logger.info(f"Email alert sent for {alert.alert_id}")
            
        except Exception as e:
            self.logger.error(f"Error sending email alert: {e}")
    
    async def _send_slack_alert(self, alert: SecurityAlert):
        """Send Slack alert"""
        try:
            webhook_url = self.notification_settings['slack']['webhook_url']
            if not webhook_url:
                return
            
            # Slack color based on alert level
            colors = {
                AlertLevel.INFO: '#36a64f',      # Green
                AlertLevel.WARNING: '#ff9900',   # Orange
                AlertLevel.ERROR: '#ff0000',     # Red
                AlertLevel.CRITICAL: '#8b0000',  # Dark Red
                AlertLevel.EMERGENCY: '#ff1493'  # Deep Pink
            }
            
            slack_payload = {
                "channel": self.notification_settings['slack']['channel'],
                "username": "Healthcare AI Security",
                "icon_emoji": ":warning:",
                "attachments": [{
                    "color": colors.get(alert.level, '#ff9900'),
                    "title": f"{alert.level.value.upper()}: {alert.title}",
                    "text": alert.description,
                    "fields": [
                        {
                            "title": "Category",
                            "value": alert.category.value,
                            "short": True
                        },
                        {
                            "title": "Source IP",
                            "value": alert.source_ip or "Unknown",
                            "short": True
                        },
                        {
                            "title": "Alert ID",
                            "value": alert.alert_id,
                            "short": True
                        },
                        {
                            "title": "Timestamp",
                            "value": alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC'),
                            "short": True
                        }
                    ],
                    "footer": "Healthcare AI V2 Security System",
                    "ts": int(alert.timestamp.timestamp())
                }]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=slack_payload)
                response.raise_for_status()
            
            self.logger.info(f"Slack alert sent for {alert.alert_id}")
            
        except Exception as e:
            self.logger.error(f"Error sending Slack alert: {e}")
    
    async def _send_webhook_alert(self, alert: SecurityAlert):
        """Send webhook alert"""
        try:
            webhook_urls = self.notification_settings['webhook']['urls']
            if not webhook_urls:
                return
            
            payload = alert.to_dict()
            
            async with httpx.AsyncClient() as client:
                for url in webhook_urls:
                    try:
                        response = await client.post(
                            url,
                            json=payload,
                            timeout=10
                        )
                        response.raise_for_status()
                        self.logger.info(f"Webhook alert sent to {url} for {alert.alert_id}")
                    except Exception as e:
                        self.logger.error(f"Error sending webhook to {url}: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error sending webhook alerts: {e}")
    
    async def _send_sms_alert(self, alert: SecurityAlert):
        """Send SMS alert (placeholder - integrate with SMS service)"""
        try:
            # This would integrate with an SMS service like Twilio, AWS SNS, etc.
            self.logger.info(f"SMS alert would be sent for {alert.alert_id}")
            # TODO: Implement SMS integration
            
        except Exception as e:
            self.logger.error(f"Error sending SMS alert: {e}")
    
    async def _store_alert_in_database(self, alert: SecurityAlert):
        """Store alert in database"""
        try:
            async with get_async_session() as session:
                audit_log = AuditLog(
                    event_type="security_alert",
                    event_category=alert.category.value,
                    event_description=f"ALERT: {alert.title} - {alert.description}",
                    user_id=alert.user_id,
                    ip_address=alert.source_ip,
                    severity_level=alert.level.value,
                    old_values=alert.technical_details,
                    result='alert_generated'
                )
                session.add(audit_log)
                await session.commit()
                
        except Exception as e:
            self.logger.error(f"Error storing alert in database: {e}")
    
    async def _log_alert(self, alert: SecurityAlert):
        """Log alert to application logs"""
        try:
            log_level_map = {
                AlertLevel.INFO: 'info',
                AlertLevel.WARNING: 'warning',
                AlertLevel.ERROR: 'error',
                AlertLevel.CRITICAL: 'critical',
                AlertLevel.EMERGENCY: 'critical'
            }
            
            log_level = log_level_map.get(alert.level, 'warning')
            
            getattr(self.logger, log_level)(
                f"SECURITY ALERT [{alert.level.value.upper()}]: {alert.title} - {alert.description}",
                extra={
                    'alert_id': alert.alert_id,
                    'category': alert.category.value,
                    'source_ip': alert.source_ip,
                    'user_id': alert.user_id,
                    'technical_details': alert.technical_details
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error logging alert: {e}")
    
    def _configure_default_rules(self) -> Dict[str, AlertRule]:
        """Configure default alert rules"""
        return {
            'failed_login_burst': AlertRule(
                rule_id='failed_login_burst',
                name='Failed Login Burst',
                description='Multiple failed login attempts detected',
                event_pattern='failed_login',
                threshold=5,
                time_window=300,  # 5 minutes
                alert_level=AlertLevel.WARNING,
                alert_channels=[AlertChannel.EMAIL, AlertChannel.LOG]
            ),
            'brute_force_attack': AlertRule(
                rule_id='brute_force_attack',
                name='Brute Force Attack',
                description='Brute force attack pattern detected',
                event_pattern='brute_force',
                threshold=1,
                time_window=60,
                alert_level=AlertLevel.CRITICAL,
                alert_channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.LOG]
            ),
            'sql_injection_attempt': AlertRule(
                rule_id='sql_injection_attempt',
                name='SQL Injection Attempt',
                description='SQL injection attack detected',
                event_pattern='sql_injection',
                threshold=1,
                time_window=60,
                alert_level=AlertLevel.CRITICAL,
                alert_channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.LOG]
            ),
            'xss_attempt': AlertRule(
                rule_id='xss_attempt',
                name='XSS Attack Attempt',
                description='Cross-site scripting attack detected',
                event_pattern='xss',
                threshold=3,
                time_window=300,
                alert_level=AlertLevel.ERROR,
                alert_channels=[AlertChannel.EMAIL, AlertChannel.LOG]
            ),
            'suspicious_file_upload': AlertRule(
                rule_id='suspicious_file_upload',
                name='Suspicious File Upload',
                description='Potentially malicious file upload detected',
                event_pattern='malicious_file',
                threshold=1,
                time_window=60,
                alert_level=AlertLevel.ERROR,
                alert_channels=[AlertChannel.EMAIL, AlertChannel.LOG]
            ),
            'rate_limit_abuse': AlertRule(
                rule_id='rate_limit_abuse',
                name='Rate Limit Abuse',
                description='Excessive rate limit violations detected',
                event_pattern='rate_limit',
                threshold=10,
                time_window=300,
                alert_level=AlertLevel.WARNING,
                alert_channels=[AlertChannel.LOG]
            ),
            'privilege_escalation': AlertRule(
                rule_id='privilege_escalation',
                name='Privilege Escalation Attempt',
                description='Unauthorized privilege escalation detected',
                event_pattern='privilege_escalation',
                threshold=1,
                time_window=60,
                alert_level=AlertLevel.CRITICAL,
                alert_channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.LOG]
            )
        }
    
    def _get_default_channels(self, level: AlertLevel) -> List[AlertChannel]:
        """Get default alert channels based on level"""
        if level == AlertLevel.EMERGENCY:
            return [AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.SMS, AlertChannel.LOG, AlertChannel.DATABASE]
        elif level == AlertLevel.CRITICAL:
            return [AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.LOG, AlertChannel.DATABASE]
        elif level == AlertLevel.ERROR:
            return [AlertChannel.EMAIL, AlertChannel.LOG, AlertChannel.DATABASE]
        elif level == AlertLevel.WARNING:
            return [AlertChannel.LOG, AlertChannel.DATABASE]
        else:
            return [AlertChannel.LOG]
    
    def _generate_alert_id(self) -> str:
        """Generate unique alert ID"""
        return f"alert_{int(time.time() * 1000)}_{hash(time.time()) % 10000:04d}"
    
    async def get_recent_alerts(self, hours: int = 24, level: Optional[AlertLevel] = None) -> List[Dict[str, Any]]:
        """Get recent security alerts"""
        try:
            alerts = []
            
            if self.redis_client:
                # Get alerts from Redis
                for hour in range(hours):
                    date_key = (datetime.utcnow() - timedelta(hours=hour)).strftime('%Y-%m-%d')
                    event_key = f"security_events:{date_key}"
                    
                    events = await self.redis_client.lrange(event_key, 0, -1)
                    for event_json in events:
                        try:
                            event = json.loads(event_json)
                            if level is None or event.get('level') == level.value:
                                alerts.append(event)
                        except json.JSONDecodeError:
                            continue
            
            # Sort by timestamp
            alerts.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            return alerts[:100]  # Limit to 100 most recent
            
        except Exception as e:
            self.logger.error(f"Error getting recent alerts: {e}")
            return []


# Global security event tracker
security_event_tracker = SecurityEventTracker()


async def initialize_security_events():
    """Initialize the security event tracker"""
    await security_event_tracker.initialize()


# Convenience functions

async def track_security_event(
    event_type: str,
    description: str,
    level: AlertLevel = AlertLevel.INFO,
    category: EventCategory = EventCategory.SYSTEM_SECURITY,
    user_id: Optional[int] = None,
    source_ip: Optional[str] = None,
    technical_details: Dict[str, Any] = None,
    affected_resources: List[str] = None
):
    """Track a security event"""
    await security_event_tracker.track_event(
        event_type=event_type,
        description=description,
        level=level,
        category=category,
        user_id=user_id,
        source_ip=source_ip,
        technical_details=technical_details,
        affected_resources=affected_resources
    )


async def create_security_alert(
    title: str,
    description: str,
    level: AlertLevel,
    category: EventCategory,
    source_ip: Optional[str] = None,
    user_id: Optional[int] = None,
    technical_details: Dict[str, Any] = None,
    recommended_actions: List[str] = None
) -> SecurityAlert:
    """Create a security alert"""
    return await security_event_tracker.create_alert(
        title=title,
        description=description,
        level=level,
        category=category,
        source_ip=source_ip,
        user_id=user_id,
        technical_details=technical_details,
        recommended_actions=recommended_actions
    )
