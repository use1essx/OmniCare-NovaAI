"""
Unit Tests for DetailedRecorder with Database Support
Tests database storage, auto-save, buffering, and export functionality
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.custom_live_ai.models.database import Base, Session, Frame, SessionTimeline, User
from src.custom_live_ai.utils.detailed_recorder import DetailedRecorder


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    # Create test user
    user = User(user_id="test_user", name="Test User")
    session.add(user)
    session.commit()
    
    yield session
    session.close()


class TestDetailedRecorderDatabaseMode:
    """Test DetailedRecorder with database storage"""
    
    def test_initialization_database_mode(self, db_session):
        """Test recorder initializes in database mode"""
        recorder = DetailedRecorder(use_database=True, db_session=db_session, user_id="test_user")
        
        assert recorder.use_database is True
        assert recorder.db_session is not None
        assert recorder.user_id == "test_user"
        assert recorder.frame_buffer == []
        assert recorder.buffer_size == 50
        assert recorder.auto_save_interval == 30
    
    def test_initialization_json_mode(self):
        """Test recorder initializes in JSON mode (fallback)"""
        recorder = DetailedRecorder(use_database=False)
        
        assert recorder.use_database is False
        assert recorder.db_session is None
    
    def test_start_recording_creates_db_session(self, db_session):
        """Test start_recording creates database session record"""
        recorder = DetailedRecorder(use_database=True, db_session=db_session, user_id="test_user")
        session_id = recorder.start_recording()
        
        # Verify session created in database
        db_session_record = db_session.query(Session).filter_by(session_id=session_id).first()
        assert db_session_record is not None
        assert db_session_record.status == "active"
        assert db_session_record.data_source == "database"
        assert db_session_record.user_id == "test_user"
    
    def test_record_frame_buffering(self, db_session):
        """Test frames are buffered before database insert"""
        recorder = DetailedRecorder(use_database=True, db_session=db_session, user_id="test_user")
        recorder.start_recording()
        
        # Record frames (less than buffer size)
        for i in range(10):
            frame_data = {
                "timestamp": i * 0.1,
                "bodyParts": {"head": {"confidence": 0.9}},
                "emotion": {"label": "neutral", "confidence": 0.8}
            }
            recorder.record_frame(frame_data)
        
        # Frames should be in buffer, not yet in database
        assert len(recorder.frame_buffer) == 10
        frame_count = db_session.query(Frame).filter_by(session_id=recorder.session_id).count()
        assert frame_count == 0  # Not saved yet
    
    def test_batch_insert_when_buffer_full(self, db_session):
        """Test frames are saved when buffer is full"""
        recorder = DetailedRecorder(use_database=True, db_session=db_session, user_id="test_user")
        recorder.buffer_size = 10  # Small buffer for testing
        recorder.start_recording()
        
        # Record frames to fill buffer
        for i in range(15):
            frame_data = {
                "timestamp": i * 0.1,
                "bodyParts": {"head": {"confidence": 0.9}},
                "emotion": {"label": "neutral", "confidence": 0.8}
            }
            recorder.record_frame(frame_data)
        
        # First 10 should be saved, 5 in buffer
        frame_count = db_session.query(Frame).filter_by(session_id=recorder.session_id).count()
        assert frame_count == 10
        assert len(recorder.frame_buffer) == 5
    
    def test_stop_recording_saves_remaining_frames(self, db_session):
        """Test stop_recording saves remaining buffered frames"""
        recorder = DetailedRecorder(use_database=True, db_session=db_session, user_id="test_user")
        recorder.start_recording()
        
        # Record some frames
        for i in range(25):
            frame_data = {
                "timestamp": i * 0.1,
                "bodyParts": {"head": {"confidence": 0.9}}
            }
            recorder.record_frame(frame_data)
        
        # Stop recording
        summary = recorder.stop_recording()
        
        # All frames should be saved
        frame_count = db_session.query(Frame).filter_by(session_id=recorder.session_id).count()
        assert frame_count == 25
        assert summary["total_frames"] == 25
        assert summary["storage_mode"] == "database"
        
        # Session should be marked completed
        db_session_record = db_session.query(Session).filter_by(session_id=recorder.session_id).first()
        assert db_session_record.status == "completed"
        assert db_session_record.total_frames == 25


class TestDetailedRecorderTimeline:
    """Test timeline event recording"""
    
    def test_emotion_timeline_saved_to_db(self, db_session):
        """Test emotion changes are saved to timeline"""
        recorder = DetailedRecorder(use_database=True, db_session=db_session, user_id="test_user")
        recorder.start_recording()
        
        # Record emotion changes
        recorder.detect_emotion_change("happy", 0.9, timestamp=1.0)
        recorder.detect_emotion_change("sad", 0.85, timestamp=5.0)
        
        # Save timeline
        recorder._save_timeline_to_db()
        
        # Verify in database
        events = db_session.query(SessionTimeline).filter_by(
            session_id=recorder.session_id,
            event_type="emotion"
        ).all()
        
        assert len(events) == 2
        assert events[0].data["emotion"] == "happy"
        assert events[1].data["emotion"] == "sad"
    
    def test_posture_events_saved_to_db(self, db_session):
        """Test posture events are saved to timeline"""
        recorder = DetailedRecorder(use_database=True, db_session=db_session, user_id="test_user")
        recorder.start_recording()
        
        # Record posture events
        recorder.detect_posture_decline("good", False, timestamp=2.0)
        recorder.detect_posture_decline("poor", True, timestamp=10.0)
        
        # Save timeline
        recorder._save_timeline_to_db()
        
        # Verify in database
        events = db_session.query(SessionTimeline).filter_by(
            session_id=recorder.session_id,
            event_type="posture"
        ).all()
        
        assert len(events) == 2


class TestDetailedRecorderExport:
    """Test export functionality"""
    
    def test_export_to_json(self, db_session, tmp_path):
        """Test exporting session from database to JSON"""
        recorder = DetailedRecorder(use_database=True, db_session=db_session, user_id="test_user")
        recorder.start_recording()
        
        # Record some data
        for i in range(5):
            frame_data = {
                "timestamp": i * 0.1,
                "bodyParts": {"head": {"confidence": 0.9}},
                "emotion": {"label": "happy", "confidence": 0.85}
            }
            recorder.record_frame(frame_data)
        
        recorder.detect_emotion_change("happy", 0.9, timestamp=0.5)
        recorder.stop_recording()
        
        # Export to JSON
        json_path = recorder.export_to_json(output_dir=str(tmp_path))
        
        # Verify file exists
        import os
        assert os.path.exists(json_path)
        
        # Verify content
        import json
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        assert data["session_id"] == recorder.session_id
        assert data["total_frames"] == 5
        assert len(data["frames"]) == 5
        assert len(data["emotion_timeline"]) == 1
        assert data["data_source"] == "database"


class TestDetailedRecorderFallback:
    """Test fallback to JSON mode"""
    
    def test_json_fallback_when_db_unavailable(self):
        """Test recorder falls back to JSON mode when database unavailable"""
        # Pass invalid db_session
        recorder = DetailedRecorder(use_database=True, db_session=None, user_id="test_user")
        
        # Start recording - should fall back to JSON mode
        recorder.start_recording()
        
        # Record frames
        for i in range(5):
            recorder.record_frame({"timestamp": i * 0.1})
        
        # Frames should be in memory list, not buffer
        assert len(recorder.frames) == 5  # JSON mode
        assert recorder.use_database is False  # Fallback detected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



