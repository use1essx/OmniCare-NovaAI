"""
Test emotion detection runtime
"""

import numpy as np
from src.custom_live_ai.emotion.runtime import EmotionRuntime, get_runtime


class TestEmotionRuntime:
    """Test EmotionRuntime class"""
    
    def test_runtime_initialization(self):
        """Test that runtime initializes correctly"""
        runtime = EmotionRuntime()
        assert runtime.smoother is not None, "Smoother should be initialized"
    
    def test_infer_one_with_faceapi_scores(self):
        """Test emotion inference with face-api.js scores"""
        runtime = EmotionRuntime()
        landmarks = np.random.rand(468, 3)
        faceapi_scores = {
            "neutral": 0.1,
            "happy": 0.8,
            "sad": 0.05,
            "angry": 0.02,
            "surprise": 0.01,
            "fear": 0.01,
            "disgust": 0.01
        }
        
        result = runtime.infer_one(landmarks, faceapi_scores=faceapi_scores)
        
        # Validate result structure
        assert "dominant" in result, "Result should have 'dominant' key"
        assert "confidence" in result, "Result should have 'confidence' key"
        assert "scores" in result, "Result should have 'scores' key"
        assert "method" in result, "Result should have 'method' key"
        
        # Validate result values
        assert result["dominant"] in ["neutral", "happy", "sad", "angry", "surprise", "fear", "disgust"], \
            "Dominant emotion should be valid"
        assert 0 <= result["confidence"] <= 100, "Confidence should be 0-100"
        assert len(result["scores"]) == 7, "Should have 7 emotion scores"
        assert result["method"] == "faceapi", "Method should be 'faceapi'"
    
    def test_infer_one_without_faceapi_scores(self):
        """Test that inference fails gracefully without face-api.js scores"""
        runtime = EmotionRuntime()
        landmarks = np.random.rand(468, 3)
        
        result = runtime.infer_one(landmarks, faceapi_scores=None)
        
        # Should return neutral when no scores provided
        assert result["dominant"] == "neutral", "Should default to neutral without scores"
        assert result["confidence"] == 0.0, "Confidence should be 0 without scores"
    
    def test_scores_sum_to_100(self):
        """Test that emotion scores sum to approximately 100"""
        runtime = EmotionRuntime()
        landmarks = np.random.rand(468, 3)
        faceapi_scores = {
            "neutral": 0.2,
            "happy": 0.5,
            "sad": 0.1,
            "angry": 0.1,
            "surprise": 0.05,
            "fear": 0.03,
            "disgust": 0.02
        }
        
        result = runtime.infer_one(landmarks, faceapi_scores=faceapi_scores)
        
        total = sum(result["scores"].values())
        assert 99.0 <= total <= 101.0, f"Scores should sum to ~100, got {total}"
    
    def test_reset_runtime(self):
        """Test runtime reset"""
        runtime = EmotionRuntime()
        landmarks = np.random.rand(468, 3)
        faceapi_scores = {"happy": 0.8, "neutral": 0.2}
        
        # Run inference
        runtime.infer_one(landmarks, faceapi_scores=faceapi_scores)
        
        # Reset
        runtime.reset()
        
        # Should work after reset
        result = runtime.infer_one(landmarks, faceapi_scores=faceapi_scores)
        assert result is not None, "Should work after reset"
    
    def test_temporal_smoothing(self):
        """Test that temporal smoothing reduces jitter"""
        runtime = EmotionRuntime()
        landmarks = np.random.rand(468, 3)
        
        # Send alternating emotions
        results = []
        for i in range(10):
            if i % 2 == 0:
                faceapi_scores = {"happy": 0.7, "neutral": 0.3}
            else:
                faceapi_scores = {"sad": 0.7, "neutral": 0.3}
            
            result = runtime.infer_one(landmarks, faceapi_scores=faceapi_scores, timestamp_ms=i*100)
            results.append(result["dominant"])
        
        # Smoothing should prevent every-frame switching
        # Count transitions
        transitions = sum(1 for i in range(1, len(results)) if results[i] != results[i-1])
        
        # Should have fewer transitions than 5 (half the frames)
        assert transitions < 5, f"Smoothing should reduce transitions, got {transitions}"
    
    def test_get_runtime_singleton(self):
        """Test that get_runtime returns singleton"""
        runtime1 = get_runtime()
        runtime2 = get_runtime()
        assert runtime1 is runtime2, "Should return same instance"
    
    def test_raw_scores_returned(self):
        """Test that raw scores are returned in result"""
        runtime = EmotionRuntime()
        landmarks = np.random.rand(468, 3)
        faceapi_scores = {"happy": 0.8, "neutral": 0.2}
        
        result = runtime.infer_one(landmarks, faceapi_scores=faceapi_scores)
        
        # Should have raw_scores in result
        assert "raw_scores" in result, "Result should include raw_scores"
        assert result["raw_scores"] is not None, "Raw scores should not be None"


class TestEmotionRuntimeEdgeCases:
    """Test edge cases and error handling"""
    
    def test_invalid_landmarks_shape(self):
        """Test handling of invalid landmarks"""
        runtime = EmotionRuntime()
        invalid_landmarks = np.random.rand(100, 3)  # Wrong shape
        faceapi_scores = {"happy": 0.8, "neutral": 0.2}
        
        # Should not crash
        result = runtime.infer_one(invalid_landmarks, faceapi_scores=faceapi_scores)
        assert result is not None, "Should handle invalid landmarks gracefully"
    
    def test_missing_emotion_keys(self):
        """Test handling of incomplete emotion scores"""
        runtime = EmotionRuntime()
        landmarks = np.random.rand(468, 3)
        incomplete_scores = {"happy": 0.8, "sad": 0.2}  # Missing emotions
        
        # Should not crash
        result = runtime.infer_one(landmarks, faceapi_scores=incomplete_scores)
        assert result is not None, "Should handle incomplete scores"
    
    def test_extreme_confidence_values(self):
        """Test handling of extreme confidence values"""
        runtime = EmotionRuntime()
        landmarks = np.random.rand(468, 3)
        
        # Test with very high confidence
        high_conf_scores = {"happy": 0.99, "neutral": 0.01}
        result = runtime.infer_one(landmarks, faceapi_scores=high_conf_scores)
        assert 0 <= result["confidence"] <= 100, "Should handle high confidence"
        
        # Test with very low confidence (ambiguous)
        low_conf_scores = {
            "neutral": 0.15,
            "happy": 0.14,
            "sad": 0.14,
            "angry": 0.14,
            "surprise": 0.14,
            "fear": 0.14,
            "disgust": 0.15
        }
        result = runtime.infer_one(landmarks, faceapi_scores=low_conf_scores)
        assert result["confidence"] < 30, "Low confidence should be reflected"




