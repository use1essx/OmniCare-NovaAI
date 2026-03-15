"""
Intervention Rules
Define when and how interventions should be triggered
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PostureRule:
    """
    Rule for posture-related interventions
    """
    # Trigger conditions
    poor_posture_duration_sec: float = 180.0  # 3 minutes
    slouch_count_threshold: int = 5
    slouch_window_sec: float = 600.0  # 10 minutes
    
    # Cooldown settings
    cooldown_sec: float = 300.0  # 5 minutes between posture reminders
    
    # Message templates
    messages: dict = None
    
    def __post_init__(self):
        if self.messages is None:
            self.messages = {
                "poor_posture": "Please check your posture. Try to sit up straight.",
                "slouching": "You've been slouching frequently. Remember to keep your back straight!",
                "posture_coaching": "Let's improve your posture! Align your shoulders and keep your chin up."
            }


@dataclass
class EmotionRule:
    """
    Rule for emotion-based interventions
    """
    # Trigger conditions
    negative_emotion_duration_sec: float = 120.0  # 2 minutes
    stress_threshold: float = 0.6  # Threshold for stress/angry/fear emotions
    
    # Negative emotions to monitor
    negative_emotions: tuple = ("sad", "angry", "fear")
    
    # Cooldown settings
    cooldown_sec: float = 180.0  # 3 minutes between emotion support
    
    # Message templates
    messages: dict = None
    
    def __post_init__(self):
        if self.messages is None:
            self.messages = {
                "sad": "I notice you might be feeling down. Would you like to take a short break?",
                "angry": "Take a deep breath. It's okay to step back for a moment.",
                "fear": "I'm here to support you. You're doing great.",
                "general_support": "Remember to take care of yourself. You're making good progress."
            }


@dataclass
class BreakRule:
    """
    Rule for break reminders
    """
    # Trigger conditions
    session_duration_threshold_sec: float = 2700.0  # 45 minutes
    break_interval_sec: float = 3600.0  # 1 hour
    
    # Cooldown settings
    cooldown_sec: float = 600.0  # 10 minutes between break reminders
    
    # Message templates
    messages: dict = None
    
    def __post_init__(self):
        if self.messages is None:
            self.messages = {
                "first_break": "You've been working for 45 minutes. Consider taking a short break.",
                "regular_break": "Time for a break! Stretch and rest your eyes for a few minutes.",
                "hydration": "Don't forget to drink some water and take a short break."
            }


@dataclass
class EngagementRule:
    """
    Rule for engagement and focus interventions
    """
    # Trigger conditions
    low_face_detection_duration_sec: float = 60.0  # 1 minute
    low_face_detection_rate: float = 0.3  # Below 30% face detection
    
    low_eye_contact_duration_sec: float = 120.0  # 2 minutes
    low_eye_contact_threshold: float = 0.4  # Below 40% eye contact
    
    # Cooldown settings
    cooldown_sec: float = 240.0  # 4 minutes between engagement reminders
    
    # Message templates
    messages: dict = None
    
    def __post_init__(self):
        if self.messages is None:
            self.messages = {
                "low_visibility": "I'm having trouble seeing you. Please check your camera position.",
                "low_engagement": "Stay focused! You're doing well.",
                "eye_contact": "Try to maintain eye contact with the camera for better tracking."
            }


class InterventionRuleSet:
    """
    Container for all intervention rules
    """
    def __init__(
        self,
        posture_rule: Optional[PostureRule] = None,
        emotion_rule: Optional[EmotionRule] = None,
        break_rule: Optional[BreakRule] = None,
        engagement_rule: Optional[EngagementRule] = None
    ):
        self.posture_rule = posture_rule or PostureRule()
        self.emotion_rule = emotion_rule or EmotionRule()
        self.break_rule = break_rule or BreakRule()
        self.engagement_rule = engagement_rule or EngagementRule()
    
    def get_all_rules(self):
        """Get all rules as a dictionary"""
        return {
            "posture": self.posture_rule,
            "emotion": self.emotion_rule,
            "break": self.break_rule,
            "engagement": self.engagement_rule
        }

