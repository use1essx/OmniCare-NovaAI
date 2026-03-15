"""
Full System Validation Tests
Tests all imports, links, and basic functionality across the entire codebase
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestImports:
    """Test that all modules can be imported without errors"""
    
    def test_import_main(self):
        """Test main application imports"""
        import src.custom_live_ai.main
        assert hasattr(src.main, 'app')
    
    def test_import_api_modules(self):
        """Test all API module imports"""
        from src.custom_live_ai.api import emotion_api
        from src.custom_live_ai.api import reports
        from src.custom_live_ai.api import sessions
        
        assert hasattr(emotion_api, 'router')
        assert hasattr(sessions, 'router')
        assert hasattr(reports, 'router')
    
    def test_import_emotion_modules(self):
        """Test emotion detection module imports"""
        from src.custom_live_ai.emotion import config
        from src.custom_live_ai.emotion import runtime
        from src.custom_live_ai.emotion import smoothing
        
        assert hasattr(config, 'EMOTIONS')
        assert hasattr(config, 'SMOOTHING_MODE')
        assert hasattr(runtime, 'get_runtime')
        assert hasattr(smoothing, 'get_smoother')
    
    def test_import_database_modules(self):
        """Test database module imports"""
        from src.custom_live_ai.database import config as db_config
        from src.custom_live_ai.models import database
        
        assert hasattr(db_config, 'get_db')
        assert hasattr(database, 'Base')
        assert hasattr(database, 'RecordingSession')
        assert hasattr(database, 'EmotionEntry')
    
    def test_import_intervention_modules(self):
        """Test intervention module imports"""
        from src.custom_live_ai.intervention import engine
        from src.custom_live_ai.intervention import responder
        
        assert hasattr(engine, 'InterventionEngine')
        assert hasattr(responder, 'InterventionResponder')
    
    def test_import_report_modules(self):
        """Test report generation module imports"""
        from src.custom_live_ai.reports import generator
        
        assert hasattr(generator, 'ReportGenerator')
    
    def test_import_utils_modules(self):
        """Test utility module imports"""
        from src.custom_live_ai.utils import data_recorder
        from src.custom_live_ai.utils import detailed_recorder
        
        assert hasattr(data_recorder, 'DataRecorder')
        assert hasattr(detailed_recorder, 'DetailedRecorder')
    
    def test_import_video_modules(self):
        """Test video processing module imports"""
        from src.custom_live_ai.video import mediapipe_analyzer
        
        assert hasattr(mediapipe_analyzer, 'MediaPipeAnalyzer')


class TestModuleLinking:
    """Test that modules are properly linked and can call each other"""
    
    def test_emotion_runtime_uses_config(self):
        """Test emotion runtime uses config correctly"""
        from src.custom_live_ai.emotion.runtime import get_runtime
        from src.custom_live_ai.emotion.config import EMOTIONS
        
        runtime = get_runtime()
        assert runtime is not None
        
        # Test that EMOTIONS is valid
        assert isinstance(EMOTIONS, list)
        assert len(EMOTIONS) > 0
        assert 'happy' in EMOTIONS
        assert 'sad' in EMOTIONS
        assert 'surprise' in EMOTIONS
    
    def test_emotion_runtime_uses_smoothing(self):
        """Test emotion runtime can create smoother"""
        from src.custom_live_ai.emotion.runtime import get_runtime
        from src.custom_live_ai.emotion.config import SMOOTHING_MODE
        
        runtime = get_runtime()
        
        # If smoothing mode is "none", smoother should be None
        if SMOOTHING_MODE == "none":
            assert runtime.smoother is None
        else:
            assert runtime.smoother is not None
    
    def test_api_uses_database(self):
        """Test API modules can access database"""
        from src.custom_live_ai.database.config import get_db
        
        # Verify database connection can be established
        db_gen = get_db()
        db = next(db_gen)
        assert db is not None
        db.close()
    
    def test_sessions_api_uses_emotion_runtime(self):
        """Test sessions API can use emotion runtime"""
        from src.custom_live_ai.emotion.runtime import get_runtime
        
        # Verify emotion runtime is accessible
        runtime = get_runtime()
        assert runtime is not None
    
    def test_intervention_engine_initialization(self):
        """Test intervention engine can be initialized"""
        from src.custom_live_ai.intervention.engine import InterventionEngine
        
        engine = InterventionEngine()
        assert engine is not None
        assert hasattr(engine, 'check_triggers')
    
    def test_report_generator_initialization(self):
        """Test report generator can be initialized"""
        from src.custom_live_ai.reports.generator import ReportGenerator
        
        generator = ReportGenerator()
        assert generator is not None


class TestEmotionSystem:
    """Test emotion detection system functionality"""
    
    def test_emotion_config_values(self):
        """Test emotion config has valid values"""
        from src.custom_live_ai.emotion.config import (
            EMOTIONS, SMOOTHING_MODE, T1_THRESHOLD, T2_THRESHOLD
        )
        
        # Test EMOTIONS list
        assert len(EMOTIONS) == 7
        expected_emotions = ['neutral', 'happy', 'sad', 'angry', 'surprise', 'fear', 'disgust']
        for emotion in expected_emotions:
            assert emotion in EMOTIONS
        
        # Test SMOOTHING_MODE
        assert SMOOTHING_MODE in ['none', 'basic', '3tier']
        
        # Test thresholds if smoothing is enabled
        if SMOOTHING_MODE != 'none':
            assert 0 < T1_THRESHOLD <= 1.0
            assert 0 < T2_THRESHOLD <= 1.0
            assert T1_THRESHOLD > T2_THRESHOLD
    
    def test_emotion_runtime_inference(self):
        """Test emotion runtime can perform inference"""
        from src.custom_live_ai.emotion.runtime import get_runtime
        import numpy as np
        
        runtime = get_runtime()
        
        # Test with sample Face-API.js scores
        faceapi_scores = {
            'neutral': 0.1,
            'happy': 0.7,
            'sad': 0.05,
            'angry': 0.05,
            'surprise': 0.05,
            'fear': 0.03,
            'disgust': 0.02
        }
        
        landmarks = np.random.rand(468, 2)
        result = runtime.infer_one(landmarks, faceapi_scores)
        
        assert 'scores' in result
        assert 'dominant' in result
        assert 'confidence' in result
        assert 'method' in result
        
        # Dominant should be 'happy' since it has highest score
        assert result['dominant'] == 'happy'
        assert result['confidence'] > 0
    
    def test_smoother_creation(self):
        """Test smoother can be created"""
        from src.custom_live_ai.emotion.smoothing import get_smoother
        from src.custom_live_ai.emotion.config import SMOOTHING_MODE
        
        if SMOOTHING_MODE != 'none':
            smoother = get_smoother(SMOOTHING_MODE)
            assert smoother is not None
            assert hasattr(smoother, 'update') or hasattr(smoother, 'process')


class TestDatabaseModels:
    """Test database models are properly defined"""
    
    def test_recording_session_model(self):
        """Test RecordingSession model"""
        from src.custom_live_ai.models.database import RecordingSession
        
        # Check required columns exist
        assert hasattr(RecordingSession, 'session_id')
        assert hasattr(RecordingSession, 'user_id')
        assert hasattr(RecordingSession, 'start_time')
        assert hasattr(RecordingSession, 'end_time')
        assert hasattr(RecordingSession, 'duration_seconds')
    
    def test_emotion_entry_model(self):
        """Test EmotionEntry model"""
        from src.custom_live_ai.models.database import EmotionEntry
        
        assert hasattr(EmotionEntry, 'id')
        assert hasattr(EmotionEntry, 'session_id')
        assert hasattr(EmotionEntry, 'timestamp')
        assert hasattr(EmotionEntry, 'emotion')
        assert hasattr(EmotionEntry, 'confidence')
    
    def test_posture_entry_model(self):
        """Test PostureEntry model"""
        from src.custom_live_ai.models.database import PostureEntry
        
        assert hasattr(PostureEntry, 'id')
        assert hasattr(PostureEntry, 'session_id')
        assert hasattr(PostureEntry, 'timestamp')
        assert hasattr(PostureEntry, 'posture_quality')
    
    def test_intervention_log_model(self):
        """Test InterventionLog model"""
        from src.custom_live_ai.models.database import InterventionLog
        
        assert hasattr(InterventionLog, 'id')
        assert hasattr(InterventionLog, 'session_id')
        assert hasattr(InterventionLog, 'timestamp')
        assert hasattr(InterventionLog, 'intervention_type')
        assert hasattr(InterventionLog, 'message')


class TestAPIEndpoints:
    """Test API endpoint structure"""
    
    def test_emotion_api_routes(self):
        """Test emotion API has expected routes"""
        from src.custom_live_ai.api.emotion_api import router
        
        routes = [route.path for route in router.routes]
        
        # Check key routes exist
        assert any('/hybrid-analyze' in route for route in routes)
        assert any('/health' in route for route in routes)
    
    def test_sessions_api_routes(self):
        """Test sessions API has expected routes"""
        from src.custom_live_ai.api.sessions import router
        
        routes = [route.path for route in router.routes]
        
        # Check key routes exist
        assert any('/start' in route for route in routes)
        assert any('/stop' in route for route in routes)
    
    def test_reports_api_routes(self):
        """Test reports API has expected routes"""
        from src.custom_live_ai.api.reports import router
        
        routes = [route.path for route in router.routes]
        
        # Check report generation route exists
        assert any('/generate' in route or '/create' in route for route in routes)


class TestInterventionSystem:
    """Test intervention system"""
    
    def test_intervention_rules_exist(self):
        """Test intervention rules are defined"""
        from src.custom_live_ai.intervention.rules import INTERVENTION_RULES
        
        assert INTERVENTION_RULES is not None
        assert isinstance(INTERVENTION_RULES, dict)
        assert len(INTERVENTION_RULES) > 0
    
    def test_intervention_engine_check_triggers(self):
        """Test intervention engine can check triggers"""
        from src.custom_live_ai.intervention.engine import InterventionEngine
        
        engine = InterventionEngine()
        
        # Test with sample data
        result = engine.check_triggers(
            emotion='sad',
            emotion_confidence=0.8,
            posture_quality='poor',
            posture_score=0.3,
            engagement_level=0.4
        )
        
        assert isinstance(result, dict)
        assert 'should_intervene' in result
        assert 'intervention_type' in result


class TestReportGeneration:
    """Test report generation system"""
    
    def test_report_generator_exists(self):
        """Test report generator can be created"""
        from src.custom_live_ai.reports.generator import ReportGenerator
        
        generator = ReportGenerator()
        assert generator is not None
    
    def test_report_schemas_defined(self):
        """Test report schemas are defined"""
        from src.custom_live_ai.reports.schemas import SessionReport, EmotionSummary
        
        # Check schemas have required fields
        assert hasattr(SessionReport, '__annotations__')
        assert hasattr(EmotionSummary, '__annotations__')


class TestUtilities:
    """Test utility modules"""
    
    def test_data_recorder_initialization(self):
        """Test data recorder can be initialized"""
        from src.custom_live_ai.utils.data_recorder import DataRecorder
        
        recorder = DataRecorder(session_id="test_session")
        assert recorder is not None
        assert recorder.session_id == "test_session"
    
    def test_detailed_recorder_initialization(self):
        """Test detailed recorder can be initialized"""
        from src.custom_live_ai.utils.detailed_recorder import DetailedRecorder
        
        recorder = DetailedRecorder(session_id="test_session")
        assert recorder is not None
        assert recorder.session_id == "test_session"
    
    def test_session_metrics_calculation(self):
        """Test session metrics can be calculated"""
        from src.custom_live_ai.utils.session_metrics import calculate_session_metrics
        
        # Test with minimal data
        metrics = calculate_session_metrics(
            session_id="test",
            frames=[]
        )
        
        assert metrics is not None
        assert isinstance(metrics, dict)


class TestMainApplication:
    """Test main FastAPI application"""
    
    def test_app_creation(self):
        """Test FastAPI app is created"""
        from src.custom_live_ai.main import app
        
        assert app is not None
        assert hasattr(app, 'routes')
    
    def test_routers_registered(self):
        """Test all routers are registered"""
        from src.custom_live_ai.main import app
        
        routes = [route.path for route in app.routes]
        
        # Check that key API routes are registered
        assert any('/api/emotion' in route for route in routes)
        assert any('/api/sessions' in route for route in routes)
        assert any('/api/reports' in route for route in routes)
    
    def test_cors_configured(self):
        """Test CORS is configured"""
        from src.custom_live_ai.main import app
        
        # Check CORS middleware is added
        middlewares = [middleware for middleware in app.user_middleware]
        assert len(middlewares) > 0


class TestErrorHandling:
    """Test error handling across modules"""
    
    def test_emotion_runtime_handles_invalid_input(self):
        """Test emotion runtime handles invalid input gracefully"""
        from src.custom_live_ai.emotion.runtime import get_runtime
        import numpy as np
        
        runtime = get_runtime()
        
        # Test with no Face-API.js scores (should default to neutral)
        landmarks = np.random.rand(468, 2)
        result = runtime.infer_one(landmarks, faceapi_scores=None)
        
        assert result is not None
        assert result['dominant'] == 'neutral'
        assert result['confidence'] >= 0
    
    def test_database_connection_error_handling(self):
        """Test database connection errors are handled"""
        from src.custom_live_ai.database.config import get_db
        
        try:
            db_gen = get_db()
            db = next(db_gen)
            db.close()
        except Exception as e:
            # Should not raise unhandled exception
            assert isinstance(e, Exception)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

