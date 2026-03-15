#!/usr/bin/env python3
"""
Local STT Server with faster-whisper
Provides offline speech-to-text for the Live2D chatbot
"""

from fastapi import FastAPI, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import tempfile
import subprocess
import os
import contextlib
import logging
from typing import Optional, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Local STT Server", version="1.0.0")

# Enable CORS for all origins (adjust for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Whisper model
MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")
model = None

try:
    from faster_whisper import WhisperModel
    
    # Choose a model:
    #  - "tiny" (~39MB) fastest but less accurate
    #  - "base" (~140MB) good balance, recommended for start
    #  - "small" (~460MB) better accuracy
    #  - "medium" (~1.5GB) even better
    #  - "large-v3" (~3GB) best accuracy
    
    logger.info(f"🎧 Loading Whisper model: {MODEL_SIZE}")
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")  # fully local
    logger.info(f"✅ Whisper model loaded: {MODEL_SIZE}")
    
except ImportError:
    logger.error("❌ faster-whisper not installed. Please run: pip install faster-whisper")
except Exception as e:
    logger.error(f"❌ Error loading Whisper model: {e}")

# Language mapping for Whisper - ONLY English and Cantonese (Hong Kong)
# Optimized for female voice preference and better language detection
LANG_MAP = {
    # Cantonese (Hong Kong) - Primary target language
    "zh-HK": ("zh", "yue"),    # Chinese with Cantonese fallback (better Whisper support)
    "zh-hk": ("zh", "yue"),    # Case variation
    "yue": ("yue", "zh"),      # Direct Cantonese
    "zh": ("zh", None),        # Chinese fallback
    
    # English - Primary target language
    "en-US": ("en", None),     # English (US)
    "en-GB": ("en", None),     # English (UK) 
    "en-us": ("en", None),     # Case variation
    "en-gb": ("en", None),     # Case variation
    "en": ("en", None),        # English fallback
    
    # Reject unsupported languages explicitly (only en and zh-HK supported)
    "zh-TW": None,             # Traditional Chinese Taiwan (not supported)
    "fr": None,                # French (not supported)
    "es": None,                # Spanish (not supported)
    "ja": None,                # Japanese (not supported)
    "ko": None,                # Korean (not supported)
}

def resolve_whisper_language(lang: Optional[str]) -> Tuple[str, Optional[str]]:
    """Return primary and fallback Whisper language codes."""
    if not lang:
        logger.info("No language specified, defaulting to English")
        return ("en", None)
    
    normalized = lang.strip()
    mapping = LANG_MAP.get(normalized)
    
    # Explicitly reject unsupported languages
    if mapping is None:
        if normalized in LANG_MAP:  # Explicitly rejected
            logger.error("❌ Language '%s' is explicitly not supported. Only English and Cantonese (Hong Kong) are supported.", normalized)
            raise ValueError(f"Unsupported language: {normalized}. Only English (en-US) and Cantonese (zh-HK) are supported.")
        else:  # Unknown language
            logger.warning("⚠️ Unknown STT language '%s'. Supported: en-US, zh-HK. Defaulting to English.", normalized)
            return ("en", None)
    
    if isinstance(mapping, tuple):
        logger.info("🎧 Using language mapping: %s -> %s (fallback: %s)", normalized, mapping[0], mapping[1] or "none")
        return mapping
    
    # Should not reach here with current mapping structure
    return (mapping, None)

def get_healthcare_prompt(language_code: str) -> str:
    """Return healthcare-specific prompt to improve medical terminology recognition."""
    if language_code == "zh" or language_code == "yue":
        # Cantonese/Chinese healthcare prompt
        return "這是一個醫療保健對話。可能包含醫學術語、症狀描述、藥物名稱和健康相關詞彙。"
    else:
        # English healthcare prompt
        return "This is a healthcare conversation. It may include medical terminology, symptom descriptions, medication names, and health-related vocabulary."

def convert_to_wav16k(input_file):
    """Convert any audio file to 16kHz WAV using ffmpeg"""
    output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    
    try:
        # Convert with ffmpeg to 16kHz mono WAV with audio enhancement
        cmd = [
            "ffmpeg", "-y", "-i", input_file,
            "-ac", "1",          # mono
            "-ar", "16000",      # 16kHz sample rate
            "-acodec", "pcm_s16le",  # 16-bit PCM
            "-af", "highpass=f=80,lowpass=f=8000,volume=1.2",  # Audio filtering for speech
            output_file
        ]
        
        subprocess.run(
            cmd, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL, 
            check=True
        )
        
        return output_file
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ FFmpeg conversion failed: {e}")
        raise Exception("Audio conversion failed. Make sure ffmpeg is installed.")
    except FileNotFoundError:
        logger.error("❌ FFmpeg not found. Please install ffmpeg.")
        raise Exception("FFmpeg not found. Please install ffmpeg and ensure it's in PATH.")

@app.get("/health")
def health_check():
    """Health check endpoint"""
    whisper_status = "available" if model else "not_available"
    
    return JSONResponse({
        "status": "healthy",
        "whisper_model": MODEL_SIZE if model else None,
        "whisper_status": whisper_status,
        "message": f"Local STT Server running with {MODEL_SIZE} model" if model else "Whisper model not loaded"
    })

@app.post("/stt/stream")
async def transcribe_audio_stream(audio: UploadFile, lang: str = Form("en-US")):
    """
    Transcribe audio chunk from the browser
    Accepts: WebM, MP3, WAV, M4A, etc.
    Returns: JSON with transcribed text
    """
    if not model:
        return JSONResponse(
            {"error": "Whisper model not available"}, 
            status_code=503
        )
    
    # Get file extension from filename or default to webm
    file_extension = ".webm"
    if audio.filename:
        _, ext = os.path.splitext(audio.filename)
        if ext:
            file_extension = ext
    
    # Save uploaded audio chunk
    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension).name
    
    try:
        # Save uploaded data
        audio_data = await audio.read()
        if not audio_data:
            return JSONResponse({"text": ""})
            
        with open(temp_input, "wb") as f:
            f.write(audio_data)
        
        # Convert to WAV
        temp_wav = convert_to_wav16k(temp_input)
        
        # Map language
        primary_lang, fallback_lang = resolve_whisper_language(lang)
        
        # Transcribe with Whisper
        logger.info(f"🎧 Transcribing {len(audio_data)} bytes, language: {primary_lang}")

        def run_transcription(language_code: str):
            return model.transcribe(
                temp_wav,
                language=language_code,
                vad_filter=True,  # Voice Activity Detection
                vad_parameters=dict(
                    min_silence_duration_ms=100,  # More sensitive to speech
                    speech_pad_ms=30,              # Add padding around speech
                    max_speech_duration_s=30      # Allow longer speech segments
                ),
                beam_size=5,      # Better accuracy (was 1)
                best_of=5,        # Better accuracy (was 1)
                patience=2,       # More patience for better results
                temperature=0,    # Deterministic
                compression_ratio_threshold=2.4,  # Filter out low-quality audio
                log_prob_threshold=-1.0,          # Filter out uncertain results
                no_speech_threshold=0.6,          # Better speech detection
                condition_on_previous_text=False, # Don't rely on previous context
                initial_prompt=get_healthcare_prompt(language_code),  # Healthcare context
                word_timestamps=False,            # Focus on accuracy over timing
                prepend_punctuations="\"'([{-",   # Better punctuation handling
                append_punctuations="\"'.。,，!！?？:：\")]}、"  # Better punctuation for Chinese
            )

        try:
            segments, info = run_transcription(primary_lang)
        except ValueError as transcribe_error:
            if fallback_lang:
                logger.warning(
                    "⚠️ Whisper language '%s' not available, falling back to '%s'",
                    primary_lang,
                    fallback_lang
                )
                segments, info = run_transcription(fallback_lang)
            else:
                raise transcribe_error
        
        # Extract text from segments
        text = "".join(segment.text for segment in segments).strip()
        
        logger.info(f"🎧 Transcribed: '{text[:50]}{'...' if len(text) > 50 else ''}'")
        
        return JSONResponse({"text": text})
        
    except Exception as e:
        logger.error(f"❌ Transcription error: {e}")
        return JSONResponse({"text": "", "error": str(e)})
        
    finally:
        # Cleanup temporary files
        with contextlib.suppress(Exception):
            if 'temp_input' in locals():
                os.remove(temp_input)
        with contextlib.suppress(Exception):
            if 'temp_wav' in locals():
                os.remove(temp_wav)

@app.post("/stt/file")
async def transcribe_audio_file(audio: UploadFile, lang: str = Form("en-US")):
    """
    Transcribe a complete audio file (for testing)
    """
    if not model:
        return JSONResponse(
            {"error": "Whisper model not available"}, 
            status_code=503
        )
    
    # Similar to stream but with full file processing
    # ... (implementation similar to stream endpoint)
    return await transcribe_audio_stream(audio, lang)

if __name__ == "__main__":
    import uvicorn
    
    print("🎧 Starting Local STT Server...")
    print(f"🎯 Whisper Model: {MODEL_SIZE}")
    print("🌐 Server will run on: http://localhost:8790")
    print("📝 Install dependencies:")
    print("   pip install fastapi uvicorn faster-whisper python-multipart")
    print("   # Also need ffmpeg installed and in PATH")
    print("\n🚀 Starting server...")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8790, 
        log_level="info"
    )
