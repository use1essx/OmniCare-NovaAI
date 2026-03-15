"""
Pytest configuration and fixtures
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import numpy as np

# Import only what we need
from src.custom_live_ai.models.database import Base


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite:///./test.db"


@pytest.fixture(scope="function")
def test_db():
    """Create test database"""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db):
    """Create test client"""
    # Lazy import to avoid loading mediapipe dependencies
    try:
        from fastapi.testclient import TestClient
        from src.custom_live_ai.main import app
        from src.custom_live_ai.database.config import get_db
        
        def override_get_db():
            try:
                yield test_db
            finally:
                pass
        
        app.dependency_overrides[get_db] = override_get_db
        
        with TestClient(app) as test_client:
            yield test_client
        
        app.dependency_overrides.clear()
    except ImportError as e:
        pytest.skip(f"Skipping API tests - missing dependencies: {e}")


@pytest.fixture
def sample_landmarks():
    """Generate sample 468 face landmarks"""
    return np.random.rand(468, 3).tolist()


@pytest.fixture
def sample_faceapi_scores():
    """Generate sample face-api.js emotion scores"""
    return {
        "neutral": 0.7,
        "happy": 0.1,
        "sad": 0.05,
        "angry": 0.05,
        "surprise": 0.05,
        "fear": 0.03,
        "disgust": 0.02
    }


@pytest.fixture
def sample_session_data():
    """Generate sample session recording data"""
    return {
        "session_id": "test_session_001",
        "session_start": "2025-01-01T10:00:00",
        "session_end": "2025-01-01T10:30:00",
        "duration": 1800.0,
        "frames": [
            {
                "timestamp": 0.0,
                "faceMesh": {
                    "landmarks": np.random.rand(468, 3).tolist()
                },
                "pose": {
                    "landmarks": np.random.rand(33, 3).tolist()
                }
            }
            for _ in range(10)
        ],
        "emotion_timeline": [
            {"timestamp": i * 0.5, "emotion": "neutral", "confidence": 0.8}
            for i in range(20)
        ],
        "posture_events": [
            {"timestamp": i * 10.0, "event_type": "good_posture", "severity": 0.2}
            for i in range(10)
        ],
        "intervention_triggers": [],
        "metadata": {
            "version": "2.1",
            "quality": "high"
        }
    }




