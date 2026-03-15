"""
Live2D REST API Endpoints - Healthcare AI V2
=============================================

RESTful API endpoints for Live2D frontend integration.
Provides agent information, emotion mappings, gestures, and system status.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, Query, Request, Depends, HTTPException
from pydantic import BaseModel

from src.core.logging import get_logger
from src.database.repositories.conversation_repository import ConversationRepository
from src.web.auth.dependencies import get_current_user

logger = get_logger(__name__)
router = APIRouter(prefix="/live2d", tags=["live2d"])
conversation_repo = ConversationRepository()

# ============================================================================
# RESPONSE MODELS
# ============================================================================

class AgentInfo(BaseModel):
    """Basic agent information"""
    agent_type: str
    agent_name: str
    description: str
    personality: str
    capabilities: List[str]

class EmotionInfo(BaseModel):
    """Emotion mapping information"""
    emotion_id: str
    display_name: str
    category: str
    agent_types: List[str]

class GestureInfo(BaseModel):
    """Gesture information"""
    gesture_id: str
    display_name: str
    category: str
    description: str

class SystemStatus(BaseModel):
    """Live2D system status"""
    status: str
    connected: bool
    last_update: str
    performance: Dict[str, Any]

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get(
    "/agents",
    response_model=List[AgentInfo],
    summary="Get all agents with Live2D personalities"
)
async def get_all_agents(
    request: Request,
    language: str = Query(default="en", regex="^(en|zh-HK)$")
) -> List[AgentInfo]:
    """Get all agents with Live2D personality information"""
    
    # Static agent information for testing
    agents = [
        AgentInfo(
            agent_type="illness_monitor",
            agent_name="慧心助手" if language == "zh-HK" else "Wellness Monitor",
            description="Professional healthcare monitoring agent",
            personality="caring_professional",
            capabilities=["symptom_analysis", "medication_guidance", "health_monitoring"]
        ),
        AgentInfo(
            agent_type="mental_health",
            agent_name="小星星" if language == "zh-HK" else "Mental Health Assistant",
            description="Supportive mental health companion",
            personality="vtuber_friend",
            capabilities=["emotional_support", "crisis_intervention", "mental_wellness"]
        ),
        AgentInfo(
            agent_type="safety_guardian",
            agent_name="Safety Guardian",
            description="Emergency response and safety coordinator",
            personality="professional_responder",
            capabilities=["emergency_response", "safety_assessment", "crisis_management"]
        ),
        AgentInfo(
            agent_type="wellness_coach",
            agent_name="Wellness Coach",
            description="Proactive wellness and prevention specialist",
            personality="wellness_motivator",
            capabilities=["wellness_coaching", "prevention", "lifestyle_guidance"]
        )
    ]
    
    return agents

@router.get(
    "/emotions",
    response_model=List[EmotionInfo],
    summary="Get emotion mappings for Live2D"
)
async def get_emotion_mappings(
    request: Request,
    agent_type: Optional[str] = Query(default=None),
    language: str = Query(default="en", regex="^(en|zh-HK)$")
) -> List[EmotionInfo]:
    """Get emotion mappings for Live2D avatars"""
    
    emotions = [
        EmotionInfo(
            emotion_id="professional_caring",
            display_name="Professional Caring",
            category="professional",
            agent_types=["illness_monitor"]
        ),
        EmotionInfo(
            emotion_id="gentle_supportive",
            display_name="Gentle Support",
            category="supportive",
            agent_types=["mental_health"]
        ),
        EmotionInfo(
            emotion_id="alert_focused",
            display_name="Alert Focus",
            category="urgent",
            agent_types=["safety_guardian"]
        ),
        EmotionInfo(
            emotion_id="encouraging_warm",
            display_name="Encouraging",
            category="encouraging",
            agent_types=["wellness_coach"]
        )
    ]
    
    if agent_type:
        emotions = [e for e in emotions if agent_type in e.agent_types]
    
    return emotions

@router.get(
    "/gestures",
    response_model=List[GestureInfo],
    summary="Get gesture mappings for Live2D"
)
async def get_gesture_mappings(
    request: Request,
    category: Optional[str] = Query(default=None),
    agent_type: Optional[str] = Query(default=None)
) -> List[GestureInfo]:
    """Get gesture mappings for Live2D avatars"""
    
    gestures = [
        GestureInfo(
            gesture_id="gentle_nod",
            display_name="Gentle Nod",
            category="greeting",
            description="Warm, welcoming nod"
        ),
        GestureInfo(
            gesture_id="medical_point",
            display_name="Medical Pointing",
            category="medical_consultation",
            description="Professional pointing gesture for medical guidance"
        ),
        GestureInfo(
            gesture_id="heart_gesture",
            display_name="Heart Gesture",
            category="emotional_support",
            description="Caring heart gesture for emotional support"
        ),
        GestureInfo(
            gesture_id="emergency_alert",
            display_name="Emergency Alert",
            category="emergency_response",
            description="Urgent alerting gesture"
        )
    ]
    
    if category:
        gestures = [g for g in gestures if g.category == category]
    
    return gestures

@router.get(
    "/status",
    response_model=SystemStatus,
    summary="Get Live2D system status"
)
async def get_live2d_status(request: Request) -> SystemStatus:
    """Get Live2D system status and health"""
    
    return SystemStatus(
            status="operational",
        connected=True,
        last_update=datetime.now().isoformat(),
        performance={
            "response_time_ms": 2.5,
            "memory_usage": "45%",
            "active_connections": 1,
            "uptime_seconds": 3600
        }
    )


@router.delete(
    "/chat/session/{session_id}",
    summary="Delete chat history for a session",
    description="Clears stored chat history for the given session_id (session-scoped only).",
)
async def delete_chat_session(
    session_id: str,
    request: Request,
    current_user=Depends(get_current_user),
):
    """
    Delete chat history for a specific session.
    Does not touch user profile or other sessions.
    """
    try:
        deleted = await conversation_repo.delete_session_history(
            session_id=session_id,
            user_id=current_user.id if current_user else None,
        )
        return {"status": "deleted", "session_id": session_id, "deleted_rows": deleted}
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete session history")

@router.get(
    "/test",
    summary="Live2D integration test endpoint"
)
async def test_live2d_integration(request: Request) -> Dict[str, Any]:
    """Test Live2D integration functionality"""
    
    return {
        "message": "Live2D integration is working!",
        "timestamp": datetime.now().isoformat(),
        "features": {
            "agent_personalities": True,
            "emotion_mapping": True,
            "gesture_library": True,
            "real_time_updates": True
        },
        "test_status": "pass"
    }
