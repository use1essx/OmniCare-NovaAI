"""
Healthcare AI V2 - Logging Configuration
Structured logging with JSON format and proper handlers
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import structlog
except ImportError:
    structlog = None

try:
    from pythonjsonlogger import jsonlogger
except ImportError:
    jsonlogger = None

from src.core.config import settings


class HealthcareAIFormatter(logging.Formatter if not jsonlogger else jsonlogger.JsonFormatter):
    """Custom JSON formatter for Healthcare AI logs"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add custom fields to log records"""
        if jsonlogger:
            super().add_fields(log_record, record, message_dict)
        else:
            # Fallback for when jsonlogger is not available
            log_record.update(message_dict)
        
        # Add standard fields
        log_record['timestamp'] = self.formatTime(record, self.datefmt)
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno
        
        # Add application context
        log_record['app_name'] = settings.app_name
        log_record['app_version'] = settings.app_version
        log_record['environment'] = settings.environment
        
        # Add thread/process info for debugging
        if settings.debug:
            log_record['thread'] = record.thread
            log_record['process'] = record.process


class SecurityFilter(logging.Filter):
    """Filter for security-related logs"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Only allow security-related log records"""
        security_keywords = [
            'login', 'logout', 'authentication', 'authorization',
            'security', 'audit', 'access', 'permission', 'token',
            'password', 'session', 'failed', 'blocked', 'suspicious'
        ]
        
        message = record.getMessage().lower()
        return any(keyword in message for keyword in security_keywords)


class DatabaseFilter(logging.Filter):
    """Filter for database-related logs"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Only allow database-related log records"""
        return (
            record.name.startswith('sqlalchemy') or
            'database' in record.getMessage().lower() or
            'sql' in record.getMessage().lower() or
            'query' in record.getMessage().lower()
        )


class AgentFilter(logging.Filter):
    """Filter for agent interaction logs"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Only allow agent-related log records"""
        agent_keywords = [
            'agent', 'conversation', 'chat', 'response',
            'routing', 'orchestrator', 'intent', 'urgency'
        ]
        
        message = record.getMessage().lower()
        return (
            record.name.startswith('src.agents') or
            any(keyword in message for keyword in agent_keywords)
        )


def setup_logging() -> None:
    """
    Setup comprehensive logging configuration
    """
    # Ensure log directory exists
    log_file = Path(settings.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Clear existing handlers
    logging.root.handlers.clear()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Create formatters
    if settings.log_format.lower() == 'json' and jsonlogger:
        formatter = HealthcareAIFormatter(
            fmt='%(timestamp)s %(level)s %(logger)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, settings.log_level.upper()))
    root_logger.addHandler(console_handler)
    
    # File handler for general logs
    file_handler = logging.handlers.RotatingFileHandler(
        filename=settings.log_file,
        maxBytes=_parse_size(settings.log_max_size),
        backupCount=settings.log_backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, settings.log_level.upper()))
    root_logger.addHandler(file_handler)
    
    # Specialized handlers based on settings
    if settings.log_security_events:
        security_handler = logging.handlers.RotatingFileHandler(
            filename=log_file.parent / 'security.log',
            maxBytes=_parse_size(settings.log_max_size),
            backupCount=settings.log_backup_count,
            encoding='utf-8'
        )
        security_handler.setFormatter(formatter)
        security_handler.addFilter(SecurityFilter())
        security_handler.setLevel(logging.INFO)
        root_logger.addHandler(security_handler)
    
    if settings.log_database_queries:
        db_handler = logging.handlers.RotatingFileHandler(
            filename=log_file.parent / 'database.log',
            maxBytes=_parse_size(settings.log_max_size),
            backupCount=settings.log_backup_count,
            encoding='utf-8'
        )
        db_handler.setFormatter(formatter)
        db_handler.addFilter(DatabaseFilter())
        db_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(db_handler)
    
    if settings.log_agent_interactions:
        agent_handler = logging.handlers.RotatingFileHandler(
            filename=log_file.parent / 'agents.log',
            maxBytes=_parse_size(settings.log_max_size),
            backupCount=settings.log_backup_count,
            encoding='utf-8'
        )
        agent_handler.setFormatter(formatter)
        agent_handler.addFilter(AgentFilter())
        agent_handler.setLevel(logging.INFO)
        root_logger.addHandler(agent_handler)
    
    # Configure third-party loggers
    _configure_third_party_loggers()
    
    # Setup structlog if using JSON format and available
    if settings.log_format.lower() == 'json' and structlog:
        _setup_structlog()
    
    # Log initial message
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured",
        extra={
            'log_level': settings.log_level,
            'log_format': settings.log_format,
            'log_file': str(settings.log_file),
            'handlers_count': len(root_logger.handlers)
        }
    )


def _parse_size(size_str: str) -> int:
    """Parse size string like '100MB' to bytes"""
    size_str = size_str.upper().strip()
    
    if size_str.endswith('KB'):
        return int(size_str[:-2]) * 1024
    elif size_str.endswith('MB'):
        return int(size_str[:-2]) * 1024 * 1024
    elif size_str.endswith('GB'):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    else:
        # Assume bytes
        return int(size_str)


def _configure_third_party_loggers() -> None:
    """Configure logging levels for third-party libraries"""
    # Reduce noise from third-party libraries
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('fastapi').setLevel(logging.WARNING)
    
    # SQLAlchemy logging
    if settings.log_database_queries:
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
        logging.getLogger('sqlalchemy.dialects').setLevel(logging.INFO)
        logging.getLogger('sqlalchemy.pool').setLevel(logging.INFO)
        logging.getLogger('sqlalchemy.orm').setLevel(logging.INFO)
    else:
        logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
    
    # HTTP clients
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    
    # Redis
    logging.getLogger('redis').setLevel(logging.WARNING)
    
    # AWS Bedrock
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)


def _setup_structlog() -> None:
    """Setup structlog for structured logging"""
    if not structlog:
        return
        
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_security_event(
    event_type: str,
    description: str,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    risk_level: str = "low",
    **kwargs: Any
) -> None:
    """
    Log a security event with structured data
    
    Args:
        event_type: Type of security event
        description: Event description
        user_id: User ID if applicable
        ip_address: IP address if applicable
        risk_level: Risk level (low, medium, high, critical)
        **kwargs: Additional context data
    """
    logger = get_logger('security')
    
    extra_data = {
        'event_type': event_type,
        'user_id': user_id,
        'ip_address': ip_address,
        'risk_level': risk_level,
        **kwargs
    }
    
    # Choose log level based on risk
    if risk_level == 'critical':
        logger.critical(description, extra=extra_data)
    elif risk_level == 'high':
        logger.error(description, extra=extra_data)
    elif risk_level == 'medium':
        logger.warning(description, extra=extra_data)
    else:
        logger.info(description, extra=extra_data)


def log_agent_interaction(
    agent_type: str,
    user_input: str,
    agent_response: str,
    confidence: float,
    urgency_level: str,
    processing_time_ms: int,
    **kwargs: Any
) -> None:
    """
    Log an agent interaction with structured data
    
    Args:
        agent_type: Type of agent that handled the interaction
        user_input: User's input (truncated for privacy)
        agent_response: Agent's response (truncated)
        confidence: Agent confidence score
        urgency_level: Detected urgency level
        processing_time_ms: Processing time in milliseconds
        **kwargs: Additional context data
    """
    logger = get_logger('agents')
    
    # Truncate sensitive data
    truncated_input = user_input[:200] + "..." if len(user_input) > 200 else user_input
    truncated_response = agent_response[:200] + "..." if len(agent_response) > 200 else agent_response
    
    extra_data = {
        'agent_type': agent_type,
        'user_input_length': len(user_input),
        'user_input_preview': truncated_input,
        'response_length': len(agent_response),
        'response_preview': truncated_response,
        'confidence': confidence,
        'urgency_level': urgency_level,
        'processing_time_ms': processing_time_ms,
        **kwargs
    }
    
    logger.info(f"Agent interaction completed: {agent_type}", extra=extra_data)


def log_api_request(
    method: str,
    endpoint: str,
    status_code: int,
    response_time_ms: int,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    **kwargs: Any
) -> None:
    """
    Log an API request with structured data
    
    Args:
        method: HTTP method
        endpoint: API endpoint
        status_code: HTTP status code
        response_time_ms: Response time in milliseconds
        user_id: User ID if authenticated
        ip_address: Client IP address
        **kwargs: Additional context data
    """
    if not settings.log_api_requests:
        return
    
    logger = get_logger('api')
    
    extra_data = {
        'method': method,
        'endpoint': endpoint,
        'status_code': status_code,
        'response_time_ms': response_time_ms,
        'user_id': user_id,
        'ip_address': ip_address,
        **kwargs
    }
    
    # Choose log level based on status code
    if status_code >= 500:
        logger.error(f"{method} {endpoint} - {status_code}", extra=extra_data)
    elif status_code >= 400:
        logger.warning(f"{method} {endpoint} - {status_code}", extra=extra_data)
    else:
        logger.info(f"{method} {endpoint} - {status_code}", extra=extra_data)


# Context managers for logging
class LogContext:
    """Context manager for adding context to logs"""
    
    def __init__(self, **context: Any):
        self.context = context
        self.old_factory = None
    
    def __enter__(self):
        self.old_factory = logging.getLogRecordFactory()
        
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)


# Export commonly used items
__all__ = [
    'setup_logging',
    'get_logger',
    'log_security_event',
    'log_agent_interaction',
    'log_api_request',
    'LogContext',
]
