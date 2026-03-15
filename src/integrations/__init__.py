"""
Integrations module for Healthcare AI system.

Contains:
- Live2D client for avatar integration
- State manager for Redis-based real-time state tracking
"""

from .live2d_client import Live2DMessageFormatter
from .state_manager import (
    RedisStateManager,
    EmotionState,
    MovementState,
    MultimodalContext,
    StateType,
    get_state_manager,
    close_state_manager,
    StateManagerContext,
)

__all__ = [
    # Live2D
    'Live2DMessageFormatter',
    
    # State Manager
    'RedisStateManager',
    'EmotionState',
    'MovementState',
    'MultimodalContext',
    'StateType',
    'get_state_manager',
    'close_state_manager',
    'StateManagerContext',
]

