"""
Social Worker Hub Module

Provides comprehensive case management, alert system, 
report generation, and analytics for social workers.
"""

from .models import (
    CaseFile,
    Alert,
    ProfessionalReport,
    Intervention,
    SafetyPlan,
    CaseNote,
)
from .case_manager import CaseManager, get_case_manager
from .alert_manager import AlertManager, get_alert_manager
from .report_generator import ReportGenerator, get_report_generator
from .analytics import AnalyticsService, get_analytics_service

__all__ = [
    # Models
    'CaseFile',
    'Alert',
    'ProfessionalReport',
    'Intervention',
    'SafetyPlan',
    'CaseNote',
    
    # Managers
    'CaseManager',
    'get_case_manager',
    'AlertManager',
    'get_alert_manager',
    
    # Report Generator
    'ReportGenerator',
    'get_report_generator',
    
    # Analytics
    'AnalyticsService',
    'get_analytics_service',
]

