"""
Intervention Responder
Delivers interventions via voice (TTS), visual notifications, and Live2D sync

Uses Edge TTS service for Hong Kong Cantonese and English speech synthesis.
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timezone

from ..audio.edge_tts_service import get_tts_service
from .tone_adapter import ToneAdapter, ToneParameters

logger = logging.getLogger(__name__)


class InterventionResponder:
    """
    Handles delivery of interventions through multiple channels
    Uses Edge TTS for speech synthesis.
    """
    
    # Map language codes
    LANGUAGE_MAP = {
        "en": "en",
        "zh": "yue",
        "yue": "yue",
        "cantonese": "yue"
    }
    
    def __init__(self, language: str = "en"):
        """
        Initialize intervention responder
        
        Args:
            language: Default language for TTS ('en' or 'yue')
        """
        self.tts_service = get_tts_service()
        self.tone_adapter = ToneAdapter()
        self.language = self.LANGUAGE_MAP.get(language, language)
        logger.info(f"✅ InterventionResponder initialized (language: {self.language}, TTS: Edge TTS)")
    
    async def deliver_voice_reminder(
        self,
        message: str,
        tone_params: ToneParameters,
        language: Optional[str] = None
    ) -> bytes:
        """
        Generate voice reminder using Edge TTS
        
        Args:
            message: Message text to synthesize
            tone_params: ToneParameters (not used, kept for compatibility)
            language: Language override (optional)
            
        Returns:
            Audio bytes (MP3 format)
        """
        try:
            target_language = self.LANGUAGE_MAP.get(
                language or self.language,
                language or self.language
            )
            
            logger.info(f"🔊 Generating voice reminder: '{message[:50]}...'")
            
            # Generate audio with Edge TTS
            result = await self.tts_service.synthesize(
                text=message,
                language=target_language
            )
            
            if not result.success:
                raise RuntimeError(f"TTS synthesis failed: {result.error_message}")
            
            audio_bytes = result.audio_data or b""
            logger.debug(f"Generated {len(audio_bytes)} bytes of audio")
            return audio_bytes
            
        except Exception as e:
            logger.error(f"Failed to generate voice reminder: {e}")
            raise
    
    async def deliver_intervention(
        self,
        intervention_type: str,
        message: str,
        session_duration_sec: float,
        current_emotion: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict:
        """
        Deliver complete intervention (voice + metadata for visual/Live2D)
        
        Args:
            intervention_type: Type of intervention
            message: Message text
            session_duration_sec: Current session duration
            current_emotion: Current user emotion (optional)
            language: Language override (optional)
            
        Returns:
            Dictionary with audio_bytes and metadata
        """
        try:
            # Get adaptive tone
            tone_params = self.tone_adapter.get_adaptive_tone(
                session_duration_sec=session_duration_sec,
                current_emotion=current_emotion,
                intervention_type=intervention_type
            )
            
            # Generate voice
            audio_bytes = await self.deliver_voice_reminder(message, tone_params, language)
            
            # Prepare response
            response = {
                "audio_bytes": audio_bytes,
                "audio_size_bytes": len(audio_bytes),
                "message": message,
                "intervention_type": intervention_type,
                "tone_used": tone_params.voice_style,
                "tone_parameters": {
                    "rate": tone_params.rate,
                    "pitch": tone_params.pitch,
                    "voice_style": tone_params.voice_style
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "language": language or self.language
            }
            
            logger.info(f"✅ Intervention delivered: {intervention_type} with {tone_params.voice_style} tone")
            return response
            
        except Exception as e:
            logger.error(f"Failed to deliver intervention: {e}")
            raise
    
    def get_visual_notification_data(
        self,
        intervention_type: str,
        message: str,
        tone_used: str
    ) -> Dict:
        """
        Prepare data for visual notification (frontend display)
        
        Args:
            intervention_type: Type of intervention
            message: Message text
            tone_used: Tone style used
            
        Returns:
            Dictionary with visual notification data
        """
        # Map intervention types to visual styles
        visual_styles = {
            "posture_reminder": {
                "icon": "🧘",
                "color": "#3b82f6",  # Blue
                "priority": "medium"
            },
            "posture_coaching": {
                "icon": "💪",
                "color": "#10b981",  # Green
                "priority": "high"
            },
            "emotion_support": {
                "icon": "💙",
                "color": "#8b5cf6",  # Purple
                "priority": "high"
            },
            "break_suggestion": {
                "icon": "☕",
                "color": "#f59e0b",  # Amber
                "priority": "medium"
            },
            "engagement_reminder": {
                "icon": "👀",
                "color": "#ef4444",  # Red
                "priority": "low"
            }
        }
        
        style = visual_styles.get(intervention_type, {
            "icon": "ℹ️",
            "color": "#6b7280",
            "priority": "low"
        })
        
        return {
            "message": message,
            "type": intervention_type,
            "tone": tone_used,
            "icon": style["icon"],
            "color": style["color"],
            "priority": style["priority"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_live2d_emotion_mapping(self, user_emotion: str) -> str:
        """
        Map user emotion to Live2D character expression
        
        Args:
            user_emotion: Current user emotion
            
        Returns:
            Live2D expression name
        """
        # Map to Live2D expressions
        emotion_mapping = {
            "happy": "smile",
            "sad": "sad",
            "angry": "angry",
            "neutral": "normal",
            "surprise": "surprised",
            "fear": "worried",
            "disgust": "disgusted"
        }
        
        return emotion_mapping.get(user_emotion.lower(), "normal")
    
    def get_intervention_live2d_response(
        self,
        intervention_type: str,
        user_emotion: str
    ) -> Dict:
        """
        Get Live2D character response for intervention
        
        Args:
            intervention_type: Type of intervention
            user_emotion: Current user emotion
            
        Returns:
            Dictionary with Live2D animation data
        """
        # Map intervention types to Live2D expressions and gestures
        intervention_responses = {
            "posture_reminder": {
                "expression": "concerned",
                "gesture": "point",
                "intensity": 0.7
            },
            "posture_coaching": {
                "expression": "smile",
                "gesture": "encourage",
                "intensity": 0.9
            },
            "emotion_support": {
                "expression": "caring",
                "gesture": "comfort",
                "intensity": 0.8
            },
            "break_suggestion": {
                "expression": "smile",
                "gesture": "suggest",
                "intensity": 0.6
            },
            "engagement_reminder": {
                "expression": "curious",
                "gesture": "call",
                "intensity": 0.5
            }
        }
        
        response = intervention_responses.get(intervention_type, {
            "expression": "normal",
            "gesture": "idle",
            "intensity": 0.5
        })
        
        # Also include user emotion mapping
        response["user_emotion"] = user_emotion
        response["mirror_expression"] = self.get_live2d_emotion_mapping(user_emotion)
        
        return response




