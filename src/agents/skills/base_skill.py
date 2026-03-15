"""
Base Skill Configuration

Defines the structure for skill configurations that can be
dynamically loaded by the unified agent.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class SkillConfig:
    """
    Configuration for a skill module.
    
    Each skill defines:
    - Keywords for activation
    - Prompt additions for the AI
    - Available functions
    - Priority for conflict resolution
    """
    
    # Identification
    name: str
    display_name: str
    description: str
    
    # Activation
    keywords_en: List[str] = field(default_factory=list)
    keywords_zh: List[str] = field(default_factory=list)
    crisis_keywords: List[str] = field(default_factory=list)
    
    # Priority (higher = more important, safety_crisis is always highest)
    priority: int = 50
    
    # Prompt augmentation
    system_prompt_addition: str = ""
    response_guidelines: str = ""
    
    # Available functions when this skill is active
    available_functions: List[str] = field(default_factory=list)
    
    # RAG categories to search
    knowledge_categories: List[str] = field(default_factory=list)
    
    # Emotion mapping hints (for Live2D)
    emotion_hints: Dict[str, str] = field(default_factory=dict)
    
    # Whether skill requires safety validation on output
    requires_safety_check: bool = True
    
    def get_all_keywords(self) -> Set[str]:
        """Get all keywords (EN + ZH)"""
        return set(self.keywords_en + self.keywords_zh)
    
    def matches_keyword(self, text: str) -> bool:
        """Check if text contains any skill keywords"""
        text_lower = text.lower()
        for kw in self.keywords_en:
            if kw.lower() in text_lower:
                return True
        for kw in self.keywords_zh:
            if kw in text:
                return True
        return False
    
    def has_crisis_keyword(self, text: str) -> bool:
        """Check if text contains crisis keywords"""
        text_lower = text.lower()
        for kw in self.crisis_keywords:
            if kw.lower() in text_lower or kw in text:
                return True
        return False


@dataclass
class SkillContext:
    """
    Runtime context for a skill during conversation.
    
    Tracks skill-specific state during a conversation turn.
    """
    
    skill_name: str
    activation_reason: str  # Why this skill was activated
    confidence: float = 1.0
    
    # Multimodal signals that contributed
    emotion_signal: Optional[str] = None
    movement_signal: Optional[str] = None
    
    # Retrieved knowledge
    knowledge_retrieved: List[Dict] = field(default_factory=list)
    citations: List[Dict] = field(default_factory=list)
    
    # Functions called
    functions_called: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'skill_name': self.skill_name,
            'activation_reason': self.activation_reason,
            'confidence': self.confidence,
            'emotion_signal': self.emotion_signal,
            'movement_signal': self.movement_signal,
            'knowledge_count': len(self.knowledge_retrieved),
            'functions_called': self.functions_called
        }

