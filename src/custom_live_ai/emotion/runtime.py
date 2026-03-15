"""
Simplified emotion detection runtime using Face-API.js only
"""

import time
import logging
from typing import Dict, Optional
import numpy as np

from .config import EMOTIONS, SMOOTHING_MODE
from .smoothing import get_smoother

logger = logging.getLogger(__name__)


class EmotionRuntime:
    """
    Simplified emotion detection using Face-API.js exclusively
    """
    
    def __init__(self):
        self.smoother = get_smoother(mode=SMOOTHING_MODE) if SMOOTHING_MODE != "none" else None
        logger.info("✅ EmotionRuntime initialized (Face-API.js only, smoothing=%s)", SMOOTHING_MODE)
    
    def infer_one(
        self,
        landmarks_478: np.ndarray,
        faceapi_scores: Optional[Dict[str, float]] = None,
        timestamp_ms: Optional[int] = None
    ) -> Dict:
        """
        Run emotion inference using Face-API.js scores with smoothing
        
        Args:
            landmarks_478: MediaPipe 478 landmarks (normalized 0-1)
            faceapi_scores: Face-API.js emotion scores (0.0-1.0)
            timestamp_ms: Current timestamp in milliseconds
            
        Returns:
            Dictionary with emotion scores and metadata
        """
        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)
        
        # Use Face-API.js scores (convert 0-1 to 0-100)
        if faceapi_scores:
            raw_scores = {e: faceapi_scores.get(e, 0.0) * 100.0 for e in EMOTIONS}
            method = "faceapi"
            
            # NO SMOOTHING MODE: Return Face-API.js scores directly
            if self.smoother is None:
                # Find dominant emotion
                dominant = max(raw_scores, key=lambda e: raw_scores.get(e, 0.0))
                confidence = raw_scores.get(dominant, 0.0)
                
                return {
                    "scores": raw_scores,
                    "dominant": dominant,
                    "confidence": confidence,
                    "method": "faceapi_raw",
                    "tier": None,
                    "alpha_eff": None,
                    "margin": None,
                    "entropy": None,
                    "cooldown_ms_left": None,
                    "raw_scores": raw_scores
                }
            
            # SMOOTHING MODE: Apply smoothing
            # Convert 0-100 scores to 0-1 for smoother
            raw_probs = {e: raw_scores[e] / 100.0 for e in EMOTIONS}
            result = self.smoother.update(raw_probs, timestamp_ms)
            
            # Return smoothed result
            return {
                "scores": result.scores,
                "dominant": result.label,
                "confidence": result.confidence,
                "method": method,
                "tier": result.tier,
                "alpha_eff": result.alpha_eff,
                "margin": result.margin,
                "entropy": result.entropy,
                "cooldown_ms_left": result.cooldown_ms_left,
                # Include raw scores for debugging
                "raw_scores": raw_scores
            }
        else:
            # No Face-API.js scores provided
            logger.warning("No Face-API.js scores provided, defaulting to neutral")
            raw_scores = {e: 0.0 for e in EMOTIONS}
            raw_scores['neutral'] = 100.0
            
            # Return fallback result with 0 confidence
            return {
                "scores": raw_scores,
                "dominant": "neutral",
                "confidence": 0.0,
                "method": "fallback",
                "tier": None,
                "alpha_eff": None,
                "margin": None,
                "entropy": None,
                "cooldown_ms_left": None,
                "raw_scores": raw_scores
            }
    
    def reset(self):
        """Reset runtime state"""
        if SMOOTHING_MODE != "none":
            self.smoother = get_smoother(mode=SMOOTHING_MODE)
        logger.info("🔄 EmotionRuntime reset")


# Global runtime instance
_runtime: Optional[EmotionRuntime] = None


def get_runtime() -> EmotionRuntime:
    """Get or create global emotion runtime instance"""
    global _runtime
    if _runtime is None:
        _runtime = EmotionRuntime()
    return _runtime


def reset_runtime():
    """Reset global runtime state"""
    global _runtime
    if _runtime:
        _runtime.reset()

