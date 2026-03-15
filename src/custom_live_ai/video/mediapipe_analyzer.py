"""
MediaPipe Video Analysis Module
Handles pose detection, face tracking, and hand gesture recognition
"""
# pylint: disable=no-member  # False positive for cv2 (C extension)

import cv2
import numpy as np
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# MediaPipe import with compatibility handling
try:
    import mediapipe as mp
    # Check if solutions attribute exists (legacy API)
    if hasattr(mp, 'solutions'):
        mp_drawing = mp.solutions.drawing_utils
        mp_drawing_styles = mp.solutions.drawing_styles
        MEDIAPIPE_LEGACY = True
    else:
        # New MediaPipe API (0.10.8+) - use tasks API
        mp_drawing = None
        mp_drawing_styles = None
        MEDIAPIPE_LEGACY = False
        logger.warning("MediaPipe legacy API not available, using tasks API")
except ImportError as e:
    logger.error(f"MediaPipe import failed: {e}")
    mp = None
    mp_drawing = None
    mp_drawing_styles = None
    MEDIAPIPE_LEGACY = False


class PostureQuality(Enum):
    """Posture quality categories"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


@dataclass
class PoseData:
    """Pose detection results"""
    landmarks: List[Tuple[float, float, float]]  # (x, y, visibility)
    posture_score: float  # 0.0-1.0
    posture_quality: PostureQuality
    shoulder_angle: float  # Degrees
    head_tilt: float  # Degrees
    is_slouching: bool


@dataclass
class FaceData:
    """Face detection results"""
    landmarks: List[Tuple[float, float]]  # (x, y)
    eye_contact_score: float  # 0.0-1.0 (looking at camera)
    head_pose: Tuple[float, float, float]  # (pitch, yaw, roll)
    face_visible: bool
    face_distance_score: float  # 0.0-1.0 (optimal distance)


@dataclass
class HandData:
    """Hand gesture detection results"""
    left_hand_visible: bool
    right_hand_visible: bool
    left_hand_landmarks: List[Tuple[float, float, float]] = field(default_factory=list)  # (x, y, z) per landmark
    right_hand_landmarks: List[Tuple[float, float, float]] = field(default_factory=list)  # (x, y, z) per landmark
    movement_score: float = 0.0  # 0.0-1.0 (amount of movement)
    is_fidgeting: bool = False


class MediaPipeAnalyzer:
    """
    Analyze video frames using MediaPipe
    Detects body pose, face, and hand gestures
    """
    
    def __init__(
        self,
        enable_pose: bool = True,
        enable_face: bool = True,
        enable_hands: bool = True,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        mirror_mode: bool = False
    ):
        """
        Initialize MediaPipe analyzer
        
        Args:
            enable_pose: Enable pose detection
            enable_face: Enable face mesh detection
            enable_hands: Enable hand detection
            min_detection_confidence: Minimum confidence for detection
            min_tracking_confidence: Minimum confidence for tracking
            mirror_mode: Flip left/right hand labels for mirrored webcam input
        """
        if mp is None:
            raise ImportError("MediaPipe is not installed or failed to import")
        
        if not MEDIAPIPE_LEGACY:
            raise ImportError(
                "MediaPipe legacy API (mp.solutions) not available. "
                "Please install mediapipe<0.10.8 or use the new Tasks API. "
                "Try: pip install mediapipe==0.10.7"
            )
        
        self.enable_pose = enable_pose
        self.enable_face = enable_face
        self.enable_hands = enable_hands
        self.mirror_mode = mirror_mode
        
        # Initialize MediaPipe solutions
        mp_solutions = mp.solutions
        
        if enable_pose:
            self.mp_pose = mp_solutions.pose
            self.pose = self.mp_pose.Pose(
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence
            )
            logger.info("MediaPipe Pose initialized")
        
        if enable_face:
            self.mp_face = mp_solutions.face_mesh
            self.face_mesh = self.mp_face.FaceMesh(
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
                max_num_faces=1
            )
            logger.info("MediaPipe Face Mesh initialized")
        
        if enable_hands:
            self.mp_hands = mp_solutions.hands
            self.hands = self.mp_hands.Hands(
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
                max_num_hands=2
            )
            logger.info("MediaPipe Hands initialized")
        
        # Track previous hand positions for movement detection
        self.previous_hand_positions: Optional[List[np.ndarray]] = None
    
    def analyze_frame(
        self,
        frame: np.ndarray
    ) -> Dict[str, Optional[object]]:
        """
        Analyze a single video frame
        
        Args:
            frame: BGR image from OpenCV
            
        Returns:
            Dictionary with pose_data, face_data, hand_data
        """
        try:
            # Convert BGR to RGB (MediaPipe uses RGB)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            results: Dict[str, Optional[object]] = {}
            
            # Process pose
            if self.enable_pose:
                results["pose_data"] = self._process_pose(rgb_frame)
            
            # Process face
            if self.enable_face:
                results["face_data"] = self._process_face(rgb_frame)
            
            # Process hands
            if self.enable_hands:
                results["hand_data"] = self._process_hands(rgb_frame)
            
            return results
            
        except Exception as e:
            logger.error(f"Frame analysis failed: {e}")
            return {
                "pose_data": None,
                "face_data": None,
                "hand_data": None
            }
    
    def _process_pose(self, rgb_frame: np.ndarray) -> Optional[PoseData]:
        """Process pose detection"""
        try:
            results = self.pose.process(rgb_frame)
            
            if not results.pose_landmarks:
                return None
            
            landmarks = [
                (lm.x, lm.y, lm.visibility)
                for lm in results.pose_landmarks.landmark
            ]
            
            # Calculate posture metrics
            posture_score, shoulder_angle, head_tilt, is_slouching = \
                self._calculate_posture_metrics(landmarks)
            
            # Determine posture quality
            if posture_score >= 0.8:
                quality = PostureQuality.EXCELLENT
            elif posture_score >= 0.6:
                quality = PostureQuality.GOOD
            elif posture_score >= 0.4:
                quality = PostureQuality.FAIR
            else:
                quality = PostureQuality.POOR
            
            return PoseData(
                landmarks=landmarks,
                posture_score=posture_score,
                posture_quality=quality,
                shoulder_angle=shoulder_angle,
                head_tilt=head_tilt,
                is_slouching=is_slouching
            )
            
        except Exception as e:
            logger.error(f"Pose processing failed: {e}")
            return None
    
    def _calculate_posture_metrics(
        self,
        landmarks: List[Tuple[float, float, float]]
    ) -> Tuple[float, float, float, bool]:
        """
        Calculate posture quality metrics
        
        Returns:
            (posture_score, shoulder_angle, head_tilt, is_slouching)
        """
        try:
            # Key landmarks (MediaPipe Pose indices)
            # 0: nose, 11: left shoulder, 12: right shoulder
            # 23: left hip, 24: right hip
            
            nose = np.array(landmarks[0][:2])
            left_shoulder = np.array(landmarks[11][:2])
            right_shoulder = np.array(landmarks[12][:2])
            left_hip = np.array(landmarks[23][:2])
            right_hip = np.array(landmarks[24][:2])
            
            # Calculate shoulder angle (should be close to 0 for good posture)
            shoulder_vector = right_shoulder - left_shoulder
            shoulder_angle = np.degrees(np.arctan2(shoulder_vector[1], shoulder_vector[0]))
            
            # Calculate head tilt (nose relative to shoulders)
            shoulder_center = (left_shoulder + right_shoulder) / 2
            head_tilt = np.degrees(np.arctan2(
                nose[1] - shoulder_center[1],
                nose[0] - shoulder_center[0]
            ))
            
            # Calculate spine alignment (shoulders relative to hips)
            hip_center = (left_hip + right_hip) / 2
            spine_vector = shoulder_center - hip_center
            spine_angle = np.degrees(np.arctan2(spine_vector[0], spine_vector[1]))
            
            # Slouching detection (shoulders too far forward)
            is_slouching = abs(spine_angle) > 15  # More than 15 degrees forward
            
            # Calculate overall posture score
            # Good posture: shoulders level, head upright, spine straight
            shoulder_score = max(0, 1.0 - abs(shoulder_angle) / 30.0)
            head_score = max(0, 1.0 - abs(head_tilt - 90) / 45.0)
            spine_score = max(0, 1.0 - abs(spine_angle) / 30.0)
            
            posture_score = (shoulder_score + head_score + spine_score) / 3.0
            
            return posture_score, shoulder_angle, head_tilt, is_slouching
            
        except Exception as e:
            logger.error(f"Posture calculation failed: {e}")
            return 0.5, 0.0, 0.0, False
    
    def _process_face(self, rgb_frame: np.ndarray) -> Optional[FaceData]:
        """Process face detection"""
        try:
            results = self.face_mesh.process(rgb_frame)
            
            if not results.multi_face_landmarks:
                return FaceData(
                    landmarks=[],
                    eye_contact_score=0.0,
                    head_pose=(0.0, 0.0, 0.0),
                    face_visible=False,
                    face_distance_score=0.0
                )
            
            face_landmarks = results.multi_face_landmarks[0]
            landmarks = [
                (lm.x, lm.y)
                for lm in face_landmarks.landmark
            ]
            
            # Calculate eye contact score (looking at camera)
            eye_contact_score = self._calculate_eye_contact(landmarks)
            
            # Estimate head pose
            head_pose = self._estimate_head_pose(landmarks)
            
            # Calculate face distance score (optimal viewing distance)
            face_distance_score = self._calculate_face_distance(landmarks)
            
            return FaceData(
                landmarks=landmarks,
                eye_contact_score=eye_contact_score,
                head_pose=head_pose,
                face_visible=True,
                face_distance_score=face_distance_score
            )
            
        except Exception as e:
            logger.error(f"Face processing failed: {e}")
            return None
    
    def _calculate_eye_contact(self, landmarks: List[Tuple[float, float]]) -> float:
        """
        Calculate eye contact score (0.0 = looking away, 1.0 = looking at camera)
        """
        try:
            # Use key facial landmarks to estimate gaze direction
            # Simplified: check if eyes are centered in frame
            
            # Eye landmarks (simplified indices)
            left_eye = np.array(landmarks[33])  # Left eye center
            right_eye = np.array(landmarks[263])  # Right eye center
            np.array(landmarks[1])  # Nose tip
            
            # Eyes should be horizontally aligned and centered
            eye_center = (left_eye + right_eye) / 2
            
            # Score based on how centered the face is
            # Ideal: eye center close to (0.5, 0.4) - slightly above center
            target = np.array([0.5, 0.4])
            distance = float(np.linalg.norm(eye_center - target))
            
            # Convert distance to score (closer = higher score)
            return max(0.0, 1.0 - distance * 3.0)
            
        except Exception as e:
            logger.error(f"Eye contact calculation failed: {e}")
            return 0.5
    
    def _estimate_head_pose(
        self,
        landmarks: List[Tuple[float, float]]
    ) -> Tuple[float, float, float]:
        """
        Estimate head pose (pitch, yaw, roll) in degrees
        Simplified estimation using facial landmarks
        """
        try:
            # Use key landmarks to estimate head rotation
            nose = np.array(landmarks[1])
            left_eye = np.array(landmarks[33])
            right_eye = np.array(landmarks[263])
            
            # Estimate yaw (left-right rotation)
            eye_center = (left_eye + right_eye) / 2
            yaw = (nose[0] - eye_center[0]) * 180  # Simplified
            
            # Estimate pitch (up-down rotation)
            pitch = (nose[1] - eye_center[1]) * 180  # Simplified
            
            # Estimate roll (tilt)
            eye_vector = right_eye - left_eye
            roll = np.degrees(np.arctan2(eye_vector[1], eye_vector[0]))
            
            return (pitch, yaw, roll)
            
        except Exception as e:
            logger.error(f"Head pose estimation failed: {e}")
            return (0.0, 0.0, 0.0)
    
    def _calculate_face_distance(self, landmarks: List[Tuple[float, float]]) -> float:
        """
        Calculate if face is at optimal distance from camera
        0.0 = too close/far, 1.0 = optimal
        """
        try:
            # Use face width to estimate distance
            left = np.array(landmarks[234])  # Left face edge
            right = np.array(landmarks[454])  # Right face edge
            
            face_width = np.linalg.norm(right - left)
            
            # Optimal face width: 0.3-0.5 of frame width
            optimal_range = (0.3, 0.5)
            
            if optimal_range[0] <= face_width <= optimal_range[1]:
                score = 1.0
            elif face_width < optimal_range[0]:
                # Too far
                score = float(face_width / optimal_range[0])
            else:
                # Too close
                score = float(optimal_range[1] / face_width)
            
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            logger.error(f"Face distance calculation failed: {e}")
            return 0.5
    
    def _process_hands(self, rgb_frame: np.ndarray) -> Optional[HandData]:
        """Process hand detection"""
        try:
            results = self.hands.process(rgb_frame)
            
            left_visible = False
            right_visible = False
            left_landmarks = []
            right_landmarks = []
            movement_score = 0.0
            
            if results.multi_hand_landmarks:
                current_positions = []
                
                for hand_landmarks, handedness in zip(
                    results.multi_hand_landmarks,
                    results.multi_handedness
                ):
                    # Determine which hand
                    mediapipe_label = handedness.classification[0].label
                    # If mirror_mode, flip the labels (MediaPipe "Left" = User's Right in mirror)
                    if self.mirror_mode:
                        is_left = mediapipe_label == "Right"  # FLIPPED for mirror mode
                    else:
                        is_left = mediapipe_label == "Left"  # ORIGINAL
                    
                    # Extract all 21 landmarks (x, y, z)
                    landmarks = [
                        (lm.x, lm.y, lm.z) for lm in hand_landmarks.landmark
                    ]
                    
                    if is_left:
                        left_visible = True
                        left_landmarks = landmarks
                    else:
                        right_visible = True
                        right_landmarks = landmarks
                    
                    # Calculate hand center position
                    hand_center = np.mean([
                        [lm.x, lm.y] for lm in hand_landmarks.landmark
                    ], axis=0)
                    current_positions.append(hand_center)
                
                # Calculate movement (compare with previous frame)
                if self.previous_hand_positions is not None:
                    movement = self._calculate_hand_movement(
                        self.previous_hand_positions,
                        current_positions
                    )
                    movement_score = movement
                
                self.previous_hand_positions = current_positions
            else:
                self.previous_hand_positions = None
            
            # Fidgeting detection (high movement score)
            is_fidgeting = movement_score > 0.15  # Threshold for excessive movement
            
            return HandData(
                left_hand_visible=left_visible,
                right_hand_visible=right_visible,
                left_hand_landmarks=left_landmarks,
                right_hand_landmarks=right_landmarks,
                movement_score=movement_score,
                is_fidgeting=is_fidgeting
            )
            
        except Exception as e:
            logger.error(f"Hand processing failed: {e}")
            return None
    
    def _calculate_hand_movement(
        self,
        previous_positions: List[np.ndarray],
        current_positions: List[np.ndarray]
    ) -> float:
        """Calculate hand movement between frames"""
        try:
            if not previous_positions or not current_positions:
                return 0.0
            
            # Calculate average movement
            movements = []
            for prev_pos in previous_positions:
                # Find closest current position
                distances = [
                    np.linalg.norm(curr_pos - prev_pos)
                    for curr_pos in current_positions
                ]
                movements.append(min(distances))
            
            avg_movement = np.mean(movements)
            
            # Normalize to 0-1 range (movement > 0.2 is significant)
            return min(1.0, avg_movement / 0.2)
            
        except Exception as e:
            logger.error(f"Movement calculation failed: {e}")
            return 0.0
    
    def draw_landmarks_on_frame(
        self,
        frame: np.ndarray,
        results: Dict[str, Optional[object]],
        draw_pose: bool = True,
        draw_face: bool = True,
        draw_hands: bool = True,
        draw_bounding_box: bool = True
    ) -> np.ndarray:
        """
        Draw pose/face/hand landmarks on the frame (like the visualization you showed!)
        
        Args:
            frame: BGR image from OpenCV
            results: Results from analyze_frame()
            draw_pose: Draw pose skeleton
            draw_face: Draw face mesh
            draw_hands: Draw hand landmarks
            draw_bounding_box: Draw bounding box around person
            
        Returns:
            Frame with landmarks drawn
        """
        if mp_drawing is None:
            logger.warning("MediaPipe drawing utils not available")
            return frame
        
        annotated_frame = frame.copy()
        h, w, c = frame.shape
        
        # Re-process frame to get MediaPipe results for drawing
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Draw pose landmarks
        if draw_pose and self.enable_pose:
            pose_results = self.pose.process(rgb_frame)
            if pose_results.pose_landmarks:
                # Draw the skeleton
                mp_drawing.draw_landmarks(
                    annotated_frame,
                    pose_results.pose_landmarks,
                    self.mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style()
                )
                
                # Draw bounding box
                if draw_bounding_box:
                    landmarks = pose_results.pose_landmarks.landmark
                    x_coords = [lm.x * w for lm in landmarks]
                    y_coords = [lm.y * h for lm in landmarks]
                    
                    x_min, x_max = int(min(x_coords)), int(max(x_coords))
                    y_min, y_max = int(min(y_coords)), int(max(y_coords))
                    
                    # Draw red bounding box
                    cv2.rectangle(annotated_frame, (x_min, y_min), (x_max, y_max), (0, 0, 255), 2)
                    
                    # Add "person" label with confidence
                    pose_data = results.get('pose_data')
                    confidence_score = 90  # Default
                    if pose_data and hasattr(pose_data, 'posture_score'):
                        confidence_score = int(pose_data.posture_score * 100)
                    
                    cv2.putText(
                        annotated_frame,
                        f"person: {confidence_score}",
                        (x_min, y_min - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 0, 255),
                        2
                    )
        
        # Draw face mesh
        if draw_face and self.enable_face:
            face_results = self.face_mesh.process(rgb_frame)
            if face_results.multi_face_landmarks:
                for face_landmarks in face_results.multi_face_landmarks:
                    mp_drawing.draw_landmarks(
                        annotated_frame,
                        face_landmarks,
                        self.mp_face.FACEMESH_CONTOURS,
                        landmark_drawing_spec=None,
                        connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_contours_style()
                    )
        
        # Draw hand landmarks
        if draw_hands and self.enable_hands:
            hands_results = self.hands.process(rgb_frame)
            if hands_results.multi_hand_landmarks:
                for hand_landmarks in hands_results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(
                        annotated_frame,
                        hand_landmarks,
                        self.mp_hands.HAND_CONNECTIONS,
                        mp_drawing_styles.get_default_hand_landmarks_style(),
                        mp_drawing_styles.get_default_hand_connections_style()
                    )
        
        return annotated_frame
    
    def close(self):
        """Clean up resources"""
        if self.enable_pose:
            self.pose.close()
        if self.enable_face:
            self.face_mesh.close()
        if self.enable_hands:
            self.hands.close()
        
        logger.info("MediaPipe analyzer closed")


