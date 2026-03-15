"""
Live2D Integration Routes for Healthcare AI V2
==============================================

FastAPI routes that integrate Live2D avatar functionality with the Healthcare AI system.
Provides endpoints for avatar interaction, model management, and real-time chat.
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
import httpx
from pydantic import BaseModel, Field

# from ...ai.ai_service import HealthcareAIService
# from ...agents.orchestrator import AgentOrchestrator  
# from ...agents.context_manager import ConversationContextManager
from ...core.logging import get_logger
from ...core.config import settings
from ...database.models_comprehensive import User
from ..auth.dependencies import get_optional_user, get_current_user
from .backend.healthcare_ai_bridge import HealthcareAIBridge

logger = get_logger(__name__)

# Initialize Live2D router
live2d_router = APIRouter(prefix="/live2d", tags=["Live2D Integration"])

# Initialize components
healthcare_bridge = HealthcareAIBridge()
# context_manager = ConversationContextManager()

# Live2D static files path
LIVE2D_STATIC_PATH = Path(__file__).parent / "frontend"
LIVE2D_RESOURCES_PATH = LIVE2D_STATIC_PATH / "Resources"
LIVE2D_SAMPLES_PATH = Path(__file__).parent / "Samples" / "TypeScript" / "Demo" / "dist"


def _build_stt_url(path_suffix: str) -> Optional[str]:
    """Helper to build full STT server URLs safely"""
    base_url = (settings.live2d_stt_service_url or "").strip()
    if not base_url:
        return None
    normalized_base = base_url.rstrip("/")
    suffix = path_suffix if path_suffix.startswith("/") else f"/{path_suffix}"
    return f"{normalized_base}{suffix}"


# Pydantic models for Live2D API
class ChatMessage(BaseModel):
    """Chat message model for Live2D interface"""
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    language: str = Field(default="en", pattern="^(en|zh-HK|auto)$")  # English, Traditional Chinese (HK), or auto-detect
    agent_preference: Optional[str] = None
    user_context: Optional[Dict[str, Any]] = None


class Live2DResponse(BaseModel):
    """Live2D chat response model"""
    message: str
    agent_type: str
    agent_name: str
    emotion: str
    gesture: str
    urgency: str
    language: str
    confidence: float
    processing_time_ms: int
    hk_facilities: List[Dict[str, Any]] = []
    avatar_state: Dict[str, Any] = {}
    voice_settings: Dict[str, Any] = {}
    animation_cues: List[str] = []
    session_id: str
    timestamp: str
    citations: List[Dict[str, Any]] = []


class ModelSwitchRequest(BaseModel):
    """Model switch request"""
    model_name: str = Field(..., description="Name of the Live2D model to switch to")
    reason: Optional[str] = Field(None, description="Reason for model switch")


class BackgroundSwitchRequest(BaseModel):
    """Background switch request"""
    background_name: str = Field(..., description="Name of the background to switch to")


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.connection_metadata[session_id] = {
            "connected_at": datetime.now().isoformat(),
            "message_count": 0,
            "last_activity": datetime.now().isoformat()
        }
        logger.info(f"Live2D WebSocket connected: {session_id}")

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.connection_metadata:
            del self.connection_metadata[session_id]
        logger.info(f"Live2D WebSocket disconnected: {session_id}")

    async def send_message(self, session_id: str, message: Dict[str, Any]):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_text(json.dumps(message))
                # Update metadata
                if session_id in self.connection_metadata:
                    metadata = self.connection_metadata[session_id]
                    metadata["message_count"] += 1
                    metadata["last_activity"] = datetime.now().isoformat()
                return True
            except Exception as e:
                logger.error(f"Error sending WebSocket message to {session_id}: {e}")
                self.disconnect(session_id)
                return False
        return False

    async def broadcast(self, message: Dict[str, Any]):
        disconnected = []
        for session_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to {session_id}: {e}")
                disconnected.append(session_id)
        
        # Clean up disconnected sessions
        for session_id in disconnected:
            self.disconnect(session_id)


connection_manager = ConnectionManager()


# Main Live2D interface route
@live2d_router.get("/", response_class=HTMLResponse)
async def live2d_interface():
    """Serve the main Live2D chat interface"""
    try:
        html_path = LIVE2D_STATIC_PATH / "index.html"
        if html_path.exists():
            logger.info(f"Serving Live2D interface from: {html_path}")
            return FileResponse(html_path)
        else:
            logger.warning(f"Live2D interface not found at: {html_path}")
            # Return a basic HTML page if the Live2D interface isn't found
            return HTMLResponse("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Healthcare AI V2 - Live2D Interface</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body>
                <h1>Healthcare AI V2 - Live2D Interface</h1>
                <p>Live2D interface is being set up. Please check back soon.</p>
                <p><a href="/docs">View API Documentation</a></p>
                <p><a href="/admin/">Admin Panel</a></p>
                <p><a href="/live2d/dev-voice-test">🔧 Developer Voice Test Suite</a></p>
            </body>
            </html>
            """)
    except Exception as e:
        logger.error(f"Error serving Live2D interface: {e}")
        raise HTTPException(status_code=500, detail="Live2D interface unavailable")


# Serve voice-input.js for admin panel and other pages
@live2d_router.get("/voice-input.js")
async def serve_voice_input_js():
    """Serve the SmartVoiceInput JavaScript file"""
    try:
        js_path = LIVE2D_STATIC_PATH / "voice-input.js"
        if js_path.exists():
            return FileResponse(js_path, media_type="application/javascript")
        else:
            logger.error(f"voice-input.js not found at: {js_path}")
            raise HTTPException(status_code=404, detail="voice-input.js not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving voice-input.js: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve voice-input.js")


# Serve simple-stt.js - minimal STT solution
@live2d_router.get("/simple-stt.js")
async def serve_simple_stt_js():
    """Serve the SimpleSTT JavaScript file"""
    try:
        js_path = LIVE2D_STATIC_PATH / "simple-stt.js"
        if js_path.exists():
            return FileResponse(js_path, media_type="application/javascript")
        else:
            logger.error(f"simple-stt.js not found at: {js_path}")
            raise HTTPException(status_code=404, detail="simple-stt.js not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving simple-stt.js: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve simple-stt.js")


# Simple STT test page
@live2d_router.get("/test-simple-stt", response_class=HTMLResponse)
async def test_simple_stt():
    """Serve simple STT test page"""
    try:
        test_path = LIVE2D_STATIC_PATH / "test-simple-stt.html"
        if not test_path.exists():
            raise HTTPException(status_code=404, detail="Test page not found")
        return FileResponse(test_path, media_type="text/html")
    except Exception as e:
        logger.error(f"Failed to serve simple STT test: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve test page")


# Working voice test page (under /live2d/ path which Chrome allows)
@live2d_router.get("/voice-test-working", response_class=HTMLResponse)
async def voice_test_working():
    """Serve working voice test page"""
    try:
        test_path = LIVE2D_STATIC_PATH / "voice_test_working.html"
        if not test_path.exists():
            raise HTTPException(status_code=404, detail="Test page not found")
        return FileResponse(test_path, media_type="text/html")
    except Exception as e:
        logger.error(f"Failed to serve voice test: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve test page")

# KB sandbox chat (pilot with citations)
@live2d_router.get("/kb-sandbox", response_class=HTMLResponse)
async def kb_sandbox():
    try:
        page_path = LIVE2D_STATIC_PATH / "kb_sandbox.html"
        if not page_path.exists():
            raise HTTPException(status_code=404, detail="Sandbox page not found")
        return FileResponse(page_path, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve kb sandbox: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve sandbox")


# Microphone diagnostic tool
@live2d_router.get("/mic-diagnostic", response_class=HTMLResponse)
async def mic_diagnostic():
    """Serve microphone diagnostic tool"""
    try:
        diagnostic_path = LIVE2D_STATIC_PATH / "mic_diagnostic.html"
        if not diagnostic_path.exists():
            raise HTTPException(status_code=404, detail="Diagnostic page not found")
        return FileResponse(diagnostic_path, media_type="text/html")
    except Exception as e:
        logger.error(f"Failed to serve mic diagnostic: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve diagnostic page")


# Microphone permission checker
@live2d_router.get("/check-microphone", response_class=HTMLResponse)
async def check_microphone():
    """Serve microphone permission checker"""
    try:
        checker_path = LIVE2D_STATIC_PATH / "check_microphone_permission.html"
        if not checker_path.exists():
            raise HTTPException(status_code=404, detail="Checker page not found")
        return FileResponse(checker_path, media_type="text/html")
    except Exception as e:
        logger.error(f"Failed to serve microphone checker: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve checker page")


# Legacy test routes - redirect to working voice test (Chrome allows /live2d/ paths)
@live2d_router.get("/dev-voice-test", response_class=HTMLResponse)
async def dev_voice_test():
    """Redirect to working voice test page"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Redirecting to Voice Test</title>
        <meta http-equiv="refresh" content="1;url=/live2d/voice-test-working">
        <style>
            body { font-family: system-ui, sans-serif; text-align: center; padding: 50px; }
            .container { max-width: 600px; margin: 0 auto; }
            .icon { font-size: 48px; margin-bottom: 20px; }
            h1 { color: #2563eb; margin-bottom: 20px; }
            p { color: #64748b; margin-bottom: 30px; }
            .btn { background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; display: inline-block; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">🎤</div>
            <h1>Voice Test Suite</h1>
            <p>Redirecting to working voice test page...</p>
            <a href="/live2d/voice-test-working" class="btn">Go to Voice Test</a>
        </div>
    </body>
    </html>
    """)


# Legacy test microphone route (redirect to working voice test)
@live2d_router.get("/test_microphone.html", response_class=HTMLResponse)
async def test_microphone():
    """Redirect legacy microphone test to working voice test"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Redirecting to Voice Test</title>
        <meta http-equiv="refresh" content="1;url=/live2d/voice-test-working">
        <style>
            body { font-family: system-ui, sans-serif; text-align: center; padding: 50px; }
            .container { max-width: 600px; margin: 0 auto; }
            .icon { font-size: 48px; margin-bottom: 20px; }
            h1 { color: #2563eb; margin-bottom: 20px; }
            p { color: #64748b; margin-bottom: 30px; }
            .btn { background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; display: inline-block; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">🎤</div>
            <h1>Voice Test Suite</h1>
            <p>Redirecting to working voice test page...</p>
            <a href="/live2d/voice-test-working" class="btn">Go to Voice Test</a>
        </div>
    </body>
    </html>
    """)


@live2d_router.get("/stt/health")
async def live2d_stt_health() -> JSONResponse:
    """Proxy STT health checks through the main backend (avoids CSP/connect-src issues)"""
    stt_health_url = _build_stt_url("/health")
    if not stt_health_url:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unconfigured", "message": "STT service URL not set"},
        )
    
    try:
        async with httpx.AsyncClient(timeout=settings.live2d_stt_timeout_seconds) as client:
            response = await client.get(stt_health_url)
            try:
                payload = response.json()
            except ValueError:
                payload = {"status": response.text}
            payload.setdefault("status_code", response.status_code)
            return JSONResponse(status_code=response.status_code, content=payload)
    except httpx.RequestError as exc:
        logger.error(f"STT health check failed: {exc}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "offline", "error": "STT server unreachable", "detail": str(exc)},
        )


@live2d_router.post("/stt/stream")
async def live2d_stt_stream(
    audio: UploadFile = File(...),
    lang: str = Form("en-US"),
) -> JSONResponse:
    """Proxy streamed audio transcription to the local Whisper STT server"""
    stt_stream_url = _build_stt_url("/stt/stream")
    if not stt_stream_url:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="STT server URL not configured")
    
    audio_bytes = await audio.read()
    if not audio_bytes:
        return JSONResponse(content={"text": ""})
    
    files = {
        "audio": (
            audio.filename or "recording.webm",
            audio_bytes,
            audio.content_type or "application/octet-stream",
        )
    }
    data = {"lang": lang}
    
    try:
        async with httpx.AsyncClient(timeout=settings.live2d_stt_timeout_seconds) as client:
            response = await client.post(stt_stream_url, data=data, files=files)
            response.raise_for_status()
            payload = response.json()
            return JSONResponse(content=payload)
    except httpx.HTTPStatusError as exc:
        logger.error(
            "STT upstream error: %s (status %s)",
            exc.response.text,
            exc.response.status_code,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "STT upstream error",
                "status_code": exc.response.status_code,
                "detail": exc.response.text,
            },
        )
    except httpx.RequestError as exc:
        logger.error(f"STT request failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to reach STT server",
        )


# Chat endpoint for Live2D integration
@live2d_router.post("/chat", response_model=Live2DResponse)
async def live2d_chat(
    message: ChatMessage,
    request: Request,
    current_user=Depends(get_optional_user)
):
    """
    Chat endpoint optimized for Live2D avatar interaction.
    
    For logged-in users: Uses persistent session based on user ID.
    For guests: Uses temporary session from request or generates new one.
    """
    try:
        start_time = datetime.now()
        
        # Persistent session management:
        # - Logged-in users get a persistent session tied to their user ID
        # - Guests get a temporary session (from request or randomly generated)
        if current_user:
            # Logged-in user: Use persistent session key
            session_id = f"user_{current_user.id}_persistent"
            user_id = current_user.id
            logger.info(f"Persistent session for user {user_id}: {session_id}")
        else:
            # Guest user: Use provided session or create temporary one
            session_id = message.session_id or f"guest_{uuid.uuid4().hex[:12]}"
            user_id = f"guest_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"Live2D chat request: {message.message[:50]}... (session: {session_id})")
        
        # Prepare user context with profile info if available
        user_context = message.user_context or {}
        if current_user:
            # Add user ID for form delivery
            user_context['user_id'] = current_user.id
            # Add user profile info for age-aware responses
            if hasattr(current_user, 'health_profile') and current_user.health_profile:
                user_context['age'] = current_user.health_profile.get('age')
                user_context['name'] = current_user.health_profile.get('name') or current_user.display_name
            elif hasattr(current_user, 'display_name'):
                user_context['name'] = current_user.display_name
        user_context["organization_id"] = getattr(current_user, "organization_id", None) if current_user else None
        user_context["visibility"] = "org"
        
        # Fetch persistent conversation history for AI memory (authenticated users only)
        conversation_history = []
        if current_user:
            try:
                from src.database.repositories.conversation_repository import ConversationRepository
                repo = ConversationRepository()
                # Get last 10 messages for context (balance between memory and performance)
                history = await repo.get_user_conversation_history(current_user.id, limit=10)
                conversation_history = history
                logger.info(f"📚 Loaded {len(conversation_history)} messages for AI memory")
            except Exception as history_err:
                logger.warning(f"Failed to load conversation history: {history_err}")
        
        # Process with Healthcare AI V2 backend
        response = await healthcare_bridge.process_chat_message(
            user_message=message.message,
            language=message.language,
            session_id=session_id,
            user_context=user_context,
            conversation_history=conversation_history  # Pass history for AI memory
        )
        
        # Calculate processing time
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Format response for Live2D
        # Handle both old format (message) and new format (reply + live2d_data)
        live2d_data = response.get("live2d_data", {})
        reply_text = response.get("reply", response.get("message", "I'm experiencing technical difficulties."))
        
        live2d_response = Live2DResponse(
            message=reply_text,
            agent_type=live2d_data.get("agent_type", response.get("agent_type", "wellness_coach")),
            agent_name=live2d_data.get("agent_name_en", response.get("agent_name", "Healthcare Assistant")),
            emotion=live2d_data.get("emotion", response.get("emotion", "neutral")),
            gesture=live2d_data.get("gesture", response.get("gesture", "default")),
            urgency=live2d_data.get("urgency", response.get("urgency", "low")),
            language=live2d_data.get("language", response.get("language", message.language)),
            confidence=live2d_data.get("confidence", response.get("confidence", 0.8)),
            processing_time_ms=processing_time,
            hk_facilities=live2d_data.get("hk_facilities", response.get("hk_facilities", [])),
            avatar_state=response.get("avatar_state", {}),
            voice_settings=live2d_data.get("voice_settings", response.get("voice_settings", {})),
            animation_cues=response.get("animation_cues", []),
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            citations=response.get("citations", [])
        )
        
        logger.info(f"Live2D response generated: {live2d_response.agent_type} ({processing_time}ms)")
        
        # Crisis Alert Detection
        try:
            await _check_and_create_crisis_alert_live2d(
                user_message=message.message,
                emotion=live2d_response.emotion,
                urgency=live2d_response.urgency,
                session_id=session_id,
                user_id=user_id,
                agent_type=live2d_response.agent_type
            )
        except Exception as alert_err:
            logger.warning(f"Failed to check crisis alert: {alert_err}")
        
        return live2d_response
        
    except Exception as e:
        logger.error(f"Error in Live2D chat: {e}")
        # Return fallback response
        return Live2DResponse(
            message="I apologize, but I'm experiencing technical difficulties. Please try again or contact support if this persists.",
            agent_type="wellness_coach",
            agent_name="Healthcare Assistant",
            emotion="apologetic",
            gesture="bow",
            urgency="low",
            language=message.language,
            confidence=0.5,
            processing_time_ms=100,
            session_id=message.session_id or f"error_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now().isoformat()
        )


# Get chat history endpoint
@live2d_router.get("/chat/history")
async def get_chat_history(
    limit: int = 50,
    current_user=Depends(get_optional_user)
):
    """
    Get conversation history for the current user.
    Only available for authenticated users.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access chat history"
        )
    
    try:
        from src.database.repositories.conversation_repository import ConversationRepository
        
        repo = ConversationRepository()
        history = await repo.get_user_conversation_history(current_user.id, limit=limit)
        
        return {
            "success": True,
            "history": history,
            "count": len(history),
            "user_id": current_user.id
        }
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve chat history"
        )


# Clear chat history endpoint
@live2d_router.delete("/chat/history")
async def clear_chat_history(
    current_user=Depends(get_optional_user)
):
    """
    Clear all conversation history for the current user.
    Only available for authenticated users.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to clear chat history"
        )
    
    try:
        from src.database.repositories.conversation_repository import ConversationRepository
        
        repo = ConversationRepository()
        deleted_count = await repo.delete_user_history(current_user.id)
        
        logger.info(f"Cleared {deleted_count} conversations for user {current_user.id}")
        
        return {
            "success": True,
            "message": "Chat history cleared",
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear chat history"
        )


# WebSocket endpoint for real-time Live2D chat
@live2d_router.websocket("/ws/chat")
async def live2d_websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for real-time Live2D chat interaction
    """
    session_id = f"ws_{uuid.uuid4().hex[:12]}"
    await connection_manager.connect(websocket, session_id)
    
    try:
        # Send welcome message
        await connection_manager.send_message(session_id, {
            "type": "welcome",
            "session_id": session_id,
            "message": "Welcome to Healthcare AI V2 with Live2D! How can I help you today?",
            "available_agents": ["illness_monitor", "mental_health", "safety_guardian", "wellness_coach"],
            "supported_languages": ["en", "zh-HK"]
        })
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Process different message types
            if message_data.get("type") == "user_message":
                # Send thinking indicator
                await connection_manager.send_message(session_id, {
                    "type": "agent_thinking",
                    "message": "Processing your request..."
                })
                
                # Process with Healthcare AI
                response = await healthcare_bridge.process_chat_message(
                    user_message=message_data.get("message", ""),
                    language=message_data.get("language", "en"),
                    session_id=session_id,
                    user_context=None
                )
                
                # Send agent response
                await connection_manager.send_message(session_id, {
                    "type": "agent_response",
                    **response,
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat()
                })
                
            elif message_data.get("type") == "ping":
                # Respond to ping with pong
                await connection_manager.send_message(session_id, {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
                
            elif message_data.get("type") == "typing_start":
                # Handle typing indicators (optional)
                pass
                
            elif message_data.get("type") == "typing_stop":
                # Handle typing indicators (optional)
                pass
    
    except WebSocketDisconnect:
        connection_manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        connection_manager.disconnect(session_id)


# =============================================================================
# Assessment Video Upload Endpoints (for Live2D chat integration)
# =============================================================================

@live2d_router.get("/movement-analysis/rules")
async def get_assessment_rules_for_chat(
    current_user=Depends(get_optional_user)
):
    """Get active assessment rules for the chat interface dropdown"""
    from src.database.connection import get_async_session_context
    from src.movement_analysis.rules_service import AssessmentRulesService
    
    try:
        async with get_async_session_context() as db:
            service = AssessmentRulesService(db)
            rules = await service.get_active_rules(current_user)
            return {
                "rules": [
                    {
                        "id": r.id,
                        "category": r.category,
                        "description": r.description,
                        "ai_role": r.ai_role
                    }
                    for r in rules
                ]
            }
    except Exception as e:
        logger.error(f"Error getting assessment rules: {e}")
        return {"rules": [], "error": str(e)}


@live2d_router.post("/movement-analysis/upload")
async def upload_assessment_video_chat(
    request: Request,
    video: UploadFile = File(...),
    rule_id: Optional[int] = Form(None),
    age_value: Optional[float] = Form(None),
    age_unit: Optional[str] = Form(None),
    age_group: Optional[str] = Form(None),  # Optional manual age group selection
    child_description: Optional[str] = Form(None),
    language_preference: Optional[str] = Form("en"),  # Language for AI response (en or zh-HK)
    current_user: User = Depends(get_current_user)  # SECURITY: Require authentication
):
    """
    Upload a video for assessment from Live2D chat interface
    Returns assessment ID for polling status
    
    Requires authentication to track assessment history and prevent abuse.
    
    Age Group Options (optional manual selection):
    - infant_toddler: 0-5 years
    - child: 6-13 years
    - teen: 14-19 years
    - adult: 20-64 years
    - elderly: 65+ years
    
    If age_group not provided, it will be calculated from age_value and age_unit.
    """
    from src.database.connection import get_async_session_context
    from src.movement_analysis.service import AssessmentService, save_uploaded_video
    from src.core.config import settings
    
    # VALIDATION: Validate age_group if provided
    valid_age_groups = ["infant_toddler", "child", "teen", "adult", "elderly"]
    if age_group and age_group not in valid_age_groups:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid age_group. Must be one of: {', '.join(valid_age_groups)}"
        )
    
    # Validate file type
    allowed_types = ["video/mp4", "video/mpeg", "video/quicktime", "video/x-msvideo", "video/webm"]
    if video.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video type. Allowed: mp4, mpeg, mov, avi, webm"
        )
    
    # Read and check file size (max 100MB)
    content = await video.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video file too large. Maximum size is 100MB"
        )
    
    try:
        # Save video file
        upload_folder = settings.upload_path / "assessments"
        filename, filepath = save_uploaded_video(content, video.filename, upload_folder)
        
        async with get_async_session_context() as db:
            service = AssessmentService(db)
            
            # SECURITY: User is authenticated, use their ID
            assessment = await service.create_assessment(
                user=current_user,
                rule_id=rule_id,
                video_filename=filename,
                video_path=filepath,
                video_type="local",
                age_value=age_value,
                age_unit=age_unit,
                age_group=age_group,  # Optional manual override
                child_description=child_description,
                language_preference=language_preference or "en"  # VALIDATION: Service validates language
            )
            
            # Start processing in background
            asyncio.create_task(_process_assessment_async(assessment.id))
            
            return {
                "success": True,
                "assessment_id": assessment.id,
                "status": "pending",
                "message": "Video uploaded successfully. Analysis will begin shortly."
            }
            
    except Exception as e:
        logger.error(f"Error uploading assessment video: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload video: {str(e)}"
        )


async def _process_assessment_async(assessment_id: int):
    """Background task to process assessment"""
    from src.database.connection import get_async_session_context
    from src.movement_analysis.service import AssessmentService
    
    try:
        async with get_async_session_context() as db:
            service = AssessmentService(db)
            await service.process_assessment(assessment_id)
            logger.info(f"Assessment {assessment_id} processed successfully")
    except Exception as e:
        logger.error(f"Error processing assessment {assessment_id}: {e}")


@live2d_router.get("/movement-analysis/{assessment_id}/status")
async def get_assessment_status_chat(
    assessment_id: int,
    current_user: User = Depends(get_current_user)  # SECURITY: Require authentication
):
    """Get assessment processing status for polling"""
    from src.database.connection import get_async_session_context
    from src.movement_analysis.service import AssessmentService
    
    try:
        async with get_async_session_context() as db:
            service = AssessmentService(db)
            
            # SECURITY: User is authenticated
            result = await service.get_assessment_status(assessment_id, current_user)
            
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Assessment not found"
                )
            
            return result
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting assessment status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get assessment status"
        )


# Model management endpoints
@live2d_router.get("/models")
async def get_available_models():
    """Get list of available Live2D models"""
    try:
        config_path = Path(__file__).parent / "admin_config.json"
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
            return {"models": config.get("models", {})}
        else:
            # Scan for models dynamically
            models = {}
            if LIVE2D_RESOURCES_PATH.exists():
                for model_dir in LIVE2D_RESOURCES_PATH.iterdir():
                    if model_dir.is_dir() and not model_dir.name.startswith('@'):
                        model_file = model_dir / f"{model_dir.name}.model3.json"
                        if model_file.exists():
                            models[model_dir.name] = {
                                "enabled": True,
                                "path": str(model_dir),
                                "model_file": model_file.name
                            }
            return {"models": models}
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        return {"models": {}, "error": str(e)}


@live2d_router.post("/models/switch")
async def switch_model(request: ModelSwitchRequest):
    """Switch the active Live2D model"""
    try:
        # This would implement the model switching logic
        # For now, return success response
        logger.info(f"Model switch requested: {request.model_name}")
        return {
            "success": True,
            "message": f"Switched to model: {request.model_name}",
            "model_name": request.model_name,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error switching model: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to switch model: {str(e)}")


@live2d_router.get("/backgrounds")
async def get_available_backgrounds():
    """Get list of available backgrounds"""
    try:
        config_path = Path(__file__).parent / "admin_config.json"
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
            return {"backgrounds": config.get("backgrounds", {})}
        else:
            return {"backgrounds": {}}
    except Exception as e:
        logger.error(f"Error getting backgrounds: {e}")
        return {"backgrounds": {}, "error": str(e)}


@live2d_router.post("/backgrounds/switch")
async def switch_background(request: BackgroundSwitchRequest):
    """Switch the active background"""
    try:
        logger.info(f"Background switch requested: {request.background_name}")
        return {
            "success": True,
            "message": f"Switched to background: {request.background_name}",
            "background_name": request.background_name,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error switching background: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to switch background: {str(e)}")


# Static file serving for Live2D assets
@live2d_router.get("/static/{file_path:path}")
async def serve_live2d_static(file_path: str):
    """Serve Live2D static files (models, textures, etc.)"""
    try:
        # Try frontend directory first
        full_path = LIVE2D_STATIC_PATH / file_path
        if full_path.exists() and full_path.is_file():
            return FileResponse(full_path)
        
        # Fallback to samples directory for Live2D core files
        fallback_path = LIVE2D_SAMPLES_PATH / file_path
        if fallback_path.exists() and fallback_path.is_file():
            return FileResponse(fallback_path)
            
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving static file {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Error serving file")

# Route to serve TTS integration JavaScript
@live2d_router.get("/tts-integration.js")
async def serve_tts_integration():
    """Serve Edge TTS integration JavaScript"""
    try:
        tts_path = LIVE2D_STATIC_PATH / "tts-integration.js"
        if tts_path.exists():
            return FileResponse(tts_path, media_type="application/javascript")
        else:
            raise HTTPException(status_code=404, detail="TTS integration file not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving TTS integration: {e}")
        raise HTTPException(status_code=500, detail="Error serving TTS integration")

# Additional route to serve frontend assets directly
@live2d_router.get("/assets/{file_path:path}")
async def serve_live2d_assets(file_path: str):
    """Serve Live2D frontend assets (CSS, JS, images, etc.)"""
    try:
        full_path = LIVE2D_STATIC_PATH / "assets" / file_path
        if full_path.exists() and full_path.is_file():
            return FileResponse(full_path)
        else:
            raise HTTPException(status_code=404, detail=f"Asset not found: {file_path}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving asset {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Error serving asset")

# Route to serve Core Live2D files
@live2d_router.get("/Core/{file_path:path}")
async def serve_live2d_core(file_path: str):
    """Serve Live2D Core engine files"""
    try:
        full_path = LIVE2D_STATIC_PATH / "Core" / file_path
        if full_path.exists() and full_path.is_file():
            return FileResponse(full_path)
        else:
            raise HTTPException(status_code=404, detail=f"Core file not found: {file_path}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving Core file {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Error serving Core file")

# Route to serve Resources (models, textures, etc.)
@live2d_router.get("/Resources/{file_path:path}")
async def serve_live2d_resources(file_path: str):
    """Serve Live2D Resources (models, textures, backgrounds, etc.)"""
    try:
        full_path = LIVE2D_STATIC_PATH / "Resources" / file_path
        if full_path.exists() and full_path.is_file():
            return FileResponse(full_path)
        else:
            raise HTTPException(status_code=404, detail=f"Resource not found: {file_path}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving Resource {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Error serving Resource")


# Health check for Live2D system
@live2d_router.get("/health")
async def live2d_health_check():
    """Health check for Live2D integration system"""
    try:
        # Check if Live2D assets exist
        core_exists = (Path(__file__).parent / "Core" / "live2dcubismcore.min.js").exists()
        models_exist = LIVE2D_RESOURCES_PATH.exists()
        
        # Check Healthcare AI connection
        healthcare_ai_status = await healthcare_bridge.check_healthcare_ai_status()
        
        status = "healthy" if core_exists and models_exist and healthcare_ai_status else "degraded"
        
        return {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "components": {
                "live2d_core": {"status": "available" if core_exists else "missing"},
                "live2d_models": {"status": "available" if models_exist else "missing"},
                "healthcare_ai": {"status": "connected" if healthcare_ai_status else "disconnected"},
                "websocket_connections": {"active": len(connection_manager.active_connections)}
            },
            "version": "2.0.0"
        }
    except Exception as e:
        logger.error(f"Live2D health check error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# Auth interface route
@live2d_router.get("/auth", response_class=HTMLResponse)
async def live2d_auth_interface():
    """Serve the Live2D authentication page"""
    try:
        auth_path = LIVE2D_STATIC_PATH / "auth.html"
        if auth_path.exists():
            logger.info(f"Serving Live2D auth interface from: {auth_path}")
            return FileResponse(auth_path)
        else:
            logger.warning(f"Live2D auth interface not found at: {auth_path}")
            raise HTTPException(status_code=404, detail="Auth interface not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving Live2D auth interface: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


# Profile interface route
@live2d_router.get("/profile", response_class=HTMLResponse)
async def live2d_profile_interface():
    """Serve the Live2D health profile page"""
    try:
        profile_path = LIVE2D_STATIC_PATH / "profile.html"
        if profile_path.exists():
            logger.info(f"Serving Live2D profile interface from: {profile_path}")
            return FileResponse(profile_path)
        else:
            logger.warning(f"Live2D profile interface not found at: {profile_path}")
            raise HTTPException(status_code=404, detail="Profile interface not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving Live2D profile interface: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


# Admin interface route - redirect to new admin panel
@live2d_router.get("/admin", response_class=RedirectResponse)
async def live2d_admin_interface():
    """Redirect to the main admin dashboard"""
    return RedirectResponse(url="/admin/", status_code=302)

# Admin endpoints for Live2D management
@live2d_router.get("/admin/status")
async def get_admin_status():
    """Get Live2D system status for admin interface"""
    try:
        # Get model configuration
        models = await get_available_models()
        backgrounds = await get_available_backgrounds()
        
        # Get connection statistics
        connection_stats = {
            "active_connections": len(connection_manager.active_connections),
            "total_sessions": len(connection_manager.connection_metadata),
            "connections": list(connection_manager.connection_metadata.keys())
        }
        
        return {
            "status": "operational",
            "models": models,
            "backgrounds": backgrounds,
            "connections": connection_stats,
            "healthcare_ai_bridge": await healthcare_bridge.get_bridge_status(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting admin status: {e}")
        return {"status": "error", "error": str(e)}


# Initialize Healthcare AI Bridge on startup
@live2d_router.on_event("startup")
async def startup_live2d():
    """Initialize Live2D system on startup"""
    try:
        logger.info("🎭 Initializing Live2D integration system...")
        
        # Initialize healthcare AI bridge
        await healthcare_bridge.initialize()
        
        # Verify Live2D assets
        if not LIVE2D_STATIC_PATH.exists():
            logger.warning(f"Live2D static path not found: {LIVE2D_STATIC_PATH}")
        
        if not LIVE2D_RESOURCES_PATH.exists():
            logger.warning(f"Live2D resources path not found: {LIVE2D_RESOURCES_PATH}")
        
        logger.info("✅ Live2D integration system initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Live2D system: {e}")


@live2d_router.on_event("shutdown")
async def shutdown_live2d():
    """Cleanup Live2D system on shutdown"""
    try:
        logger.info("🛑 Shutting down Live2D integration system...")
        
        # Disconnect all WebSocket connections
        for session_id in list(connection_manager.active_connections.keys()):
            connection_manager.disconnect(session_id)
        
        # Cleanup healthcare AI bridge
        await healthcare_bridge.cleanup()
        
        logger.info("✅ Live2D integration system shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during Live2D shutdown: {e}")


# Emotion and gesture mapping endpoints (for Live2D frontend)
@live2d_router.get("/emotions/{agent_type}")
async def get_agent_emotions(agent_type: str):
    """Get available emotions for specific agent type"""
    try:
        emotions = healthcare_bridge.get_agent_emotions(agent_type)
        return {"agent_type": agent_type, "emotions": emotions}
    except Exception as e:
        logger.error(f"Error getting emotions for {agent_type}: {e}")
        return {"agent_type": agent_type, "emotions": [], "error": str(e)}


@live2d_router.get("/gestures/{agent_type}")
async def get_agent_gestures(agent_type: str):
    """Get available gestures for specific agent type"""
    try:
        gestures = healthcare_bridge.get_agent_gestures(agent_type)
        return {"agent_type": agent_type, "gestures": gestures}
    except Exception as e:
        logger.error(f"Error getting gestures for {agent_type}: {e}")
        return {"agent_type": agent_type, "gestures": [], "error": str(e)}


@live2d_router.post("/swap-model")
async def swap_live2d_model(request: Dict[str, Any]):
    """Swap the current Live2D model"""
    try:
        model_name = request.get("model", "Hiyori")
        logger.info(f"Model swap requested: {model_name}")
        
        # For now, we'll just return a success response
        # In a full implementation, you'd update the model state
        return {
            "success": True,
            "message": f"Model changed to {model_name}",
            "current_model": model_name,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error swapping model: {e}")
        return {
            "success": False,
            "message": f"Failed to swap model: {str(e)}",
            "current_model": "Hiyori"  # fallback
        }


# ============================================================================
# CRISIS ALERT DETECTION FOR LIVE2D
# ============================================================================

CRISIS_KEYWORDS_EN = [
    "suicide", "kill myself", "want to die", "end my life", "hurt myself",
    "self-harm", "cutting", "overdose", "jump off", "hang myself",
    "don't want to live", "not want to live", "live anymore", "no point living",
    "end it all", "wish i was dead", "better off dead", "hopeless"
]

CRISIS_KEYWORDS_ZH = [
    "自殺", "想死", "殺死自己", "唔想活", "自殘", "割自己",
    "唔想再活", "死咗好", "活唔落去", "唔想做人"
]


async def _check_and_create_crisis_alert_live2d(
    user_message: str,
    emotion: str,
    urgency: str,
    session_id: str,
    user_id: Optional[str],
    agent_type: str
) -> None:
    """Check for crisis in Live2D chat and create alert if needed."""
    message_lower = user_message.lower()
    is_crisis = False
    detected_keywords = []
    
    for keyword in CRISIS_KEYWORDS_EN:
        if keyword in message_lower:
            is_crisis = True
            detected_keywords.append(keyword)
    
    for keyword in CRISIS_KEYWORDS_ZH:
        if keyword in user_message:
            is_crisis = True
            detected_keywords.append(keyword)
    
    # Also check emotion/urgency
    if emotion in ["urgent_alert", "crisis"] or urgency in ["emergency", "high", "critical"]:
        is_crisis = True
    
    if not is_crisis:
        return
    
    logger.warning(f"Crisis detected in Live2D chat! Keywords: {detected_keywords}, Emotion: {emotion}")
    
    try:
        from src.social_worker.alert_manager import get_alert_manager
        
        alert_manager = get_alert_manager()
        
        severity = 5 if any(kw in message_lower for kw in ["suicide", "kill myself"]) or "自殺" in user_message else 4
        
        # Convert user_id to int if possible
        child_id = None
        if user_id and not user_id.startswith("guest_"):
            try:
                child_id = int(user_id)
            except (ValueError, TypeError):
                pass
        
        alert = await alert_manager.create_alert(
            session_id=session_id,
            child_id=child_id,
            alert_type="emergency" if severity == 5 else "risk_detected",
            severity=severity,
            message=f"Live2D Chat Crisis: {user_message[:200]}...",
            detected_by="live2d_chat",
            skill_involved=agent_type,
            trigger_reason=f"Keywords: {', '.join(detected_keywords[:3]) if detected_keywords else f'Emotion: {emotion}'}",
            recommended_action="Immediate review required. Contact child/family as soon as possible.",
            force_create=True
        )
        
        if alert:
            logger.warning(f"Crisis alert created from Live2D: ID={alert.id}")
            
    except Exception as e:
        logger.error(f"Failed to create crisis alert from Live2D: {e}")


# Export the router for inclusion in main FastAPI app
__all__ = ["live2d_router"]
