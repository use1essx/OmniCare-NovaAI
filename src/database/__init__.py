"""
Database Package
Provides database connection, models, and repositories
"""

from .connection import get_async_db, get_sync_db, init_database, close_database
from .models_comprehensive import Base, User

__all__ = [
    "get_async_db",
    "get_sync_db",
    "init_database",
    "close_database",
    "Base",
    "User",
]

# Health profile models (teen/kids mental health)
try:
    from .health_profile_models import (  # noqa: F401
        HealthProfile, MoodLog, GrowthRecord, GoalTracking, ConversationContext
    )
    __all__.extend(["HealthProfile", "MoodLog", "GrowthRecord", "GoalTracking", "ConversationContext"])
except ImportError:
    pass  # Health profile models optional

# Session models available for import
try:
    from .models_session import ScreeningSession, SessionQAPair, SessionEvent  # noqa: F401
    __all__.extend(["ScreeningSession", "SessionQAPair", "SessionEvent"])
except ImportError:
    pass  # Session models optional

# Questionnaire models available for import
try:
    from .models_questionnaire import (  # noqa: F401
        QuestionnaireBank, QuestionnaireQuestion, QuestionOption, 
        QuestionAnswer, QuestionnaireResponse, CategoryScore, ScoringRule
    )
    __all__.extend(["QuestionnaireBank", "QuestionnaireQuestion", "QuestionOption", "QuestionAnswer", "QuestionnaireResponse", "CategoryScore", "ScoringRule"])
except ImportError:
    pass  # Questionnaire models optional

