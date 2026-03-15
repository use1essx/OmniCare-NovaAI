"""
Report Data Schemas
Pydantic models for structured session reports
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime


class EmotionChange(BaseModel):
    """Single emotion change event"""
    timestamp: float
    from_emotion: str
    to_emotion: str
    confidence: float


class EmotionTimelineReport(BaseModel):
    """Emotion timeline analysis"""
    dominant_emotion: str = Field(..., description="Most frequent emotion")
    dominant_percentage: float = Field(..., description="Percentage of time in dominant emotion")
    emotion_distribution: Dict[str, float] = Field(..., description="Distribution of all emotions (%)")
    emotion_changes: List[EmotionChange] = Field(..., description="List of emotion transitions")
    emotion_stability: float = Field(..., description="Stability score (0-1, higher = more stable)")
    total_changes: int = Field(..., description="Total number of emotion changes")


class PostureEvent(BaseModel):
    """Single posture event"""
    timestamp: float
    event_type: str
    severity: float


class PostureAnalysisReport(BaseModel):
    """Posture quality analysis"""
    average_quality: str = Field(..., description="Average posture quality")
    quality_distribution: Dict[str, float] = Field(..., description="Distribution of posture qualities (%)")
    slouch_events: List[PostureEvent] = Field(..., description="List of slouching events")
    total_slouches: int = Field(..., description="Total number of slouch events")
    improvement_score: float = Field(..., description="Posture improvement score (-1 to 1)")
    posture_stability: float = Field(..., description="Stability score (0-1)")


class EngagementReport(BaseModel):
    """User engagement metrics"""
    face_detection_rate: float = Field(..., ge=0, le=1, description="Percentage of frames with face detected")
    average_eye_contact: Optional[float] = Field(None, ge=0, le=1, description="Average eye contact score")
    engagement_level: float = Field(..., ge=0, le=1, description="Overall engagement level")
    attention_span_minutes: float = Field(..., description="Estimated attention span in minutes")


class BehavioralPattern(BaseModel):
    """Detected behavioral pattern"""
    pattern_type: str
    description: str
    confidence: float
    recommendation: Optional[str] = None


class BehavioralInsightsReport(BaseModel):
    """Behavioral insights and patterns"""
    patterns_detected: List[BehavioralPattern] = Field(..., description="List of detected patterns")
    key_findings: List[str] = Field(..., description="Key behavioral findings")
    recommendations: List[str] = Field(..., description="Recommendations for improvement")


class InterventionSummary(BaseModel):
    """Summary of interventions during session"""
    total_interventions: int
    interventions_by_type: Dict[str, int]
    intervention_effectiveness: float = Field(..., ge=0, le=1)


class KeyMoment(BaseModel):
    """Significant moment in the session"""
    time: str = Field(..., description="When it happened (e.g., '5:30')")
    event: str = Field(..., description="What happened")
    significance: str = Field(..., description="Why it matters")


class BehavioralPatternAI(BaseModel):
    """AI-detected behavioral pattern"""
    pattern: str = Field(..., description="The pattern observed")
    frequency: str = Field(..., description="How often it occurs")
    recommendation: str = Field(..., description="What to do about it")


class AIInsights(BaseModel):
    """AI-generated insights from session data"""
    executive_summary: str = Field(..., description="High-level overview of the session")
    emotional_journey: str = Field(..., description="Emotional progression throughout session")
    key_moments: List[KeyMoment] = Field(default_factory=list, description="Significant moments")
    behavioral_patterns: List[BehavioralPatternAI] = Field(default_factory=list, description="Patterns observed")
    posture_insights: str = Field(..., description="Posture analysis and ergonomics")
    engagement_analysis: str = Field(..., description="Engagement patterns and changes")
    wellness_score: int = Field(..., ge=0, le=100, description="Overall wellness score")
    wellness_explanation: str = Field(..., description="Explanation of wellness score")
    recommendations: List[str] = Field(default_factory=list, description="Actionable recommendations")
    positive_highlights: List[str] = Field(default_factory=list, description="Things done well")
    areas_for_improvement: List[str] = Field(default_factory=list, description="Areas to improve")
    
    # Token usage tracking
    tokens_used: Optional[int] = Field(None, description="API tokens used")
    model_used: Optional[str] = Field(None, description="AI model used")


class DetailedTimelinePoint(BaseModel):
    """Single point in detailed session timeline"""
    timestamp: float = Field(..., description="Seconds from session start")
    minute: int = Field(..., description="Minute number in session")
    event_type: str = Field(..., description="Type: emotion, posture, intervention, engagement")
    data: str = Field(..., description="Human-readable event description")
    metadata: Optional[Dict] = Field(None, description="Additional event data")


class SessionReport(BaseModel):
    """Complete session report"""
    session_id: str
    user_id: Optional[str] = None
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    
    # Sub-reports
    emotion_timeline: EmotionTimelineReport
    posture_analysis: PostureAnalysisReport
    engagement: EngagementReport
    behavioral_insights: BehavioralInsightsReport
    intervention_summary: Optional[InterventionSummary] = None
    
    # AI-generated insights (NEW!)
    ai_insights: Optional[AIInsights] = Field(None, description="AI-generated personalized insights")
    
    # Detailed timeline (NEW!)
    detailed_timeline: List[DetailedTimelinePoint] = Field(
        default_factory=list, 
        description="Minute-by-minute timeline of what happened"
    )
    
    # Overall metrics
    overall_quality_score: float = Field(..., ge=0, le=100, description="Overall session quality (0-100)")
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    report_version: str = "2.0"  # Updated version with AI insights



