"""
Preprocessing utilities for face landmarks normalization
"""

import numpy as np
from typing import Dict


def procrustes_normalize(landmarks_468: np.ndarray) -> np.ndarray:
    """
    Normalize 468 face landmarks for translation, scale, and rotation
    
    Args:
        landmarks_468: Array of shape (468, 2) or (468, 3) with x, y, (z) coordinates
        
    Returns:
        Normalized landmarks of shape (468, 2) - 2D coordinates only
    """
    if landmarks_468.shape[0] != 468:
        raise ValueError(f"Expected 468 landmarks, got {landmarks_468.shape[0]}")
    
    # Work with 2D coordinates only (x, y)
    if landmarks_468.shape[1] >= 2:
        coords = landmarks_468[:, :2].copy()
    else:
        raise ValueError(f"Expected at least 2 columns, got {landmarks_468.shape[1]}")
    
    # 1. Remove translation (center at origin)
    centroid = np.mean(coords, axis=0)
    coords_centered = coords - centroid
    
    # 2. Remove scale (normalize to unit scale)
    scale = np.sqrt(np.sum(coords_centered ** 2))
    if scale < 1e-8:
        # Degenerate case: all points at same location
        return coords
    coords_scaled = coords_centered / scale
    
    # 3. Remove rotation (align to canonical orientation)
    # Use eyes as reference: left eye (33) and right eye (263)
    left_eye = coords_scaled[33]
    right_eye = coords_scaled[263]
    
    # Calculate angle to rotate eyes to horizontal
    dx = right_eye[0] - left_eye[0]
    dy = right_eye[1] - left_eye[1]
    angle = np.arctan2(dy, dx)
    
    # Rotation matrix
    cos_a = np.cos(-angle)
    sin_a = np.sin(-angle)
    rotation_matrix = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
    
    # Apply rotation
    coords_rotated = coords_scaled @ rotation_matrix.T
    
    return coords_rotated


def face_size_metrics(landmarks: np.ndarray) -> Dict[str, float]:
    """
    Calculate face size metrics for normalization reference
    
    Args:
        landmarks: Array of shape (468, 2) with normalized coordinates
        
    Returns:
        Dictionary with face metrics
    """
    if landmarks.shape[0] != 468 or landmarks.shape[1] < 2:
        return {"inter_ocular_distance": 0.0, "face_width": 0.0, "face_height": 0.0}
    
    # Inter-ocular distance (left eye 33 to right eye 263)
    left_eye = landmarks[33]
    right_eye = landmarks[263]
    inter_ocular = np.linalg.norm(right_eye - left_eye)
    
    # Face width (left cheek 234 to right cheek 454)
    left_cheek = landmarks[234]
    right_cheek = landmarks[454]
    face_width = np.linalg.norm(right_cheek - left_cheek)
    
    # Face height (top 10 to bottom 152)
    top = landmarks[10]
    bottom = landmarks[152]
    face_height = np.linalg.norm(bottom - top)
    
    return {
        "inter_ocular_distance": float(inter_ocular),
        "face_width": float(face_width),
        "face_height": float(face_height)
    }

