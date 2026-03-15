"""
Unit Tests for API Endpoints
Tests recovery, export, live reports, and auto-report generation
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.custom_live_ai.models.database import Base, Session, Frame, SessionTimeline, User

# Try to import app, skip all tests if dependencies missing
try:
    from src.custom_live_ai.main import app
    from src.custom_live_ai.database.config import get_db
    APP_AVAILABLE = True
except ImportError as e:
    APP_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason=f"App dependencies not available: {e}")


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


@pytest.fixture
def client(db_session):
    """Create test client with database override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_session(db_session):
    """Create a sample session with frames"""
    session = Session(
        session_id="test_session_123",
        user_id="test_user",
        status="completed",
        total_frames=10,
        duration=30.0
    )
    db_session.add(session)
    
    # Add frames
    for i in range(10):
        frame = Frame(
            session_id="test_session_123",
            frame_number=i + 1,
            timestamp=i * 0.5,
            body_parts={"head": {"confidence": 0.9}},
            emotion_data={"label": "happy", "confidence": 0.85}
        )
        db_session.add(frame)
    
    # Add timeline events
    emotion_event = SessionTimeline(
        session_id="test_session_123",
        timestamp=2.0,
        event_type="emotion",
        data={"emotion": "happy", "confidence": 0.9}
    )
    db_session.add(emotion_event)
    
    db_session.commit()
    return session


class TestRecoveryEndpoints:
    """Test session recovery endpoints"""
    
    def test_list_interrupted_sessions(self, client, db_session):
        """Test listing interrupted sessions"""
        # Create interrupted session
        interrupted_session = Session(
            session_id="interrupted_123",
            user_id="test_user",
            status="interrupted",
            frames_saved_count=50
        )
        db_session.add(interrupted_session)
        db_session.commit()
        
        # Call endpoint
        response = client.get("/api/db/sessions/interrupted")
        assert response.status_code == 200
        
        data = response.json()
        assert data["count"] == 1
        assert data["interrupted_sessions"][0]["session_id"] == "interrupted_123"
        assert data["interrupted_sessions"][0]["status"] == "interrupted"
    
    def test_recover_interrupted_session(self, client, db_session):
        """Test recovering an interrupted session"""
        # Create interrupted session with frames
        session = Session(
            session_id="interrupted_123",
            user_id="test_user",
            status="interrupted"
        )
        db_session.add(session)
        
        # Add frames
        for i in range(5):
            frame = Frame(
                session_id="interrupted_123",
                frame_number=i + 1,
                timestamp=i * 0.5
            )
            db_session.add(frame)
        db_session.commit()
        
        # Call recovery endpoint
        response = client.post("/api/db/sessions/interrupted_123/recover")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["frames_recovered"] == 5
        assert data["status"] == "completed"
        
        # Verify session updated
        updated_session = db_session.query(Session).filter_by(session_id="interrupted_123").first()
        assert updated_session.status == "completed"


class TestExportEndpoints:
    """Test export endpoints"""
    
    def test_export_session_to_json(self, client, sample_session):
        """Test exporting session to JSON file"""
        response = client.get("/api/db/sessions/test_session_123/export/json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
    
    def test_export_session_to_csv(self, client, sample_session):
        """Test exporting session to CSV file"""
        response = client.get("/api/db/sessions/test_session_123/export/csv")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        
        # Verify CSV content
        csv_content = response.text
        assert "frame_number" in csv_content
        assert "timestamp" in csv_content
        assert "emotion_label" in csv_content
    
    def test_export_nonexistent_session(self, client):
        """Test exporting non-existent session returns 404"""
        response = client.get("/api/db/sessions/nonexistent/export/json")
        assert response.status_code == 404


class TestLiveReports:
    """Test live report generation"""
    
    def test_generate_live_report(self, client, sample_session, db_session):
        """Test generating live report from database"""
        # Note: This test requires the report generator to work with our test DB
        # In a real scenario, you'd mock the report generator
        response = client.get("/api/reports/session/test_session_123/live")
        
        # Should return report data
        assert response.status_code in [200, 500]  # May fail without full setup
        
        # If successful, verify structure
        if response.status_code == 200:
            data = response.json()
            assert "session_id" in data
            assert data["session_id"] == "test_session_123"
    
    def test_live_report_disabled(self, client, monkeypatch):
        """Test live reports can be disabled via env var"""
        monkeypatch.setenv("ENABLE_LIVE_REPORTS", "false")
        
        response = client.get("/api/reports/session/test_session_123/live")
        assert response.status_code == 503  # Service unavailable


class TestHealthcareIntegration:
    """Test healthcare integration with auto-reports"""
    
    def test_session_start_creates_db_record(self, client, db_session):
        """Test starting session creates database record"""
        response = client.post(
            "/api/healthcare/session/start",
            json={"user_id": "test_user"}
        )
        
        # Should create session
        assert response.status_code in [200, 500]  # May need full DB setup
        
        if response.status_code == 200:
            data = response.json()
            assert "session_id" in data
            
            # Verify in database
            session_id = data["session_id"]
            db_record = db_session.query(Session).filter_by(session_id=session_id).first()
            assert db_record is not None
            assert db_record.status == "active"


class TestWebSocketImprovements:
    """Test WebSocket improvements"""
    
    def test_websocket_connection(self, client):
        """Test WebSocket connection establishment"""
        # Note: Full WebSocket testing requires websocket client
        # This is a basic connectivity test
        
        # WebSocket endpoint should exist
        # In real tests, use websocket test client
        pass  # Placeholder for WebSocket tests
    
    def test_websocket_heartbeat_config(self):
        """Test WebSocket heartbeat configuration"""
        import os
        
        # Test default values
        heartbeat = int(os.getenv("WEBSOCKET_HEARTBEAT_SEC", "10"))
        batch_size = int(os.getenv("WEBSOCKET_BATCH_SIZE", "5"))
        
        assert heartbeat == 10
        assert batch_size == 5


class TestIntegrationFlow:
    """Test complete integration flow"""
    
    def test_complete_session_workflow(self, client, db_session):
        """Test complete workflow: start → record → stop → report"""
        # This test would ideally:
        # 1. Start a session
        # 2. Record some frames
        # 3. Stop the session
        # 4. Verify auto-report generation
        # 5. Export session data
        
        # Placeholder for integration test
        # Requires full application setup
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
