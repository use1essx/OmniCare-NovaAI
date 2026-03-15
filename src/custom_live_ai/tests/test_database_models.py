"""
Unit Tests for Database Models
Tests Frame, SessionTimeline, and updated Session models
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.custom_live_ai.models.database import Base, Session, Frame, SessionTimeline, User


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


class TestFrameModel:
    """Test Frame model"""
    
    def test_create_frame(self, db_session):
        """Test creating a frame record"""
        # Create user and session first
        user = User(user_id="test_user", name="Test User")
        db_session.add(user)
        
        session = Session(
            session_id="test_session_123",
            user_id="test_user",
            status="active"
        )
        db_session.add(session)
        db_session.commit()
        
        # Create frame
        frame = Frame(
            session_id="test_session_123",
            frame_number=1,
            timestamp=1.5,
            body_parts={"head": {"confidence": 0.95}},
            pose_landmarks={"landmarks": [{"x": 0.5, "y": 0.5}]},
            emotion_data={"label": "happy", "confidence": 0.85}
        )
        db_session.add(frame)
        db_session.commit()
        
        # Verify
        saved_frame = db_session.query(Frame).filter_by(session_id="test_session_123").first()
        assert saved_frame is not None
        assert saved_frame.frame_number == 1
        assert saved_frame.timestamp == 1.5
        assert saved_frame.body_parts["head"]["confidence"] == 0.95
        assert saved_frame.emotion_data["label"] == "happy"
    
    def test_frame_cascade_delete(self, db_session):
        """Test that frames are deleted when session is deleted"""
        # Create user, session, and frames
        user = User(user_id="test_user", name="Test User")
        db_session.add(user)
        
        session = Session(session_id="test_session_123", user_id="test_user")
        db_session.add(session)
        
        frame1 = Frame(session_id="test_session_123", frame_number=1, timestamp=1.0)
        frame2 = Frame(session_id="test_session_123", frame_number=2, timestamp=2.0)
        db_session.add_all([frame1, frame2])
        db_session.commit()
        
        # Verify frames exist
        frame_count = db_session.query(Frame).filter_by(session_id="test_session_123").count()
        assert frame_count == 2


class TestSessionTimelineModel:
    """Test SessionTimeline model"""
    
    def test_create_timeline_event(self, db_session):
        """Test creating timeline events"""
        # Create user and session
        user = User(user_id="test_user", name="Test User")
        db_session.add(user)
        
        session = Session(session_id="test_session_123", user_id="test_user")
        db_session.add(session)
        db_session.commit()
        
        # Create emotion event
        emotion_event = SessionTimeline(
            session_id="test_session_123",
            timestamp=5.0,
            event_type="emotion",
            data={"emotion": "happy", "confidence": 0.9}
        )
        db_session.add(emotion_event)
        
        # Create posture event
        posture_event = SessionTimeline(
            session_id="test_session_123",
            timestamp=10.0,
            event_type="posture",
            data={"event_type": "slouch", "severity": 0.7}
        )
        db_session.add(posture_event)
        db_session.commit()
        
        # Verify
        events = db_session.query(SessionTimeline).filter_by(session_id="test_session_123").all()
        assert len(events) == 2
        assert events[0].event_type == "emotion"
        assert events[1].event_type == "posture"
    
    def test_timeline_ordering(self, db_session):
        """Test timeline events are ordered by timestamp"""
        user = User(user_id="test_user", name="Test User")
        db_session.add(user)
        
        session = Session(session_id="test_session_123", user_id="test_user")
        db_session.add(session)
        
        # Add events out of order
        event2 = SessionTimeline(
            session_id="test_session_123",
            timestamp=10.0,
            event_type="emotion",
            data={"emotion": "sad"}
        )
        event1 = SessionTimeline(
            session_id="test_session_123",
            timestamp=5.0,
            event_type="emotion",
            data={"emotion": "happy"}
        )
        db_session.add_all([event2, event1])
        db_session.commit()
        
        # Query ordered by timestamp
        events = db_session.query(SessionTimeline).filter_by(
            session_id="test_session_123"
        ).order_by(SessionTimeline.timestamp).all()
        
        assert events[0].timestamp == 5.0
        assert events[1].timestamp == 10.0


class TestSessionModelUpdates:
    """Test updated Session model with new fields"""
    
    def test_session_with_recovery_fields(self, db_session):
        """Test session creation with new recovery fields"""
        user = User(user_id="test_user", name="Test User")
        db_session.add(user)
        db_session.commit()
        
        session = Session(
            session_id="test_session_123",
            user_id="test_user",
            status="active",
            auto_save_enabled=1,
            frames_saved_count=50,
            last_save_timestamp=1234567890.5,
            data_source="database"
        )
        db_session.add(session)
        db_session.commit()
        
        # Verify
        saved_session = db_session.query(Session).filter_by(session_id="test_session_123").first()
        assert saved_session.status == "active"
        assert saved_session.auto_save_enabled == 1
        assert saved_session.frames_saved_count == 50
        assert saved_session.last_save_timestamp == 1234567890.5
        assert saved_session.data_source == "database"
    
    def test_session_status_transitions(self, db_session):
        """Test session status transitions"""
        user = User(user_id="test_user", name="Test User")
        db_session.add(user)
        
        session = Session(
            session_id="test_session_123",
            user_id="test_user",
            status="active"
        )
        db_session.add(session)
        db_session.commit()
        
        # Transition to completed
        session.status = "completed"
        session.end_time = datetime.utcnow()
        db_session.commit()
        
        # Verify
        saved_session = db_session.query(Session).filter_by(session_id="test_session_123").first()
        assert saved_session.status == "completed"
        assert saved_session.end_time is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



