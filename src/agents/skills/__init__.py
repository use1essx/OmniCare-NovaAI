"""
Skills Module for Unified Agent

Each skill represents a specialized capability that can be dynamically
activated based on conversation context, keywords, and multimodal signals.

Features:
- AI-powered intelligent routing (understands context, not just keywords)
- Keyword-based fallback detection
- Multimodal signal integration
- Crisis detection with highest priority
"""

from .base_skill import SkillConfig, SkillContext
from .skill_activator import SkillActivator, get_skill_activator
from .intelligent_router import IntelligentSkillRouter, get_intelligent_router

# Skill module imports
from .mental_health import MENTAL_HEALTH_SKILL
from .physical_health import PHYSICAL_HEALTH_SKILL
from .safety_crisis import SAFETY_CRISIS_SKILL
from .wellness_coaching import WELLNESS_COACHING_SKILL
from .sleep_support import SLEEP_SUPPORT_SKILL
from .social_support import SOCIAL_SUPPORT_SKILL
from .motor_screening import MOTOR_SCREENING_SKILL

# All available skills
ALL_SKILLS = {
    'mental_health': MENTAL_HEALTH_SKILL,
    'physical_health': PHYSICAL_HEALTH_SKILL,
    'safety_crisis': SAFETY_CRISIS_SKILL,
    'wellness_coaching': WELLNESS_COACHING_SKILL,
    'sleep_support': SLEEP_SUPPORT_SKILL,
    'social_support': SOCIAL_SUPPORT_SKILL,
    'motor_screening': MOTOR_SCREENING_SKILL,
}

__all__ = [
    'SkillConfig',
    'SkillContext',
    'SkillActivator',
    'get_skill_activator',
    'IntelligentSkillRouter',
    'get_intelligent_router',
    'ALL_SKILLS',
    'MENTAL_HEALTH_SKILL',
    'PHYSICAL_HEALTH_SKILL',
    'SAFETY_CRISIS_SKILL',
    'WELLNESS_COACHING_SKILL',
    'SLEEP_SUPPORT_SKILL',
    'SOCIAL_SUPPORT_SKILL',
    'MOTOR_SCREENING_SKILL',
]
