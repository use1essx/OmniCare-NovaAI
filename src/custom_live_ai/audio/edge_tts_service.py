"""
Edge TTS Service Client
Handles text-to-speech using Microsoft Edge TTS.

Selected Voices:
- Cantonese: zh-HK-HiuMaanNeural (Female)
- English: en-US-AvaNeural (Female)

Free, real-time, no API key required.
"""

import os
import logging
import tempfile
from typing import Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass

import edge_tts

logger = logging.getLogger(__name__)


@dataclass
class TTSResult:
    """Result from TTS synthesis"""
    success: bool
    audio_data: Optional[bytes] = None
    audio_path: Optional[Path] = None
    audio_length_seconds: float = 0.0
    error_message: Optional[str] = None


class EdgeTTSService:
    """
    Edge TTS Service for Healthcare AI
    
    Selected Voices:
    - Cantonese: zh-HK-HiuMaanNeural (Female)
    - English: en-US-AvaNeural (Female)
    
    Features:
    - Real Hong Kong Cantonese
    - Free, no API key required
    - Real-time synthesis
    """
    
    # Fixed voices - do not change
    CANTONESE_VOICE = "zh-HK-HiuMaanNeural"
    ENGLISH_VOICE = "en-US-AvaNeural"
    
    # Language to voice mapping
    LANGUAGE_VOICE_MAP = {
        "yue": "zh-HK-HiuMaanNeural",
        "zh-HK": "zh-HK-HiuMaanNeural",
        "cantonese": "zh-HK-HiuMaanNeural",
        "zh": "zh-HK-HiuMaanNeural",
        "en": "en-US-AvaNeural",
        "english": "en-US-AvaNeural",
        "en-US": "en-US-AvaNeural",
    }
    
    def __init__(self):
        """Initialize Edge TTS service with fixed voices"""
        logger.info(
            f"EdgeTTSService initialized: "
            f"Cantonese={self.CANTONESE_VOICE}, English={self.ENGLISH_VOICE}"
        )
    
    def _get_voice(self, language: Optional[str], text: str) -> str:
        """Get voice based on language or auto-detect from text"""
        if language:
            return self.LANGUAGE_VOICE_MAP.get(language, self.CANTONESE_VOICE)
        
        # Auto-detect: Chinese characters = Cantonese, else English
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in text)
        return self.CANTONESE_VOICE if has_chinese else self.ENGLISH_VOICE
    
    def _strip_emojis(self, text: str) -> str:
        """Remove emojis from text before TTS synthesis"""
        import re
        # More precise emoji pattern that doesn't affect CJK characters
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U0001F900-\U0001F9FF"  # supplemental symbols
            "\U0001FA00-\U0001FA6F"  # chess symbols
            "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-A
            "\U00002702-\U000027B0"  # dingbats (safe range)
            "\U0001F004"  # mahjong tile
            "\U0001F0CF"  # playing card
            "\U0001F18E"  # AB button
            "\U0001F191-\U0001F19A"  # squared letters
            "\U0001F1E6-\U0001F1FF"  # regional indicators
            "\U0001F201-\U0001F202"  # squared katakana
            "\U0001F21A"  # squared CJK
            "\U0001F22F"  # squared CJK
            "\U0001F232-\U0001F23A"  # squared CJK
            "\U0001F250-\U0001F251"  # circled ideograph
            "\U00002600-\U000026FF"  # misc symbols (sun, cloud, etc)
            "\U00002700-\U000027BF"  # dingbats
            "\U0000FE00-\U0000FE0F"  # variation selectors
            "\U0001F000-\U0001F02F"  # mahjong tiles
            "]+",
            flags=re.UNICODE
        )
        return emoji_pattern.sub('', text).strip()
    
    async def synthesize(
        self,
        text: str,
        language: Optional[str] = None,
        save_to_file: bool = False,
        output_dir: Optional[Path] = None
    ) -> TTSResult:
        """
        Synthesize speech from text
        
        Args:
            text: Text to synthesize
            language: Language code (yue/cantonese for Cantonese, en/english for English)
            save_to_file: Whether to save audio to file
            output_dir: Directory for output file
            
        Returns:
            TTSResult with audio data (MP3 format)
        """
        if not text or not text.strip():
            return TTSResult(success=False, error_message="Text is required")
        
        text = text.strip()
        
        # Strip emojis from text before TTS (emojis can't be spoken)
        text = self._strip_emojis(text)
        
        if not text or not text.strip():
            return TTSResult(success=False, error_message="Text is empty after removing emojis")
        
        voice = self._get_voice(language, text)
        
        logger.info(f"Synthesizing: text='{text[:30]}...' voice={voice}")
        
        try:
            communicate = edge_tts.Communicate(text, voice)
            
            # Collect audio data
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            
            if not audio_chunks:
                return TTSResult(success=False, error_message="No audio generated")
            
            audio_data = b"".join(audio_chunks)
            audio_length = len(audio_data) / 16000  # Estimate
            
            logger.info(f"Synthesis complete: {len(audio_data)} bytes")
            
            result = TTSResult(
                success=True,
                audio_data=audio_data,
                audio_length_seconds=audio_length
            )
            
            if save_to_file:
                if output_dir:
                    output_dir = Path(output_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    audio_path = output_dir / f"tts_{id(audio_data)}.mp3"
                else:
                    fd, temp_path = tempfile.mkstemp(suffix=".mp3")
                    os.close(fd)
                    audio_path = Path(temp_path)
                
                audio_path.write_bytes(audio_data)
                result.audio_path = audio_path
            
            return result
            
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return TTSResult(success=False, error_message=str(e))
    
    async def synthesize_cantonese(self, text: str) -> TTSResult:
        """Synthesize Cantonese speech using HiuMaan voice"""
        return await self.synthesize(text=text, language="yue")
    
    async def synthesize_english(self, text: str) -> TTSResult:
        """Synthesize English speech using Ava voice"""
        return await self.synthesize(text=text, language="en")
    
    def get_voices(self) -> Dict[str, str]:
        """Get the fixed voices used by this service"""
        return {
            "cantonese": self.CANTONESE_VOICE,
            "english": self.ENGLISH_VOICE
        }


# =============================================================================
# Singleton Instance
# =============================================================================
_service_instance: Optional[EdgeTTSService] = None


def get_tts_service() -> EdgeTTSService:
    """Get or create Edge TTS service singleton"""
    global _service_instance
    if _service_instance is None:
        _service_instance = EdgeTTSService()
    return _service_instance


async def synthesize_speech(text: str, language: str = "yue") -> TTSResult:
    """
    Convenience function for quick TTS synthesis
    
    Args:
        text: Text to synthesize
        language: Language code (yue for Cantonese, en for English)
        
    Returns:
        TTSResult
    """
    service = get_tts_service()
    return await service.synthesize(text=text, language=language)
