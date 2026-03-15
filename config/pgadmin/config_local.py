# Healthcare AI V2 - pgAdmin Configuration
# Custom configuration for Healthcare AI database administration

import os

# Basic Configuration
THREADS_PER_PAGE = 8
WTF_CSRF_ENABLED = True
WTF_CSRF_TIME_LIMIT = 3600

# Security Configuration
ENHANCED_COOKIE_PROTECTION = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Authentication Configuration
AUTHENTICATION_SOURCES = ['internal']
AUTHENTICATION_LOCKOUT_DURATION = 300  # 5 minutes
MAX_LOGIN_ATTEMPTS = 5
LOGIN_CHECK_ATTEMPTS = 3

# UI Customization
APPLICATION_NAME = "Healthcare AI V2 - Database Administration"
LOGIN_BANNER = "Healthcare AI V2 Database Administration"
SHOW_GRAVATAR_IMAGE = False

# Query Tool Configuration
QUERY_HISTORY_TIMEOUT = 86400  # 24 hours
QUERY_TOOL_AUTO_COMMIT = False
QUERY_TOOL_AUTO_ROLLBACK = True

# Grid Configuration
ON_DEMAND_RECORD_COUNT_THRESHOLD = 1000
DEFAULT_BINARY_PATHS = {
    'pg': os.path.join('/usr', 'bin')
}

# File Manager Configuration
FILE_MANAGER_ENABLED = True
FILE_UPLOAD_MAX_SIZE = 50 * 1024 * 1024  # 50MB

# Custom Healthcare AI Configuration
HEALTHCARE_AI_CONFIG = {
    'enable_patient_data_protection': True,
    'audit_all_queries': True,
    'max_export_rows': 10000,
    'sensitive_tables': [
        'users',
        'conversations', 
        'uploaded_documents',
        'audit_logs'
    ]
}

# Console Log Level (10=DEBUG, 20=INFO, 30=WARNING, 40=ERROR, 50=CRITICAL)
CONSOLE_LOG_LEVEL = 20

# Email Configuration (Optional)
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

# Custom Healthcare AI Extensions
CUSTOM_PLUGINS = [
    'healthcare_ai_dashboard',
    'healthcare_ai_reports',
    'healthcare_ai_backup'
]

# Dashboard Configuration
DASHBOARD_CONFIG = {
    'show_activity': True,
    'show_sessions': True,
    'show_locks': True,
    'show_prepared': True,
    'show_config': True,
    'auto_refresh_interval': 30000  # 30 seconds
}

# Backup Configuration
BACKUP_CONFIG = {
    'backup_path': '/var/lib/pgadmin/storage/backups',
    'retention_days': 30,
    'compress_backups': True,
    'exclude_tables': ['temp_*', 'cache_*']
}

# Performance Monitoring
PERFORMANCE_CONFIG = {
    'enable_query_stats': True,
    'slow_query_threshold': 1000,  # milliseconds
    'log_slow_queries': True
}
