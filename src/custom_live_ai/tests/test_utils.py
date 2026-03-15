"""
Test utility functions and classes
"""

import time
from src.custom_live_ai.utils.detailed_recorder import DetailedRecorder
from src.custom_live_ai.utils.session_metrics import SessionMetrics


class TestDetailedRecorder:
    """Test DetailedRecorder class"""
    
    def test_recorder_initialization(self):
        """Test DetailedRecorder initialization"""
        recorder = DetailedRecorder()
        assert recorder.session_id is None
        assert recorder.is_recording is False
        assert len(recorder.frames) == 0
    
    def test_start_recording(self):
        """Test starting a recording"""
        recorder = DetailedRecorder()
        session_id = recorder.start_recording()
        
        assert session_id is not None
        assert len(session_id) > 0
        assert recorder.session_id == session_id
        assert recorder.is_recording is True
        assert recorder.start_datetime is not None
    
    def test_stop_recording(self):
        """Test stopping a recording"""
        recorder = DetailedRecorder()
        recorder.start_recording()
        time.sleep(0.1)
        
        summary = recorder.stop_recording()
        
        assert recorder.is_recording is False
        assert "session_id" in summary
        assert "duration" in summary
        assert summary["duration"] >= 0.1
        assert "total_frames" in summary
    
    def test_record_frame(self):
        """Test recording a frame"""
        recorder = DetailedRecorder()
        recorder.start_recording()
        
        frame_data = {
            "timestamp": time.time(),
            "faceMesh": {
                "landmarks": [[0.1, 0.2, 0.3] for _ in range(468)]
            },
            "pose": {
                "landmarks": [[0.1, 0.2, 0.3] for _ in range(33)]
            }
        }
        
        recorder.record_frame(frame_data)
        
        assert len(recorder.frames) == 1
        assert recorder.frames[0] == frame_data
    
    def test_detect_emotion_change(self):
        """Test emotion change detection"""
        recorder = DetailedRecorder()
        recorder.start_recording()
        
        # First emotion
        changed1 = recorder.detect_emotion_change("neutral", 0.8)
        assert changed1 is True, "First emotion should register as change"
        
        # Same emotion
        changed2 = recorder.detect_emotion_change("neutral", 0.8)
        assert changed2 is False, "Same emotion should not register as change"
        
        # Different emotion
        changed3 = recorder.detect_emotion_change("happy", 0.9)
        assert changed3 is True, "Different emotion should register as change"
        
        # Check timeline
        assert len(recorder.emotion_timeline) == 2
    
    def test_detect_posture_decline(self):
        """Test posture decline detection"""
        recorder = DetailedRecorder()
        recorder.start_recording()
        
        # Good posture
        declined1 = recorder.detect_posture_decline("excellent", False)
        assert declined1 is False, "Good posture should not trigger decline"
        
        # Slouching
        declined2 = recorder.detect_posture_decline("poor", True)
        assert declined2 is True, "Slouching should trigger decline"
        
        # Check events
        assert len(recorder.posture_events) > 0
    
    def test_add_intervention_trigger(self):
        """Test adding intervention trigger"""
        recorder = DetailedRecorder()
        recorder.start_recording()
        
        recorder.add_intervention_trigger("posture_reminder")
        recorder.add_intervention_trigger("emotion_support")
        
        assert len(recorder.intervention_triggers) == 2
        assert recorder.intervention_triggers[0]["trigger_type"] == "posture_reminder"
        assert recorder.intervention_triggers[1]["trigger_type"] == "emotion_support"
    
    def test_get_status(self):
        """Test getting recorder status"""
        recorder = DetailedRecorder()
        recorder.start_recording()
        time.sleep(0.1)
        
        # Record some data
        recorder.detect_emotion_change("happy", 0.8)
        recorder.add_intervention_trigger("test")
        
        status = recorder.get_status()
        
        assert "session_id" in status
        assert "is_recording" in status
        assert "duration" in status
        assert "frames_recorded" in status
        assert "emotion_changes" in status
        assert "posture_events" in status
        assert "interventions_triggered" in status
        
        assert status["is_recording"] is True
        assert status["duration"] >= 0.1
        assert status["emotion_changes"] == 1
        assert status["interventions_triggered"] == 1


class TestSessionMetrics:
    """Test SessionMetrics class"""
    
    def test_metrics_initialization(self):
        """Test SessionMetrics initialization"""
        metrics = SessionMetrics("test_session")
        assert metrics.session_id == "test_session"
        assert len(metrics.emotion_points) == 0
        assert len(metrics.posture_events) == 0
    
    def test_add_emotion_point(self):
        """Test adding emotion data point"""
        metrics = SessionMetrics("test_session")
        
        metrics.add_emotion_point(1.0, "happy", 0.8)
        metrics.add_emotion_point(2.0, "happy", 0.9)
        
        assert len(metrics.emotion_points) == 2
    
    def test_add_posture_event(self):
        """Test adding posture event"""
        metrics = SessionMetrics("test_session")
        
        metrics.add_posture_event(1.0, "good_posture", 0.2)
        metrics.add_posture_event(10.0, "slouch", 0.8)
        
        assert len(metrics.posture_events) == 2
    
    def test_add_engagement_data(self):
        """Test adding engagement data"""
        metrics = SessionMetrics("test_session")
        
        metrics.add_engagement_data(face_detected=True, eye_contact_score=0.8)
        metrics.add_engagement_data(face_detected=True, eye_contact_score=0.7)
        metrics.add_engagement_data(face_detected=False, eye_contact_score=None)
        
        assert len(metrics.engagement_data) == 3
    
    def test_add_intervention_trigger(self):
        """Test adding intervention trigger"""
        metrics = SessionMetrics("test_session")
        
        metrics.add_intervention_trigger(10.0, "posture_reminder", "poor_posture_3min")
        metrics.add_intervention_trigger(120.0, "emotion_support", "sad_2min")
        
        assert len(metrics.intervention_history) == 2
    
    def test_calculate_emotion_variance(self):
        """Test emotion variance calculation"""
        metrics = SessionMetrics("test_session")
        
        # Add stable emotions
        for i in range(10):
            metrics.add_emotion_point(i * 1.0, "happy", 0.8)
        
        variance = metrics.calculate_emotion_variance()
        
        assert variance == 0.0, "Stable emotions should have 0 variance"
        
        # Add varied emotions
        for i in range(10):
            emotion = "happy" if i % 2 == 0 else "sad"
            metrics.add_emotion_point((i + 10) * 1.0, emotion, 0.7)
        
        variance = metrics.calculate_emotion_variance()
        assert variance > 0.0, "Varied emotions should have positive variance"
    
    def test_calculate_posture_stability(self):
        """Test posture stability calculation"""
        metrics = SessionMetrics("test_session")
        
        # Add stable posture events
        for i in range(10):
            metrics.add_posture_event(i * 10.0, "good_posture", 0.2)
        
        stability = metrics.calculate_posture_stability()
        
        assert stability > 0.8, "Stable posture should have high stability"
    
    def test_calculate_posture_improvement(self):
        """Test posture improvement calculation"""
        metrics = SessionMetrics("test_session")
        
        # Poor posture at start
        for i in range(5):
            metrics.add_posture_event(i * 10.0, "poor_posture", 0.8)
        
        # Good posture later
        for i in range(5, 10):
            metrics.add_posture_event(i * 10.0, "good_posture", 0.2)
        
        improvement = metrics.calculate_posture_improvement()
        
        assert improvement > 0, "Improving posture should have positive score"
    
    def test_calculate_engagement_level(self):
        """Test engagement level calculation"""
        metrics = SessionMetrics("test_session")
        
        # High engagement
        for i in range(10):
            metrics.add_engagement_data(face_detected=True, eye_contact_score=0.8)
        
        engagement = metrics.calculate_engagement_level()
        
        assert engagement > 0.7, "High engagement data should produce high level"
        
        # Low engagement
        for i in range(10):
            metrics.add_engagement_data(face_detected=False, eye_contact_score=0.2)
        
        engagement = metrics.calculate_engagement_level()
        assert engagement < 0.5, "Low engagement data should produce low level"
    
    def test_get_emotion_distribution(self):
        """Test emotion distribution calculation"""
        metrics = SessionMetrics("test_session")
        
        # Add emotions
        metrics.add_emotion_point(1.0, "happy", 0.8)
        metrics.add_emotion_point(2.0, "happy", 0.8)
        metrics.add_emotion_point(3.0, "happy", 0.8)
        metrics.add_emotion_point(4.0, "neutral", 0.7)
        
        distribution = metrics.get_emotion_distribution()
        
        assert "happy" in distribution
        assert "neutral" in distribution
        assert distribution["happy"] == 75.0  # 3/4 = 75%
        assert distribution["neutral"] == 25.0  # 1/4 = 25%
    
    def test_get_dominant_emotion(self):
        """Test getting dominant emotion"""
        metrics = SessionMetrics("test_session")
        
        # Add emotions with happy dominant
        for i in range(7):
            metrics.add_emotion_point(i * 1.0, "happy", 0.8)
        for i in range(3):
            metrics.add_emotion_point((i + 7) * 1.0, "neutral", 0.7)
        
        dominant, percentage = metrics.get_dominant_emotion()
        
        assert dominant == "happy"
        assert percentage == 70.0  # 7/10 = 70%
    
    def test_get_summary(self):
        """Test getting metrics summary"""
        metrics = SessionMetrics("test_session")
        
        # Add some data
        metrics.add_emotion_point(1.0, "happy", 0.8)
        metrics.add_posture_event(1.0, "good_posture", 0.2)
        metrics.add_engagement_data(face_detected=True, eye_contact_score=0.8)
        metrics.add_intervention_trigger(10.0, "test", "test_reason")
        
        summary = metrics.get_summary()
        
        assert "session_id" in summary
        assert "emotion_variance" in summary
        assert "posture_stability" in summary
        assert "engagement_level" in summary
        assert "dominant_emotion" in summary
        assert "total_interventions" in summary
        
        assert summary["session_id"] == "test_session"
        assert summary["total_interventions"] == 1


class TestRecorderIntegration:
    """Test integration between recorder and metrics"""
    
    def test_recorder_with_full_workflow(self):
        """Test complete recording workflow"""
        recorder = DetailedRecorder()
        
        # Start recording
        session_id = recorder.start_recording()
        assert session_id is not None
        
        # Record some frames
        for i in range(5):
            frame_data = {
                "timestamp": i * 0.1,
                "faceMesh": {"landmarks": [[0.1, 0.2, 0.3] for _ in range(468)]}
            }
            recorder.record_frame(frame_data)
        
        # Add emotion changes
        recorder.detect_emotion_change("neutral", 0.8)
        recorder.detect_emotion_change("happy", 0.9)
        
        # Add posture events
        recorder.detect_posture_decline("good", False)
        recorder.detect_posture_decline("poor", True)
        
        # Add interventions
        recorder.add_intervention_trigger("posture_reminder")
        
        # Get status
        status = recorder.get_status()
        assert status["frames_recorded"] == 5
        assert status["emotion_changes"] == 2
        assert status["interventions_triggered"] == 1
        
        # Stop recording
        summary = recorder.stop_recording()
        assert summary["total_frames"] == 5
        assert recorder.is_recording is False




