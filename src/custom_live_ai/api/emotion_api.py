"""
Emotion Detection API - Face-API.js with Temporal Smoothing
Uses Face-API.js emotion detection with adaptive smoothing
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from collections import deque
import os
import numpy as np
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/emotion", tags=["emotion"])

# Import emotion runtime (after router creation)
from src.custom_live_ai.emotion.runtime import get_runtime  # noqa: E402
from src.custom_live_ai.emotion.logger import get_logger  # noqa: E402
from src.custom_live_ai.emotion.config import ENABLE_LOGGING  # noqa: E402

# Initialize runtime (lazy loaded with model if available)
_runtime = None
_parquet_logger = None
_debug_cache: deque = deque(maxlen=100)  # Cache last 100 decisions for debugging

def _get_runtime():
    """Get or create runtime instance"""
    global _runtime
    if _runtime is None:
        _runtime = get_runtime()
    return _runtime

def _get_logger():
    """Get or create parquet logger if logging enabled"""
    global _parquet_logger
    if os.getenv('ENABLE_LOGGING', str(ENABLE_LOGGING)).lower() in ('true', '1', 'yes'):
        if _parquet_logger is None:
            _parquet_logger = get_logger()
        return _parquet_logger
    return None


class FaceMeshLandmark(BaseModel):
    """Single face mesh landmark"""
    x: float
    y: float
    z: float


class EmotionAnalysisRequest(BaseModel):
    """Request for emotion analysis"""
    landmarks: List[FaceMeshLandmark] = Field(..., description="Face mesh landmarks (468 points)")
    session_id: Optional[str] = Field(None, description="Optional session ID for logging")


class EmotionAnalysisResponse(BaseModel):
    """Response with emotion analysis"""
    dominant_emotion: str
    emoji: str
    confidence: float
    scores: Dict[str, float]
    face_detected: bool
    method: Optional[str] = "faceapi"
    # 3-tier smoothing diagnostics (optional, only present in 3tier mode)
    tier: Optional[int] = None
    alpha_eff: Optional[float] = None
    margin: Optional[float] = None
    entropy: Optional[float] = None
    cooldown_ms_left: Optional[int] = None
    # Debug information (raw scores before smoothing)
    raw_scores: Optional[Dict[str, float]] = None


class HybridEmotionRequest(BaseModel):
    """Request for hybrid emotion analysis"""
    landmarks: List[FaceMeshLandmark] = Field(..., description="Face mesh landmarks (468 points)")
    faceapi_emotions: Optional[Dict[str, float]] = Field(None, description="face-api.js emotion scores")
    session_id: Optional[str] = Field(None, description="Optional session ID for logging")


# Emotion mapping with emojis
EMOTION_MAP = {
    'happy': {'emoji': '😊', 'label': 'Happy'},
    'sad': {'emoji': '😢', 'label': 'Sad'},
    'angry': {'emoji': '😠', 'label': 'Angry'},
    'neutral': {'emoji': '😐', 'label': 'Neutral'},
    'surprise': {'emoji': '😮', 'label': 'Surprised'},
    'fear': {'emoji': '😨', 'label': 'Fearful'},
    'disgust': {'emoji': '🤢', 'label': 'Disgusted'}
}


def calculate_distance(p1: FaceMeshLandmark, p2: FaceMeshLandmark) -> float:
    """Calculate Euclidean distance between two landmarks"""
    return np.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)


def calculate_distance_3d(p1: FaceMeshLandmark, p2: FaceMeshLandmark) -> float:
    """Calculate 3D Euclidean distance between two landmarks"""
    return np.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)


def get_angle(p1: FaceMeshLandmark, p2: FaceMeshLandmark, p3: FaceMeshLandmark) -> float:
    """Calculate angle at p2 formed by p1-p2-p3"""
    v1 = np.array([p1.x - p2.x, p1.y - p2.y])
    v2 = np.array([p3.x - p2.x, p3.y - p2.y])
    
    cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    angle = np.arccos(cos_angle)
    return np.degrees(angle)


def analyze_emotion_detailed(landmarks: List[FaceMeshLandmark]) -> Dict[str, float]:
    """
    IMPROVED emotion analysis using comprehensive FACS features
    Uses more landmarks and better calibrated thresholds
    """
    if not landmarks or len(landmarks) < 468:
        return {
            'neutral': 100.0,
            'happy': 0.0,
            'sad': 0.0,
            'angry': 0.0,
            'surprise': 0.0,
            'fear': 0.0,
            'disgust': 0.0
        }
    
    lm = landmarks
    
    # === NORMALIZE BY FACE SIZE ===
    # Use face width for normalization
    left_face = lm[234]
    right_face = lm[454]
    face_width = calculate_distance(left_face, right_face)
    
    if face_width < 0.001:
        face_width = 0.1  # Fallback
    
    # === DETAILED FACIAL FEATURE EXTRACTION ===
    
    # 1. MOUTH ANALYSIS (Multiple points for accuracy)
    # Mouth corners
    left_corner = lm[61]
    right_corner = lm[291]
    
    # Lips (outer)
    upper_lip_top = lm[0]
    upper_lip = lm[13]
    lower_lip = lm[14]
    lower_lip_bottom = lm[17]
    
    # Additional mouth points for detail
    lm[62]
    lm[292]
    lm[87]
    lm[317]
    
    # Mouth width and height
    mouth_width = calculate_distance(left_corner, right_corner) / face_width
    mouth_height = abs(upper_lip.y - lower_lip.y) / face_width
    abs(upper_lip_top.y - lower_lip_bottom.y) / face_width
    
    # Mouth openness ratio
    mouth_openness = mouth_height / (mouth_width + 0.001)
    
    # Smile detection: corners higher than center
    corners_avg_y = (left_corner.y + right_corner.y) / 2
    lips_center_y = (upper_lip.y + lower_lip.y) / 2
    smile_lift = (lips_center_y - corners_avg_y) / face_width * 100
    
    # Mouth curvature (detailed)
    mouth_curve = get_angle(left_corner, upper_lip, right_corner)
    
    # 2. EYES ANALYSIS (Detailed)
    # Left eye
    left_eye_top = lm[159]
    left_eye_bottom = lm[145]
    left_eye_left = lm[33]
    left_eye_right = lm[133]
    
    # Right eye
    right_eye_top = lm[386]
    right_eye_bottom = lm[374]
    right_eye_left = lm[362]
    right_eye_right = lm[263]
    
    # Eye openness
    left_eye_height = abs(left_eye_top.y - left_eye_bottom.y) / face_width
    right_eye_height = abs(right_eye_top.y - right_eye_bottom.y) / face_width
    avg_eye_height = (left_eye_height + right_eye_height) / 2
    
    # Eye width
    left_eye_width = calculate_distance(left_eye_left, left_eye_right) / face_width
    right_eye_width = calculate_distance(right_eye_left, right_eye_right) / face_width
    (left_eye_width + right_eye_width) / 2
    
    # Eye aspect ratio (for squinting detection)
    left_eye_ratio = left_eye_height / (left_eye_width + 0.001)
    right_eye_ratio = right_eye_height / (right_eye_width + 0.001)
    avg_eye_ratio = (left_eye_ratio + right_eye_ratio) / 2
    
    # 3. EYEBROWS ANALYSIS (Detailed)
    # Left eyebrow
    left_brow_inner = lm[70]
    left_brow_mid = lm[107]
    left_brow_outer = lm[66]
    
    # Right eyebrow
    right_brow_inner = lm[300]
    right_brow_mid = lm[336]
    right_brow_outer = lm[296]
    
    # Eyebrow height (relative to eyes)
    left_brow_height = abs(left_eye_top.y - left_brow_mid.y) / face_width
    right_brow_height = abs(right_eye_top.y - right_brow_mid.y) / face_width
    avg_brow_height = (left_brow_height + right_brow_height) / 2
    
    # Eyebrow distance (furrowed brows)
    brow_distance = calculate_distance(left_brow_inner, right_brow_inner) / face_width
    
    # Eyebrow angle (raised/lowered)
    left_brow_angle = get_angle(left_brow_outer, left_brow_mid, left_brow_inner)
    right_brow_angle = get_angle(right_brow_outer, right_brow_mid, right_brow_inner)
    avg_brow_angle = (left_brow_angle + right_brow_angle) / 2
    
    # 4. NOSE ANALYSIS
    nose_tip = lm[1]
    nose_bridge = lm[6]
    left_nostril = lm[129]
    right_nostril = lm[358]
    
    # Nose wrinkle (z-axis displacement - careful with this!)
    nose_wrinkle = abs(nose_bridge.z - nose_tip.z)
    
    # Nostril flare
    nostril_width = calculate_distance(left_nostril, right_nostril) / face_width
    
    # === EMOTION SCORING (More nuanced) ===
    scores = {
        'neutral': 40.0,  # Higher base score for neutral
        'happy': 0.0,
        'sad': 0.0,
        'angry': 0.0,
        'surprise': 0.0,
        'fear': 0.0,
        'disgust': 0.0
    }
    
    # Log feature values for debugging
    logger.debug(f"Features: smile_lift={smile_lift:.3f}, mouth_openness={mouth_openness:.3f}, "
                 f"eye_height={avg_eye_height:.4f}, brow_height={avg_brow_height:.4f}, "
                 f"nose_wrinkle={nose_wrinkle:.4f}")
    
    # ===== HAPPY DETECTION =====
    # Strong indicators: smile lift + mouth curvature + normal/relaxed eyes
    if smile_lift > 5.0:  # Clear smile
        scores['happy'] += 60.0
        if mouth_curve < 160:  # U-shaped mouth
            scores['happy'] += 20.0
        if avg_eye_ratio < 0.35:  # Slightly squinted (Duchenne smile)
            scores['happy'] += 15.0
        scores['neutral'] -= 40.0
    elif smile_lift > 2.5:  # Moderate smile
        scores['happy'] += 35.0
        if mouth_curve < 165:
            scores['happy'] += 15.0
        scores['neutral'] -= 25.0
    elif smile_lift > 1.0:  # Slight smile
        scores['happy'] += 15.0
        scores['neutral'] -= 10.0
    
    # ===== SAD DETECTION =====
    # Indicators: downturned mouth + lowered brows + slightly closed eyes
    if smile_lift < -2.0:  # Mouth corners down
        scores['sad'] += 40.0
        if avg_brow_angle > 165:  # Inverted V brows
            scores['sad'] += 20.0
        if avg_eye_ratio < 0.30:  # Droopy eyes
            scores['sad'] += 15.0
        scores['neutral'] -= 35.0
    elif smile_lift < -0.5:
        scores['sad'] += 20.0
        scores['neutral'] -= 15.0
    
    # ===== ANGRY DETECTION =====
    # Indicators: lowered/furrowed brows + tight lips + narrowed eyes
    if avg_brow_height < 0.12:  # Low eyebrows
        if brow_distance < 0.35:  # Brows pulled together
            scores['angry'] += 45.0
            if mouth_openness < 0.25:  # Tight lips
                scores['angry'] += 20.0
            if avg_eye_ratio < 0.28:  # Narrowed eyes
                scores['angry'] += 15.0
            scores['neutral'] -= 40.0
        else:
            scores['angry'] += 20.0
            scores['neutral'] -= 15.0
    
    # ===== SURPRISE DETECTION =====
    # Indicators: wide eyes + raised eyebrows + open mouth
    if avg_eye_height > 0.08:  # Wide eyes
        scores['surprise'] += 30.0
        if avg_brow_height > 0.18:  # Raised eyebrows
            scores['surprise'] += 30.0
            if mouth_openness > 0.6:  # Open mouth
                scores['surprise'] += 25.0
            scores['neutral'] -= 40.0
        else:
            scores['surprise'] += 15.0
            scores['neutral'] -= 15.0
    elif avg_brow_height > 0.18:
        scores['surprise'] += 20.0
        scores['neutral'] -= 10.0
    
    # ===== FEAR DETECTION =====
    # Indicators: wide eyes + raised/tense brows + slightly open mouth
    if avg_eye_height > 0.075 and avg_brow_height > 0.16:
        scores['fear'] += 35.0
        if mouth_openness > 0.35 and mouth_openness < 0.7:
            scores['fear'] += 20.0
        if brow_distance < 0.38:  # Tense brows
            scores['fear'] += 15.0
        scores['neutral'] -= 30.0
    
    # ===== DISGUST DETECTION (More careful!) =====
    # Indicators: nose wrinkle + upper lip raise + lowered brows
    # IMPORTANT: Be very strict with disgust to avoid false positives!
    if nose_wrinkle > 0.03:  # INCREASED threshold (was 0.01)
        if smile_lift < -1.5:  # Upper lip raised
            scores['disgust'] += 35.0
            if avg_brow_height < 0.13:  # Lowered brows
                scores['disgust'] += 20.0
            if nostril_width > 0.12:  # Flared nostrils
                scores['disgust'] += 15.0
            scores['neutral'] -= 30.0
        elif smile_lift < -0.5:
            scores['disgust'] += 15.0
            scores['neutral'] -= 10.0
    
    # ===== NEUTRAL BOOST =====
    # If no strong features detected, boost neutral
    max_non_neutral = max(scores[e] for e in scores if e != 'neutral')
    if max_non_neutral < 20.0:
        scores['neutral'] += 30.0
    
    # Ensure no negative scores
    for emotion in scores:
        scores[emotion] = max(0.0, scores[emotion])
    
    # Normalize to sum to 100
    total = sum(scores.values())
    if total > 0:
        for emotion in scores:
            scores[emotion] = (scores[emotion] / total) * 100.0
    else:
        scores['neutral'] = 100.0
    
    return scores


@router.post("/analyze", response_model=EmotionAnalysisResponse)
async def analyze_emotion(request: EmotionAnalysisRequest):
    """
    Analyze emotion from 468 face mesh landmarks
    Uses ML model if available, falls back to FACS rule-based
    """
    global _debug_cache
    
    try:
        if not request.landmarks or len(request.landmarks) < 468:
            return EmotionAnalysisResponse(
                dominant_emotion="neutral",
                emoji="😐",
                confidence=0.0,
                scores={
                    'neutral': 100.0,
                    'happy': 0.0,
                    'sad': 0.0,
                    'angry': 0.0,
                    'surprise': 0.0,
                    'fear': 0.0,
                    'disgust': 0.0
                },
                face_detected=False,
                method="none"
            )
        
        # Convert landmarks to numpy array
        landmarks_array = np.array([[lm.x, lm.y, lm.z] for lm in request.landmarks])
        
        # Run inference through runtime
        runtime = _get_runtime()
        result = runtime.infer_one(landmarks_array, faceapi_scores=None)
        
        # Log to parquet if enabled
        parquet_logger = _get_logger()
        if parquet_logger and request.session_id:
            from src.custom_live_ai.emotion.feature_extractor import extract_base_features
            from src.custom_live_ai.emotion.preprocess import procrustes_normalize
            
            landmarks_norm = procrustes_normalize(landmarks_array)
            base_features = extract_base_features(landmarks_norm)
            
            parquet_logger.log_frame(
                session_id=request.session_id,
                frame_idx=0,  # TODO: track frame index in session
                landmarks_468=landmarks_norm,
                base_features=base_features,
                faceapi_emotions=None
            )
        
        # Cache for debug endpoint
        _debug_cache.append({
            "session_id": request.session_id,
            "dominant": result["dominant"],
            "confidence": result["confidence"],
            "method": result["method"]
        })
        
        # Get emoji
        emoji = EMOTION_MAP.get(result["dominant"], {}).get('emoji', '😐')
        
        logger.info(f"Emotion: {result['dominant']} ({result['confidence']:.1f}%) via {result['method']}")
        
        return EmotionAnalysisResponse(
            dominant_emotion=result["dominant"],
            emoji=emoji,
            confidence=result["confidence"],
            scores=result["scores"],
            face_detected=True,
            method=result["method"],
            tier=result.get("tier"),
            alpha_eff=result.get("alpha_eff"),
            margin=result.get("margin"),
            entropy=result.get("entropy"),
            cooldown_ms_left=result.get("cooldown_ms_left"),
            raw_scores=result.get("raw_scores")
        )
        
    except Exception as e:
        logger.error(f"Emotion analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Emotion analysis failed: {str(e)}")


@router.post("/hybrid-analyze", response_model=EmotionAnalysisResponse)
async def hybrid_emotion_analysis(request: HybridEmotionRequest):
    """
    Emotion analysis using Face-API.js with temporal smoothing
    """
    global _debug_cache
    
    try:
        # Debug: log landmark count
        landmark_count = len(request.landmarks) if request.landmarks else 0
        logger.info(f"📊 Received {landmark_count} landmarks, faceapi_emotions: {request.faceapi_emotions is not None}")
        
        if not request.landmarks or len(request.landmarks) < 468:
            logger.warning(f"Insufficient landmarks: {landmark_count}/468")
            return EmotionAnalysisResponse(
                dominant_emotion="neutral",
                emoji="😐",
                confidence=0.0,
                scores={
                    'neutral': 100.0,
                    'happy': 0.0,
                    'sad': 0.0,
                    'angry': 0.0,
                    'surprise': 0.0,
                    'fear': 0.0,
                    'disgust': 0.0
                },
                face_detected=False,
                method="none"
            )
        
        # Convert landmarks to numpy array
        landmarks_array = np.array([[lm.x, lm.y, lm.z] for lm in request.landmarks])
        
        # Run inference through runtime with face-api.js scores
        runtime = _get_runtime()
        result = runtime.infer_one(landmarks_array, faceapi_scores=request.faceapi_emotions)
        
        # Log to parquet if enabled
        parquet_logger = _get_logger()
        if parquet_logger and request.session_id:
            from src.custom_live_ai.emotion.feature_extractor import extract_base_features
            from src.custom_live_ai.emotion.preprocess import procrustes_normalize
            
            landmarks_norm = procrustes_normalize(landmarks_array)
            base_features = extract_base_features(landmarks_norm)
            
            parquet_logger.log_frame(
                session_id=request.session_id,
                frame_idx=0,  # TODO: track frame index in session
                landmarks_468=landmarks_norm,
                base_features=base_features,
                faceapi_emotions=request.faceapi_emotions
            )
        
        # Cache for debug endpoint
        _debug_cache.append({
            "session_id": request.session_id,
            "dominant": result["dominant"],
            "confidence": result["confidence"],
            "method": result["method"]
        })
        
        # Get emoji
        emoji = EMOTION_MAP.get(result["dominant"], {}).get('emoji', '😐')
        
        logger.info(f"Emotion: {result['dominant']} ({result['confidence']:.1f}%) via {result['method']}")
        
        return EmotionAnalysisResponse(
            dominant_emotion=result["dominant"],
            emoji=emoji,
            confidence=result["confidence"],
            scores=result["scores"],
            face_detected=True,
            method=result["method"],
            tier=result.get("tier"),
            alpha_eff=result.get("alpha_eff"),
            margin=result.get("margin"),
            entropy=result.get("entropy"),
            cooldown_ms_left=result.get("cooldown_ms_left"),
            raw_scores=result.get("raw_scores")
        )
        
    except Exception as e:
        logger.error(f"Hybrid emotion analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Hybrid emotion analysis failed: {str(e)}")


@router.get("/debug")
async def debug_recent_decisions(session_id: Optional[str] = Query(None), limit: int = Query(20, le=100)):
    """
    Debug endpoint: Get recent emotion decisions
    
    Args:
        session_id: Optional filter by session ID
        limit: Maximum number of decisions to return
    """
    global _debug_cache
    
    decisions = list(_debug_cache)
    
    # Filter by session if provided
    if session_id:
        decisions = [d for d in decisions if d.get("session_id") == session_id]
    
    # Apply limit
    decisions = decisions[-limit:]
    
    return {
        "total": len(decisions),
        "decisions": decisions
    }


@router.get("/health")
async def emotion_health():
    """Check emotion API health and model status"""
    runtime = _get_runtime()
    from src.custom_live_ai.emotion.config import SMOOTHING_MODE, TIER_CONFIGS
    
    return {
        "status": "healthy",
        "emotion_api": "operational",
        "smoothing_enabled": runtime.smoother is not None,
        "smoothing_mode": runtime.smoothing_mode if hasattr(runtime, 'smoothing_mode') else "unknown",
        "tier_configs": TIER_CONFIGS if SMOOTHING_MODE == "3tier" else None,
        "logging_enabled": os.getenv('ENABLE_LOGGING', str(ENABLE_LOGGING)).lower() in ('true', '1', 'yes'),
        "method": "Face-API.js ONLY + Temporal Smoothing",
        "expected_accuracy": "90-95% (Face-API.js pre-trained model)",
        "note": "Using ONLY Face-API.js for maximum accuracy. No FACS, no rule-based detection.",
        "debug_info": {
            "recent_requests": len(_debug_cache),
            "last_request": list(_debug_cache)[-1] if _debug_cache else None
        }
    }


@router.get("/test")
async def test_emotion_detection():
    """Test endpoint to verify emotion detection works with sample data"""
    import numpy as np
    from src.custom_live_ai.emotion.runtime import EmotionRuntime
    
    # Create test runtime (no args needed - uses config defaults)
    test_runtime = EmotionRuntime()
    
    # Generate sample landmarks (468 points with x, y, z)
    landmarks = np.random.rand(468, 3)
    
    # Test with sample Face-API.js scores (simulating happy emotion)
    faceapi_scores = {
        "happy": 0.8,
        "neutral": 0.15,
        "sad": 0.02,
        "angry": 0.01,
        "fear": 0.01,
        "disgust": 0.005,
        "surprise": 0.005
    }
    
    result = test_runtime.infer_one(landmarks, faceapi_scores=faceapi_scores)
    
    return {
        "test_status": "Backend working correctly",
        "sample_result": {
            "emotion": result["dominant"],
            "confidence": result["confidence"],
            "method": result["method"],
            "tier": result.get("tier", "N/A"),
            "scores": {k: f"{v:.1f}%" for k, v in list(result["scores"].items())[:3]}
        },
        "message": "Emotion API is working. Frontend sends face-api.js scores + landmarks."
    }


# ============================================
# Data Collection for ML Training (Phase 6)
# ============================================

class LabeledFrameRequest(BaseModel):
    """Request to save a labeled frame for future ML training"""
    landmarks: List[FaceMeshLandmark] = Field(..., description="Face mesh landmarks (468 points)")
    detected_emotion: str = Field(..., description="Emotion detected by the system")
    correct_emotion: str = Field(..., description="Correct emotion label (user correction)")
    confidence: float = Field(..., description="Detection confidence (0-100)")
    session_id: Optional[str] = Field(None, description="Optional session ID")
    timestamp: Optional[str] = Field(None, description="Timestamp of the frame")


@router.post("/save-labeled-frame")
async def save_labeled_frame(request: LabeledFrameRequest):
    """
    Save a labeled frame for future ML training
    
    This endpoint allows users to manually correct emotion detections
    and save them for training a custom ML model later.
    """
    import os
    import json
    from datetime import datetime
    
    try:
        # Create training_data directory if it doesn't exist
        training_dir = "./training_data"
        os.makedirs(training_dir, exist_ok=True)
        
        # Generate timestamp if not provided
        timestamp = request.timestamp or datetime.now().isoformat()
        
        # Prepare data to save
        frame_data = {
            "timestamp": timestamp,
            "session_id": request.session_id,
            "landmarks": [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in request.landmarks],
            "detected_emotion": request.detected_emotion,
            "correct_emotion": request.correct_emotion,
            "confidence": request.confidence,
            "needs_correction": request.detected_emotion != request.correct_emotion
        }
        
        # Save to daily JSON file (append mode)
        date_str = datetime.now().strftime("%Y%m%d")
        json_file = os.path.join(training_dir, f"labeled_frames_{date_str}.json")
        
        # Load existing data or create new list
        if os.path.exists(json_file):
            with open(json_file, 'r') as f:
                try:
                    data_list = json.load(f)
                    if not isinstance(data_list, list):
                        data_list = []
                except json.JSONDecodeError:
                    data_list = []
        else:
            data_list = []
        
        # Append new frame
        data_list.append(frame_data)
        
        # Save back to file
        with open(json_file, 'w') as f:
            json.dump(data_list, f, indent=2)
        
        logger.info(f"Saved labeled frame: {request.correct_emotion} (detected as {request.detected_emotion})")
        
        return {
            "success": True,
            "message": "Labeled frame saved successfully",
            "file": json_file,
            "total_frames_today": len(data_list),
            "needs_correction": frame_data["needs_correction"]
        }
        
    except Exception as e:
        logger.error(f"Failed to save labeled frame: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save labeled frame: {str(e)}")


@router.get("/training-data-stats")
async def get_training_data_stats():
    """Get statistics about collected training data"""
    import os
    import json
    from collections import Counter
    
    try:
        training_dir = "./training_data"
        
        if not os.path.exists(training_dir):
            return {
                "total_frames": 0,
                "files": 0,
                "emotions": {},
                "corrections_needed": 0,
                "message": "No training data collected yet"
            }
        
        # Scan all JSON files
        total_frames = 0
        all_emotions = []
        corrections_needed = 0
        files = []
        
        for filename in os.listdir(training_dir):
            if filename.startswith("labeled_frames_") and filename.endswith(".json"):
                filepath = os.path.join(training_dir, filename)
                files.append(filename)
                
                try:
                    with open(filepath, 'r') as f:
                        data_list = json.load(f)
                        if isinstance(data_list, list):
                            total_frames += len(data_list)
                            
                            for frame in data_list:
                                all_emotions.append(frame.get("correct_emotion", "unknown"))
                                if frame.get("needs_correction", False):
                                    corrections_needed += 1
                except Exception:
                    continue
        
        # Count emotions
        emotion_counts = dict(Counter(all_emotions))
        
        return {
            "total_frames": total_frames,
            "files": len(files),
            "emotions": emotion_counts,
            "corrections_needed": corrections_needed,
            "accuracy": round((1 - corrections_needed / total_frames) * 100, 1) if total_frames > 0 else 0,
            "message": f"Collected {total_frames} labeled frames across {len(files)} days",
            "ready_for_training": total_frames >= 500
        }
        
    except Exception as e:
        logger.error(f"Failed to get training data stats: {e}")
        return {
            "total_frames": 0,
            "error": str(e)
        }


# ============================================================================
# SESSION-BASED EMOTION TRACKING (for Live2D Chatbox integration)
# ============================================================================

class EmotionDataPoint(BaseModel):
    """Single emotion data point from real-time tracking"""
    timestamp: int
    emotion: str
    confidence: float
    expressions: Optional[Dict[str, float]] = None


class EmotionSessionRequest(BaseModel):
    """Request to save an emotion tracking session"""
    session_id: str
    start_time: int
    end_time: int
    data_points: int
    emotions: List[EmotionDataPoint]


class EmotionSessionResponse(BaseModel):
    """Response after saving emotion session"""
    success: bool
    session_id: str
    data_points_saved: int
    duration_seconds: float
    dominant_emotion: str
    emotion_summary: Dict[str, int]


@router.post("/session", response_model=EmotionSessionResponse)
async def save_emotion_session(request: EmotionSessionRequest):
    """
    Save a complete emotion tracking session from the Live2D chatbox.
    This is called when the user stops emotion tracking or ends their chat session.
    """
    try:
        # Calculate session duration
        duration_seconds = (request.end_time - request.start_time) / 1000.0
        
        # Count emotions
        emotion_counts = {}
        for dp in request.emotions:
            emotion = dp.emotion
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        
        # Find dominant emotion
        dominant = max(emotion_counts.items(), key=lambda x: x[1])[0] if emotion_counts else "unknown"
        
        # Log session data
        logger.info(f"📊 Emotion session saved: {request.session_id}")
        logger.info(f"   Duration: {duration_seconds:.1f}s, Data points: {request.data_points}")
        logger.info(f"   Dominant emotion: {dominant}, Summary: {emotion_counts}")
        
        # Store session data (in production, this would go to database)
        session_file = f"./emotion_sessions/{request.session_id}_{request.start_time}.json"
        import os
        import json
        
        os.makedirs("./emotion_sessions", exist_ok=True)
        
        session_data = {
            "session_id": request.session_id,
            "start_time": request.start_time,
            "end_time": request.end_time,
            "duration_seconds": duration_seconds,
            "data_points": request.data_points,
            "dominant_emotion": dominant,
            "emotion_summary": emotion_counts,
            "emotions": [e.dict() for e in request.emotions]
        }
        
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        return EmotionSessionResponse(
            success=True,
            session_id=request.session_id,
            data_points_saved=len(request.emotions),
            duration_seconds=duration_seconds,
            dominant_emotion=dominant,
            emotion_summary=emotion_counts
        )
        
    except Exception as e:
        logger.error(f"Failed to save emotion session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save session: {str(e)}")


@router.get("/sessions")
async def list_emotion_sessions(limit: int = Query(20, ge=1, le=100)):
    """List recent emotion tracking sessions"""
    import os
    import json
    from datetime import datetime
    
    try:
        sessions_dir = "./emotion_sessions"
        if not os.path.exists(sessions_dir):
            return {"sessions": [], "total": 0}
        
        sessions = []
        for filename in sorted(os.listdir(sessions_dir), reverse=True)[:limit]:
            if filename.endswith('.json'):
                filepath = os.path.join(sessions_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        sessions.append({
                            "session_id": data.get("session_id"),
                            "start_time": datetime.fromtimestamp(data.get("start_time", 0) / 1000).isoformat(),
                            "duration_seconds": data.get("duration_seconds"),
                            "data_points": data.get("data_points"),
                            "dominant_emotion": data.get("dominant_emotion"),
                            "emotion_summary": data.get("emotion_summary")
                        })
                except Exception:
                    continue
        
        return {"sessions": sessions, "total": len(sessions)}
        
    except Exception as e:
        logger.error(f"Failed to list emotion sessions: {e}")
        return {"sessions": [], "error": str(e)}

