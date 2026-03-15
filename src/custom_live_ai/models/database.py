"""
Database Models for Motion Capture and Emotion Tracking
SQLAlchemy ORM models for PostgreSQL
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    """
    User model for tracking individuals in the system
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<User(id={self.id}, user_id='{self.user_id}', name='{self.name}')>"


class Session(Base):
    """
    Session model for tracking motion capture recording sessions
    Links to User and stores comprehensive session statistics
    """
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(String(100), ForeignKey("users.user_id"), nullable=False, index=True)
    
    # Session timing
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration = Column(Float, nullable=True)  # Duration in seconds
    
    # Recording quality
    total_frames = Column(Integer, nullable=True)
    avg_fps = Column(Float, nullable=True)
    recording_quality = Column(String(50), nullable=True)  # Ultra Low, Low, Medium, High
    
    # File paths
    json_file = Column(String(500), nullable=True)
    csv_file = Column(String(500), nullable=True)
    
    # Detection rates
    face_detection_rate = Column(Float, nullable=True)  # 0.0 to 1.0
    
    # Average emotion metrics (from face mesh analysis)
    avg_smile_score = Column(Float, nullable=True)
    avg_eye_open_left = Column(Float, nullable=True)
    avg_eye_open_right = Column(Float, nullable=True)
    avg_eyebrow_height = Column(Float, nullable=True)
    avg_mouth_open = Column(Float, nullable=True)
    
    # Behavioral insights
    blinks_detected = Column(Integer, nullable=True)
    smile_frames = Column(Integer, nullable=True)
    surprise_moments = Column(Integer, nullable=True)
    
    # Real-time tracking metrics
    intervention_count = Column(Integer, nullable=True, default=0)
    avg_response_time = Column(Float, nullable=True)  # Average time to respond to interventions
    emotion_variance = Column(Float, nullable=True)  # Variance in emotion scores (stability measure)
    posture_improvement_score = Column(Float, nullable=True)  # How much posture improved during session
    
    # Database-first recording fields (NEW)
    auto_save_enabled = Column(Integer, nullable=True, default=1)  # Boolean: 1=True, 0=False
    last_save_timestamp = Column(Float, nullable=True)
    frames_saved_count = Column(Integer, nullable=True, default=0)
    status = Column(String(50), nullable=True, default="active")  # active, completed, interrupted
    data_source = Column(String(20), nullable=True, default="database")  # database or json
    
    # Additional data
    session_metadata = Column(JSON, nullable=True)  # Renamed from 'metadata' to avoid SQLAlchemy conflict
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<Session(id={self.id}, session_id='{self.session_id}', user_id='{self.user_id}')>"


class EmotionEvent(Base):
    """
    Optional: Track specific emotion events during sessions
    For detailed emotion event logging (future use)
    """
    __tablename__ = "emotion_events"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), ForeignKey("sessions.session_id"), nullable=False, index=True)
    
    # Event details
    timestamp = Column(DateTime(timezone=True), nullable=False)
    frame_number = Column(Integer, nullable=False)
    event_type = Column(String(50), nullable=False)  # e.g., 'smile', 'blink', 'surprise'
    intensity = Column(Float, nullable=True)  # 0.0 to 1.0
    duration = Column(Float, nullable=True)  # Duration in seconds
    
    # Additional event data
    data = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<EmotionEvent(id={self.id}, type='{self.event_type}', session='{self.session_id}')>"


class InterventionLog(Base):
    """
    Real-time AI intervention tracking
    Logs when the system provides interventions (reminders, support, etc.)
    """
    __tablename__ = "intervention_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), ForeignKey("sessions.session_id"), nullable=False, index=True)
    
    # Intervention details
    timestamp = Column(DateTime(timezone=True), nullable=False)
    intervention_type = Column(String(100), nullable=False)  # posture_reminder, emotion_support, break_suggestion, etc.
    trigger_reason = Column(String(255), nullable=True)  # poor_posture_5min, negative_emotion_3min, etc.
    message_sent = Column(Text, nullable=True)
    tone_used = Column(String(50), nullable=True)  # formal, friendly, encouraging, gentle, calm, etc.
    user_response = Column(String(100), nullable=True)  # acknowledged, ignored, improved, etc.
    effectiveness_score = Column(Float, nullable=True)  # 0.0-1.0 for future ML
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<InterventionLog(id={self.id}, type='{self.intervention_type}', session='{self.session_id}')>"


class Report(Base):
    """
    Session Report model
    Stores generated reports for sessions with complete analysis
    """
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), ForeignKey("sessions.session_id"), unique=True, nullable=False, index=True)
    user_id = Column(String(100), ForeignKey("users.user_id"), nullable=True, index=True)
    
    # Report metadata
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    report_version = Column(String(50), nullable=True)  # e.g., "1.0", "2.0"
    
    # Report data (stored as JSON and text)
    report_data = Column(JSON, nullable=False)  # Full report JSON (for detailed analysis)
    text_report = Column(Text, nullable=True)  # Compact text format (~80% smaller, human-readable)
    
    # Quick access fields (denormalized for performance)
    overall_quality_score = Column(Float, nullable=True)  # 0-100
    dominant_emotion = Column(String(50), nullable=True)  # e.g., "happy", "neutral"
    average_posture_quality = Column(String(50), nullable=True)  # "excellent", "good", "poor"
    engagement_level = Column(Float, nullable=True)  # 0.0-1.0
    total_interventions = Column(Integer, nullable=True, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<Report(id={self.id}, session_id='{self.session_id}', quality={self.overall_quality_score})>"


class Frame(Base):
    """
    Frame model for storing individual frame data
    Part of database-first recording architecture
    """
    __tablename__ = "frames"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), ForeignKey("sessions.session_id"), nullable=False, index=True)
    frame_number = Column(Integer, nullable=False)
    timestamp = Column(Float, nullable=False)
    
    # JSON columns for landmarks and detection data
    body_parts = Column(JSON, nullable=True)  # head, hands, body confidence
    pose_landmarks = Column(JSON, nullable=True)  # MediaPipe pose landmarks
    hand_landmarks = Column(JSON, nullable=True)  # Hand landmarks
    face_mesh_landmarks = Column(JSON, nullable=True)  # 468-point face mesh
    emotion_data = Column(JSON, nullable=True)  # label, confidence, scores
    frame_metadata = Column(JSON, nullable=True)  # Additional frame metadata (renamed from 'metadata')
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<Frame(id={self.id}, session='{self.session_id}', frame={self.frame_number})>"


class SessionTimeline(Base):
    """
    Session Timeline model for tracking significant events during sessions
    Stores emotion changes, posture events, engagement markers, interventions
    """
    __tablename__ = "session_timeline"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), ForeignKey("sessions.session_id"), nullable=False, index=True)
    timestamp = Column(Float, nullable=False)
    event_type = Column(String(50), nullable=False, index=True)  # emotion, posture, engagement, intervention
    data = Column(JSON, nullable=False)  # Event-specific data
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<SessionTimeline(id={self.id}, session='{self.session_id}', type='{self.event_type}')>"
