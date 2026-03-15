#!/usr/bin/env python3
"""
Local TTS Server with Edge TTS
Provides text-to-speech for the Live2D chatbot
"""

import os
import io
import logging
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# SECURITY: Import authentication dependencies
try:
    from src.web.auth.dependencies import get_current_user
    from src.database.models_comprehensive import User
    AUTH_AVAILABLE = True
except ImportError:
    # Fallback for standalone TTS server
    AUTH_AVAILABLE = False
    logger.warning("⚠️ Authentication not available - running in standalone mode")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Healthcare AI TTS Server",
    description="Edge TTS Server for Live2D Chatbot",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Edge TTS
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
    logger.info("✅ Edge TTS loaded successfully")
except ImportError:
    logger.error("❌ edge-tts not installed. Please run: pip install edge-tts")
    EDGE_TTS_AVAILABLE = False

# Default voices for different languages (English and Traditional Chinese - Hong Kong only)
DEFAULT_VOICES = {
    "zh-HK": os.environ.get("TTS_DEFAULT_VOICE", "zh-HK-HiuGaaiNeural"),  # Cantonese female
    "en-US": "en-US-JennyNeural",      # English US female
    "en-GB": "en-GB-SoniaNeural",      # English UK female
    "en": "en-US-JennyNeural",         # Default English
}


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "edge_tts_available": EDGE_TTS_AVAILABLE,
        "default_voices": DEFAULT_VOICES,
        "message": "TTS Server running" if EDGE_TTS_AVAILABLE else "Edge TTS not available"
    })


@app.get("/voices")
async def list_voices():
    """List available voices"""
    if not EDGE_TTS_AVAILABLE:
        return JSONResponse(
            {"error": "Edge TTS not available"},
            status_code=503
        )
    
    try:
        voices = await edge_tts.list_voices()
        return JSONResponse({"voices": voices})
    except Exception as e:
        logger.error(f"Error listing voices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tts/synthesize")
async def synthesize_speech(
    text: str = Form(...),
    lang: str = Form("zh-HK"),
    voice: Optional[str] = Form(None),
    rate: str = Form("+0%"),
    pitch: str = Form("+0Hz"),
    current_user: User = Depends(get_current_user) if AUTH_AVAILABLE else None,
):
    """
    Synthesize speech from text
    
    SECURITY: Requires authentication to prevent abuse
    
    Args:
        text: Text to synthesize
        lang: Language code (zh-HK, en-US, etc.)
        voice: Voice name (optional, uses default for language)
        rate: Speech rate (-50% to +100%)
        pitch: Voice pitch (-50Hz to +50Hz)
        current_user: Authenticated user (required)
    
    Returns:
        Audio stream in MP3 format
    """
    # SECURITY: Check authentication if available
    if AUTH_AVAILABLE and not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to use TTS service"
        )
    
    if not EDGE_TTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Edge TTS not available")
    
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Text is required")
    
    # Select voice
    selected_voice = voice or DEFAULT_VOICES.get(lang, DEFAULT_VOICES["zh-HK"])
    
    # PRIVACY: Log user ID only, not the text content
    user_info = f"user_id={current_user.id}" if (AUTH_AVAILABLE and current_user) else "unauthenticated"
    logger.info(f"🔊 TTS request from {user_info}, voice={selected_voice}, text_length={len(text)}")
    
    try:
        # Create communicate object
        communicate = edge_tts.Communicate(
            text,
            voice=selected_voice,
            rate=rate,
            pitch=pitch
        )
        
        # Collect audio chunks
        audio_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])
        
        audio_buffer.seek(0)
        
        logger.info(f"✅ Synthesized {audio_buffer.getbuffer().nbytes} bytes for {user_info}")
        
        return StreamingResponse(
            audio_buffer,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "attachment; filename=speech.mp3"
            }
        )
        
    except Exception as e:
        logger.error(f"❌ TTS synthesis failed for {user_info}: {e}")
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {e}")


if __name__ == "__main__":
    import uvicorn
    
    print("🔊 Starting Local TTS Server...")
    print(f"🎤 Default voice: {DEFAULT_VOICES['zh-HK']}")
    print("🌐 Server will run on: http://localhost:8791")
    print("\n📝 Install dependencies:")
    print("   pip install fastapi uvicorn edge-tts")
    print("\n🚀 Starting server...")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8791,
        log_level="info"
    )
