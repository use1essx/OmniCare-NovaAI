"""
Intervention Engine
Monitors user behavior and triggers appropriate interventions
"""

import time
import logging
from typing import Dict, List, Optional, Tuple
from collections import deque
from dataclasses import dataclass

from .rules import InterventionRuleSet

logger = logging.getLogger(__name__)


@dataclass
class InterventionEvent:
    """
    Represents a single intervention event
    """
    timestamp: float
    intervention_type: str
    trigger_reason: str
    message: str
    tone_used: str
    session_id: str


class SessionState:
    """
    Tracks state for a single session to determine interventions
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.start_time = time.time()
        self.last_intervention_times: Dict[str, float] = {}
        
        # Posture tracking
        self.poor_posture_start: Optional[float] = None
        self.slouch_events: deque = deque(maxlen=20)  # Track last 20 slouch events
        self.current_posture_quality: Optional[str] = None  # Current posture quality (excellent, good, poor)
        
        # Emotion tracking
        self.negative_emotion_start: Optional[float] = None
        self.current_emotion: Optional[str] = None
        self.emotion_history: deque = deque(maxlen=60)  # Track last minute of emotions
        
        # Engagement tracking
        self.low_face_detection_start: Optional[float] = None
        self.low_eye_contact_start: Optional[float] = None
        
        # Break tracking
        self.last_break_reminder: Optional[float] = None
        
        # Intervention history
        self.intervention_history: List[InterventionEvent] = []
    
    def get_session_duration(self) -> float:
        """Get current session duration in seconds"""
        return time.time() - self.start_time
    
    def add_intervention(self, event: InterventionEvent):
        """Record an intervention event"""
        self.intervention_history.append(event)
        self.last_intervention_times[event.intervention_type] = time.time()
    
    def can_intervene(self, intervention_type: str, cooldown_sec: float) -> bool:
        """Check if enough time has passed since last intervention of this type"""
        last_time = self.last_intervention_times.get(intervention_type)
        if last_time is None:
            return True
        return (time.time() - last_time) >= cooldown_sec


class InterventionEngine:
    """
    Main intervention engine that monitors sessions and triggers interventions
    """
    
    def __init__(self, rules: Optional[InterventionRuleSet] = None):
        """
        Initialize intervention engine
        
        Args:
            rules: Custom intervention rules (uses defaults if None)
        """
        self.rules = rules or InterventionRuleSet()
        self.active_sessions: Dict[str, SessionState] = {}
        logger.info("✅ InterventionEngine initialized with default rules")
    
    def start_session(self, session_id: str):
        """
        Start monitoring a new session
        
        Args:
            session_id: Unique session identifier
        """
        self.active_sessions[session_id] = SessionState(session_id)
        logger.info(f"📊 Started monitoring session: {session_id}")
    
    def stop_session(self, session_id: str) -> Dict:
        """
        Stop monitoring a session and return summary
        
        Args:
            session_id: Session identifier
            
        Returns:
            Summary of interventions for this session
        """
        if session_id not in self.active_sessions:
            return {"error": "Session not found"}
        
        state = self.active_sessions[session_id]
        duration = state.get_session_duration()
        summary = {
            "session_id": session_id,
            "duration_sec": duration,
            "duration_seconds": duration,  # For test compatibility
            "intervention_count": len(state.intervention_history),
            "interventions_by_type": {},
            "interventions": [
                {
                    "time": e.timestamp,
                    "type": e.intervention_type,
                    "reason": e.trigger_reason,
                    "message": e.message,
                    "tone": e.tone_used
                }
                for e in state.intervention_history
            ]
        }
        
        # Count interventions by type
        for event in state.intervention_history:
            itype = event.intervention_type
            summary["interventions_by_type"][itype] = summary["interventions_by_type"].get(itype, 0) + 1
        
        # Remove from active sessions
        del self.active_sessions[session_id]
        logger.info(f"🏁 Stopped monitoring session: {session_id} ({len(state.intervention_history)} interventions)")
        
        return summary
    
    def update_frame_data(
        self,
        session_id: str,
        posture_quality: Optional[str] = None,
        is_slouching: Optional[bool] = None,
        current_emotion: Optional[str] = None,
        face_detected: Optional[bool] = None,
        eye_contact_score: Optional[float] = None
    ):
        """
        Update session state with new frame data
        
        Args:
            session_id: Session identifier
            posture_quality: Current posture quality ("excellent", "good", "fair", "poor")
            is_slouching: Whether user is currently slouching
            current_emotion: Current dominant emotion
            face_detected: Whether face is detected
            eye_contact_score: Eye contact score (0-1)
        """
        if session_id not in self.active_sessions:
            logger.warning(f"Session {session_id} not found, starting new session")
            self.start_session(session_id)
        
        state = self.active_sessions[session_id]
        current_time = time.time()
        
        # Update posture state
        if posture_quality:
            state.current_posture_quality = posture_quality
            
        if posture_quality == "poor":
            if state.poor_posture_start is None:
                state.poor_posture_start = current_time
        else:
            state.poor_posture_start = None
        
        if is_slouching:
            state.slouch_events.append(current_time)
        
        # Update emotion state
        if current_emotion:
            state.current_emotion = current_emotion
            state.emotion_history.append((current_time, current_emotion))
            
            # Track negative emotions
            if current_emotion.lower() in self.rules.emotion_rule.negative_emotions:
                if state.negative_emotion_start is None:
                    state.negative_emotion_start = current_time
            else:
                state.negative_emotion_start = None
        
        # Update engagement state
        if face_detected is False:
            if state.low_face_detection_start is None:
                state.low_face_detection_start = current_time
        else:
            state.low_face_detection_start = None
        
        if eye_contact_score is not None and eye_contact_score < self.rules.engagement_rule.low_eye_contact_threshold:
            if state.low_eye_contact_start is None:
                state.low_eye_contact_start = current_time
        else:
            state.low_eye_contact_start = None
    
    def check_interventions(self, session_id: str) -> List[Tuple[str, str, str]]:
        """
        Check if any interventions should be triggered
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of (intervention_type, trigger_reason, message) tuples
        """
        if session_id not in self.active_sessions:
            return []
        
        state = self.active_sessions[session_id]
        current_time = time.time()
        interventions = []
        
        # Check posture interventions
        if state.poor_posture_start:
            duration = current_time - state.poor_posture_start
            if duration >= self.rules.posture_rule.poor_posture_duration_sec:
                if state.can_intervene("posture_reminder", self.rules.posture_rule.cooldown_sec):
                    interventions.append((
                        "posture_reminder",
                        f"poor_posture_{int(duration)}sec",
                        self.rules.posture_rule.messages["poor_posture"]
                    ))
        
        # Check slouch frequency
        recent_slouches = [t for t in state.slouch_events if (current_time - t) <= self.rules.posture_rule.slouch_window_sec]
        if len(recent_slouches) >= self.rules.posture_rule.slouch_count_threshold:
            if state.can_intervene("posture_coaching", self.rules.posture_rule.cooldown_sec):
                interventions.append((
                    "posture_coaching",
                    f"slouch_{len(recent_slouches)}_times_in_{int(self.rules.posture_rule.slouch_window_sec)}sec",
                    self.rules.posture_rule.messages["posture_coaching"]
                ))
        
        # Check emotion interventions
        if state.negative_emotion_start and state.current_emotion:
            duration = current_time - state.negative_emotion_start
            if duration >= self.rules.emotion_rule.negative_emotion_duration_sec:
                if state.can_intervene("emotion_support", self.rules.emotion_rule.cooldown_sec):
                    message = self.rules.emotion_rule.messages.get(
                        state.current_emotion.lower(),
                        self.rules.emotion_rule.messages["general_support"]
                    )
                    interventions.append((
                        "emotion_support",
                        f"negative_emotion_{state.current_emotion}_{int(duration)}sec",
                        message
                    ))
        
        # Check break interventions
        session_duration = state.get_session_duration()
        if session_duration >= self.rules.break_rule.session_duration_threshold_sec:
            if state.can_intervene("break_suggestion", self.rules.break_rule.cooldown_sec):
                if state.last_break_reminder is None:
                    message = self.rules.break_rule.messages["first_break"]
                else:
                    message = self.rules.break_rule.messages["regular_break"]
                interventions.append((
                    "break_suggestion",
                    f"session_duration_{int(session_duration)}sec",
                    message
                ))
                state.last_break_reminder = current_time
        
        # Check engagement interventions
        if state.low_face_detection_start:
            duration = current_time - state.low_face_detection_start
            if duration >= self.rules.engagement_rule.low_face_detection_duration_sec:
                if state.can_intervene("engagement_reminder", self.rules.engagement_rule.cooldown_sec):
                    interventions.append((
                        "engagement_reminder",
                        f"low_face_detection_{int(duration)}sec",
                        self.rules.engagement_rule.messages["low_visibility"]
                    ))
        
        if state.low_eye_contact_start:
            duration = current_time - state.low_eye_contact_start
            if duration >= self.rules.engagement_rule.low_eye_contact_duration_sec:
                if state.can_intervene("engagement_reminder", self.rules.engagement_rule.cooldown_sec):
                    interventions.append((
                        "engagement_reminder",
                        f"low_eye_contact_{int(duration)}sec",
                        self.rules.engagement_rule.messages["eye_contact"]
                    ))
        
        return interventions
    
    def get_session_state(self, session_id: str) -> Optional[Dict]:
        """
        Get current state of a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with session state or None if not found
        """
        if session_id not in self.active_sessions:
            return None
        
        state = self.active_sessions[session_id]
        return {
            "session_id": session_id,
            "session_duration_sec": state.get_session_duration(),
            "duration_sec": state.get_session_duration(),  # For backward compatibility
            "current_emotion": state.current_emotion,
            "current_posture_quality": state.current_posture_quality,
            "intervention_count": len(state.intervention_history),
            "is_tracking_poor_posture": state.poor_posture_start is not None,
            "is_tracking_negative_emotion": state.negative_emotion_start is not None
        }

