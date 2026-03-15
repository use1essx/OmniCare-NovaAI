"""
Data Recording Module
Records pose, face, hand landmarks and metrics over time
"""

import json
import csv
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class FrameRecord:
    """Single frame recording"""
    timestamp: float
    frame_number: int
    
    # Pose data
    pose_landmarks: Optional[List[Dict[str, float]]] = None
    posture_score: Optional[float] = None
    posture_quality: Optional[str] = None
    shoulder_angle: Optional[float] = None
    head_tilt: Optional[float] = None
    is_slouching: Optional[bool] = None
    
    # Face data
    face_landmarks: Optional[List[Dict[str, float]]] = None
    face_visible: Optional[bool] = None
    eye_contact_score: Optional[float] = None
    head_pose_pitch: Optional[float] = None
    head_pose_yaw: Optional[float] = None
    head_pose_roll: Optional[float] = None
    
    # Hand data
    left_hand_landmarks: Optional[List[Dict[str, float]]] = None
    right_hand_landmarks: Optional[List[Dict[str, float]]] = None
    left_hand_visible: Optional[bool] = None
    right_hand_visible: Optional[bool] = None
    movement_score: Optional[float] = None
    is_fidgeting: Optional[bool] = None
    
    # Emotion data
    dominant_emotion: Optional[str] = None
    emotion_confidence: Optional[float] = None


class SessionRecorder:
    """
    Records video analysis data over a session
    Saves all landmark positions and metrics to file
    """
    
    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize recorder
        
        Args:
            session_id: Unique session identifier (auto-generated if None)
        """
        self.session_id = session_id or f"session_{int(time.time())}"
        self.start_time = time.time()
        self.frame_count = 0
        self.frames: List[FrameRecord] = []
        self.is_recording = False
        
        logger.info(f"Session recorder initialized: {self.session_id}")
    
    def start_recording(self):
        """Start recording data"""
        self.is_recording = True
        self.start_time = time.time()
        self.frame_count = 0
        self.frames = []
        logger.info(f"Recording started: {self.session_id}")
    
    def stop_recording(self):
        """Stop recording data"""
        self.is_recording = False
        logger.info(f"Recording stopped: {self.session_id} ({self.frame_count} frames)")
    
    def record_frame(
        self,
        pose_data: Optional[Any] = None,
        face_data: Optional[Any] = None,
        hand_data: Optional[Any] = None,
        emotion_data: Optional[Any] = None,
        raw_landmarks: Optional[Dict] = None
    ):
        """
        Record a single frame of data
        
        Args:
            pose_data: PoseData object
            face_data: FaceData object
            hand_data: HandData object
            emotion_data: EmotionResult object
            raw_landmarks: Raw MediaPipe landmarks
        """
        if not self.is_recording:
            return
        
        timestamp = time.time() - self.start_time
        self.frame_count += 1
        
        # Create frame record
        record = FrameRecord(
            timestamp=timestamp,
            frame_number=self.frame_count
        )
        
        # Add pose data
        if pose_data:
            record.posture_score = float(pose_data.posture_score)
            record.posture_quality = pose_data.posture_quality.value
            record.shoulder_angle = float(pose_data.shoulder_angle)
            record.head_tilt = float(pose_data.head_tilt)
            record.is_slouching = bool(pose_data.is_slouching)
            
            # Add landmarks if available
            if hasattr(pose_data, 'landmarks') and pose_data.landmarks:
                record.pose_landmarks = [
                    {"x": float(lm[0]), "y": float(lm[1]), "visibility": float(lm[2])}
                    for lm in pose_data.landmarks
                ]
        
        # Add face data
        if face_data:
            record.face_visible = bool(face_data.face_visible)
            record.eye_contact_score = float(face_data.eye_contact_score)
            record.head_pose_pitch = float(face_data.head_pose[0])
            record.head_pose_yaw = float(face_data.head_pose[1])
            record.head_pose_roll = float(face_data.head_pose[2])
            
            # Add landmarks if available
            if hasattr(face_data, 'landmarks') and face_data.landmarks:
                record.face_landmarks = [
                    {"x": float(lm[0]), "y": float(lm[1])}
                    for lm in face_data.landmarks
                ]
        
        # Add hand data
        if hand_data:
            record.left_hand_visible = bool(hand_data.left_hand_visible)
            record.right_hand_visible = bool(hand_data.right_hand_visible)
            record.movement_score = float(hand_data.movement_score)
            record.is_fidgeting = bool(hand_data.is_fidgeting)
            
            # Add hand landmarks if available
            if hasattr(hand_data, 'left_hand_landmarks') and hand_data.left_hand_landmarks:
                record.left_hand_landmarks = [
                    {"x": float(lm[0]), "y": float(lm[1]), "z": float(lm[2])}
                    for lm in hand_data.left_hand_landmarks
                ]
            if hasattr(hand_data, 'right_hand_landmarks') and hand_data.right_hand_landmarks:
                record.right_hand_landmarks = [
                    {"x": float(lm[0]), "y": float(lm[1]), "z": float(lm[2])}
                    for lm in hand_data.right_hand_landmarks
                ]
        
        # Add emotion data
        if emotion_data and hasattr(emotion_data, 'face_detected') and emotion_data.face_detected:
            record.dominant_emotion = emotion_data.dominant_emotion.value
            record.emotion_confidence = float(emotion_data.confidence)
        
        self.frames.append(record)
    
    def save_to_json(self, filepath: Optional[str] = None) -> str:
        """
        Save recording to JSON file
        
        Args:
            filepath: Output file path (auto-generated if None)
            
        Returns:
            Path to saved file
        """
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"recordings/{self.session_id}_{timestamp}.json"
        
        # Create directory if needed
        import os
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        
        # Prepare data
        data = {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "duration": time.time() - self.start_time,
            "total_frames": self.frame_count,
            "frames": [asdict(frame) for frame in self.frames]
        }
        
        # Save to file
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved {self.frame_count} frames to {filepath}")
        return filepath
    
    def save_to_csv(self, filepath: Optional[str] = None) -> str:
        """
        Save recording to CSV file (metrics only, no landmarks)
        
        Args:
            filepath: Output file path (auto-generated if None)
            
        Returns:
            Path to saved file
        """
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"recordings/{self.session_id}_{timestamp}.csv"
        
        # Create directory if needed
        import os
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        
        # CSV headers (metrics only, excluding landmark arrays)
        headers = [
            "timestamp", "frame_number",
            "posture_score", "posture_quality", "shoulder_angle", "head_tilt", "is_slouching",
            "face_visible", "eye_contact_score", "head_pose_pitch", "head_pose_yaw", "head_pose_roll",
            "left_hand_visible", "right_hand_visible", "movement_score", "is_fidgeting",
            "dominant_emotion", "emotion_confidence"
        ]
        
        # Write CSV
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            
            for frame in self.frames:
                row = {
                    "timestamp": frame.timestamp,
                    "frame_number": frame.frame_number,
                    "posture_score": frame.posture_score,
                    "posture_quality": frame.posture_quality,
                    "shoulder_angle": frame.shoulder_angle,
                    "head_tilt": frame.head_tilt,
                    "is_slouching": frame.is_slouching,
                    "face_visible": frame.face_visible,
                    "eye_contact_score": frame.eye_contact_score,
                    "head_pose_pitch": frame.head_pose_pitch,
                    "head_pose_yaw": frame.head_pose_yaw,
                    "head_pose_roll": frame.head_pose_roll,
                    "left_hand_visible": frame.left_hand_visible,
                    "right_hand_visible": frame.right_hand_visible,
                    "movement_score": frame.movement_score,
                    "is_fidgeting": frame.is_fidgeting,
                    "dominant_emotion": frame.dominant_emotion,
                    "emotion_confidence": frame.emotion_confidence
                }
                writer.writerow(row)
        
        logger.info(f"Saved {self.frame_count} frames to {filepath}")
        return filepath
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics of the session
        
        Returns:
            Dictionary with summary stats
        """
        if not self.frames:
            return {"error": "No frames recorded"}
        
        # Calculate averages
        posture_scores = [f.posture_score for f in self.frames if f.posture_score is not None]
        eye_contact_scores = [f.eye_contact_score for f in self.frames if f.eye_contact_score is not None]
        
        slouching_count = sum(1 for f in self.frames if f.is_slouching)
        fidgeting_count = sum(1 for f in self.frames if f.is_fidgeting)
        
        emotions = {}
        for f in self.frames:
            if f.dominant_emotion:
                emotions[f.dominant_emotion] = emotions.get(f.dominant_emotion, 0) + 1
        
        return {
            "session_id": self.session_id,
            "duration": time.time() - self.start_time,
            "total_frames": self.frame_count,
            "average_posture_score": sum(posture_scores) / len(posture_scores) if posture_scores else None,
            "average_eye_contact": sum(eye_contact_scores) / len(eye_contact_scores) if eye_contact_scores else None,
            "slouching_percentage": (slouching_count / self.frame_count * 100) if self.frame_count > 0 else 0,
            "fidgeting_percentage": (fidgeting_count / self.frame_count * 100) if self.frame_count > 0 else 0,
            "emotion_distribution": emotions
        }



