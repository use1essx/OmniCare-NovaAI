"""
Database API Routes for User and Session Management
Provides endpoints for PostgreSQL integration
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import json
import os
import logging

from src.custom_live_ai.database.config import get_db
from src.custom_live_ai.models.database import User, Session as DBSession, EmotionEvent

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api/db", tags=["database"])


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class UserCreate(BaseModel):
    """Schema for creating a new user"""
    user_id: str = Field(..., description="Unique user identifier")
    name: str = Field(..., description="User's full name")
    age: Optional[int] = Field(None, description="User's age")
    gender: Optional[str] = Field(None, description="User's gender")
    notes: Optional[str] = Field(None, description="Additional notes about the user")


class UserResponse(BaseModel):
    """Schema for user response"""
    id: int
    user_id: str
    name: str
    age: Optional[int]
    gender: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    """Schema for creating a session record"""
    session_id: str = Field(..., description="Unique session identifier (from recording filename)")
    user_id: str = Field(..., description="User identifier who recorded the session")


class SessionResponse(BaseModel):
    """Schema for session response"""
    id: int
    session_id: str
    user_id: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    duration: Optional[float]
    total_frames: Optional[int]
    avg_fps: Optional[float]
    recording_quality: Optional[str]
    json_file: Optional[str]
    csv_file: Optional[str]
    face_detection_rate: Optional[float]
    avg_smile_score: Optional[float]
    avg_eye_open_left: Optional[float]
    avg_eye_open_right: Optional[float]
    avg_eyebrow_height: Optional[float]
    avg_mouth_open: Optional[float]
    blinks_detected: Optional[int]
    smile_frames: Optional[int]
    surprise_moments: Optional[int]
    session_metadata: Optional[Dict]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class EmotionEventCreate(BaseModel):
    """Schema for creating emotion event"""
    session_id: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(..., description="Event timestamp")
    frame_number: int = Field(..., description="Frame number where event occurred")
    event_type: str = Field(..., description="Type of emotion event (e.g., 'smile', 'blink', 'surprise', 'emotion_change')")
    intensity: Optional[float] = Field(None, ge=0.0, le=1.0, description="Intensity of the event (0.0 to 1.0)")
    duration: Optional[float] = Field(None, description="Duration of the event in seconds")
    data: Optional[Dict] = Field(None, description="Additional event data (emotion scores, etc.)")


class EmotionEventResponse(BaseModel):
    """Schema for emotion event response"""
    id: int
    session_id: str
    timestamp: datetime
    frame_number: int
    event_type: str
    intensity: Optional[float]
    duration: Optional[float]
    data: Optional[Dict]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user in the database
    """
    try:
        # Check if user_id already exists
        existing_user = db.query(User).filter(User.user_id == user.user_id).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with user_id '{user.user_id}' already exists"
            )
        
        # Create new user
        db_user = User(
            user_id=user.user_id,
            name=user.name,
            age=user.age,
            gender=user.gender,
            notes=user.notes
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        logger.info(f"Created new user: {user.user_id}")
        return db_user
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all users with pagination
    """
    try:
        users = db.query(User).offset(skip).limit(limit).all()
        return users
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}"
        )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, db: Session = Depends(get_db)):
    """
    Get a specific user by user_id
    """
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{user_id}' not found"
            )
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user: {str(e)}"
        )


# ============================================================================
# SESSION MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/sessions/save", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def save_session(session: SessionCreate, db: Session = Depends(get_db)):
    """
    Save a session to the database by analyzing the recording files
    Automatically extracts all statistics from JSON and CSV files
    """
    try:
        # Check if user exists
        user = db.query(User).filter(User.user_id == session.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{session.user_id}' not found. Create user first."
            )
        
        # Check if session already exists
        existing_session = db.query(DBSession).filter(DBSession.session_id == session.session_id).first()
        if existing_session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Session '{session.session_id}' already exists"
            )
        
        # Find recording files
        recordings_dir = "recordings"
        json_file = os.path.join(recordings_dir, f"{session.session_id}_detailed.json")
        csv_file = os.path.join(recordings_dir, f"{session.session_id}_summary.csv")
        
        if not os.path.exists(json_file):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recording file not found: {json_file}"
            )
        
        # Analyze recording files
        session_data = analyze_recording_files(json_file, csv_file)
        
        # Create session record
        db_session = DBSession(
            session_id=session.session_id,
            user_id=session.user_id,
            **session_data
        )
        
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        
        logger.info(f"Saved session: {session.session_id} for user: {session.user_id}")
        return db_session
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save session: {str(e)}"
        )


@router.get("/sessions/user/{user_id}", response_model=List[SessionResponse])
async def get_user_sessions(
    user_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get all sessions for a specific user
    """
    try:
        sessions = (
            db.query(DBSession)
            .filter(DBSession.user_id == user_id)
            .order_by(DBSession.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return sessions
    except Exception as e:
        logger.error(f"Error getting user sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sessions: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: Session = Depends(get_db)):
    """
    Get details for a specific session
    """
    try:
        session = db.query(DBSession).filter(DBSession.session_id == session_id).first()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found"
            )
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session: {str(e)}"
        )


# ============================================================================
# STATISTICS ENDPOINTS
# ============================================================================

@router.get("/stats/user/{user_id}")
async def get_user_stats(user_id: str, db: Session = Depends(get_db)):
    """
    Get aggregated statistics for a user across all their sessions
    """
    try:
        sessions = db.query(DBSession).filter(DBSession.user_id == user_id).all()
        
        if not sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No sessions found for user '{user_id}'"
            )
        
        # Calculate aggregated stats
        total_sessions = len(sessions)
        total_duration = sum(s.duration for s in sessions if s.duration)
        total_frames = sum(s.total_frames for s in sessions if s.total_frames)
        avg_smile = sum(s.avg_smile_score for s in sessions if s.avg_smile_score) / total_sessions if total_sessions > 0 else 0
        total_blinks = sum(s.blinks_detected for s in sessions if s.blinks_detected)
        total_smiles = sum(s.smile_frames for s in sessions if s.smile_frames)
        
        return {
            "user_id": user_id,
            "total_sessions": total_sessions,
            "total_duration_seconds": round(total_duration, 2) if total_duration else 0,
            "total_frames_captured": total_frames or 0,
            "average_smile_score": round(avg_smile, 3) if avg_smile else 0,
            "total_blinks": total_blinks or 0,
            "total_smile_moments": total_smiles or 0,
            "sessions": [s.session_id for s in sessions]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def analyze_recording_files(json_file: str, csv_file: str) -> Dict[str, Any]:
    """
    Analyze recording files and extract session statistics
    """
    result = {
        "json_file": json_file,
        "csv_file": csv_file if os.path.exists(csv_file) else None,
    }
    
    try:
        # Load JSON file
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        # Extract basic info
        session_start = data.get("session_start")
        result["start_time"] = datetime.fromisoformat(session_start.replace("Z", "+00:00")) if session_start else None
        result["end_time"] = datetime.fromisoformat(data.get("session_end", "").replace("Z", "+00:00")) if data.get("session_end") else None
        result["duration"] = data.get("duration")
        result["total_frames"] = len(data.get("frames", []))
        result["session_metadata"] = data.get("metadata", {})
        result["recording_quality"] = data.get("metadata", {}).get("quality", "unknown")
        
        # Calculate FPS
        if result["duration"] and result["total_frames"]:
            result["avg_fps"] = result["total_frames"] / result["duration"]
        
        # Analyze frames for emotion metrics
        frames = data.get("frames", [])
        if frames:
            face_detected_count = sum(1 for f in frames if f.get("faceMesh"))
            result["face_detection_rate"] = face_detected_count / len(frames)
            
            # Calculate average emotion metrics from frames with face data
            smiles = []
            eye_left = []
            eye_right = []
            eyebrows = []
            mouth_open = []
            blinks = 0
            smile_frames_count = 0
            surprise_count = 0
            
            for frame in frames:
                face = frame.get("faceMesh")
                if face:
                    # Extract emotion indicators from face mesh
                    # This is a simplified version - you may want to implement more sophisticated analysis
                    landmarks = face.get("landmarks", [])
                    if landmarks and len(landmarks) >= 478:
                        # Calculate smile score (mouth corners vs center)
                        smile_score = calculate_smile_score(landmarks)
                        smiles.append(smile_score)
                        if smile_score > 0.3:
                            smile_frames_count += 1
                        
                        # Eye openness
                        left_eye = calculate_eye_openness(landmarks, "left")
                        right_eye = calculate_eye_openness(landmarks, "right")
                        eye_left.append(left_eye)
                        eye_right.append(right_eye)
                        
                        # Detect blinks
                        if left_eye < 0.2 or right_eye < 0.2:
                            blinks += 1
                        
                        # Eyebrow height (surprise indicator)
                        eyebrow_h = calculate_eyebrow_height(landmarks)
                        eyebrows.append(eyebrow_h)
                        if eyebrow_h > 0.6:
                            surprise_count += 1
                        
                        # Mouth openness
                        mouth = calculate_mouth_openness(landmarks)
                        mouth_open.append(mouth)
            
            result["avg_smile_score"] = sum(smiles) / len(smiles) if smiles else None
            result["avg_eye_open_left"] = sum(eye_left) / len(eye_left) if eye_left else None
            result["avg_eye_open_right"] = sum(eye_right) / len(eye_right) if eye_right else None
            result["avg_eyebrow_height"] = sum(eyebrows) / len(eyebrows) if eyebrows else None
            result["avg_mouth_open"] = sum(mouth_open) / len(mouth_open) if mouth_open else None
            result["blinks_detected"] = blinks
            result["smile_frames"] = smile_frames_count
            result["surprise_moments"] = surprise_count
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing recording files: {e}")
        return result


def calculate_smile_score(landmarks: List) -> float:
    """Calculate smile score from face mesh landmarks"""
    try:
        # Simplified: compare mouth corners height
        if len(landmarks) < 478:
            return 0.0
        # Mouth corners: 61 (left), 291 (right), center: 13
        left_corner = landmarks[61] if len(landmarks) > 61 else {"y": 0}
        right_corner = landmarks[291] if len(landmarks) > 291 else {"y": 0}
        center = landmarks[13] if len(landmarks) > 13 else {"y": 0}
        
        corner_avg_y = (left_corner.get("y", 0) + right_corner.get("y", 0)) / 2
        center_y = center.get("y", 0)
        
        # If corners are higher than center, it's a smile
        smile = max(0, center_y - corner_avg_y)
        return min(1.0, smile * 10)  # Normalize
    except Exception:
        return 0.0


@router.post("/emotion-events", response_model=EmotionEventResponse, status_code=status.HTTP_201_CREATED)
async def log_emotion_event(event: EmotionEventCreate, db: Session = Depends(get_db)):
    """
    Log a significant emotion event during a session
    
    Examples of emotion events:
    - emotion_change: When dominant emotion changes
    - high_confidence: When emotion confidence exceeds threshold
    - smile: Smile detected
    - surprise: Surprise expression detected
    - blink: Blink detected
    """
    try:
        # Create emotion event record
        db_event = EmotionEvent(
            session_id=event.session_id,
            timestamp=event.timestamp,
            frame_number=event.frame_number,
            event_type=event.event_type,
            intensity=event.intensity,
            duration=event.duration,
            data=event.data
        )
        
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        
        logger.info(f"Emotion event logged: {event.event_type} for session {event.session_id}")
        return db_event
        
    except Exception as e:
        logger.error(f"Error logging emotion event: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log emotion event: {str(e)}"
        )


@router.get("/emotion-events/session/{session_id}", response_model=List[EmotionEventResponse])
async def get_session_emotion_events(
    session_id: str,
    event_type: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get all emotion events for a specific session
    Optionally filter by event type
    """
    try:
        query = db.query(EmotionEvent).filter(EmotionEvent.session_id == session_id)
        
        if event_type:
            query = query.filter(EmotionEvent.event_type == event_type)
        
        events = query.order_by(EmotionEvent.timestamp).limit(limit).all()
        
        logger.info(f"Retrieved {len(events)} emotion events for session {session_id}")
        return events
        
    except Exception as e:
        logger.error(f"Error retrieving emotion events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve emotion events: {str(e)}"
        )


@router.get("/emotion-events/stats/{session_id}")
async def get_session_emotion_stats(session_id: str, db: Session = Depends(get_db)):
    """
    Get emotion statistics for a session
    Returns aggregated emotion data and event counts
    """
    try:
        events = db.query(EmotionEvent).filter(EmotionEvent.session_id == session_id).all()
        
        if not events:
            return {
                "session_id": session_id,
                "total_events": 0,
                "event_types": {},
                "avg_intensity": 0.0,
                "emotion_distribution": {}
            }
        
        # Count events by type
        event_types = {}
        intensities = []
        
        for event in events:
            event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
            if event.intensity is not None:
                intensities.append(event.intensity)
        
        avg_intensity = sum(intensities) / len(intensities) if intensities else 0.0
        
        return {
            "session_id": session_id,
            "total_events": len(events),
            "event_types": event_types,
            "avg_intensity": avg_intensity,
            "most_frequent_event": max(event_types, key=event_types.get) if event_types else None
        }
        
    except Exception as e:
        logger.error(f"Error calculating emotion stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate emotion stats: {str(e)}"
        )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_eye_openness(landmarks: List, eye: str) -> float:
    """Calculate eye openness (0=closed, 1=open)"""
    try:
        if eye == "left":
            # Left eye landmarks: 159 (top), 145 (bottom)
            top = landmarks[159] if len(landmarks) > 159 else {"y": 0}
            bottom = landmarks[145] if len(landmarks) > 145 else {"y": 0}
        else:
            # Right eye landmarks: 386 (top), 374 (bottom)
            top = landmarks[386] if len(landmarks) > 386 else {"y": 0}
            bottom = landmarks[374] if len(landmarks) > 374 else {"y": 0}
        
        openness = abs(bottom.get("y", 0) - top.get("y", 0))
        return min(1.0, openness * 20)  # Normalize
    except Exception:
        return 0.5


def calculate_eyebrow_height(landmarks: List) -> float:
    """Calculate eyebrow height (surprise indicator)"""
    try:
        # Left eyebrow: 70, right eyebrow: 300
        left_brow = landmarks[70] if len(landmarks) > 70 else {"y": 0}
        right_brow = landmarks[300] if len(landmarks) > 300 else {"y": 0}
        nose = landmarks[1] if len(landmarks) > 1 else {"y": 0.5}
        
        avg_brow_y = (left_brow.get("y", 0) + right_brow.get("y", 0)) / 2
        nose_y = nose.get("y", 0.5)
        
        height = abs(nose_y - avg_brow_y)
        return min(1.0, height * 5)  # Normalize
    except Exception:
        return 0.5


def calculate_mouth_openness(landmarks: List) -> float:
    """Calculate how open the mouth is"""
    try:
        # Mouth top: 13, mouth bottom: 14
        top = landmarks[13] if len(landmarks) > 13 else {"y": 0}
        bottom = landmarks[14] if len(landmarks) > 14 else {"y": 0}
        
        openness = abs(bottom.get("y", 0) - top.get("y", 0))
        return min(1.0, openness * 15)  # Normalize
    except Exception:
        return 0.0


# ============================================================================
# RECOVERY & EXPORT ENDPOINTS (Database-First Features)
# ============================================================================

@router.get("/sessions/interrupted")
async def list_interrupted_sessions(db: Session = Depends(get_db)):
    """
    List sessions that need recovery (interrupted or still active but old)
    
    Returns sessions with status='interrupted' or status='active' with 
    last_save_timestamp older than 5 minutes
    """
    try:
        import time
        from src.custom_live_ai.models.database import Session as DBSession
        
        current_time = time.time()
        timeout_threshold = current_time - (5 * 60)  # 5 minutes ago
        
        # Query interrupted sessions or active sessions that are stale
        interrupted = db.query(DBSession).filter(
            (DBSession.status == "interrupted") |
            ((DBSession.status == "active") & 
             (DBSession.last_save_timestamp < timeout_threshold))
        ).all()
        
        results = []
        for session in interrupted:
            results.append({
                "session_id": session.session_id,
                "user_id": session.user_id,
                "status": session.status,
                "start_time": session.start_time.isoformat() if session.start_time else None,
                "last_save_timestamp": session.last_save_timestamp,
                "frames_saved": session.frames_saved_count or 0
            })
        
        logger.info(f"Found {len(results)} interrupted/stale sessions")
        return {
            "interrupted_sessions": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Error listing interrupted sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list interrupted sessions: {str(e)}"
        )


@router.post("/sessions/{session_id}/recover")
async def recover_session(session_id: str, db: Session = Depends(get_db)):
    """
    Recover an interrupted session
    
    Updates session status to 'completed' and calculates final statistics
    based on saved frames
    """
    try:
        from src.custom_live_ai.models.database import Session as DBSession, Frame
        
        # Find session
        session = db.query(DBSession).filter(DBSession.session_id == session_id).first()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        # Check if session needs recovery
        if session.status == "completed":
            return {
                "success": True,
                "message": "Session already completed",
                "session_id": session_id
            }
        
        # Count frames in database
        frame_count = db.query(Frame).filter(Frame.session_id == session_id).count()
        
        # Calculate duration if not set
        if not session.duration and session.start_time:
            from datetime import datetime
            end_time = datetime.utcnow()
            duration = (end_time - session.start_time).total_seconds()
        else:
            duration = session.duration or 0
        
        # Update session
        session.status = "completed"
        session.total_frames = frame_count
        session.frames_saved_count = frame_count
        if not session.end_time:
            from datetime import datetime
            session.end_time = datetime.utcnow()
        if not session.duration:
            session.duration = duration
        if duration > 0 and frame_count > 0:
            session.avg_fps = frame_count / duration
        
        db.commit()
        
        logger.info(f"✅ Recovered session: {session_id} ({frame_count} frames)")
        
        return {
            "success": True,
            "message": "Session recovered successfully",
            "session_id": session_id,
            "frames_recovered": frame_count,
            "duration": duration,
            "status": "completed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recovering session: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to recover session: {str(e)}"
        )


@router.get("/sessions/{session_id}/export/json")
async def export_session_json(session_id: str, db: Session = Depends(get_db)):
    """
    Export session data from database to JSON file
    
    Returns the JSON file as a download
    """
    try:
        from src.custom_live_ai.utils.detailed_recorder import DetailedRecorder
        from fastapi.responses import FileResponse
        
        # Create recorder with database session
        recorder = DetailedRecorder(use_database=True, db_session=db)
        
        # Export to JSON
        filepath = recorder.export_to_json(session_id=session_id)
        
        # Return as file download
        return FileResponse(
            filepath,
            media_type="application/json",
            filename=f"{session_id}_detailed.json"
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error exporting session to JSON: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export session: {str(e)}"
        )


@router.get("/sessions/{session_id}/export/csv")
async def export_session_csv(session_id: str, db: Session = Depends(get_db)):
    """
    Export session frame data as CSV
    
    Returns CSV with frame-by-frame metrics
    """
    try:
        from src.custom_live_ai.models.database import Frame
        from fastapi.responses import StreamingResponse
        import csv
        import io
        
        # Query frames
        frames = db.query(Frame).filter(
            Frame.session_id == session_id
        ).order_by(Frame.frame_number).all()
        
        if not frames:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No frames found for session {session_id}"
            )
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'frame_number', 'timestamp', 'emotion_label', 'emotion_confidence',
            'face_detected', 'pose_detected', 'hands_detected'
        ])
        writer.writeheader()
        
        for frame in frames:
            emotion = frame.emotion_data or {}
            writer.writerow({
                'frame_number': frame.frame_number,
                'timestamp': round(frame.timestamp, 3),
                'emotion_label': emotion.get('label', 'Unknown'),
                'emotion_confidence': emotion.get('confidence', 0),
                'face_detected': 'Yes' if frame.face_mesh_landmarks else 'No',
                'pose_detected': 'Yes' if frame.pose_landmarks else 'No',
                'hands_detected': 'Yes' if frame.hand_landmarks else 'No'
            })
        
        # Return CSV as streaming response
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={session_id}_frames.csv"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting session to CSV: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export session: {str(e)}"
        )

