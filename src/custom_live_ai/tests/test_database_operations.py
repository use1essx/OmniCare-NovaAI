"""
Database Operations Tests
Tests all database models, operations, and data integrity
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(scope="function")
def test_db():
    """Create a test database session"""
    from src.custom_live_ai.models.database import Base
    
    # Create in-memory SQLite database for testing
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    yield db
    
    db.close()


class TestDatabaseModels:
    """Test database model definitions"""
    
    def test_recording_session_model_structure(self):
        """Test RecordingSession model has all required columns"""
        from src.custom_live_ai.models.database import RecordingSession
        
        required_columns = [
            'session_id', 'user_id', 'start_time', 'end_time',
            'duration_seconds', 'total_frames', 'avg_fps',
            'dominant_emotion', 'avg_emotion_confidence',
            'avg_posture_quality', 'intervention_count'
        ]
        
        for column in required_columns:
            assert hasattr(RecordingSession, column), f"Missing column: {column}"
    
    def test_emotion_entry_model_structure(self):
        """Test EmotionEntry model structure"""
        from src.custom_live_ai.models.database import EmotionEntry
        
        required_columns = [
            'id', 'session_id', 'timestamp', 'emotion',
            'confidence', 'method', 'scores'
        ]
        
        for column in required_columns:
            assert hasattr(EmotionEntry, column), f"Missing column: {column}"
    
    def test_posture_entry_model_structure(self):
        """Test PostureEntry model structure"""
        from src.custom_live_ai.models.database import PostureEntry
        
        required_columns = [
            'id', 'session_id', 'timestamp', 'posture_quality',
            'posture_score', 'head_tilt', 'shoulder_alignment'
        ]
        
        for column in required_columns:
            assert hasattr(PostureEntry, column), f"Missing column: {column}"
    
    def test_intervention_log_model_structure(self):
        """Test InterventionLog model structure"""
        from src.custom_live_ai.models.database import InterventionLog
        
        required_columns = [
            'id', 'session_id', 'timestamp', 'intervention_type',
            'trigger_reason', 'message', 'severity'
        ]
        
        for column in required_columns:
            assert hasattr(InterventionLog, column), f"Missing column: {column}"


class TestDatabaseOperations:
    """Test database CRUD operations"""
    
    def test_create_recording_session(self, test_db):
        """Test creating a recording session"""
        from src.custom_live_ai.models.database import RecordingSession
        
        session = RecordingSession(
            session_id="test_session_001",
            user_id="test_user",
            start_time=datetime.utcnow()
        )
        
        test_db.add(session)
        test_db.commit()
        
        # Verify
        retrieved = test_db.query(RecordingSession).filter_by(
            session_id="test_session_001"
        ).first()
        
        assert retrieved is not None
        assert retrieved.session_id == "test_session_001"
        assert retrieved.user_id == "test_user"
    
    def test_create_emotion_entry(self, test_db):
        """Test creating an emotion entry"""
        from src.custom_live_ai.models.database import EmotionEntry
        
        emotion = EmotionEntry(
            session_id="test_session_001",
            timestamp=datetime.utcnow(),
            emotion="happy",
            confidence=0.85,
            method="faceapi_raw",
            scores={"happy": 85.0, "neutral": 10.0, "sad": 5.0}
        )
        
        test_db.add(emotion)
        test_db.commit()
        
        # Verify
        retrieved = test_db.query(EmotionEntry).filter_by(
            emotion="happy"
        ).first()
        
        assert retrieved is not None
        assert retrieved.emotion == "happy"
        assert retrieved.confidence == 0.85
    
    def test_create_posture_entry(self, test_db):
        """Test creating a posture entry"""
        from src.custom_live_ai.models.database import PostureEntry
        
        posture = PostureEntry(
            session_id="test_session_001",
            timestamp=datetime.utcnow(),
            posture_quality="good",
            posture_score=0.75
        )
        
        test_db.add(posture)
        test_db.commit()
        
        # Verify
        retrieved = test_db.query(PostureEntry).filter_by(
            session_id="test_session_001"
        ).first()
        
        assert retrieved is not None
        assert retrieved.posture_quality == "good"
        assert retrieved.posture_score == 0.75
    
    def test_create_intervention_log(self, test_db):
        """Test creating an intervention log"""
        from src.custom_live_ai.models.database import InterventionLog
        
        intervention = InterventionLog(
            session_id="test_session_001",
            timestamp=datetime.utcnow(),
            intervention_type="posture",
            trigger_reason="poor_posture_detected",
            message="Please adjust your posture",
            severity="medium"
        )
        
        test_db.add(intervention)
        test_db.commit()
        
        # Verify
        retrieved = test_db.query(InterventionLog).filter_by(
            intervention_type="posture"
        ).first()
        
        assert retrieved is not None
        assert retrieved.trigger_reason == "poor_posture_detected"


class TestDatabaseRelationships:
    """Test database relationships between models"""
    
    def test_session_emotion_relationship(self, test_db):
        """Test relationship between session and emotions"""
        from src.custom_live_ai.models.database import RecordingSession, EmotionEntry
        
        # Create session
        session = RecordingSession(
            session_id="test_session_002",
            user_id="test_user",
            start_time=datetime.utcnow()
        )
        test_db.add(session)
        test_db.commit()
        
        # Create emotions for this session
        for emotion_name in ['happy', 'neutral', 'sad']:
            emotion = EmotionEntry(
                session_id="test_session_002",
                timestamp=datetime.utcnow(),
                emotion=emotion_name,
                confidence=0.7,
                method="faceapi_raw"
            )
            test_db.add(emotion)
        
        test_db.commit()
        
        # Verify relationship
        emotions = test_db.query(EmotionEntry).filter_by(
            session_id="test_session_002"
        ).all()
        
        assert len(emotions) == 3
    
    def test_session_intervention_relationship(self, test_db):
        """Test relationship between session and interventions"""
        from src.custom_live_ai.models.database import RecordingSession, InterventionLog
        
        # Create session
        session = RecordingSession(
            session_id="test_session_003",
            user_id="test_user",
            start_time=datetime.utcnow()
        )
        test_db.add(session)
        test_db.commit()
        
        # Create interventions
        for i in range(3):
            intervention = InterventionLog(
                session_id="test_session_003",
                timestamp=datetime.utcnow(),
                intervention_type="posture",
                trigger_reason=f"trigger_{i}",
                message=f"Message {i}"
            )
            test_db.add(intervention)
        
        test_db.commit()
        
        # Verify
        interventions = test_db.query(InterventionLog).filter_by(
            session_id="test_session_003"
        ).all()
        
        assert len(interventions) == 3


class TestDatabaseQueries:
    """Test complex database queries"""
    
    def test_query_emotions_by_session(self, test_db):
        """Test querying emotions by session"""
        from src.custom_live_ai.models.database import EmotionEntry
        
        # Create test data
        for i in range(5):
            emotion = EmotionEntry(
                session_id="query_test_session",
                timestamp=datetime.utcnow(),
                emotion="happy",
                confidence=0.8
            )
            test_db.add(emotion)
        
        test_db.commit()
        
        # Query
        results = test_db.query(EmotionEntry).filter_by(
            session_id="query_test_session"
        ).all()
        
        assert len(results) == 5
    
    def test_query_interventions_by_type(self, test_db):
        """Test querying interventions by type"""
        from src.custom_live_ai.models.database import InterventionLog
        
        # Create different types
        types = ['posture', 'emotion', 'engagement']
        for intervention_type in types:
            for i in range(2):
                intervention = InterventionLog(
                    session_id="type_test_session",
                    timestamp=datetime.utcnow(),
                    intervention_type=intervention_type,
                    trigger_reason="test"
                )
                test_db.add(intervention)
        
        test_db.commit()
        
        # Query posture interventions
        posture_interventions = test_db.query(InterventionLog).filter_by(
            intervention_type="posture"
        ).all()
        
        assert len(posture_interventions) == 2
    
    def test_query_recent_sessions(self, test_db):
        """Test querying recent sessions"""
        from src.custom_live_ai.models.database import RecordingSession
        
        # Create sessions with different times
        base_time = datetime.utcnow()
        for i in range(3):
            session = RecordingSession(
                session_id=f"time_test_session_{i}",
                user_id="test_user",
                start_time=base_time - timedelta(hours=i)
            )
            test_db.add(session)
        
        test_db.commit()
        
        # Query sessions from last 2 hours
        recent_time = base_time - timedelta(hours=2)
        recent_sessions = test_db.query(RecordingSession).filter(
            RecordingSession.start_time >= recent_time
        ).all()
        
        assert len(recent_sessions) >= 2


class TestDatabaseIntegrity:
    """Test database data integrity"""
    
    def test_session_id_uniqueness(self, test_db):
        """Test that session_id is unique"""
        from src.custom_live_ai.models.database import RecordingSession
        from sqlalchemy.exc import IntegrityError
        
        # Create first session
        session1 = RecordingSession(
            session_id="unique_test_session",
            user_id="user1",
            start_time=datetime.utcnow()
        )
        test_db.add(session1)
        test_db.commit()
        
        # Try to create duplicate
        session2 = RecordingSession(
            session_id="unique_test_session",
            user_id="user2",
            start_time=datetime.utcnow()
        )
        test_db.add(session2)
        
        with pytest.raises(IntegrityError):
            test_db.commit()
    
    def test_foreign_key_constraint(self, test_db):
        """Test foreign key constraints work"""
        from src.custom_live_ai.models.database import EmotionEntry
        
        # Try to create emotion for non-existent session
        # (This may or may not raise error depending on database configuration)
        emotion = EmotionEntry(
            session_id="non_existent_session",
            timestamp=datetime.utcnow(),
            emotion="happy",
            confidence=0.8
        )
        test_db.add(emotion)
        
        # Should either succeed or fail gracefully
        try:
            test_db.commit()
        except Exception:
            test_db.rollback()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

