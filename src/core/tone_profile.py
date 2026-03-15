"""
Tone Profile Manager for Healthcare AI

Provides age-aware and profile-aware tone settings for LLM responses.
Maps user profiles to appropriate tone, style, and formatting guidance.
"""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING, Union, Dict, Any

if TYPE_CHECKING:
    from src.models.user_profile import UserProfile


@dataclass
class ToneProfile:
    """
    Tone and style settings for LLM responses.
    
    Used by PromptComposer to add appropriate guidance to system prompts
    based on user age group and preferences.
    """
    age_group: Optional[str] = None  # "child" | "teen" | "adult" | "elder" | None
    max_sentences: int = 8
    max_bullets: int = 5
    emoji_level: str = "low"          # "none" | "low" | "medium" | "high"
    formality: str = "neutral"        # "casual" | "neutral" | "formal"
    explanation_depth: str = "normal"  # "light" | "normal" | "deep"


class ToneProfileManager:
    """
    Creates ToneProfile from UserProfile or user_profile dict.
    
    Maps user characteristics (age, preferences) to appropriate
    tone settings for LLM responses.
    """
    
    @staticmethod
    def from_user_profile(
        user_profile: Optional[Union["UserProfile", Dict[str, Any]]]
    ) -> ToneProfile:
        """
        Create ToneProfile from a UserProfile or user_profile dict.
        
        Args:
            user_profile: UserProfile object, dict with profile keys, or None
            
        Returns:
            ToneProfile with appropriate settings for the user
        """
        if user_profile is None:
            return ToneProfile()
        
        # Handle both UserProfile objects and dicts
        if hasattr(user_profile, 'age_group'):
            # It's a UserProfile object
            age_group = user_profile.age_group
            age = getattr(user_profile, 'age', None)
        elif isinstance(user_profile, dict):
            # It's a dict
            age_group = user_profile.get('age_group')
            age = user_profile.get('age')
        else:
            return ToneProfile()
        
        # Derive age_group from age if not explicitly set
        if not age_group and age is not None:
            from src.models.user_profile import derive_age_group
            age_group = derive_age_group(age)
        
        # Map age_group to tone settings
        if age_group == "child":
            return ToneProfile(
                age_group=age_group,
                max_sentences=3,  # Reduced from 4 - keep it short and fun
                max_bullets=2,
                emoji_level="high",
                formality="casual",
                explanation_depth="light",
            )
        elif age_group == "teen":
            return ToneProfile(
                age_group=age_group,
                max_sentences=4,  # Reduced from 6 - teens prefer brief
                max_bullets=3,
                emoji_level="medium",
                formality="casual",
                explanation_depth="normal",
            )
        elif age_group == "adult":
            return ToneProfile(
                age_group=age_group,
                max_sentences=5,  # Reduced from 10 - conversational, not essays
                max_bullets=4,
                emoji_level="low",
                formality="neutral",
                explanation_depth="normal",  # Changed from deep - spread across exchanges
            )
        elif age_group == "elder":
            return ToneProfile(
                age_group=age_group,
                max_sentences=5,  # Reduced from 8 - clear and concise
                max_bullets=3,
                emoji_level="low",
                formality="neutral",
                explanation_depth="normal",
            )
        
        # Default for unknown or None age_group
        return ToneProfile(age_group=age_group)
