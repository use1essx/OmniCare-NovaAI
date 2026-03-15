"""
Speech-to-Text Module using Whisper
Handles voice recognition for English and Cantonese
"""

import whisper
import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    """Result of speech-to-text transcription"""
    text: str
    language: str
    confidence: float
    duration: float  # Duration of audio in seconds
    
    def is_confident(self, threshold: float = 0.7) -> bool:
        """Check if transcription confidence is above threshold"""
        return self.confidence >= threshold


class SpeechToText:
    """
    Whisper-based speech recognition engine
    Supports English and Cantonese (Hong Kong)
    """
    
    # Model sizes: tiny, base, small, medium, large
    SUPPORTED_MODELS = ["tiny", "base", "small", "medium", "large"]
    
    def __init__(
        self,
        model_size: str = "base",
        language: Optional[str] = None,
        device: str = "cpu"
    ):
        """
        Initialize Whisper STT engine
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
            language: Target language ('en', 'zh', or None for auto-detect)
            device: Device to run on ('cpu' or 'cuda')
        """
        if model_size not in self.SUPPORTED_MODELS:
            raise ValueError(
                f"Unsupported model size: {model_size}. "
                f"Choose from: {self.SUPPORTED_MODELS}"
            )
        
        self.model_size = model_size
        self.language = language
        self.device = device
        
        logger.info(f"Loading Whisper model: {model_size} on {device}")
        self.model = whisper.load_model(model_size, device=device)
        logger.info("Whisper model loaded successfully")
    
    async def transcribe(
        self,
        audio_data: np.ndarray,
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Numpy array of audio samples (16kHz, mono, float32)
            language: Override language ('en', 'zh', or None)
            
        Returns:
            TranscriptionResult with text, language, and confidence
        """
        try:
            # Use instance language if not provided
            target_language = language or self.language
            
            # Transcribe
            result = self.model.transcribe(
                audio_data,
                language=target_language,
                task="transcribe",  # or "translate" for non-English
                fp16=False if self.device == "cpu" else True
            )
            
            # Extract results
            text = result["text"].strip()
            detected_language = result["language"]
            
            # Calculate confidence (Whisper doesn't provide direct confidence,
            # so we estimate from segment probabilities)
            segments = result.get("segments", [])
            if segments:
                avg_log_prob = sum(s.get("avg_logprob", 0) for s in segments) / len(segments)
                # Convert log probability to confidence (0.0-1.0)
                confidence = min(1.0, max(0.0, np.exp(avg_log_prob)))
            else:
                confidence = 0.5  # Default if no segments
            
            # Calculate duration
            duration = len(audio_data) / 16000.0  # 16kHz sample rate
            
            logger.info(
                f"Transcribed: '{text[:50]}...' "
                f"({detected_language}, confidence: {confidence:.2f})"
            )
            
            return TranscriptionResult(
                text=text,
                language=detected_language,
                confidence=confidence,
                duration=duration
            )
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise RuntimeError(f"Failed to transcribe audio: {e}")
    
    async def detect_language(self, audio_data: np.ndarray) -> Tuple[str, float]:
        """
        Detect language of audio
        
        Args:
            audio_data: Numpy array of audio samples
            
        Returns:
            Tuple of (language_code, confidence)
        """
        try:
            # Use Whisper's language detection
            # Process first 30 seconds (Whisper requirement)
            audio_sample = audio_data[:30 * 16000]
            
            # Detect language
            audio_sample = whisper.pad_or_trim(audio_sample)
            mel = whisper.log_mel_spectrogram(audio_sample).to(self.model.device)
            _, probs = self.model.detect_language(mel)
            
            # Get top language
            detected_language = max(probs, key=probs.get)
            confidence = probs[detected_language]
            
            logger.info(
                f"Detected language: {detected_language} "
                f"(confidence: {confidence:.2f})"
            )
            
            return detected_language, confidence
            
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            raise RuntimeError(f"Failed to detect language: {e}")
    
    async def is_silence(
        self,
        audio_data: np.ndarray,
        threshold: float = 0.02
    ) -> bool:
        """
        Check if audio is mostly silence (Voice Activity Detection)
        
        Args:
            audio_data: Numpy array of audio samples
            threshold: RMS threshold below which is considered silence
            
        Returns:
            True if audio is mostly silent
        """
        try:
            # Calculate RMS (Root Mean Square) of audio
            rms = np.sqrt(np.mean(audio_data**2))
            
            is_silent = rms < threshold
            
            if is_silent:
                logger.debug(f"Silence detected (RMS: {rms:.4f})")
            
            return is_silent
            
        except Exception as e:
            logger.error(f"Silence detection failed: {e}")
            return False
    
    async def transcribe_with_retry(
        self,
        audio_data: np.ndarray,
        max_retries: int = 2,
        min_confidence: float = 0.5
    ) -> Optional[TranscriptionResult]:
        """
        Transcribe with retry logic for low confidence
        
        Args:
            audio_data: Audio data to transcribe
            max_retries: Maximum retry attempts
            min_confidence: Minimum acceptable confidence
            
        Returns:
            TranscriptionResult or None if failed
        """
        for attempt in range(max_retries + 1):
            try:
                result = await self.transcribe(audio_data)
                
                if result.is_confident(min_confidence):
                    return result
                else:
                    logger.warning(
                        f"Low confidence transcription (attempt {attempt + 1}): "
                        f"{result.confidence:.2f}"
                    )
                    
                    if attempt < max_retries:
                        # Could apply audio enhancement here before retry
                        continue
                    else:
                        # Return low confidence result on final attempt
                        return result
                        
            except Exception as e:
                logger.error(f"Transcription attempt {attempt + 1} failed: {e}")
                if attempt == max_retries:
                    return None
                continue
        
        return None
    
    def get_model_info(self) -> dict:
        """
        Get information about loaded model
        
        Returns:
            Dictionary with model information
        """
        return {
            "model_size": self.model_size,
            "device": self.device,
            "language": self.language or "auto-detect",
            "supported_languages": ["en", "zh", "auto"]
        }


class CantoneseSpeechToText(SpeechToText):
    """
    Specialized STT for Hong Kong Cantonese
    Optimized settings for HK accent and code-switching
    """
    
    def __init__(self, model_size: str = "base", device: str = "cpu"):
        """
        Initialize Cantonese-optimized STT
        
        Args:
            model_size: Whisper model size (recommend 'base' or 'small' for Cantonese)
            device: Device to run on
        """
        # Initialize with Chinese language
        super().__init__(
            model_size=model_size,
            language="zh",  # Chinese (includes Cantonese)
            device=device
        )
        
        logger.info("Initialized Cantonese STT (HK dialect)")
    
    async def transcribe(
        self,
        audio_data: np.ndarray,
        allow_code_switching: bool = True
    ) -> TranscriptionResult:
        """
        Transcribe Cantonese audio with code-switching support
        
        Args:
            audio_data: Audio data
            allow_code_switching: Allow English-Cantonese mixing
            
        Returns:
            TranscriptionResult
        """
        # If code-switching allowed, use auto language detection
        language = None if allow_code_switching else "zh"
        
        result = await super().transcribe(audio_data, language=language)
        
        # Post-process for HK-specific patterns if needed
        # (e.g., common HK slang, place names, etc.)
        
        return result


