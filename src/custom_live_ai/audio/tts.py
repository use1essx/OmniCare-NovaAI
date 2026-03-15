"""
Text-to-Speech Module using Microsoft Edge TTS
Handles speech synthesis for English and Cantonese (Hong Kong)
"""

from typing import Optional, List
from dataclasses import dataclass
import logging

# Make edge_tts optional for development/testing
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    logging.warning("edge_tts not available - TTS functionality will be disabled")

logger = logging.getLogger(__name__)


@dataclass
class Voice:
    """Voice configuration for TTS"""
    name: str
    language: str
    gender: str
    locale: str


class TextToSpeech:
    """
    Edge TTS-based speech synthesis engine
    Free, high quality, supports Cantonese (HK dialect)
    """
    
    # Default voices for each language
    DEFAULT_VOICES = {
        "en": "en-US-AriaNeural",      # English (US) - Female, friendly
        "en-male": "en-US-GuyNeural",  # English (US) - Male
        "zh": "zh-HK-HiuMaanNeural",   # Cantonese (HK) - Female
        "zh-male": "zh-HK-WanLungNeural"  # Cantonese (HK) - Male
    }
    
    def __init__(
        self,
        default_language: str = "en",
        default_gender: str = "female",
        rate: str = "+0%",
        pitch: str = "+0Hz",
        volume: str = "+0%"
    ):
        """
        Initialize Edge TTS engine
        
        Args:
            default_language: Default language ('en' or 'zh')
            default_gender: Default gender ('female' or 'male')
            rate: Speech rate (-50% to +100%)
            pitch: Pitch adjustment (-50Hz to +50Hz)
            volume: Volume adjustment (-50% to +50%)
        """
        self.default_language = default_language
        self.default_gender = default_gender
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        
        # Select default voice
        voice_key = default_language
        if default_gender == "male":
            voice_key += "-male"
        
        self.default_voice = self.DEFAULT_VOICES.get(
            voice_key,
            self.DEFAULT_VOICES["en"]
        )
        
        logger.info(
            f"Initialized TTS with voice: {self.default_voice} "
            f"(rate: {rate}, pitch: {pitch})"
        )
    
    async def synthesize(
        self,
        text: str,
        language: Optional[str] = None,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None
    ) -> bytes:
        """
        Convert text to speech audio
        
        Args:
            text: Text to synthesize
            language: Language override ('en' or 'zh')
            voice: Voice name override
            rate: Speech rate override
            pitch: Pitch override
            
        Returns:
            Audio bytes in MP3 format
        """
        if not EDGE_TTS_AVAILABLE:
            logger.warning("TTS synthesis skipped - edge_tts not available")
            return b""  # Return empty bytes
        
        try:
            # Select voice
            if voice is None:
                if language:
                    voice_key = language
                    if self.default_gender == "male":
                        voice_key += "-male"
                    voice = self.DEFAULT_VOICES.get(voice_key, self.default_voice)
                else:
                    voice = self.default_voice
            
            # Use provided or default rate/pitch
            speech_rate = rate if rate is not None else self.rate
            speech_pitch = pitch if pitch is not None else self.pitch
            
            logger.debug(
                f"Synthesizing with voice: {voice}, "
                f"rate: {speech_rate}, pitch: {speech_pitch}"
            )
            
            # Create communicate object
            communicate = edge_tts.Communicate(
                text,
                voice=voice,
                rate=speech_rate,
                pitch=speech_pitch,
                volume=self.volume
            )
            
            # Generate audio
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            
            if not audio_chunks:
                raise RuntimeError("No audio generated")
            
            audio_data = b"".join(audio_chunks)
            
            logger.info(
                f"Synthesized {len(text)} characters → "
                f"{len(audio_data)} bytes audio"
            )
            
            return audio_data
            
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            raise RuntimeError(f"Failed to synthesize speech: {e}")
    
    async def synthesize_bilingual(
        self,
        text: str,
        primary_language: str = "en"
    ) -> bytes:
        """
        Synthesize text with automatic language detection for code-switching
        
        Args:
            text: Text that may contain mixed languages
            primary_language: Primary language to use
            
        Returns:
            Audio bytes
        """
        try:
            # Simple heuristic: if text contains Chinese characters, use Cantonese
            has_chinese = any('\u4e00' <= char <= '\u9fff' for char in text)
            
            if has_chinese:
                # Use Cantonese voice
                language = "zh"
            else:
                # Use English voice
                language = "en"
            
            logger.debug(f"Detected language: {language} for text: {text[:50]}...")
            
            return await self.synthesize(text, language=language)
            
        except Exception as e:
            logger.error(f"Bilingual synthesis failed: {e}")
            raise
    
    async def synthesize_with_emotion(
        self,
        text: str,
        emotion: str = "neutral",
        language: Optional[str] = None
    ) -> bytes:
        """
        Synthesize speech with emotional expression
        
        Args:
            text: Text to synthesize
            emotion: Emotion to express (neutral, happy, sad, excited, calm)
            language: Language override
            
        Returns:
            Audio bytes
        """
        # Adjust rate and pitch based on emotion
        emotion_settings = {
            "neutral": {"rate": "+0%", "pitch": "+0Hz"},
            "happy": {"rate": "+10%", "pitch": "+5Hz"},
            "sad": {"rate": "-10%", "pitch": "-5Hz"},
            "excited": {"rate": "+20%", "pitch": "+10Hz"},
            "calm": {"rate": "-5%", "pitch": "-3Hz"},
            "concerned": {"rate": "-5%", "pitch": "+0Hz"}
        }
        
        settings = emotion_settings.get(emotion, emotion_settings["neutral"])
        
        logger.debug(f"Synthesizing with emotion: {emotion}")
        
        return await self.synthesize(
            text,
            language=language,
            rate=settings["rate"],
            pitch=settings["pitch"]
        )
    
    async def list_available_voices(
        self,
        language_filter: Optional[str] = None
    ) -> List[Voice]:
        """
        Get list of available voices
        
        Args:
            language_filter: Filter by language (e.g., 'en', 'zh')
            
        Returns:
            List of Voice objects
        """
        if not EDGE_TTS_AVAILABLE:
            logger.warning("Voice listing skipped - edge_tts not available")
            return []
        
        try:
            voices_list = await edge_tts.list_voices()
            
            result = []
            for v in voices_list:
                # Filter by language if specified
                locale = v.get("Locale", "")
                if language_filter:
                    if language_filter == "en" and not locale.startswith("en-"):
                        continue
                    elif language_filter == "zh" and not locale.startswith("zh-"):
                        continue
                
                # Only include Hong Kong Cantonese and English variants
                if locale.startswith("en-") or locale.startswith("zh-HK"):
                    result.append(Voice(
                        name=v["Name"],
                        language=locale.split("-")[0],
                        gender=v.get("Gender", "Unknown"),
                        locale=locale
                    ))
            
            logger.info(f"Found {len(result)} available voices")
            return result
            
        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            raise
    
    def adjust_speaking_rate(self, rate_adjustment: str):
        """
        Adjust default speaking rate
        
        Args:
            rate_adjustment: Rate adjustment (-50% to +100%)
        """
        self.rate = rate_adjustment
        logger.info(f"Speech rate adjusted to: {rate_adjustment}")
    
    def adjust_pitch(self, pitch_adjustment: str):
        """
        Adjust default pitch
        
        Args:
            pitch_adjustment: Pitch adjustment (-50Hz to +50Hz)
        """
        self.pitch = pitch_adjustment
        logger.info(f"Pitch adjusted to: {pitch_adjustment}")
    
    def set_voice(self, voice_name: str):
        """
        Set default voice
        
        Args:
            voice_name: Full voice name (e.g., "en-US-AriaNeural")
        """
        self.default_voice = voice_name
        logger.info(f"Default voice set to: {voice_name}")
    
    def get_config(self) -> dict:
        """
        Get current TTS configuration
        
        Returns:
            Dictionary with configuration
        """
        return {
            "default_voice": self.default_voice,
            "default_language": self.default_language,
            "default_gender": self.default_gender,
            "rate": self.rate,
            "pitch": self.pitch,
            "volume": self.volume
        }


class ChildFriendlyTTS(TextToSpeech):
    """
    Child-friendly TTS with optimized settings for children
    Slower speech rate, clearer pronunciation
    """
    
    def __init__(self, language: str = "en"):
        """
        Initialize child-friendly TTS
        
        Args:
            language: Primary language ('en' or 'zh')
        """
        # Slower rate, slightly higher pitch for child-friendly voice
        super().__init__(
            default_language=language,
            default_gender="female",
            rate="-5%",  # Slightly slower
            pitch="+2Hz",  # Slightly higher (friendlier)
            volume="+0%"
        )
        
        logger.info("Initialized child-friendly TTS")
    
    async def synthesize_encouragement(self, message: str = "Great job!") -> bytes:
        """
        Synthesize encouraging message with happy emotion
        
        Args:
            message: Encouragement message
            
        Returns:
            Audio bytes
        """
        return await self.synthesize_with_emotion(message, emotion="happy")
    
    async def synthesize_comfort(self, message: str = "It's okay, take your time.") -> bytes:
        """
        Synthesize comforting message with calm emotion
        
        Args:
            message: Comfort message
            
        Returns:
            Audio bytes
        """
        return await self.synthesize_with_emotion(message, emotion="calm")


# Convenience functions for quick usage

async def text_to_speech_en(text: str) -> bytes:
    """Quick English TTS"""
    tts = TextToSpeech(default_language="en")
    return await tts.synthesize(text)


async def text_to_speech_zh(text: str) -> bytes:
    """Quick Cantonese TTS"""
    tts = TextToSpeech(default_language="zh")
    return await tts.synthesize(text)


async def text_to_speech_auto(text: str) -> bytes:
    """Auto-detect language and synthesize"""
    tts = TextToSpeech()
    return await tts.synthesize_bilingual(text)


