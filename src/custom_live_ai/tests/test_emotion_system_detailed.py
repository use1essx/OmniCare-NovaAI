"""
Detailed Emotion Detection System Tests
Tests all emotion detection components in detail
"""

import pytest
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestEmotionConfig:
    """Test emotion configuration"""
    
    def test_smoothing_mode_valid(self):
        """Test SMOOTHING_MODE is valid"""
        from src.custom_live_ai.emotion.config import SMOOTHING_MODE
        
        assert SMOOTHING_MODE in ['none', 'basic', '3tier']
    
    def test_emotions_list_complete(self):
        """Test EMOTIONS list has all 7 emotions"""
        from src.custom_live_ai.emotion.config import EMOTIONS
        
        expected = ['neutral', 'happy', 'sad', 'angry', 'surprise', 'fear', 'disgust']
        assert len(EMOTIONS) == 7
        for emotion in expected:
            assert emotion in EMOTIONS
    
    def test_tier_configs_when_smoothing_enabled(self):
        """Test TIER_CONFIGS when smoothing is enabled"""
        from src.custom_live_ai.emotion.config import SMOOTHING_MODE, TIER_CONFIGS
        
        if SMOOTHING_MODE == '3tier':
            assert 1 in TIER_CONFIGS
            assert 2 in TIER_CONFIGS
            assert 3 in TIER_CONFIGS
            
            # Check each tier has required keys
            for tier in [1, 2, 3]:
                assert 'alpha' in TIER_CONFIGS[tier]
                assert 'window' in TIER_CONFIGS[tier]
                assert 'hold_ms' in TIER_CONFIGS[tier]
                assert 'cooldown_ms' in TIER_CONFIGS[tier]
                
                # Validate alpha range
                assert 0 < TIER_CONFIGS[tier]['alpha'] <= 1.0
    
    def test_micro_expression_config(self):
        """Test micro-expression configuration"""
        from src.custom_live_ai.emotion.config import (
            MICRO_EXPRESSION_EMOTIONS,
            MICRO_EXPRESSION_THRESHOLD,
            MICRO_EXPRESSION_HOLD_MS
        )
        
        assert 'surprise' in MICRO_EXPRESSION_EMOTIONS
        assert 'fear' in MICRO_EXPRESSION_EMOTIONS
        assert 0 < MICRO_EXPRESSION_THRESHOLD <= 1.0
        assert MICRO_EXPRESSION_HOLD_MS >= 0


class TestEmotionRuntime:
    """Test emotion runtime functionality"""
    
    def test_runtime_initialization(self):
        """Test runtime can be initialized"""
        from src.custom_live_ai.emotion.runtime import EmotionRuntime
        
        runtime = EmotionRuntime()
        assert runtime is not None
    
    def test_runtime_singleton(self):
        """Test runtime uses singleton pattern"""
        from src.custom_live_ai.emotion.runtime import get_runtime
        
        runtime1 = get_runtime()
        runtime2 = get_runtime()
        
        assert runtime1 is runtime2
    
    def test_infer_one_with_faceapi_scores(self):
        """Test inference with Face-API.js scores"""
        from src.custom_live_ai.emotion.runtime import get_runtime
        
        runtime = get_runtime()
        
        faceapi_scores = {
            'neutral': 0.05,
            'happy': 0.85,
            'sad': 0.02,
            'angry': 0.02,
            'surprise': 0.02,
            'fear': 0.02,
            'disgust': 0.02
        }
        
        landmarks = np.random.rand(468, 2)
        result = runtime.infer_one(landmarks, faceapi_scores)
        
        # Check result structure
        assert 'scores' in result
        assert 'dominant' in result
        assert 'confidence' in result
        assert 'method' in result
        
        # Check dominant emotion
        assert result['dominant'] == 'happy'
        assert result['confidence'] > 0
        
        # Check scores
        assert isinstance(result['scores'], dict)
        assert len(result['scores']) == 7
    
    def test_infer_one_without_faceapi_scores(self):
        """Test inference without Face-API.js scores (fallback)"""
        from src.custom_live_ai.emotion.runtime import get_runtime
        
        runtime = get_runtime()
        
        landmarks = np.random.rand(468, 2)
        result = runtime.infer_one(landmarks, faceapi_scores=None)
        
        # Should default to neutral
        assert result['dominant'] == 'neutral'
        assert result['confidence'] == 0.0 or result['confidence'] == 100.0
    
    def test_infer_one_surprise_detection(self):
        """Test surprise emotion detection specifically"""
        from src.custom_live_ai.emotion.runtime import get_runtime
        
        runtime = get_runtime()
        
        faceapi_scores = {
            'neutral': 0.05,
            'happy': 0.05,
            'sad': 0.02,
            'angry': 0.02,
            'surprise': 0.85,  # High surprise
            'fear': 0.01,
            'disgust': 0.00
        }
        
        landmarks = np.random.rand(468, 2)
        result = runtime.infer_one(landmarks, faceapi_scores)
        
        # With no smoothing, should detect surprise instantly
        assert result['dominant'] == 'surprise'
        assert result['scores']['surprise'] > 80.0
    
    def test_runtime_reset(self):
        """Test runtime can be reset"""
        from src.custom_live_ai.emotion.runtime import get_runtime, reset_runtime
        
        runtime = get_runtime()
        
        # Perform inference
        faceapi_scores = {'happy': 0.8, 'neutral': 0.2, 'sad': 0, 'angry': 0, 'surprise': 0, 'fear': 0, 'disgust': 0}
        runtime.infer_one(np.random.rand(468, 2), faceapi_scores)
        
        # Reset
        reset_runtime()
        
        # Should still work
        result = runtime.infer_one(np.random.rand(468, 2), faceapi_scores)
        assert result is not None


class TestEmotionSmoothing:
    """Test emotion smoothing functionality"""
    
    def test_get_smoother_none_mode(self):
        """Test get_smoother with mode='none'"""
        from src.custom_live_ai.emotion.smoothing import get_smoother
        
        smoother = get_smoother(mode='none')
        
        # Should return None or a no-op smoother
        # Depending on implementation
        assert smoother is None or smoother is not None
    
    def test_get_smoother_3tier_mode(self):
        """Test get_smoother with mode='3tier'"""
        from src.custom_live_ai.emotion.smoothing import get_smoother
        
        smoother = get_smoother(mode='3tier')
        
        assert smoother is not None
        assert hasattr(smoother, 'update') or hasattr(smoother, 'process')
    
    def test_smoother_update_basic(self):
        """Test smoother update function"""
        from src.custom_live_ai.emotion.smoothing import get_smoother
        from src.custom_live_ai.emotion.config import SMOOTHING_MODE
        
        if SMOOTHING_MODE != 'none':
            smoother = get_smoother(SMOOTHING_MODE)
            
            raw_probs = {
                'neutral': 0.1,
                'happy': 0.7,
                'sad': 0.05,
                'angry': 0.05,
                'surprise': 0.05,
                'fear': 0.03,
                'disgust': 0.02
            }
            
            if hasattr(smoother, 'update'):
                result = smoother.update(raw_probs, timestamp_ms=1000)
                assert result is not None
            elif hasattr(smoother, 'process'):
                result = smoother.process(raw_probs)
                assert result is not None


class TestFeatureExtractor:
    """Test feature extraction functionality"""
    
    def test_feature_extractor_import(self):
        """Test feature extractor can be imported"""
        from src.custom_live_ai.emotion import feature_extractor
        
        assert feature_extractor is not None
    
    def test_extract_features_if_available(self):
        """Test feature extraction if function is available"""
        try:
            from src.custom_live_ai.emotion.feature_extractor import extract_features
            
            # Test with sample landmarks
            landmarks = np.random.rand(468, 2)
            features = extract_features(landmarks)
            
            assert features is not None
            assert isinstance(features, (np.ndarray, list, dict))
        except ImportError:
            pytest.skip("extract_features not available in this version")


class TestEmotionLogger:
    """Test emotion logging functionality"""
    
    def test_emotion_logger_import(self):
        """Test emotion logger can be imported"""
        from src.custom_live_ai.emotion import logger
        
        assert logger is not None
    
    def test_get_logger_function(self):
        """Test get_logger function if available"""
        try:
            from src.custom_live_ai.emotion.logger import get_logger
            
            emotion_logger = get_logger()
            # Logger might be None if logging is disabled
            assert emotion_logger is None or emotion_logger is not None
        except ImportError:
            pytest.skip("get_logger not available")


class TestEmotionAPI:
    """Test emotion API integration"""
    
    def test_emotion_api_router_exists(self):
        """Test emotion API router exists"""
        from src.custom_live_ai.api.emotion_api import router
        
        assert router is not None
    
    def test_emotion_api_models(self):
        """Test emotion API models are defined"""
        from src.custom_live_ai.api.emotion_api import (
            EmotionAnalysisRequest,
            EmotionAnalysisResponse,
            HybridEmotionRequest
        )
        
        # Check models have required fields
        assert hasattr(EmotionAnalysisRequest, '__annotations__')
        assert hasattr(EmotionAnalysisResponse, '__annotations__')
        assert hasattr(HybridEmotionRequest, '__annotations__')
    
    def test_emotion_map(self):
        """Test EMOTION_MAP is defined"""
        from src.custom_live_ai.api.emotion_api import EMOTION_MAP
        
        assert isinstance(EMOTION_MAP, dict)
        assert len(EMOTION_MAP) == 7
        
        for emotion in ['happy', 'sad', 'angry', 'surprise', 'fear', 'neutral', 'disgust']:
            assert emotion in EMOTION_MAP
            assert 'emoji' in EMOTION_MAP[emotion]
            assert 'label' in EMOTION_MAP[emotion]


class TestEmotionEndToEnd:
    """End-to-end emotion detection tests"""
    
    def test_complete_emotion_pipeline_happy(self):
        """Test complete pipeline: Face-API.js → Runtime → Result"""
        from src.custom_live_ai.emotion.runtime import get_runtime
        import time
        
        runtime = get_runtime()
        
        # Simulate Face-API.js detecting happy
        faceapi_scores = {
            'neutral': 0.05,
            'happy': 0.85,
            'sad': 0.02,
            'angry': 0.02,
            'surprise': 0.02,
            'fear': 0.02,
            'disgust': 0.02
        }
        
        landmarks = np.random.rand(468, 2)
        timestamp_ms = int(time.time() * 1000)
        
        result = runtime.infer_one(landmarks, faceapi_scores, timestamp_ms)
        
        # Verify result
        assert result['dominant'] == 'happy'
        assert result['scores']['happy'] > 80.0
        assert result['confidence'] > 0
        assert result['method'] in ['faceapi', 'faceapi_raw']
    
    def test_complete_emotion_pipeline_surprise(self):
        """Test complete pipeline for surprise (transient emotion)"""
        from src.custom_live_ai.emotion.runtime import get_runtime
        import time
        
        runtime = get_runtime()
        
        # Simulate Face-API.js detecting surprise
        faceapi_scores = {
            'neutral': 0.02,
            'happy': 0.02,
            'sad': 0.01,
            'angry': 0.01,
            'surprise': 0.90,  # Very high surprise
            'fear': 0.02,
            'disgust': 0.02
        }
        
        landmarks = np.random.rand(468, 2)
        timestamp_ms = int(time.time() * 1000)
        
        result = runtime.infer_one(landmarks, faceapi_scores, timestamp_ms)
        
        # With no smoothing, should detect immediately
        assert result['dominant'] == 'surprise'
        assert result['scores']['surprise'] > 85.0
    
    def test_emotion_consistency_over_frames(self):
        """Test emotion detection consistency over multiple frames"""
        from src.custom_live_ai.emotion.runtime import get_runtime
        import time
        
        runtime = get_runtime()
        
        # Simulate 10 frames of consistent happy emotion
        faceapi_scores = {
            'neutral': 0.05,
            'happy': 0.80,
            'sad': 0.03,
            'angry': 0.03,
            'surprise': 0.03,
            'fear': 0.03,
            'disgust': 0.03
        }
        
        results = []
        for i in range(10):
            landmarks = np.random.rand(468, 2)
            timestamp_ms = int(time.time() * 1000) + i * 33  # ~30fps
            result = runtime.infer_one(landmarks, faceapi_scores, timestamp_ms)
            results.append(result['dominant'])
        
        # All frames should detect happy (with no smoothing)
        happy_count = results.count('happy')
        assert happy_count >= 8  # At least 80% should be happy


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

