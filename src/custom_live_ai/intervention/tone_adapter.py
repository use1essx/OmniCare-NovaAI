"""
Adaptive Tone System
Determines appropriate tone for TTS based on session duration and user emotion
"""

from dataclasses import dataclass
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToneParameters:
    """
    Parameters for TTS voice generation
    """
    rate: str  # Speech rate (-50% to +100%)
    pitch: str  # Pitch adjustment (-50Hz to +50Hz)
    voice_style: str  # formal, friendly, encouraging, gentle, calm
    volume: str = "+0%"  # Volume adjustment


class ToneAdapter:
    """
    Adapts TTS tone based on context (session duration, user emotion)
    """
    
    # Session duration thresholds (in seconds)
    SHORT_SESSION = 900  # 0-15 minutes: formal
    MEDIUM_SESSION = 1800  # 15-30 minutes: friendly
    # 30+ minutes: encouraging/casual
    
    # Tone profiles for different contexts
    TONE_PROFILES = {
        # Duration-based tones
        "formal": ToneParameters(rate="+0%", pitch="+0Hz", voice_style="formal"),
        "friendly": ToneParameters(rate="+5%", pitch="+2Hz", voice_style="friendly"),
        "encouraging": ToneParameters(rate="+10%", pitch="+3Hz", voice_style="encouraging"),
        
        # Emotion-based tones
        "gentle": ToneParameters(rate="-10%", pitch="-3Hz", voice_style="gentle"),  # For sad
        "calm": ToneParameters(rate="-5%", pitch="-2Hz", voice_style="calm"),  # For angry/stressed
        "upbeat": ToneParameters(rate="+8%", pitch="+4Hz", voice_style="upbeat"),  # For happy
        "reassuring": ToneParameters(rate="-5%", pitch="+0Hz", voice_style="reassuring"),  # For fear
        "supportive": ToneParameters(rate="+0%", pitch="-1Hz", voice_style="supportive"),  # General support
    }
    
    # Emotion to tone mapping
    EMOTION_TONE_MAP = {
        "neutral": "friendly",
        "happy": "upbeat",
        "sad": "gentle",
        "angry": "calm",
        "fear": "reassuring",
        "surprise": "friendly",
        "disgust": "supportive"
    }
    
    def __init__(self):
        """Initialize tone adapter"""
        logger.info("ToneAdapter initialized")
    
    def get_tone_for_duration(self, session_duration_sec: float) -> str:
        """
        Get appropriate tone based on session duration
        
        Args:
            session_duration_sec: Session duration in seconds
            
        Returns:
            Tone style name
        """
        if session_duration_sec < self.SHORT_SESSION:
            return "formal"
        elif session_duration_sec < self.MEDIUM_SESSION:
            return "friendly"
        else:
            return "encouraging"
    
    def get_tone_for_emotion(self, emotion: str) -> str:
        """
        Get appropriate tone based on current emotion
        
        Args:
            emotion: Current dominant emotion
            
        Returns:
            Tone style name
        """
        return self.EMOTION_TONE_MAP.get(emotion.lower(), "friendly")
    
    def get_adaptive_tone(
        self,
        session_duration_sec: float,
        current_emotion: Optional[str] = None,
        intervention_type: Optional[str] = None
    ) -> ToneParameters:
        """
        Get adaptive tone parameters based on multiple factors
        
        Args:
            session_duration_sec: Current session duration in seconds
            current_emotion: Current user emotion (optional)
            intervention_type: Type of intervention being delivered (optional)
            
        Returns:
            ToneParameters for TTS
        """
        # Priority: emotion > intervention type > duration
        
        # 1. If emotion is provided and negative, use emotion-based tone
        if current_emotion:
            emotion_lower = current_emotion.lower()
            if emotion_lower in ["sad", "angry", "fear"]:
                tone_style = self.get_tone_for_emotion(emotion_lower)
                logger.debug(f"Using emotion-based tone: {tone_style} for emotion: {emotion_lower}")
                return self.TONE_PROFILES[tone_style]
        
        # 2. Special tones for specific intervention types
        if intervention_type:
            if intervention_type == "emotion_support":
                logger.debug("Using supportive tone for emotion support")
                return self.TONE_PROFILES["supportive"]
            elif intervention_type == "break_suggestion":
                logger.debug("Using gentle tone for break suggestion")
                return self.TONE_PROFILES["gentle"]
        
        # 3. Default to duration-based tone
        duration_tone = self.get_tone_for_duration(session_duration_sec)
        logger.debug(f"Using duration-based tone: {duration_tone} for duration: {session_duration_sec}s")
        return self.TONE_PROFILES[duration_tone]
    
    def get_tone_parameters_dict(self, tone_params: ToneParameters) -> Dict[str, str]:
        """
        Convert ToneParameters to dictionary for TTS
        
        Args:
            tone_params: ToneParameters object
            
        Returns:
            Dictionary with rate, pitch, volume for TTS
        """
        return {
            "rate": tone_params.rate,
            "pitch": tone_params.pitch,
            "volume": tone_params.volume
        }
    
    def get_voice_style_description(self, tone_params: ToneParameters) -> str:
        """
        Get human-readable description of voice style
        
        Args:
            tone_params: ToneParameters object
            
        Returns:
            Description string
        """
        return f"{tone_params.voice_style.capitalize()} tone (rate: {tone_params.rate}, pitch: {tone_params.pitch})"




