"""
Live2D Synchronization API
Endpoints for synchronizing with Live2D character system
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/live2d", tags=["live2d"])


class EmotionUpdateRequest(BaseModel):
    """Request to update emotion state"""
    user_emotion: str = Field(..., description="Current user emotion (happy, sad, angry, etc.)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Emotion confidence (0-1)")
    session_id: Optional[str] = Field(None, description="Session identifier")


class EmotionUpdateResponse(BaseModel):
    """Response with Live2D character expression"""
    character_expression: str = Field(..., description="Live2D expression to display")
    mirror_emotion: bool = Field(default=True, description="Whether to mirror user emotion")
    intensity: float = Field(..., description="Expression intensity (0-1)")
    transition_duration_ms: int = Field(default=500, description="Transition duration in milliseconds")


class InterventionTriggerRequest(BaseModel):
    """Request to trigger Live2D intervention"""
    intervention_type: str = Field(..., description="Type of intervention (posture_reminder, emotion_support, etc.)")
    message: str = Field(..., description="Intervention message")
    user_emotion: Optional[str] = Field(None, description="Current user emotion")
    session_id: Optional[str] = Field(None, description="Session identifier")


class InterventionTriggerResponse(BaseModel):
    """Response for Live2D intervention"""
    character_expression: str
    character_gesture: str
    intensity: float
    speak_text: bool = True
    audio_url: Optional[str] = None


# Emotion to Live2D expression mapping
EMOTION_TO_EXPRESSION = {
    "happy": "smile",
    "sad": "sad",
    "angry": "angry",
    "neutral": "normal",
    "surprise": "surprised",
    "fear": "worried",
    "disgust": "disgusted"
}


# Intervention to Live2D response mapping
INTERVENTION_TO_RESPONSE = {
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


@router.post("/emotion-update", response_model=EmotionUpdateResponse)
async def update_emotion(request: EmotionUpdateRequest):
    """
    Update Live2D character expression based on user emotion
    
    The Live2D character will mirror the user's emotion with appropriate expression
    """
    try:
        # Map user emotion to Live2D expression
        user_emotion_lower = request.user_emotion.lower()
        character_expression = EMOTION_TO_EXPRESSION.get(user_emotion_lower, "normal")
        
        # Calculate intensity based on confidence
        # High confidence = stronger expression
        intensity = min(1.0, request.confidence * 1.2)  # Boost slightly for visibility
        
        logger.info(
            f"Live2D emotion update: {request.user_emotion} -> {character_expression} "
            f"(intensity: {intensity:.2f})"
        )
        
        return EmotionUpdateResponse(
            character_expression=character_expression,
            mirror_emotion=True,
            intensity=intensity,
            transition_duration_ms=500
        )
        
    except Exception as e:
        logger.error(f"Error updating Live2D emotion: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update emotion: {str(e)}")


@router.post("/intervention-trigger", response_model=InterventionTriggerResponse)
async def trigger_intervention(request: InterventionTriggerRequest):
    """
    Trigger Live2D character intervention
    
    The character will perform appropriate gesture and expression for the intervention
    """
    try:
        # Get intervention response configuration
        intervention_config = INTERVENTION_TO_RESPONSE.get(
            request.intervention_type,
            {
                "expression": "normal",
                "gesture": "idle",
                "intensity": 0.5
            }
        )
        
        logger.info(
            f"Live2D intervention triggered: {request.intervention_type} "
            f"(expression: {intervention_config['expression']}, gesture: {intervention_config['gesture']})"
        )
        
        return InterventionTriggerResponse(
            character_expression=str(intervention_config["expression"]),
            character_gesture=str(intervention_config["gesture"]),
            intensity=float(intervention_config["intensity"]),
            speak_text=True,
            audio_url=None  # Audio generation handled by intervention responder
        )
        
    except Exception as e:
        logger.error(f"Error triggering Live2D intervention: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger intervention: {str(e)}")


@router.get("/expressions")
async def list_expressions():
    """
    List available Live2D expressions
    
    Returns the mapping of emotions to Live2D expressions
    """
    return {
        "expressions": EMOTION_TO_EXPRESSION,
        "intervention_responses": {
            itype: {
                "expression": config["expression"],
                "gesture": config["gesture"]
            }
            for itype, config in INTERVENTION_TO_RESPONSE.items()
        }
    }


@router.get("/health")
async def live2d_health():
    """Check Live2D sync API health"""
    return {
        "status": "healthy",
        "service": "Live2D Synchronization",
        "expressions_available": len(EMOTION_TO_EXPRESSION),
        "intervention_types_supported": len(INTERVENTION_TO_RESPONSE)
    }

