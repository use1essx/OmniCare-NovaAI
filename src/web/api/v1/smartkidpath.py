"""
OmniCare Screener API

Adult-facing early screening chat (text-only) for 3–9 y/o movement/social-emotional concerns.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.core.logging import get_logger, log_agent_interaction
from src.security.auth import InputSanitizer
from src.web.auth.dependencies import get_optional_user
from src.agents.context_manager import ConversationContextManager
from src.agents.specialized.smartkidpath_screener import SmartKidPathScreenerAgent
from src.ai.ai_service import get_ai_service


logger = get_logger(__name__)
router = APIRouter(prefix="/smartkidpath", tags=["smartkidpath"])


class SmartKidPathChatRequest(BaseModel):
    """Chat request for OmniCare Screener."""

    message: str = Field(..., min_length=1, max_length=4000, description="Adult's message about a child's movement/wellbeing")
    session_id: Optional[str] = Field(None, description="Conversation session ID")
    language: Optional[str] = Field("en", pattern="^(en|zh-HK|auto)$", description="Preferred language (en, zh-HK, auto)")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context information")


class SmartKidPathChatResponse(BaseModel):
    """Chat response for OmniCare Screener."""

    message: str
    agent_type: str
    session_id: str
    language: str
    processing_time_ms: int
    confidence: float
    urgency_level: str


@router.post(
    "/chat",
    response_model=SmartKidPathChatResponse,
    summary="OmniCare Screener chat",
    description="Adult-facing early screening chat for children's movement (non-diagnostic).",
)
async def chat_smartkidpath(
    chat_request: SmartKidPathChatRequest,
    current_user=Depends(get_optional_user),
):
    """Handle OmniCare Screener chat (text-only)."""
    start_time = datetime.utcnow()

    sanitizer = InputSanitizer()
    safe_message = sanitizer.sanitize_string(chat_request.message, max_length=4000)
    if not safe_message.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty")

    session_id = chat_request.session_id or f"skp_{int(datetime.utcnow().timestamp())}"
    user_id = str(getattr(current_user, "id", "")) if current_user else "anonymous_skp"

    ai_service = await get_ai_service()
    context_manager = ConversationContextManager()
    agent = SmartKidPathScreenerAgent(ai_service)

    context = context_manager.create_context(
        user_id=user_id,
        session_id=session_id,
        user_input=safe_message,
        additional_context={"language": chat_request.language or "en"},
    )

    agent_response = await agent.generate_response(safe_message, context)

    processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

    # Log interaction (non-blocking semantics not needed here)
    try:
        log_agent_interaction(
            agent_type=agent.agent_id,
            user_input=safe_message,
            agent_response=agent_response.content,
            confidence=agent_response.confidence,
            urgency_level=agent_response.urgency_level.value if hasattr(agent_response.urgency_level, "value") else str(agent_response.urgency_level),
            processing_time_ms=processing_time,
            user_id=getattr(current_user, "id", None),
            session_id=session_id,
        )
    except Exception as log_error:
        logger.warning(f"OmniCare interaction logging failed: {log_error}")

    return SmartKidPathChatResponse(
        message=agent_response.content,
        agent_type=agent.agent_id,
        session_id=session_id,
        language=chat_request.language or "en",
        processing_time_ms=processing_time,
        confidence=agent_response.confidence,
        urgency_level=agent_response.urgency_level.value if hasattr(agent_response.urgency_level, "value") else str(agent_response.urgency_level),
    )
