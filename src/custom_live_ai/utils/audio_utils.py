"""
Audio Utilities Module
Handles audio format conversion, processing, and manipulation
"""

import io
import numpy as np
from pydub import AudioSegment
from typing import Tuple
import wave


class AudioUtils:
    """Utility functions for audio processing"""
    
    @staticmethod
    def convert_to_wav(audio_data: bytes, source_format: str = "webm") -> bytes:
        """
        Convert audio from any format to WAV format
        
        Args:
            audio_data: Audio bytes in source format
            source_format: Source audio format (webm, mp3, ogg, etc.)
            
        Returns:
            Audio bytes in WAV format
        """
        try:
            # Load audio from bytes
            audio = AudioSegment.from_file(
                io.BytesIO(audio_data),
                format=source_format
            )
            
            # Export as WAV
            wav_io = io.BytesIO()
            audio.export(wav_io, format="wav")
            wav_io.seek(0)
            
            return wav_io.read()
        except Exception as e:
            raise ValueError(f"Failed to convert audio to WAV: {e}")
    
    @staticmethod
    def resample_audio(
        audio_data: bytes,
        target_sample_rate: int = 16000,
        source_format: str = "wav"
    ) -> bytes:
        """
        Resample audio to target sample rate (Whisper needs 16kHz)
        
        Args:
            audio_data: Audio bytes
            target_sample_rate: Target sample rate in Hz
            source_format: Source audio format
            
        Returns:
            Resampled audio bytes in WAV format
        """
        try:
            # Load audio
            audio = AudioSegment.from_file(
                io.BytesIO(audio_data),
                format=source_format
            )
            
            # Resample
            audio = audio.set_frame_rate(target_sample_rate)
            
            # Export as WAV
            wav_io = io.BytesIO()
            audio.export(wav_io, format="wav")
            wav_io.seek(0)
            
            return wav_io.read()
        except Exception as e:
            raise ValueError(f"Failed to resample audio: {e}")
    
    @staticmethod
    def convert_to_mono(audio_data: bytes, source_format: str = "wav") -> bytes:
        """
        Convert audio to mono (single channel)
        
        Args:
            audio_data: Audio bytes
            source_format: Source audio format
            
        Returns:
            Mono audio bytes in WAV format
        """
        try:
            # Load audio
            audio = AudioSegment.from_file(
                io.BytesIO(audio_data),
                format=source_format
            )
            
            # Convert to mono
            audio = audio.set_channels(1)
            
            # Export as WAV
            wav_io = io.BytesIO()
            audio.export(wav_io, format="wav")
            wav_io.seek(0)
            
            return wav_io.read()
        except Exception as e:
            raise ValueError(f"Failed to convert to mono: {e}")
    
    @staticmethod
    def normalize_volume(audio_data: bytes, target_dBFS: float = -20.0) -> bytes:
        """
        Normalize audio volume to target level
        
        Args:
            audio_data: Audio bytes
            target_dBFS: Target volume in dBFS (default -20.0)
            
        Returns:
            Normalized audio bytes
        """
        try:
            # Load audio
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format="wav")
            
            # Calculate change needed
            change_in_dBFS = target_dBFS - audio.dBFS
            
            # Apply normalization
            normalized_audio = audio.apply_gain(change_in_dBFS)
            
            # Export
            wav_io = io.BytesIO()
            normalized_audio.export(wav_io, format="wav")
            wav_io.seek(0)
            
            return wav_io.read()
        except Exception as e:
            raise ValueError(f"Failed to normalize volume: {e}")
    
    @staticmethod
    def detect_silence(
        audio_data: bytes,
        silence_threshold: float = 0.02,
        min_silence_duration_ms: int = 500
    ) -> Tuple[bool, float]:
        """
        Detect if audio contains mostly silence (Voice Activity Detection)
        
        Args:
            audio_data: Audio bytes (WAV format)
            silence_threshold: RMS threshold below which is considered silence
            min_silence_duration_ms: Minimum duration of silence to detect
            
        Returns:
            Tuple of (is_silent, silence_percentage)
        """
        try:
            # Load audio
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format="wav")
            
            # Calculate RMS (volume) for each chunk
            chunk_length_ms = 100  # 100ms chunks
            chunks = [
                audio[i:i + chunk_length_ms]
                for i in range(0, len(audio), chunk_length_ms)
            ]
            
            # Count silent chunks
            silent_chunks = sum(
                1 for chunk in chunks
                if chunk.rms < silence_threshold * 32768  # Convert to 16-bit scale
            )
            
            silence_percentage = silent_chunks / len(chunks) if chunks else 1.0
            
            # Consider silent if most of audio is below threshold
            is_silent = silence_percentage > 0.8
            
            return is_silent, silence_percentage
            
        except Exception as e:
            raise ValueError(f"Failed to detect silence: {e}")
    
    @staticmethod
    def chunk_audio(
        audio_data: bytes,
        chunk_duration_ms: int = 1000
    ) -> list[bytes]:
        """
        Split audio into chunks of specified duration
        
        Args:
            audio_data: Audio bytes (WAV format)
            chunk_duration_ms: Duration of each chunk in milliseconds
            
        Returns:
            List of audio chunk bytes
        """
        try:
            # Load audio
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format="wav")
            
            # Split into chunks
            chunks = []
            for i in range(0, len(audio), chunk_duration_ms):
                chunk = audio[i:i + chunk_duration_ms]
                
                # Export chunk
                chunk_io = io.BytesIO()
                chunk.export(chunk_io, format="wav")
                chunk_io.seek(0)
                chunks.append(chunk_io.read())
            
            return chunks
            
        except Exception as e:
            raise ValueError(f"Failed to chunk audio: {e}")
    
    @staticmethod
    def bytes_to_numpy(audio_data: bytes) -> np.ndarray:
        """
        Convert audio bytes (WAV) to numpy array (for Whisper)
        
        Args:
            audio_data: Audio bytes in WAV format
            
        Returns:
            Numpy array of audio samples (normalized to -1.0 to 1.0)
        """
        try:
            # Open WAV file from bytes
            with wave.open(io.BytesIO(audio_data), 'rb') as wav_file:
                # Get audio parameters
                sample_width = wav_file.getsampwidth()
                n_channels = wav_file.getnchannels()
                wav_file.getframerate()
                n_frames = wav_file.getnframes()
                
                # Read frames
                frames = wav_file.readframes(n_frames)
                
                # Convert to numpy array
                if sample_width == 2:  # 16-bit
                    audio_np = np.frombuffer(frames, dtype=np.int16)
                elif sample_width == 4:  # 32-bit
                    audio_np = np.frombuffer(frames, dtype=np.int32)
                else:
                    raise ValueError(f"Unsupported sample width: {sample_width}")
                
                # Convert to float32 and normalize to [-1.0, 1.0]
                audio_np = audio_np.astype(np.float32) / np.iinfo(audio_np.dtype).max
                
                # Convert stereo to mono if needed
                if n_channels == 2:
                    audio_np = audio_np.reshape(-1, 2).mean(axis=1)
                
                return audio_np
                
        except Exception as e:
            raise ValueError(f"Failed to convert bytes to numpy: {e}")
    
    @staticmethod
    def prepare_for_whisper(audio_data: bytes) -> np.ndarray:
        """
        Prepare audio for Whisper model (16kHz, mono, normalized)
        
        Args:
            audio_data: Audio bytes in any format
            
        Returns:
            Numpy array ready for Whisper
        """
        # Convert to WAV
        wav_data = AudioUtils.convert_to_wav(audio_data)
        
        # Resample to 16kHz
        wav_data = AudioUtils.resample_audio(wav_data, target_sample_rate=16000)
        
        # Convert to mono
        wav_data = AudioUtils.convert_to_mono(wav_data)
        
        # Convert to numpy
        audio_np = AudioUtils.bytes_to_numpy(wav_data)
        
        return audio_np
    
    @staticmethod
    def get_audio_duration(audio_data: bytes) -> float:
        """
        Get duration of audio in seconds
        
        Args:
            audio_data: Audio bytes
            
        Returns:
            Duration in seconds
        """
        try:
            audio = AudioSegment.from_file(io.BytesIO(audio_data))
            return len(audio) / 1000.0  # Convert ms to seconds
        except Exception as e:
            raise ValueError(f"Failed to get audio duration: {e}")
    
    @staticmethod
    def concatenate_audio(audio_chunks: list[bytes]) -> bytes:
        """
        Concatenate multiple audio chunks into one
        
        Args:
            audio_chunks: List of audio bytes (WAV format)
            
        Returns:
            Combined audio bytes
        """
        try:
            if not audio_chunks:
                raise ValueError("No audio chunks provided")
            
            # Load first chunk
            combined = AudioSegment.from_file(
                io.BytesIO(audio_chunks[0]),
                format="wav"
            )
            
            # Append remaining chunks
            for chunk_data in audio_chunks[1:]:
                chunk = AudioSegment.from_file(
                    io.BytesIO(chunk_data),
                    format="wav"
                )
                combined += chunk
            
            # Export combined audio
            output_io = io.BytesIO()
            combined.export(output_io, format="wav")
            output_io.seek(0)
            
            return output_io.read()
            
        except Exception as e:
            raise ValueError(f"Failed to concatenate audio: {e}")


