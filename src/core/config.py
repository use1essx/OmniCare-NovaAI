"""
Healthcare AI V2 - Configuration Management
Centralized configuration using Pydantic Settings for type safety and validation
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union

from pydantic import Field, field_validator, model_validator

try:
    from pydantic_settings import BaseSettings
except ImportError:
    # Fallback for pydantic v1
    from pydantic import BaseSettings

# Type aliases for URL validation
PostgresDsn = str
RedisDsn = str


class Settings(BaseSettings):
    """
    Application settings with environment variable support and validation
    """
    
    # =============================================================================
    # APPLICATION CONFIGURATION
    # =============================================================================
    
    app_name: str = Field(default="Healthcare AI V2")
    app_version: str = Field(default="2.0.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    
    # Server Configuration
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    reload: bool = Field(default=False)
    
    # API Configuration
    api_v1_prefix: str = Field(default="/api/v1")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        env="CORS_ORIGINS"
    )
    live2d_connect_sources: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:8790",
            "https://localhost:8790"
        ],
        env="LIVE2D_CONNECT_SOURCES"
    )
    live2d_permissions_policy: str = Field(
        default=(
            'geolocation=(self "http://localhost" "https://localhost"), '
            'microphone=(self "http://localhost" "https://localhost"), '
            'camera=()'
        ),
        env="LIVE2D_PERMISSIONS_POLICY"
    )
    default_permissions_policy: str = Field(
        default="camera=(), microphone=(), geolocation=(), payment=(), usb=(), magnetometer=(), gyroscope=()",
        env="DEFAULT_PERMISSIONS_POLICY"
    )
    enable_live2d_security_headers: bool = Field(
        default=True,
        env="ENABLE_LIVE2D_SECURITY_HEADERS"
    )
    live2d_enable_csp: bool = Field(
        default=True,
        env="LIVE2D_ENABLE_CSP"
    )
    live2d_stt_service_url: str = Field(
        default="http://localhost:8790",
        env="LIVE2D_STT_SERVICE_URL"
    )
    live2d_stt_timeout_seconds: int = Field(
        default=90,
        env="LIVE2D_STT_TIMEOUT_SECONDS"
    )
    
    # =============================================================================
    # SECURITY CONFIGURATION
    # =============================================================================
    
    secret_key: str = Field(..., min_length=32)
    jwt_secret_key: Optional[str] = Field(default=None)
    
    # Token Configuration
    access_token_expire_minutes: int = Field(default=30)
    refresh_token_expire_days: int = Field(default=7)
    
    # Password Policy
    password_min_length: int = Field(default=8)
    max_login_attempts: int = Field(default=5)
    account_lockout_duration_minutes: int = Field(default=30)
    
    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60)
    rate_limit_per_hour: int = Field(default=1000)
    
    # =============================================================================
    # DATABASE CONFIGURATION
    # =============================================================================
    
    database_host: str = Field(default="localhost")
    database_port: int = Field(default=5432)
    database_name: str = Field(default="healthcare_ai_v2")
    database_user: str = Field(default="admin")
    database_password: str = Field(...)
    
    # Connection Pool Settings
    database_pool_size: int = Field(default=10)
    database_max_overflow: int = Field(default=20)
    database_pool_timeout: int = Field(default=30)
    database_pool_recycle: int = Field(default=3600)
    
    # Database URLs (auto-generated or override)
    database_url: Optional[str] = Field(default=None)
    database_sync_url: Optional[str] = Field(default=None)
    
    # Demo Data Seeding
    seed_demo_data: bool = Field(default=True)  # Set to False in production
    
    # =============================================================================
    # REDIS CONFIGURATION
    # =============================================================================
    
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)
    redis_password: Optional[str] = Field(default=None)
    
    # Redis URL (auto-generated or override)
    redis_url: Optional[str] = Field(default=None)
    
    # Cache TTL Settings (in seconds)
    redis_cache_ttl: int = Field(default=3600)  # 1 hour
    redis_session_ttl: int = Field(default=1800)  # 30 minutes
    hk_data_cache_ttl: int = Field(default=1800)  # 30 minutes
    
    # =============================================================================
    # EXTERNAL API CONFIGURATION
    # =============================================================================
    
    # AWS Bedrock Configuration (Primary and Only AI Provider)
    use_bedrock: bool = Field(default=True)
    aws_access_key_id: Optional[str] = Field(default=None)
    aws_secret_access_key: Optional[str] = Field(default=None)
    aws_region: str = Field(default="us-east-1")
    
    # Nova Model Configuration
    nova_lite_model_id: str = Field(default="amazon.nova-2-lite-v1:0")
    nova_pro_model_id: str = Field(default="amazon.nova-pro-v1:0")
    
    # Titan Embeddings Configuration
    titan_embed_model_id: str = Field(default="amazon.titan-embed-text-v1")
    
    # Budget Protection ($50 hard limit)
    budget_limit_usd: float = Field(default=50.00)
    budget_warning_threshold: float = Field(default=0.80)  # 80%
    enable_cost_tracking: bool = Field(default=True)
    
    # Hong Kong Data Configuration
    hk_data_update_interval: int = Field(default=3600)  # 1 hour
    hk_data_cache_ttl: int = Field(default=1800)  # 30 minutes
    hk_data_retry_attempts: int = Field(default=3)
    hk_data_timeout: int = Field(default=30)
    
    # =============================================================================
    # FILE UPLOAD CONFIGURATION
    # =============================================================================
    
    upload_path: Path = Field(default=Path("./uploads"))
    upload_max_size: int = Field(default=52428800)  # 50MB
    upload_allowed_extensions: List[str] = Field(
        default=[".pdf", ".jpg", ".jpeg", ".png", ".txt", ".doc", ".docx"],
        env="UPLOAD_ALLOWED_EXTENSIONS"
    )

    # Knowledge base / RAG
    knowledge_upload_path: Path = Field(default=Path("./uploads/knowledge"))
    knowledge_max_video_minutes: int = Field(default=10)  # hard cap duration
    knowledge_max_upload_size: int = Field(default=104857600)  # 100 MB
    rag_enabled: bool = Field(default=False)
    rag_per_skill: List[str] = Field(default=[])
    kb_sandbox_dev_mode: bool = Field(default=False)
    kb_sandbox_dev_org_id: int = Field(default=1)
    
    # File Processing
    enable_ocr: bool = Field(default=True)
    ocr_language: str = Field(default="eng+chi_tra")
    pdf_max_pages: int = Field(default=100)
    
    # =============================================================================
    # AI SEMANTIC CHUNKING CONFIGURATION
    # =============================================================================
    
    # Feature Flag
    ai_semantic_chunking_enabled: bool = Field(default=False)
    
    # AI Service Configuration
    semantic_chunk_timeout: int = Field(default=30)  # seconds
    semantic_chunk_max_concurrent: int = Field(default=5)  # max concurrent AI requests
    
    # =============================================================================
    # AGENT SYSTEM CONFIGURATION
    # =============================================================================
    
    # Agent Configuration
    default_agent_timeout: int = Field(default=30)
    max_conversation_history: int = Field(default=50)
    agent_confidence_threshold: float = Field(default=0.6)
    
    # Agent Routing
    enable_intelligent_routing: bool = Field(default=True)
    routing_model: str = Field(default="amazon.nova-lite-v1:0")
    urgency_detection_threshold: float = Field(default=0.8)
    
    # Cultural Settings
    default_language: str = Field(default="en")
    supported_languages: List[str] = Field(default=["en", "zh-HK"])  # Only English and Cantonese (Hong Kong)
    cultural_context: str = Field(default="hong_kong")
    
    # =============================================================================
    # LOGGING AND MONITORING CONFIGURATION
    # =============================================================================
    
    # Logging Configuration
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    log_file: Path = Field(default=Path("./logs/healthcare_ai.log"))
    log_max_size: str = Field(default="100MB")
    log_backup_count: int = Field(default=5)
    
    # Logging Categories
    log_database_queries: bool = Field(default=False)
    log_api_requests: bool = Field(default=True)
    log_agent_interactions: bool = Field(default=True)
    log_security_events: bool = Field(default=True)
    
    # Monitoring
    enable_metrics: bool = Field(default=True)
    metrics_port: int = Field(default=9090)
    enable_health_checks: bool = Field(default=True)
    health_check_interval: int = Field(default=30)
    
    # Error Tracking
    sentry_dsn: Optional[str] = Field(default=None)
    sentry_environment: str = Field(default="development")
    sentry_traces_sample_rate: float = Field(default=0.1)
    
    # =============================================================================
    # BACKGROUND TASKS CONFIGURATION
    # =============================================================================
    
    # Worker Configuration
    worker_concurrency: int = Field(default=4)
    worker_max_tasks_per_child: int = Field(default=1000)
    
    # Task Queues
    enable_background_tasks: bool = Field(default=True)
    task_queue_url: Optional[str] = Field(default=None)
    
    # Scheduled Tasks
    enable_data_sync: bool = Field(default=True)
    data_sync_interval: int = Field(default=3600)  # 1 hour
    
    enable_learning_updates: bool = Field(default=True)
    learning_update_interval: int = Field(default=86400)  # 24 hours
    
    enable_cleanup_tasks: bool = Field(default=True)
    cleanup_interval: int = Field(default=604800)  # 7 days
    
    # =============================================================================
    # SECURITY MONITORING CONFIGURATION
    # =============================================================================
    
    # Security Event Tracking
    enable_security_monitoring: bool = Field(default=True)
    security_alert_email: str = Field(default="security@healthcare-ai.com")
    admin_emails: List[str] = Field(default=["admin@healthcare-ai.com"])
    
    # SMTP Configuration for Security Alerts
    smtp_server: str = Field(default="localhost")
    smtp_port: int = Field(default=587)
    smtp_username: str = Field(default="")
    smtp_password: str = Field(default="")
    alert_from_email: str = Field(default="security@healthcare-ai.com")
    
    # Slack Integration
    slack_webhook_url: str = Field(default="")
    slack_channel: str = Field(default="#security-alerts")
    
    # Webhook Alerts
    alert_webhook_urls: List[str] = Field(default=[])
    
    # Security Thresholds
    failed_login_threshold: int = Field(default=5)
    brute_force_threshold: int = Field(default=10)
    rate_limit_violation_threshold: int = Field(default=10)
    
    # IP Blocking
    auto_block_suspicious_ips: bool = Field(default=True)
    default_ip_block_duration_minutes: int = Field(default=60)
    
    # =============================================================================
    # DEVELOPMENT CONFIGURATION
    # =============================================================================
    
    # Development Tools
    enable_api_docs: bool = Field(default=True)
    enable_admin_interface: bool = Field(default=True)
    enable_debug_toolbar: bool = Field(default=False)
    
    # Testing
    test_database_url: Optional[str] = Field(default=None)
    enable_test_data: bool = Field(default=False)
    
    # =============================================================================
    # VALIDATORS
    # =============================================================================
    
    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret_key(cls, v: Optional[str]) -> str:
        """Use secret_key if jwt_secret_key is not provided"""
        if v is None:
            return ""  # Will be set in model_validator
        return v
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is one of the allowed values"""
        allowed_environments = ["development", "staging", "production", "testing"]
        if v not in allowed_environments:
            raise ValueError(f"Environment must be one of: {allowed_environments}")
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the allowed values"""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in allowed_levels:
            raise ValueError(f"Log level must be one of: {allowed_levels}")
        return v_upper
    
    @field_validator("upload_path", mode="before")
    @classmethod
    def validate_upload_path(cls, v: Union[str, Path]) -> Path:
        """Convert string to Path and ensure it's absolute"""
        path = Path(v) if isinstance(v, str) else v
        if not path.is_absolute():
            path = Path.cwd() / path
        return path

    @field_validator("cors_origins", "live2d_connect_sources", mode="before")
    @classmethod
    def parse_csv_list(cls, v: Union[str, List[str]]) -> List[str]:
        """Allow comma or newline separated env vars for list fields"""
        if isinstance(v, str):
            # Support comma or whitespace separated lists
            items = [
                item.strip()
                for part in v.splitlines()
                for item in part.split(",")
                if item.strip()
            ]
            return items
        return v
    
    @field_validator("log_file", mode="before")
    @classmethod
    def validate_log_file(cls, v: Union[str, Path]) -> Path:
        """Convert string to Path and ensure directory exists"""
        path = Path(v) if isinstance(v, str) else v
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Create log directory if it doesn't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    
    def _validate_no_placeholders(self) -> None:
        """
        SECURITY: Validate that no placeholder values are used in production
        
        Raises:
            ValueError: If placeholder values detected in production environment
        """
        placeholder_indicators = [
            "CHANGE_IN_PRODUCTION",
            "your-api-key-here",
            "your_secure_password_here",
            "generate_with_openssl",
            "your-aws-access-key",
            "your-aws-secret-key",
        ]
        
        # Check critical fields for placeholder values
        critical_fields = {
            "secret_key": self.secret_key,
            "jwt_secret_key": self.jwt_secret_key,
            "database_password": self.database_password,
        }
        
        # Check AWS credentials if they're set
        if self.aws_access_key_id:
            critical_fields["aws_access_key_id"] = self.aws_access_key_id
        if self.aws_secret_access_key:
            critical_fields["aws_secret_access_key"] = self.aws_secret_access_key
        
        errors = []
        for field_name, field_value in critical_fields.items():
            if not field_value:
                errors.append(f"{field_name} is empty")
                continue
                
            field_value_lower = str(field_value).lower()
            for indicator in placeholder_indicators:
                if indicator.lower() in field_value_lower:
                    errors.append(
                        f"{field_name} contains placeholder value '{indicator}'. "
                        f"Please set a real value in your .env file."
                    )
                    break
        
        if errors:
            error_msg = (
                "SECURITY ERROR: Placeholder values detected in production environment!\n\n"
                + "\n".join(f"  - {error}" for error in errors)
                + "\n\nPlease update your .env file with real credentials before deploying to production."
            )
            raise ValueError(error_msg)
    
    @model_validator(mode="after")
    def validate_all_settings(self) -> "Settings":
        """Validate and auto-generate URLs and other settings"""
        # SECURITY: Validate no placeholder values in production
        if self.is_production:
            self._validate_no_placeholders()
        
        # Set jwt_secret_key if not provided
        if not self.jwt_secret_key:
            self.jwt_secret_key = self.secret_key
        
        # Auto-generate database URLs if not provided
        if not self.database_url:
            self.database_url = (
                f"postgresql+asyncpg://{self.database_user}:"
                f"{self.database_password}@{self.database_host}:"
                f"{self.database_port}/{self.database_name}"
            )
        
        if not self.database_sync_url:
            self.database_sync_url = (
                f"postgresql://{self.database_user}:"
                f"{self.database_password}@{self.database_host}:"
                f"{self.database_port}/{self.database_name}"
            )
        
        # Auto-generate Redis URL if not provided
        if not self.redis_url:
            password_part = ""
            if self.redis_password:
                password_part = f":{self.redis_password}@"
            
            self.redis_url = (
                f"redis://{password_part}{self.redis_host}:"
                f"{self.redis_port}/{self.redis_db}"
            )
        
        # Auto-generate task queue URL if not provided
        if not self.task_queue_url and self.enable_background_tasks:
            password_part = ""
            if self.redis_password:
                password_part = f":{self.redis_password}@"
            
            self.task_queue_url = (
                f"redis://{password_part}{self.redis_host}:"
                f"{self.redis_port}/1"  # Different DB for task queue
            )
        
        return self
    
    # =============================================================================
    # PROPERTIES
    # =============================================================================
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment == "production"
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment"""
        return self.environment == "testing"
    
    @property
    def database_url_str(self) -> str:
        """Get database URL as string"""
        return str(self.database_url) if self.database_url else ""
    
    @property
    def database_sync_url_str(self) -> str:
        """Get synchronous database URL as string"""
        return str(self.database_sync_url) if self.database_sync_url else ""
    
    @property
    def redis_url_str(self) -> str:
        """Get Redis URL as string"""
        return str(self.redis_url) if self.redis_url else ""
    
    # =============================================================================
    # CONFIGURATION
    # =============================================================================
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from environment


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    Uses lru_cache to avoid re-reading environment variables on every call
    """
    return Settings()


# Global settings instance
settings = get_settings()


def reload_settings() -> Settings:
    """
    Reload settings (useful for testing or configuration changes)
    """
    get_settings.cache_clear()
    return get_settings()


# Environment-specific settings
class DevelopmentSettings(Settings):
    """Development-specific settings"""
    debug: bool = True
    log_level: str = "DEBUG"
    enable_api_docs: bool = True
    log_database_queries: bool = True


class ProductionSettings(Settings):
    """Production-specific settings"""
    debug: bool = False
    log_level: str = "WARNING"
    enable_api_docs: bool = False
    enable_debug_toolbar: bool = False
    log_database_queries: bool = False


class TestingSettings(Settings):
    """Testing-specific settings"""
    environment: str = "testing"
    debug: bool = True
    log_level: str = "DEBUG"
    enable_test_data: bool = True
    
    class Config:
        env_file = ".env.test"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


def get_environment_settings() -> Settings:
    """Get environment-specific settings"""
    env = os.getenv("ENVIRONMENT", "development").lower()

    if env == "production":
        return ProductionSettings()
    elif env == "testing":
        return TestingSettings()
    else:
        return DevelopmentSettings()
