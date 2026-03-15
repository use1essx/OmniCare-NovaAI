"""
Conversation Models - Healthcare AI V2
=====================================

Data models for conversation management and context tracking.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ConversationState(Enum):
    """Conversation state tracking."""
    NEW_SESSION = "new_session"
    ACTIVE = "active"
    ESCALATED = "escalated"
    CONCLUDED = "concluded"
    EMERGENCY = "emergency"


class LanguagePreference(Enum):
    """Language preference options."""
    AUTO = "auto"  # Bilingual
    ENGLISH = "en"
    TRADITIONAL_CHINESE = "zh"


@dataclass
class HealthPattern:
    """Health pattern detected in conversation."""
    pattern_type: str  # "symptom", "medication", "concern", "improvement"
    description: str
    first_mentioned: datetime
    last_mentioned: datetime
    frequency: int = 1
    severity_trend: str = "unknown"  # "improving", "stable", "worsening", "unknown"
    agent_context: str = ""  # Which agent detected/tracked this


@dataclass
class UserProfile:
    """User profile and preferences."""
    user_id: str
    language_preference: LanguagePreference = LanguagePreference.AUTO
    age_group: Optional[str] = None  # "child", "teen", "adult", "elderly"
    location: str = "hong_kong"
    cultural_context: Dict[str, Any] = field(default_factory=dict)
    health_conditions: List[str] = field(default_factory=list)
    medications: List[str] = field(default_factory=list)
    allergies: List[str] = field(default_factory=list)
    emergency_contacts: List[Dict[str, str]] = field(default_factory=list)
    preferred_agents: List[str] = field(default_factory=list)
    communication_style: str = "formal"  # "formal", "casual", "medical"
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ConversationMemory:
    """Memory structure for conversation context."""
    session_id: str
    user_id: str
    
    # Session metadata
    session_start: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    conversation_state: ConversationState = ConversationState.NEW_SESSION
    
    # Agent management
    active_agent: Optional[str] = None
    agent_history: List[str] = field(default_factory=list)
    agent_handoffs: List[Dict[str, Any]] = field(default_factory=list)
    
    # Conversation content
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    health_topics_discussed: List[str] = field(default_factory=list)
    health_patterns: Dict[str, HealthPattern] = field(default_factory=dict)
    concerns_raised: List[str] = field(default_factory=list)
    
    # Progress tracking
    goals_set: List[str] = field(default_factory=list)
    progress_notes: List[str] = field(default_factory=list)
    follow_up_needed: List[str] = field(default_factory=list)
    
    # Professional alerts
    alerts_generated: List[Dict[str, Any]] = field(default_factory=list)
    escalation_history: List[Dict[str, Any]] = field(default_factory=list)
