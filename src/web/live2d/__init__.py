"""
Live2D Integration Module for Healthcare AI V2
==============================================

This module integrates Live2D avatar functionality with the Healthcare AI V2 system,
providing interactive animated healthcare assistants with emotional expressions and gestures.

Components:
- Live2D Core engine and avatar models
- Avatar emotion and gesture mapping
- Speech-to-text integration
- Healthcare AI bridge for seamless communication
- Admin interface for model management
"""

from .routes import live2d_router
from .backend.healthcare_ai_bridge import HealthcareAIBridge

__all__ = [
    "live2d_router",
    "HealthcareAIBridge"
]
