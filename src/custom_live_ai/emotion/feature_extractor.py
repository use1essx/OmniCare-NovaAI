"""
Feature extraction from normalized face landmarks
"""

import numpy as np
from typing import Dict, List, Optional
from collections import deque
from .config import FEATURE_WINDOW


def extract_base_features(landmarks: np.ndarray) -> Dict[str, float]:
    """
    Extract geometric features from normalized 468 landmarks
    
    Args:
        landmarks: Array of shape (468, 2) with normalized coordinates
        
    Returns:
        Dictionary of base geometric features
    """
    if landmarks.shape[0] != 468 or landmarks.shape[1] != 2:
        return {}
    
    lm = landmarks
    features = {}
    
    # === MOUTH FEATURES ===
    # Mouth corners
    left_corner = lm[61]
    right_corner = lm[291]
    upper_lip = lm[13]
    lower_lip = lm[14]
    
    # Mouth width and height
    mouth_width = np.linalg.norm(right_corner - left_corner)
    mouth_height = np.linalg.norm(upper_lip - lower_lip)
    features['mouth_width'] = float(mouth_width)
    features['mouth_height'] = float(mouth_height)
    features['mouth_aspect_ratio'] = float(mouth_height / (mouth_width + 1e-6))
    
    # Smile lift (corners higher than center)
    corners_avg_y = (left_corner[1] + right_corner[1]) / 2
    lips_center_y = (upper_lip[1] + lower_lip[1]) / 2
    features['smile_lift'] = float(lips_center_y - corners_avg_y)
    
    # === EYE FEATURES ===
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
    left_eye_height = np.linalg.norm(left_eye_top - left_eye_bottom)
    right_eye_height = np.linalg.norm(right_eye_top - right_eye_bottom)
    avg_eye_height = (left_eye_height + right_eye_height) / 2
    features['left_eye_height'] = float(left_eye_height)
    features['right_eye_height'] = float(right_eye_height)
    features['avg_eye_height'] = float(avg_eye_height)
    
    # Eye width
    left_eye_width = np.linalg.norm(left_eye_right - left_eye_left)
    right_eye_width = np.linalg.norm(right_eye_right - right_eye_left)
    features['left_eye_width'] = float(left_eye_width)
    features['right_eye_width'] = float(right_eye_width)
    
    # Eye aspect ratios
    features['left_eye_ratio'] = float(left_eye_height / (left_eye_width + 1e-6))
    features['right_eye_ratio'] = float(right_eye_height / (right_eye_width + 1e-6))
    features['avg_eye_ratio'] = float(avg_eye_height / ((left_eye_width + right_eye_width) / 2 + 1e-6))
    
    # === EYEBROW FEATURES ===
    # Left eyebrow
    left_brow_inner = lm[70]
    left_brow_mid = lm[107]
    left_brow_outer = lm[66]
    
    # Right eyebrow
    right_brow_inner = lm[300]
    right_brow_mid = lm[336]
    right_brow_outer = lm[296]
    
    # Eyebrow height (relative to eyes)
    left_brow_height = np.linalg.norm(left_eye_top - left_brow_mid)
    right_brow_height = np.linalg.norm(right_eye_top - right_brow_mid)
    avg_brow_height = (left_brow_height + right_brow_height) / 2
    features['left_brow_height'] = float(left_brow_height)
    features['right_brow_height'] = float(right_brow_height)
    features['avg_brow_height'] = float(avg_brow_height)
    
    # Eyebrow distance (furrowed brows)
    brow_distance = np.linalg.norm(right_brow_inner - left_brow_inner)
    features['brow_distance'] = float(brow_distance)
    
    # === NOSE FEATURES ===
    nose_tip = lm[1]
    nose_bridge = lm[6]
    left_nostril = lm[129]
    right_nostril = lm[358]
    
    # Nostril width
    nostril_width = np.linalg.norm(right_nostril - left_nostril)
    features['nostril_width'] = float(nostril_width)
    
    # Nose vertical extent
    nose_height = np.linalg.norm(nose_bridge - nose_tip)
    features['nose_height'] = float(nose_height)
    
    # === ADVANCED FEATURES FOR DISGUST ===
    # Nose wrinkle intensity (distance between nose bridge and nostril width)
    # When nose wrinkles, nostrils flare and bridge compresses
    nose_wrinkle_intensity = nostril_width / (nose_height + 1e-6)
    features['nose_wrinkle_intensity'] = float(nose_wrinkle_intensity)
    
    # Upper lip raise (distance from upper lip to nose tip - smaller = raised lip)
    upper_lip_to_nose = np.linalg.norm(nose_tip - upper_lip)
    features['upper_lip_raise'] = float(upper_lip_to_nose)
    
    # Lip corner asymmetry (left vs right corner height difference)
    lip_corner_asymmetry = abs(left_corner[1] - right_corner[1])
    features['lip_corner_asymmetry'] = float(lip_corner_asymmetry)
    
    # === ADVANCED FEATURES FOR SURPRISE/FEAR ===
    # Eyebrow arch curvature (measure brow curve using outer, mid, inner points)
    # Higher curvature = more arched (surprise), flatter = fear/angry
    left_brow_curve = abs((left_brow_mid[1] - (left_brow_inner[1] + left_brow_outer[1]) / 2))
    right_brow_curve = abs((right_brow_mid[1] - (right_brow_inner[1] + right_brow_outer[1]) / 2))
    avg_brow_curve = (left_brow_curve + right_brow_curve) / 2
    features['eyebrow_arch_curvature'] = float(avg_brow_curve)
    
    # Eye white exposure (eye height to width ratio - higher = more white exposed)
    # Similar to avg_eye_ratio but specifically for surprise/fear detection
    eye_white_exposure = avg_eye_height / ((left_eye_width + right_eye_width) / 2 + 1e-6)
    features['eye_white_exposure'] = float(eye_white_exposure)
    
    # Jaw drop amount (vertical distance from chin to lower lip)
    # Chin landmark: 152 (bottom of face)
    chin = lm[152]
    jaw_drop = np.linalg.norm(chin - lower_lip)
    features['jaw_drop_amount'] = float(jaw_drop)
    
    # === ADVANCED FEATURES FOR ANGRY ===
    # Brow furrow depth (inner brow convergence - lower = more furrowed)
    # Measured as distance between inner brow points
    brow_furrow_depth = brow_distance  # Already calculated, just alias for clarity
    features['brow_furrow_depth'] = float(brow_furrow_depth)
    
    # Jaw clench indicator (mouth width vs baseline - narrower = clenched)
    # Using mouth width / face width ratio
    face_width = np.linalg.norm(lm[234] - lm[454])  # Left to right face edge
    jaw_clench_indicator = mouth_width / (face_width + 1e-6)
    features['jaw_clench_indicator'] = float(jaw_clench_indicator)
    
    # Eye narrowing (left vs right eye width variance)
    eye_width_diff = abs(left_eye_width - right_eye_width)
    features['eye_narrowing'] = float(eye_width_diff)
    
    return features


class FeatureBuffer:
    """
    Ring buffer for storing per-frame features for temporal analysis
    """
    
    def __init__(self, window: int = FEATURE_WINDOW):
        """
        Args:
            window: Maximum number of frames to store
        """
        self.window = window
        self.buffer: deque = deque(maxlen=window)
        self.feature_names: Optional[List[str]] = None
        
    def add_frame(self, features: Dict[str, float]) -> None:
        """
        Add a frame's features to the buffer
        
        Args:
            features: Dictionary of feature values
        """
        if self.feature_names is None:
            self.feature_names = sorted(features.keys())
        
        # Store as ordered list matching feature_names
        feature_vector = [features.get(name, 0.0) for name in self.feature_names]
        self.buffer.append(feature_vector)
        
    def get_temporal_stats(self) -> Dict[str, float]:
        """
        Calculate temporal statistics over the buffer
        
        Returns:
            Dictionary with mean, std, min, max, and delta features
        """
        if len(self.buffer) == 0 or self.feature_names is None:
            return {}
        
        # Convert buffer to numpy array (frames × features)
        data: np.ndarray = np.array(self.buffer)
        
        stats = {}
        
        for i, name in enumerate(self.feature_names):
            col = data[:, i]
            
            # Basic statistics
            stats[f'{name}_mean'] = float(np.mean(col))
            stats[f'{name}_std'] = float(np.std(col))
            stats[f'{name}_min'] = float(np.min(col))
            stats[f'{name}_max'] = float(np.max(col))
            
            # Temporal derivatives (last frame - N frames ago)
            if len(col) >= 2:
                stats[f'{name}_delta_1'] = float(col[-1] - col[-2])
            else:
                stats[f'{name}_delta_1'] = 0.0
                
            if len(col) >= 6:
                stats[f'{name}_delta_5'] = float(col[-1] - col[-6])
            else:
                stats[f'{name}_delta_5'] = 0.0
        
        return stats
        
    def get_full_feature_vector(self, base_features: Dict[str, float]) -> Dict[str, float]:
        """
        Get combined base + temporal features
        
        Args:
            base_features: Current frame's base features
            
        Returns:
            Combined feature dictionary
        """
        # Add current frame to buffer
        self.add_frame(base_features)
        
        # Get temporal stats
        temporal_stats = self.get_temporal_stats()
        
        # Combine base + temporal
        combined = {**base_features, **temporal_stats}
        
        return combined
        
    def reset(self) -> None:
        """Clear the buffer"""
        self.buffer.clear()
        self.feature_names = None

