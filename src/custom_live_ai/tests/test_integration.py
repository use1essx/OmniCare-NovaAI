"""
Integration Tests for Database-First Recording
End-to-end tests for the complete workflow
"""

import pytest
import time
import os
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


class TestCompleteRecordingWorkflow:
    """Test complete recording workflow from start to finish"""
    
    def test_full_session_lifecycle(self, db_session):
        """
        Test complete session lifecycle:
        1. Start recording
        2. Record frames
        3. Trigger auto-save (simulated)
        4. Record more frames
        5. Stop recording
        6. Verify data integrity
        """
        # Initialize recorder
        recorder = DetailedRecorder(
            use_database=True,
            db_session=db_session,
            user_id="test_user"
        )
        
        # 1. Start recording
        session_id = recorder.start_recording()
        assert session_id is not None
        assert recorder.is_recording is True
        
        # Verify session created in database
        db_record = db_session.query(Session).filter_by(session_id=session_id).first()
        assert db_record is not None
        assert db_record.status == "active"
        assert db_record.data_source == "database"
        
        # 2. Record first batch of frames
        for i in range(25):
            frame_data = {
                "timestamp": i * 0.1,
                "bodyParts": {
                    "head": {"confidence": 0.95},
                    "leftHand": {"confidence": 0.88},
                    "rightHand": {"confidence": 0.87}
                },
                "pose": {
                    "landmarks": [{"x": 0.5, "y": 0.5, "z": 0.1}] * 33
                },
                "hands": {
                    "landmarks": [[{"x": 0.3, "y": 0.4, "z": 0.05}] * 21],
                    "handedness": ["Left"]
                },
                "faceMesh": {
                    "landmarks": [[{"x": 0.5, "y": 0.5, "z": 0.02}] * 468]
                },
                "emotion": {
                    "label": "happy",
                    "emoji": "😊",
                    "confidence": 0.85,
                    "scores": {"happy": 0.85, "neutral": 0.15}
                },
                "metadata": {"fps": 30.0}
            }
            recorder.record_frame(frame_data)
        
        # Record emotion changes
        recorder.detect_emotion_change("happy", 0.85, timestamp=1.0)
        recorder.detect_emotion_change("neutral", 0.75, timestamp=5.0)
        
        # Record posture events
        recorder.detect_posture_decline("good", False, timestamp=2.0)
        recorder.detect_posture_decline("poor", True, timestamp=8.0)
        
        # Record intervention triggers
        recorder.add_intervention_trigger("posture_reminder", timestamp=10.0)
        
        # 3. Simulate auto-save (manually trigger)
        recorder._save_frames_to_db()
        recorder._save_timeline_to_db()
        
        # Verify frames saved
        frame_count = db_session.query(Frame).filter_by(session_id=session_id).count()
        assert frame_count == 25
        
        # Verify timeline events saved
        timeline_count = db_session.query(SessionTimeline).filter_by(session_id=session_id).count()
        assert timeline_count > 0  # Should have emotion, posture, and intervention events
        
        # 4. Record more frames
        for i in range(25, 50):
            frame_data = {
                "timestamp": i * 0.1,
                "bodyParts": {"head": {"confidence": 0.92}},
                "emotion": {"label": "neutral", "confidence": 0.78}
            }
            recorder.record_frame(frame_data)
        
        # 5. Stop recording
        summary = recorder.stop_recording()
        
        assert summary["total_frames"] == 50
        assert summary["storage_mode"] == "database"
        assert summary["duration"] > 0
        
        # 6. Verify data integrity
        # Check all frames saved
        final_frame_count = db_session.query(Frame).filter_by(session_id=session_id).count()
        assert final_frame_count == 50
        
        # Check session updated
        final_session = db_session.query(Session).filter_by(session_id=session_id).first()
        assert final_session.status == "completed"
        assert final_session.total_frames == 50
        assert final_session.duration > 0
        
        # Verify frames are in correct order
        frames = db_session.query(Frame).filter_by(session_id=session_id).order_by(Frame.frame_number).all()
        for i, frame in enumerate(frames):
            assert frame.frame_number == i + 1
    
    def test_recovery_after_crash_simulation(self, db_session):
        """
        Test recovery of interrupted session:
        1. Start recording
        2. Record some frames
        3. Simulate crash (without calling stop)
        4. Verify session can be recovered
        """
        # 1. Start recording
        recorder = DetailedRecorder(
            use_database=True,
            db_session=db_session,
            user_id="test_user"
        )
        session_id = recorder.start_recording()
        
        # 2. Record frames
        for i in range(30):
            recorder.record_frame({
                "timestamp": i * 0.1,
                "bodyParts": {"head": {"confidence": 0.9}}
            })
        
        # 3. Simulate crash - trigger one save but don't stop properly
        recorder._save_frames_to_db()
        
        # Simulate crash - don't call stop_recording
        # Session should be in "active" status
        
        # 4. Recovery process
        crashed_session = db_session.query(Session).filter_by(session_id=session_id).first()
        assert crashed_session.status == "active"
        
        # Count saved frames
        saved_frames = db_session.query(Frame).filter_by(session_id=session_id).count()
        assert saved_frames > 0  # Some frames should be saved
        
        # Perform recovery
        crashed_session.status = "completed"
        crashed_session.total_frames = saved_frames
        db_session.commit()
        
        # Verify recovery
        recovered_session = db_session.query(Session).filter_by(session_id=session_id).first()
        assert recovered_session.status == "completed"
        assert recovered_session.total_frames == saved_frames
    
    def test_export_and_reimport_workflow(self, db_session, tmp_path):
        """
        Test export and reimport workflow:
        1. Record session to database
        2. Export to JSON
        3. Verify JSON content matches database
        """
        # 1. Record session
        recorder = DetailedRecorder(
            use_database=True,
            db_session=db_session,
            user_id="test_user"
        )
        session_id = recorder.start_recording()
        
        for i in range(10):
            recorder.record_frame({
                "timestamp": i * 0.1,
                "bodyParts": {"head": {"confidence": 0.9}},
                "emotion": {"label": "happy", "confidence": 0.85}
            })
        
        recorder.detect_emotion_change("happy", 0.85, timestamp=0.5)
        recorder.stop_recording()
        
        # 2. Export to JSON
        json_path = recorder.export_to_json(output_dir=str(tmp_path))
        assert os.path.exists(json_path)
        
        # 3. Verify JSON content
        import json
        with open(json_path, 'r') as f:
            exported_data = json.load(f)
        
        assert exported_data["session_id"] == session_id
        assert exported_data["total_frames"] == 10
        assert len(exported_data["frames"]) == 10
        assert len(exported_data["emotion_timeline"]) == 1
        assert exported_data["data_source"] == "database"
        
        # Verify frame data matches
        for i, frame in enumerate(exported_data["frames"]):
            assert frame["frame_number"] == i + 1
            assert frame["bodyParts"]["head"]["confidence"] == 0.9


class TestPerformance:
    """Performance tests for database-first recording"""
    
    def test_bulk_insert_performance(self, db_session):
        """Test bulk insert performance with many frames"""
        recorder = DetailedRecorder(
            use_database=True,
            db_session=db_session,
            user_id="test_user"
        )
        recorder.buffer_size = 100  # Large buffer
        recorder.start_recording()
        
        # Record 500 frames
        start_time = time.time()
        for i in range(500):
            recorder.record_frame({
                "timestamp": i * 0.033,  # 30 fps
                "bodyParts": {"head": {"confidence": 0.9}},
                "emotion": {"label": "neutral", "confidence": 0.8}
            })
        recorder.stop_recording()
        elapsed_time = time.time() - start_time
        
        # Verify all frames saved
        frame_count = db_session.query(Frame).filter_by(session_id=recorder.session_id).count()
        assert frame_count == 500
        
        # Performance assertion - should complete in reasonable time
        # 500 frames in < 5 seconds is acceptable
        assert elapsed_time < 5.0, f"Bulk insert took too long: {elapsed_time}s"
        
        print(f"✅ Inserted 500 frames in {elapsed_time:.2f}s ({500/elapsed_time:.1f} fps)")


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_graceful_fallback_on_db_error(self):
        """Test graceful fallback when database is unavailable"""
        # Initialize with invalid db_session
        recorder = DetailedRecorder(
            use_database=True,
            db_session=None,  # Invalid
            user_id="test_user"
        )
        
        # Should start in JSON fallback mode
        recorder.start_recording()
        
        # Record frames - should use JSON mode
        for i in range(10):
            recorder.record_frame({"timestamp": i * 0.1})
        
        # Verify using JSON mode (frames in memory)
        assert len(recorder.frames) == 10
    
    def test_concurrent_sessions(self, db_session):
        """Test multiple concurrent sessions"""
        # Create multiple recorders
        recorder1 = DetailedRecorder(use_database=True, db_session=db_session, user_id="test_user")
        recorder2 = DetailedRecorder(use_database=True, db_session=db_session, user_id="test_user")
        
        session1_id = recorder1.start_recording()
        session2_id = recorder2.start_recording()
        
        # Record to both
        recorder1.record_frame({"timestamp": 1.0})
        recorder2.record_frame({"timestamp": 1.0})
        
        recorder1.stop_recording()
        recorder2.stop_recording()
        
        # Verify both sessions exist independently
        session1_frames = db_session.query(Frame).filter_by(session_id=session1_id).count()
        session2_frames = db_session.query(Frame).filter_by(session_id=session2_id).count()
        
        assert session1_frames == 1
        assert session2_frames == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])



