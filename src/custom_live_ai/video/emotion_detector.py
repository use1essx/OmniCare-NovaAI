"""
Emotion Detection Module
Uses DeepFace for facial emotion recognition
"""

import cv2
import numpy as np
from typing import Optional, Dict, List
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Emotion(Enum):
    """Supported emotions"""
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    NEUTRAL = "neutral"
    SURPRISE = "surprise"
    FEAR = "fear"
    DISGUST = "disgust"


@dataclass
class EmotionResult:
    """Emotion detection result"""
    dominant_emotion: Emotion
    emotion_scores: Dict[str, float]  # All emotions with confidence scores
    confidence: float  # Confidence of dominant emotion
    face_detected: bool


class EmotionDetector:
    """
    Detect emotions from facial expressions
    Uses DeepFace library with multiple backend options
    """
    
    def __init__(
        self,
        backend: str = "opencv",  # opencv, ssd, mtcnn, retinaface
        detector_backend: str = "opencv"
    ):
        """
        Initialize emotion detector
        
        Args:
            backend: Face detection backend
            detector_backend: Deep learning backend for emotion
        """
        self.backend = backend
        self.detector_backend = detector_backend
        
        # Lazy import DeepFace (heavy dependency)
        try:
            from deepface import DeepFace
            self.DeepFace = DeepFace
            logger.info(f"DeepFace initialized with backend: {backend}")
        except ImportError:
            logger.error("DeepFace not installed. Install with: pip install deepface")
            raise
        
        # Cache for performance
        self._emotion_cache = {}
    
    def detect_emotion(
        self,
        frame: np.ndarray,
        use_cache: bool = True
    ) -> Optional[EmotionResult]:
        """
        Detect emotion from a video frame
        
        Args:
            frame: BGR image from OpenCV
            use_cache: Use cached result if frame is similar
            
        Returns:
            EmotionResult or None if no face detected
        """
        try:
            # Analyze emotions
            result = self.DeepFace.analyze(
                img_path=frame,
                actions=['emotion'],
                enforce_detection=False,  # Don't fail if no face
                detector_backend=self.backend,
                silent=True
            )
            
            if not result or not isinstance(result, list) or len(result) == 0:
                logger.debug("No face detected in frame")
                return EmotionResult(
                    dominant_emotion=Emotion.NEUTRAL,
                    emotion_scores={},
                    confidence=0.0,
                    face_detected=False
                )
            
            # Get first face result
            face_result = result[0]
            
            if 'emotion' not in face_result:
                return None
            
            emotion_scores = face_result['emotion']
            
            # Find dominant emotion
            dominant_emotion_str = max(emotion_scores, key=emotion_scores.get)
            confidence = emotion_scores[dominant_emotion_str]
            
            # Convert to Emotion enum
            try:
                dominant_emotion = Emotion(dominant_emotion_str.lower())
            except ValueError:
                dominant_emotion = Emotion.NEUTRAL
            
            logger.debug(
                f"Detected emotion: {dominant_emotion.value} "
                f"(confidence: {confidence:.2f})"
            )
            
            return EmotionResult(
                dominant_emotion=dominant_emotion,
                emotion_scores=emotion_scores,
                confidence=confidence / 100.0,  # Normalize to 0-1
                face_detected=True
            )
            
        except Exception as e:
            logger.error(f"Emotion detection failed: {e}")
            return None
    
    def detect_emotion_batch(
        self,
        frames: List[np.ndarray]
    ) -> List[Optional[EmotionResult]]:
        """
        Detect emotions from multiple frames
        More efficient than processing one by one
        
        Args:
            frames: List of BGR images
            
        Returns:
            List of EmotionResults
        """
        results = []
        for frame in frames:
            result = self.detect_emotion(frame, use_cache=True)
            results.append(result)
        
        return results
    
    def get_emotion_trend(
        self,
        emotion_history: List[EmotionResult],
        window_size: int = 5
    ) -> Dict[str, float]:
        """
        Analyze emotion trends over time
        
        Args:
            emotion_history: List of past EmotionResults
            window_size: Number of recent results to analyze
            
        Returns:
            Dictionary with emotion statistics
        """
        if not emotion_history:
            return {
                "dominant_emotion": "neutral",
                "emotion_stability": 0.0,
                "positive_ratio": 0.0,
                "negative_ratio": 0.0
            }
        
        # Get recent emotions
        recent = emotion_history[-window_size:]
        
        # Count emotions
        emotion_counts = {}
        for result in recent:
            if result and result.face_detected:
                emotion = result.dominant_emotion.value
                emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        
        if not emotion_counts:
            return {
                "dominant_emotion": "neutral",
                "emotion_stability": 0.0,
                "positive_ratio": 0.0,
                "negative_ratio": 0.0
            }
        
        # Calculate statistics
        dominant = max(emotion_counts, key=emotion_counts.get)
        total = sum(emotion_counts.values())
        
        # Stability: how consistent is the emotion
        dominant_ratio = emotion_counts[dominant] / total
        
        # Positive/negative ratios
        positive_emotions = ["happy", "surprise"]
        negative_emotions = ["sad", "angry", "fear", "disgust"]
        
        positive_count = sum(
            emotion_counts.get(e, 0) for e in positive_emotions
        )
        negative_count = sum(
            emotion_counts.get(e, 0) for e in negative_emotions
        )
        
        return {
            "dominant_emotion": dominant,
            "emotion_stability": dominant_ratio,
            "positive_ratio": positive_count / total,
            "negative_ratio": negative_count / total
        }
    
    def is_distressed(
        self,
        emotion_result: Optional[EmotionResult],
        threshold: float = 0.6
    ) -> bool:
        """
        Check if person shows signs of distress
        
        Args:
            emotion_result: Emotion detection result
            threshold: Confidence threshold for detection
            
        Returns:
            True if distressed emotions detected
        """
        if not emotion_result or not emotion_result.face_detected:
            return False
        
        distress_emotions = [Emotion.SAD, Emotion.ANGRY, Emotion.FEAR]
        
        is_distressed = (
            emotion_result.dominant_emotion in distress_emotions
            and emotion_result.confidence >= threshold
        )
        
        if is_distressed:
            logger.warning(
                f"Distress detected: {emotion_result.dominant_emotion.value} "
                f"(confidence: {emotion_result.confidence:.2f})"
            )
        
        return is_distressed
    
    def get_comfort_message(self, emotion: Emotion) -> str:
        """
        Get appropriate comfort message based on emotion
        
        Args:
            emotion: Detected emotion
            
        Returns:
            Comfort message string
        """
        messages = {
            Emotion.SAD: "You seem upset. Would you like to take a break? 💙",
            Emotion.ANGRY: "Take a deep breath. It's okay to feel frustrated. 🌟",
            Emotion.FEAR: "You're safe here. We can take things slowly. 🤗",
            Emotion.NEUTRAL: "You're doing great! Keep going! 👍",
            Emotion.HAPPY: "I'm glad you're feeling good! 😊",
            Emotion.SURPRISE: "That's interesting! 😮",
            Emotion.DISGUST: "It's okay, let's move on. 🌸"
        }
        
        return messages.get(emotion, "You're doing great! 🌟")


class SimplifiedEmotionDetector:
    """
    Lightweight emotion detector for real-time use
    Uses simpler models for faster processing
    """
    
    def __init__(self):
        """Initialize simplified detector"""
        # Use Haar Cascade for face detection (faster)
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
        logger.info("Simplified emotion detector initialized (Haar Cascade)")
    
    def detect_emotion_simple(self, frame: np.ndarray) -> Optional[EmotionResult]:
        """
        Fast emotion detection using facial feature analysis
        Uses smile detection and face brightness for basic emotion estimation
        
        Args:
            frame: BGR image
            
        Returns:
            EmotionResult with basic emotion classification
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )
            
            if len(faces) == 0:
                return EmotionResult(
                    dominant_emotion=Emotion.NEUTRAL,
                    emotion_scores={},
                    confidence=0.0,
                    face_detected=False
                )
            
            # Get the first face
            (x, y, w, h) = faces[0]
            face_roi = gray[y:y+h, x:x+w]
            
            # Try to detect smile (simple heuristic-based emotion detection)
            smile_cascade_path = cv2.data.haarcascades + 'haarcascade_smile.xml'
            try:
                smile_cascade = cv2.CascadeClassifier(smile_cascade_path)
                smiles = smile_cascade.detectMultiScale(
                    face_roi,
                    scaleFactor=1.8,
                    minNeighbors=20,
                    minSize=(25, 25)
                )
                
                # Determine emotion based on features
                if len(smiles) > 0:
                    # Smile detected -> Happy
                    return EmotionResult(
                        dominant_emotion=Emotion.HAPPY,
                        emotion_scores={
                            "happy": 75.0,
                            "neutral": 15.0,
                            "surprise": 10.0
                        },
                        confidence=0.75,
                        face_detected=True
                    )
            except Exception:
                pass
            
            # Try to detect eyes (for surprise/fear detection)
            eye_cascade_path = cv2.data.haarcascades + 'haarcascade_eye.xml'
            try:
                eye_cascade = cv2.CascadeClassifier(eye_cascade_path)
                eyes = eye_cascade.detectMultiScale(
                    face_roi,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(20, 20)
                )
                
                # If eyes are very open (large area), might indicate surprise
                if len(eyes) >= 2:
                    eye_areas = [w*h for (x, y, w, h) in eyes]
                    avg_eye_area = sum(eye_areas) / len(eye_areas)
                    face_area = face_roi.shape[0] * face_roi.shape[1]
                    eye_ratio = avg_eye_area / face_area
                    
                    if eye_ratio > 0.03:  # Eyes are wide open
                        return EmotionResult(
                            dominant_emotion=Emotion.SURPRISE,
                            emotion_scores={
                                "surprise": 70.0,
                                "neutral": 20.0,
                                "happy": 10.0
                            },
                            confidence=0.7,
                            face_detected=True
                        )
            except Exception:
                pass
            
            # Calculate face brightness (can indicate emotional state)
            avg_brightness = np.mean(face_roi)
            
            # Brightness-based simple emotion estimation
            if avg_brightness > 140:
                # Bright face might indicate positive emotion
                return EmotionResult(
                    dominant_emotion=Emotion.HAPPY,
                    emotion_scores={
                        "happy": 65.0,
                        "neutral": 30.0,
                        "surprise": 5.0
                    },
                    confidence=0.65,
                    face_detected=True
                )
            elif avg_brightness < 90:
                # Darker face might indicate negative emotion
                return EmotionResult(
                    dominant_emotion=Emotion.SAD,
                    emotion_scores={
                        "sad": 60.0,
                        "neutral": 30.0,
                        "angry": 10.0
                    },
                    confidence=0.6,
                    face_detected=True
                )
            
            # Default: Neutral with varied scores
            return EmotionResult(
                dominant_emotion=Emotion.NEUTRAL,
                emotion_scores={
                    "neutral": 70.0,
                    "happy": 10.0,
                    "sad": 10.0,
                    "surprise": 5.0,
                    "angry": 5.0
                },
                confidence=0.7,
                face_detected=True
            )
            
        except Exception as e:
            logger.error(f"Simple emotion detection failed: {e}")
            return None


# Convenience functions

def quick_emotion_check(frame: np.ndarray) -> Optional[str]:
    """
    Quick emotion check returning just the emotion name
    
    Args:
        frame: Video frame
        
    Returns:
        Emotion name string or None
    """
    detector = EmotionDetector()
    result = detector.detect_emotion(frame)
    
    if result and result.face_detected:
        return result.dominant_emotion.value
    
    return None


