"""
Session Metrics Calculator
Calculates real-time metrics during active recording sessions
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from collections import deque
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class EmotionPoint:
    """Single emotion data point"""
    timestamp: float
    emotion: str
    confidence: float


@dataclass
class PostureEvent:
    """Single posture event"""
    timestamp: float
    event_type: str  # "good_posture", "poor_posture", "slouch", "improvement"
    severity: float  # 0.0-1.0


class SessionMetrics:
    """
    Calculates real-time metrics for an active session
    """
    
    def __init__(self, session_id: str, window_size: int = 300):
        """
        Initialize session metrics calculator
        
        Args:
            session_id: Session identifier
            window_size: Number of recent frames to consider for metrics
        """
        self.session_id = session_id
        self.window_size = window_size
        
        # Emotion tracking
        self.emotion_points: List[EmotionPoint] = []  # For test compatibility
        self.emotion_timeline: List[EmotionPoint] = self.emotion_points  # Alias
        self.emotion_window: deque = deque(maxlen=window_size)
        
        # Posture tracking
        self.posture_events: List[PostureEvent] = []
        self.posture_window: deque = deque(maxlen=window_size)
        
        # Engagement tracking
        self.engagement_data: List[Dict] = []  # For test compatibility
        self.face_detection_history: deque = deque(maxlen=window_size)
        self.eye_contact_history: deque = deque(maxlen=window_size)
        
        # Intervention tracking
        self.intervention_history: List[Dict] = []  # For test compatibility
        self.intervention_triggers: List[Dict] = self.intervention_history  # Alias
        
        logger.info(f"📊 SessionMetrics initialized for session: {session_id}")
    
    def add_emotion_point(self, timestamp: float, emotion: str, confidence: float):
        """
        Add emotion data point
        
        Args:
            timestamp: Frame timestamp
            emotion: Detected emotion
            confidence: Detection confidence (0-1)
        """
        point = EmotionPoint(timestamp, emotion, confidence)
        self.emotion_points.append(point)
        self.emotion_window.append(point)
    
    def add_posture_event(self, timestamp: float, event_type: str, severity: float = 0.5):
        """
        Add posture event
        
        Args:
            timestamp: Event timestamp
            event_type: Type of posture event
            severity: Severity (0-1)
        """
        event = PostureEvent(timestamp, event_type, severity)
        self.posture_events.append(event)
        self.posture_window.append(event)
    
    def add_engagement_data(self, face_detected: bool, eye_contact_score: Optional[float] = None):
        """
        Add engagement data
        
        Args:
            face_detected: Whether face was detected
            eye_contact_score: Eye contact score (0-1)
        """
        self.engagement_data.append({
            "face_detected": face_detected,
            "eye_contact_score": eye_contact_score or 0.0
        })
        self.face_detection_history.append(1.0 if face_detected else 0.0)
        if eye_contact_score is not None:
            self.eye_contact_history.append(eye_contact_score)
    
    def add_intervention_trigger(self, timestamp: float, trigger_type: str, reason: str):
        """
        Record intervention trigger
        
        Args:
            timestamp: Trigger timestamp
            trigger_type: Type of intervention
            reason: Trigger reason
        """
        self.intervention_history.append({
            "timestamp": timestamp,
            "type": trigger_type,
            "reason": reason
        })
    
    def calculate_emotion_variance(self) -> float:
        """
        Calculate emotion variance (stability measure)
        
        Returns:
            Variance value (0 = very stable, higher = more variable)
        """
        if len(self.emotion_window) < 2:
            return 0.0
        
        # Count emotion changes
        changes = 0
        for i in range(1, len(self.emotion_window)):
            if self.emotion_window[i].emotion != self.emotion_window[i-1].emotion:
                changes += 1
        
        # Normalize by window size
        variance = changes / len(self.emotion_window)
        return variance
    
    def calculate_posture_stability(self) -> float:
        """
        Calculate posture stability score
        
        Returns:
            Stability score (0-1, higher = more stable/good)
        """
        if len(self.posture_window) == 0:
            return 0.5  # Neutral
        
        # Count poor posture events
        poor_events = sum(1 for e in self.posture_window if e.event_type in ["poor_posture", "slouch"])
        
        # Calculate stability (inverse of poor event rate)
        stability = 1.0 - (poor_events / len(self.posture_window))
        return max(0.0, min(1.0, stability))
    
    def calculate_posture_improvement(self) -> float:
        """
        Calculate posture improvement score during session
        
        Returns:
            Improvement score (-1 to 1, positive = improved, negative = worsened)
        """
        if len(self.posture_events) < 10:
            return 0.0  # Not enough data
        
        # Split into first half and second half
        mid = len(self.posture_events) // 2
        first_half = self.posture_events[:mid]
        second_half = self.posture_events[mid:]
        
        # Calculate average severity in each half (lower = better)
        first_avg = np.mean([e.severity for e in first_half if e.event_type in ["poor_posture", "slouch"]] or [0.0])
        second_avg = np.mean([e.severity for e in second_half if e.event_type in ["poor_posture", "slouch"]] or [0.0])
        
        # Improvement = reduction in severity
        improvement = first_avg - second_avg
        return max(-1.0, min(1.0, improvement))
    
    def calculate_engagement_level(self) -> float:
        """
        Calculate overall engagement level
        
        Returns:
            Engagement score (0-1, higher = more engaged)
        """
        if len(self.face_detection_history) == 0:
            return 0.0
        
        # Face detection rate (most important)
        face_rate = np.mean(self.face_detection_history)
        
        # Eye contact rate (if available)
        if len(self.eye_contact_history) > 0:
            eye_contact_rate = np.mean(self.eye_contact_history)
            # Weighted average: 60% face detection, 40% eye contact
            engagement = 0.6 * face_rate + 0.4 * eye_contact_rate
        else:
            engagement = face_rate
        
        return engagement
    
    def calculate_intervention_effectiveness(self) -> float:
        """
        Calculate intervention effectiveness score
        
        Returns:
            Effectiveness score (0-1, higher = more effective)
        """
        if len(self.intervention_history) == 0:
            return 0.0  # No interventions yet
        
        # Analyze posture improvement after interventions
        # (Simplified: check if posture events decreased after interventions)
        effectiveness_scores = []
        
        for trigger in self.intervention_history:
            if trigger["type"] in ["posture_reminder", "posture_coaching"]:
                # Check posture events in next 60 seconds
                trigger_time = trigger["timestamp"]
                after_events = [
                    e for e in self.posture_events
                    if e.timestamp > trigger_time and e.timestamp <= trigger_time + 60
                    and e.event_type in ["poor_posture", "slouch"]
                ]
                
                # Fewer events = more effective
                if len(after_events) < 3:
                    effectiveness_scores.append(0.8)
                elif len(after_events) < 5:
                    effectiveness_scores.append(0.5)
                else:
                    effectiveness_scores.append(0.2)
        
        if len(effectiveness_scores) == 0:
            return 0.5  # Neutral
        
        return np.mean(effectiveness_scores)
    
    def get_emotion_distribution(self) -> Dict[str, float]:
        """
        Get emotion distribution over session
        
        Returns:
            Dictionary with emotion percentages
        """
        if len(self.emotion_points) == 0:
            return {}
        
        # Count emotions
        emotion_counts = {}
        for point in self.emotion_points:
            emotion_counts[point.emotion] = emotion_counts.get(point.emotion, 0) + 1
        
        # Convert to percentages
        total = len(self.emotion_points)
        distribution = {
            emotion: (count / total) * 100
            for emotion, count in emotion_counts.items()
        }
        
        return distribution
    
    def get_dominant_emotion(self) -> Tuple[str, float]:
        """
        Get most frequent emotion
        
        Returns:
            Tuple of (emotion, percentage)
        """
        distribution = self.get_emotion_distribution()
        if not distribution:
            return ("neutral", 0.0)
        
        dominant = max(distribution.items(), key=lambda x: x[1])
        return dominant
    
    def get_summary(self) -> Dict:
        """
        Get complete metrics summary
        
        Returns:
            Dictionary with all calculated metrics
        """
        return {
            "session_id": self.session_id,
            "total_frames": len(self.emotion_window),
            "emotion_variance": self.calculate_emotion_variance(),
            "posture_stability": self.calculate_posture_stability(),
            "posture_improvement": self.calculate_posture_improvement(),
            "engagement_level": self.calculate_engagement_level(),
            "intervention_effectiveness": self.calculate_intervention_effectiveness(),
            "emotion_distribution": self.get_emotion_distribution(),
            "dominant_emotion": self.get_dominant_emotion()[0],
            "intervention_count": len(self.intervention_history),
            "total_interventions": len(self.intervention_history),  # For test compatibility
            "posture_events_count": len(self.posture_events)
        }


