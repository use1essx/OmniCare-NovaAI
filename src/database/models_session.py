"""
Session Storage Models for ADK Tools
Manages conversation sessions, Q&A pairs, and video metadata
"""


from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    DECIMAL,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.connection import Base


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class ScreeningSession(Base, TimestampMixin):
    """
    Screening session model for managing conversation-based assessments
    Tracks the entire lifecycle of a screening session from start to completion
    """
    
    __tablename__ = "screening_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    # Session Type and Purpose
    session_type = Column(String(50), default="screening", nullable=False, index=True)
    # session_type: "screening", "follow_up", "reassessment", "casual_chat"
    
    questionnaire_id = Column(Integer, ForeignKey("questionnaire_banks.id"), index=True)
    # Links to the questionnaire being administered (if applicable)
    
    # Session Status
    status = Column(String(50), default="created", nullable=False, index=True)
    # status: "created", "in_progress", "paused", "completed", "abandoned", "error"
    
    # Progress Tracking
    total_questions = Column(Integer, default=0)
    answered_questions = Column(Integer, default=0)
    progress_percentage = Column(DECIMAL(5, 2), default=0.0)
    
    # Timing
    started_at = Column(DateTime(timezone=True), index=True)
    completed_at = Column(DateTime(timezone=True), index=True)
    duration_seconds = Column(Integer)  # Total session duration
    
    # Agent Information
    primary_agent = Column(String(50), default="screening_agent", index=True)
    # primary_agent: "screening_agent", "mental_health", "illness_monitor", etc.
    
    agent_handoffs = Column(JSONB)  # Track agent switches during session
    # Format: [{"from": "screening", "to": "safety", "timestamp": "...", "reason": "crisis"}]
    
    # Language and Context
    language = Column(String(10), default="en", index=True)
    cultural_context = Column(JSONB)  # HK-specific context data
    
    # Video/Audio Metadata
    has_video = Column(Boolean, default=False)
    has_audio = Column(Boolean, default=True)
    
    video_metadata = Column(JSONB)
    # Format: {
    #   "recording_started": "timestamp",
    #   "recording_ended": "timestamp",
    #   "file_path": "s3://bucket/session_123.mp4",
    #   "file_size_mb": 145.2,
    #   "duration_seconds": 1850,
    #   "resolution": "1280x720",
    #   "fps": 30,
    #   "codec": "h264"
    # }
    
    audio_metadata = Column(JSONB)
    # Format: {
    #   "recording_started": "timestamp",
    #   "recording_ended": "timestamp",
    #   "file_path": "s3://bucket/session_123.mp3",
    #   "file_size_mb": 25.5,
    #   "duration_seconds": 1850,
    #   "sample_rate": 44100,
    #   "codec": "mp3"
    # }
    
    # Session Summary and Scores
    preliminary_scores = Column(JSONB)
    # Real-time scores built during conversation (50-70% confidence)
    # Format: {
    #   "mood": 3.8,
    #   "stress": 2.5,
    #   "support": 4.2,
    #   "confidence_level": 0.65
    # }
    
    final_scores = Column(JSONB)
    # Final scores after professional review (Phase 2)
    
    category_scores = Column(JSONB)
    # Detailed scores by category
    # Format: {
    #   "mood": {"score": 3.8, "interpretation": "good", "flagged": false},
    #   "stress": {"score": 2.5, "interpretation": "concerning", "flagged": true}
    # }
    
    # Flags and Alerts
    safety_flags = Column(JSONB)
    # Critical safety concerns detected
    # Format: [{"type": "self_harm", "timestamp": "...", "context": "..."}]
    
    clinical_flags = Column(JSONB)
    # Clinical concerns requiring attention
    
    # Session Notes
    session_notes = Column(Text)  # Automated notes
    professional_notes = Column(Text)  # Added by healthcare professional (Phase 2)
    
    # Quality Metrics
    completion_quality = Column(String(20))  # "excellent", "good", "partial", "poor"
    user_engagement_score = Column(DECIMAL(3, 2))
    # 0-5 scale, based on response times, interaction patterns
    
    technical_issues = Column(JSONB)
    # Track any technical problems during session
    # Format: [{"type": "connection_loss", "timestamp": "...", "duration": 30}]
    
    # Review Status (Phase 2)
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(DateTime(timezone=True))
    review_status = Column(String(50))  # "pending", "in_review", "approved", "needs_revision"
    
    # Metadata
    session_metadata = Column(JSONB)
    # Additional session-specific data
    
    # Indexes
    __table_args__ = (
        Index('idx_session_user_status', 'user_id', 'status'),
        Index('idx_session_type_status', 'session_type', 'status'),
        Index('idx_session_created_status', 'created_at', 'status'),
    )
    
    # Relationships
    qa_pairs = relationship("SessionQAPair", back_populates="session", cascade="all, delete-orphan")
    user = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    
    def __repr__(self):
        return f"<ScreeningSession(id={self.id}, session_id='{self.session_id}', status='{self.status}')>"


class SessionQAPair(Base, TimestampMixin):
    """
    Question-Answer pairs within a screening session
    Stores each interaction between AI and user
    """
    
    __tablename__ = "session_qa_pairs"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("screening_sessions.id"), nullable=False, index=True)
    
    # Question Information
    question_id = Column(Integer, ForeignKey("questionnaire_questions.id"), index=True)
    # Links to the specific question from question bank
    
    question_code = Column(String(50), index=True)  # e.g., "Q001", "MOOD_01"
    question_text = Column(Text, nullable=False)
    question_category = Column(String(50), index=True)
    
    # Sequence and Timing
    sequence_order = Column(Integer, nullable=False)
    # Order in which this question was asked
    
    asked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    answered_at = Column(DateTime(timezone=True), index=True)
    response_time_seconds = Column(Integer)
    # Time taken to answer
    
    # Answer Information
    user_answer = Column(Text)
    # Raw user response (text, voice transcription)
    
    answer_value = Column(Integer)
    # Numeric value (for scale questions: 1-5)
    
    answer_option = Column(String(255))
    # Selected option text (for multiple choice)
    
    # Scoring
    question_score = Column(DECIMAL(3, 2))
    # Individual question score
    
    contributes_to_category = Column(String(50))
    # Which category this question scores towards
    
    # AI Processing
    intent_detected = Column(String(100))
    sentiment_score = Column(DECIMAL(3, 2))
    emotion_detected = Column(String(50))
    # Emotion from voice/video analysis
    
    # Follow-up and Clarification
    required_clarification = Column(Boolean, default=False)
    clarification_count = Column(Integer, default=0)
    # How many times AI had to rephrase/clarify
    
    skipped = Column(Boolean, default=False)
    skip_reason = Column(String(255))
    
    # Flags
    flagged = Column(Boolean, default=False)
    flag_reason = Column(String(255))
    # e.g., "concerning_answer", "safety_risk", "inconsistent"
    
    # Video/Audio Markers
    video_timestamp = Column(Integer)
    # Timestamp in video recording (seconds from start)
    
    audio_timestamp = Column(Integer)
    # Timestamp in audio recording
    
    behavioral_markers = Column(JSONB)
    # Video analysis markers for this Q&A
    # Format: {
    #   "eye_contact": 0.75,
    #   "fidgeting": true,
    #   "facial_expression": "neutral",
    #   "speech_rate": 145  # words per minute
    # }
    
    # Metadata
    qa_metadata = Column(JSONB)
    
    # Indexes
    __table_args__ = (
        Index('idx_qa_session_sequence', 'session_id', 'sequence_order'),
        Index('idx_qa_category', 'question_category'),
        Index('idx_qa_flagged', 'flagged'),
    )
    
    # Relationships
    session = relationship("ScreeningSession", back_populates="qa_pairs")
    
    def __repr__(self):
        return f"<SessionQAPair(id={self.id}, session_id={self.session_id}, question_code='{self.question_code}')>"


class SessionEvent(Base, TimestampMixin):
    """
    Session events and state changes
    Tracks important moments during a session
    """
    
    __tablename__ = "session_events"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("screening_sessions.id"), nullable=False, index=True)
    
    # Event Information
    event_type = Column(String(50), nullable=False, index=True)
    # event_type: "session_started", "paused", "resumed", "completed", "error",
    #             "safety_flag", "agent_handoff", "technical_issue"
    
    event_category = Column(String(50), index=True)
    # "lifecycle", "safety", "technical", "clinical"
    
    event_description = Column(Text)
    
    # Event Data
    event_data = Column(JSONB)
    # Detailed event information
    
    severity = Column(String(20))  # "info", "warning", "error", "critical"
    
    # Timing
    event_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Video/Audio Position
    video_timestamp = Column(Integer)  # Second in video where event occurred
    
    # Action Taken
    action_required = Column(Boolean, default=False)
    action_taken = Column(String(255))
    action_by = Column(Integer, ForeignKey("users.id"))
    
    # Metadata
    event_metadata = Column(JSONB)
    
    # Indexes
    __table_args__ = (
        Index('idx_event_session_type', 'session_id', 'event_type'),
        Index('idx_event_timestamp', 'event_timestamp'),
    )
    
    def __repr__(self):
        return f"<SessionEvent(id={self.id}, type='{self.event_type}', session_id={self.session_id})>"

