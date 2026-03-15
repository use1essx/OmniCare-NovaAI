"""
Healthcare System Integration API
Endpoints for integrating with healthcare_ai_live2d_unified
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict
import logging
from datetime import datetime

from ..intervention.engine import InterventionEngine
from ..intervention.responder import InterventionResponder
from ..utils.detailed_recorder import DetailedRecorder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/healthcare", tags=["healthcare-integration"])

# Global instances
intervention_engine = InterventionEngine()
intervention_responder = InterventionResponder()
active_sessions: Dict[str, DetailedRecorder] = {}


class SessionStartRequest(BaseModel):
    """Request to start new session"""
    user_id: Optional[str] = Field(None, description="User identifier")
    metadata: Optional[Dict] = Field(None, description="Additional metadata")


class SessionStartResponse(BaseModel):
    """Response with new session ID"""
    session_id: str
    start_time: datetime
    message: str


class SessionStopRequest(BaseModel):
    """Request to stop session"""
    session_id: str


class SessionStopResponse(BaseModel):
    """Response when session is stopped"""
    session_id: str
    duration_seconds: float
    total_frames: int
    intervention_count: int
    summary: Dict


class SessionStatusResponse(BaseModel):
    """Real-time session status"""
    session_id: str
    is_active: bool
    duration_seconds: float
    frames_recorded: int
    current_emotion: Optional[str] = None
    current_posture_quality: Optional[str] = None
    intervention_count: int
    engagement_level: Optional[float] = None


class InterventionTriggerRequest(BaseModel):
    """Manual intervention trigger from healthcare system"""
    session_id: str
    intervention_type: str = Field(..., description="Type of intervention")
    reason: Optional[str] = Field(None, description="Reason for intervention")
    message: Optional[str] = Field(None, description="Intervention message")
    force: bool = Field(False, description="Force intervention even if cooldown active")
    data: Optional[Dict] = Field(None, description="Additional data")


class EmotionUpdateRequest(BaseModel):
    """Emotion update from healthcare system"""
    session_id: str
    emotion: str
    emotion_confidence: float = Field(..., ge=0, le=1, description="Emotion confidence score")
    face_detected: Optional[bool] = Field(None, description="Whether face was detected")
    pose_landmarks: Optional[Dict] = Field(None, description="Pose landmarks data")
    timestamp: Optional[float] = None


class FrameDataRequest(BaseModel):
    """Full frame data from healthcare system"""
    session_id: str
    timestamp: Optional[float] = None
    bodyParts: Optional[Dict] = Field(None, description="Body part detections")
    pose: Optional[Dict] = Field(None, description="Pose landmarks")
    hands: Optional[Dict] = Field(None, description="Hand landmarks")
    faceMesh: Optional[Dict] = Field(None, description="Face mesh landmarks")
    emotion: Optional[Dict] = Field(None, description="Emotion detection data")
    metadata: Optional[Dict] = Field(None, description="Additional metadata")


@router.post("/session/start", response_model=SessionStartResponse)
async def start_integration_session(request: SessionStartRequest, db = None):
    """
    Start new integrated session
    
    Initializes recording and intervention monitoring for a healthcare session
    """
    try:
        from ..database.config import get_db
        
        # Get database session if not provided
        if db is None:
            db_gen = get_db()
            db = next(db_gen)
        
        # Create new recorder with database support
        recorder = DetailedRecorder(
            use_database=True,
            db_session=db,
            user_id=request.user_id or "anonymous"
        )
        session_id = recorder.start_recording()
        
        # Store in active sessions
        active_sessions[session_id] = recorder
        
        # Start intervention monitoring
        intervention_engine.start_session(session_id)
        
        logger.info(f"✅ Started integrated session: {session_id} for user: {request.user_id}")
        
        return SessionStartResponse(
            session_id=session_id,
            start_time=datetime.utcnow(),
            message="Session started successfully"
        )
        
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")


@router.post("/session/stop", response_model=SessionStopResponse)
async def stop_integration_session(request: SessionStopRequest, db = None):
    """
    Stop integrated session
    
    Stops recording, auto-generates report, and returns comprehensive session summary
    """
    session_id = request.session_id
    try:
        from ..database.config import get_db
        from ..reports.generator import ReportGenerator
        import os
        
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        recorder = active_sessions[session_id]
        
        # Stop recording
        recording_summary = recorder.stop_recording()
        
        # Stop intervention monitoring
        intervention_summary = intervention_engine.stop_session(session_id)
        
        # Get database session if not provided
        if db is None:
            db_gen = get_db()
            db = next(db_gen)
        
        # Auto-generate report if enabled
        report_summary = None
        if os.getenv("AUTO_GENERATE_REPORTS", "true").lower() == "true":
            try:
                logger.info(f"📊 Auto-generating report for session: {session_id}")
                report_gen = ReportGenerator()
                
                # Generate report from database
                report = report_gen.generate_from_database(session_id, db)
                
                # Save report to database
                from src.custom_live_ai.models.database import Report as ReportModel
                import json
                
                report_dict = json.loads(report.json())
                
                new_report = ReportModel(
                    session_id=session_id,
                    user_id=recorder.user_id if hasattr(recorder, 'user_id') else None,
                    report_data=report_dict,
                    overall_quality_score=report.overall_quality_score,
                    dominant_emotion=report.emotion_timeline.dominant_emotion,
                    average_posture_quality=report.posture_analysis.average_quality,
                    engagement_level=report.engagement.engagement_level,
                    total_interventions=report.intervention_summary.total_interventions if report.intervention_summary else 0,
                    report_version="2.2"
                )
                db.add(new_report)
                db.commit()
                
                report_summary = {
                    "quality_score": report.overall_quality_score,
                    "dominant_emotion": report.emotion_timeline.dominant_emotion,
                    "engagement_level": report.engagement.engagement_level
                }
                logger.info(f"✅ Report auto-generated and saved for session: {session_id}")
                
            except Exception as report_error:
                logger.error(f"Failed to auto-generate report: {report_error}")
                # Don't fail the whole stop operation if report generation fails
                report_summary = {"error": str(report_error)}
        
        # Save files (for backwards compatibility / backup)
        if hasattr(recorder, 'save_to_json') and recording_summary.get("storage_mode") != "database":
            recorder.save_to_json()
            recorder.save_summary_csv()
        
        # Remove from active sessions
        del active_sessions[session_id]
        
        logger.info(f"🏁 Stopped integrated session: {session_id}")
        
        return SessionStopResponse(
            session_id=session_id,
            duration_seconds=recording_summary.get("duration", 0),
            total_frames=recording_summary.get("total_frames", 0),
            intervention_count=intervention_summary.get("intervention_count", 0),
            summary={
                "recording": recording_summary,
                "interventions": intervention_summary,
                "report": report_summary
            }
        )
        
    except Exception as e:
        logger.error(f"Error stopping session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop session: {str(e)}")


@router.get("/session/{session_id}/status", response_model=SessionStatusResponse)
async def get_session_status(session_id: str):
    """
    Get real-time session status
    
    Returns current session metrics and state
    """
    try:
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found or not active")
        
        recorder = active_sessions[session_id]
        recorder_status = recorder.get_status()
        
        # Get intervention engine state
        engine_state = intervention_engine.get_session_state(session_id)
        
        return SessionStatusResponse(
            session_id=session_id,
            is_active=recorder_status["is_recording"],
            duration_seconds=recorder_status["duration"],
            frames_recorded=recorder_status["frames_recorded"],
            current_emotion=engine_state.get("current_emotion") if engine_state else None,
            current_posture_quality=engine_state.get("current_posture_quality") if engine_state else None,
            intervention_count=recorder_status.get("interventions_triggered", 0),
            engagement_level=None  # Would calculate from recent frames
        )
        
    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.post("/intervention/trigger")
async def trigger_manual_intervention(request: InterventionTriggerRequest):
    """
    Manually trigger intervention from healthcare system
    
    Allows healthcare system to proactively trigger interventions
    """
    try:
        if request.session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        recorder = active_sessions[request.session_id]
        
        # Get session duration for tone adaptation
        status = recorder.get_status()
        session_duration = status["duration"]
        
        # Get current emotion from engine
        engine_state = intervention_engine.get_session_state(request.session_id)
        current_emotion = engine_state.get("current_emotion") if engine_state else None
        
        # Generate message if not provided
        intervention_message = request.message or request.reason or f"Testing {request.intervention_type} intervention"
        
        # Deliver intervention
        intervention_response = await intervention_responder.deliver_intervention(
            intervention_type=request.intervention_type,
            message=intervention_message,
            session_duration_sec=session_duration,
            current_emotion=current_emotion
        )
        
        # Record trigger
        recorder.add_intervention_trigger(request.intervention_type)
        
        logger.info(f"📢 Manual intervention triggered for session: {request.session_id}")
        
        return {
            "success": True,
            "session_id": request.session_id,
            "intervention_type": request.intervention_type,
            "tone_used": intervention_response["tone_used"],
            "audio_size_bytes": intervention_response["audio_size_bytes"],
            "message": intervention_message
        }
        
    except Exception as e:
        logger.error(f"Error triggering intervention: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger intervention: {str(e)}")


@router.post("/frame-data")
async def record_frame_data(request: FrameDataRequest):
    """
    Receive and record full frame data from healthcare system
    
    Records complete frame with landmarks, emotion, and metadata to database
    """
    try:
        if request.session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        recorder = active_sessions[request.session_id]
        
        # Prepare frame data for recording
        frame_data = {
            "timestamp": request.timestamp,
            "bodyParts": request.bodyParts or {},
            "pose": request.pose or {"landmarks": []},
            "hands": request.hands or {"landmarks": [], "handedness": []},
            "faceMesh": request.faceMesh or {"landmarks": []},
            "emotion": request.emotion or {"label": "Neutral", "emoji": "😐", "confidence": 0, "scores": {}},
            "metadata": request.metadata or {}
        }
        
        # Record the frame
        recorder.record_frame(frame_data)
        
        # Also update intervention engine if emotion provided
        if request.emotion and "label" in request.emotion:
            intervention_engine.update_frame_data(
                session_id=request.session_id,
                current_emotion=request.emotion.get("label")
            )
        
        logger.debug(f"Frame recorded for session: {request.session_id}")
        
        return {
            "success": True,
            "session_id": request.session_id,
            "frames_recorded": recorder.frame_count
        }
        
    except Exception as e:
        logger.error(f"Error recording frame: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record frame: {str(e)}")


@router.post("/emotion-update")
async def update_emotion_from_healthcare(request: EmotionUpdateRequest):
    """
    Receive emotion update from healthcare system
    
    Syncs emotion state with recording system and records a frame with emotion data
    """
    try:
        if request.session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        recorder = active_sessions[request.session_id]
        
        # Record emotion change in timeline
        recorder.detect_emotion_change(
            current_emotion=request.emotion,
            confidence=request.emotion_confidence,
            timestamp=request.timestamp
        )
        
        # Also record a frame with this emotion data
        frame_data = {
            "timestamp": request.timestamp,
            "bodyParts": {"face": request.face_detected} if request.face_detected is not None else {},
            "pose": request.pose_landmarks or {"landmarks": []},
            "hands": {"landmarks": [], "handedness": []},
            "faceMesh": {"landmarks": []},
            "emotion": {
                "label": request.emotion,
                "confidence": request.emotion_confidence,
                "emoji": "😐",  # Default, would be mapped from emotion
                "scores": {}
            },
            "metadata": {"source": "emotion_update"}
        }
        recorder.record_frame(frame_data)
        
        # Update intervention engine
        intervention_engine.update_frame_data(
            session_id=request.session_id,
            current_emotion=request.emotion
        )
        
        logger.debug(f"Emotion updated and frame recorded: {request.emotion} ({request.emotion_confidence:.2f})")
        
        return {
            "success": True,
            "session_id": request.session_id,
            "emotion_recorded": request.emotion,
            "frames_recorded": recorder.frame_count
        }
        
    except Exception as e:
        logger.error(f"Error updating emotion: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update emotion: {str(e)}")


@router.get("/active-sessions")
async def list_active_sessions():
    """
    List all active integration sessions
    
    Returns list of currently active session IDs
    """
    return {
        "active_sessions": list(active_sessions.keys()),
        "count": len(active_sessions)
    }


@router.get("/health")
async def integration_health():
    """Check healthcare integration API health"""
    return {
        "status": "healthy",
        "service": "Healthcare Integration API",
        "active_sessions": len(active_sessions),
        "intervention_engine": "operational",
        "responder": "operational"
    }


# WebSocket endpoint for real-time streaming (defined in main.py)
# This is a placeholder showing the expected endpoint structure
# Actual implementation will be in main.py to avoid circular imports

