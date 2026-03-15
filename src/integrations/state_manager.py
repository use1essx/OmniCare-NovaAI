"""
Redis State Manager for Real-time Emotion/Movement Tracking

Provides async state management for:
- Real-time emotion state updates
- Movement/pose tracking data
- Session state caching
- Cross-service state synchronization

All state updates are designed for < 500ms latency.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

try:
    import redis.asyncio as aioredis
except ImportError:
    import aioredis

from ..core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class StateType(str, Enum):
    """Types of state stored in Redis"""
    EMOTION = "emotion"
    MOVEMENT = "movement"
    SESSION = "session"
    MULTIMODAL = "multimodal"
    ALERT = "alert"
    SKILL = "skill"


@dataclass
class EmotionState:
    """Current emotion state for a session"""
    emotion: str
    intensity: int  # 1-5
    confidence: float  # 0-1
    gaze_direction: Optional[str] = None
    facial_features: Optional[Dict] = None
    detected_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        if self.detected_at is None:
            data['detected_at'] = datetime.utcnow().isoformat()
        return data


@dataclass
class MovementState:
    """Current movement/pose state for a session"""
    gesture: str
    posture: str
    energy_level: str  # high, medium, low, very_low
    activity: str
    confidence: float
    movement_intensity: float  # 0-1
    behavioral_markers: Optional[Dict] = None
    detected_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        if self.detected_at is None:
            data['detected_at'] = datetime.utcnow().isoformat()
        return data


@dataclass
class MultimodalContext:
    """Combined multimodal context for agent processing"""
    session_id: str
    emotion: Optional[EmotionState] = None
    movement: Optional[MovementState] = None
    last_updated: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'session_id': self.session_id,
            'emotion': self.emotion.to_dict() if self.emotion else None,
            'movement': self.movement.to_dict() if self.movement else None,
            'last_updated': self.last_updated or datetime.utcnow().isoformat()
        }


class RedisStateManager:
    """
    Async Redis state manager for real-time state tracking.
    
    Manages:
    - Emotion states (updated every ~500ms during video analysis)
    - Movement states (updated every ~500ms during video analysis)
    - Session contexts (multimodal data for agent)
    - Skill activation states
    
    All operations are async for non-blocking performance.
    """
    
    # Key prefixes for different state types
    KEY_PREFIX = "hiyori:"
    EMOTION_PREFIX = f"{KEY_PREFIX}emotion:"
    MOVEMENT_PREFIX = f"{KEY_PREFIX}movement:"
    SESSION_PREFIX = f"{KEY_PREFIX}session:"
    MULTIMODAL_PREFIX = f"{KEY_PREFIX}multimodal:"
    ALERT_PREFIX = f"{KEY_PREFIX}alert:"
    SKILL_PREFIX = f"{KEY_PREFIX}skill:"
    
    # TTL defaults (seconds)
    DEFAULT_TTL = 3600  # 1 hour
    EMOTION_TTL = 300   # 5 minutes (frequently updated)
    MOVEMENT_TTL = 300  # 5 minutes (frequently updated)
    SESSION_TTL = 1800  # 30 minutes
    MULTIMODAL_TTL = 600  # 10 minutes
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize Redis state manager.
        
        Args:
            redis_url: Redis connection URL. Uses settings if not provided.
        """
        self.redis_url = redis_url or settings.redis_url
        self._redis: Optional[aioredis.Redis] = None
        self._connected = False
    
    async def connect(self) -> None:
        """Establish Redis connection"""
        if self._connected and self._redis:
            return
        
        try:
            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0
            )
            # Test connection
            await self._redis.ping()
            self._connected = True
            logger.info("Redis state manager connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            raise
    
    async def disconnect(self) -> None:
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
            self._connected = False
            logger.info("Redis state manager disconnected")
    
    async def ensure_connected(self) -> None:
        """Ensure Redis is connected"""
        if not self._connected or not self._redis:
            await self.connect()
    
    # =========================================================================
    # EMOTION STATE OPERATIONS
    # =========================================================================
    
    async def set_emotion_state(
        self,
        session_id: str,
        emotion: str,
        intensity: int,
        confidence: float,
        gaze_direction: Optional[str] = None,
        facial_features: Optional[Dict] = None,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Update emotion state for a session.
        
        Args:
            session_id: Session identifier
            emotion: Detected emotion (sad, happy, anxious, etc.)
            intensity: Emotion intensity 1-5
            confidence: Detection confidence 0-1
            gaze_direction: Where user is looking
            facial_features: Detailed facial analysis
            ttl: Optional TTL override
            
        Returns:
            True if successful
        """
        await self.ensure_connected()
        
        state = EmotionState(
            emotion=emotion,
            intensity=intensity,
            confidence=confidence,
            gaze_direction=gaze_direction,
            facial_features=facial_features
        )
        
        key = f"{self.EMOTION_PREFIX}{session_id}"
        ttl = ttl or self.EMOTION_TTL
        
        try:
            await self._redis.setex(
                key,
                ttl,
                json.dumps(state.to_dict())
            )
            
            # Also update multimodal context
            await self._update_multimodal_emotion(session_id, state)
            
            logger.debug(f"Emotion state updated for session {session_id}: {emotion}")
            return True
        except Exception as e:
            logger.error(f"Failed to set emotion state: {e}")
            return False
    
    async def get_emotion_state(self, session_id: str) -> Optional[EmotionState]:
        """
        Get current emotion state for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            EmotionState or None if not found
        """
        await self.ensure_connected()
        
        key = f"{self.EMOTION_PREFIX}{session_id}"
        
        try:
            data = await self._redis.get(key)
            if data:
                state_dict = json.loads(data)
                return EmotionState(**state_dict)
            return None
        except Exception as e:
            logger.error(f"Failed to get emotion state: {e}")
            return None
    
    # =========================================================================
    # MOVEMENT STATE OPERATIONS
    # =========================================================================
    
    async def set_movement_state(
        self,
        session_id: str,
        gesture: str,
        posture: str,
        energy_level: str,
        activity: str,
        confidence: float,
        movement_intensity: float = 0.0,
        behavioral_markers: Optional[Dict] = None,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Update movement state for a session.
        
        Args:
            session_id: Session identifier
            gesture: Detected gesture (slouched, fidgeting, etc.)
            posture: Body posture
            energy_level: Energy level (high, medium, low, very_low)
            activity: Current activity
            confidence: Detection confidence
            movement_intensity: Movement intensity 0-1
            behavioral_markers: Detailed behavioral analysis
            ttl: Optional TTL override
            
        Returns:
            True if successful
        """
        await self.ensure_connected()
        
        state = MovementState(
            gesture=gesture,
            posture=posture,
            energy_level=energy_level,
            activity=activity,
            confidence=confidence,
            movement_intensity=movement_intensity,
            behavioral_markers=behavioral_markers
        )
        
        key = f"{self.MOVEMENT_PREFIX}{session_id}"
        ttl = ttl or self.MOVEMENT_TTL
        
        try:
            await self._redis.setex(
                key,
                ttl,
                json.dumps(state.to_dict())
            )
            
            # Also update multimodal context
            await self._update_multimodal_movement(session_id, state)
            
            logger.debug(f"Movement state updated for session {session_id}: {gesture}")
            return True
        except Exception as e:
            logger.error(f"Failed to set movement state: {e}")
            return False
    
    async def get_movement_state(self, session_id: str) -> Optional[MovementState]:
        """
        Get current movement state for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            MovementState or None if not found
        """
        await self.ensure_connected()
        
        key = f"{self.MOVEMENT_PREFIX}{session_id}"
        
        try:
            data = await self._redis.get(key)
            if data:
                state_dict = json.loads(data)
                return MovementState(**state_dict)
            return None
        except Exception as e:
            logger.error(f"Failed to get movement state: {e}")
            return None
    
    # =========================================================================
    # MULTIMODAL CONTEXT OPERATIONS
    # =========================================================================
    
    async def get_multimodal_context(self, session_id: str) -> Optional[Dict]:
        """
        Get combined multimodal context for agent processing.
        
        This is the primary method for the unified agent to get
        current emotion + movement state for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dict with emotion and movement data, or None
        """
        await self.ensure_connected()
        
        key = f"{self.MULTIMODAL_PREFIX}{session_id}"
        
        try:
            data = await self._redis.get(key)
            if data:
                return json.loads(data)
            
            # If no cached multimodal context, build from components
            emotion = await self.get_emotion_state(session_id)
            movement = await self.get_movement_state(session_id)
            
            if emotion or movement:
                context = MultimodalContext(
                    session_id=session_id,
                    emotion=emotion,
                    movement=movement
                )
                return context.to_dict()
            
            return None
        except Exception as e:
            logger.error(f"Failed to get multimodal context: {e}")
            return None
    
    async def _update_multimodal_emotion(
        self,
        session_id: str,
        emotion: EmotionState
    ) -> None:
        """Update emotion component of multimodal context"""
        key = f"{self.MULTIMODAL_PREFIX}{session_id}"
        
        try:
            # Get existing context
            data = await self._redis.get(key)
            if data:
                context = json.loads(data)
            else:
                context = {
                    'session_id': session_id,
                    'emotion': None,
                    'movement': None,
                    'last_updated': None
                }
            
            # Update emotion
            context['emotion'] = emotion.to_dict()
            context['last_updated'] = datetime.utcnow().isoformat()
            
            await self._redis.setex(
                key,
                self.MULTIMODAL_TTL,
                json.dumps(context)
            )
        except Exception as e:
            logger.error(f"Failed to update multimodal emotion: {e}")
    
    async def _update_multimodal_movement(
        self,
        session_id: str,
        movement: MovementState
    ) -> None:
        """Update movement component of multimodal context"""
        key = f"{self.MULTIMODAL_PREFIX}{session_id}"
        
        try:
            # Get existing context
            data = await self._redis.get(key)
            if data:
                context = json.loads(data)
            else:
                context = {
                    'session_id': session_id,
                    'emotion': None,
                    'movement': None,
                    'last_updated': None
                }
            
            # Update movement
            context['movement'] = movement.to_dict()
            context['last_updated'] = datetime.utcnow().isoformat()
            
            await self._redis.setex(
                key,
                self.MULTIMODAL_TTL,
                json.dumps(context)
            )
        except Exception as e:
            logger.error(f"Failed to update multimodal movement: {e}")
    
    # =========================================================================
    # SESSION STATE OPERATIONS
    # =========================================================================
    
    async def set_session_state(
        self,
        session_id: str,
        state: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set arbitrary session state.
        
        Args:
            session_id: Session identifier
            state: State dictionary to store
            ttl: Optional TTL override
            
        Returns:
            True if successful
        """
        await self.ensure_connected()
        
        key = f"{self.SESSION_PREFIX}{session_id}"
        ttl = ttl or self.SESSION_TTL
        
        try:
            state['_updated_at'] = datetime.utcnow().isoformat()
            await self._redis.setex(key, ttl, json.dumps(state))
            return True
        except Exception as e:
            logger.error(f"Failed to set session state: {e}")
            return False
    
    async def get_session_state(self, session_id: str) -> Optional[Dict]:
        """
        Get session state.
        
        Args:
            session_id: Session identifier
            
        Returns:
            State dictionary or None
        """
        await self.ensure_connected()
        
        key = f"{self.SESSION_PREFIX}{session_id}"
        
        try:
            data = await self._redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get session state: {e}")
            return None
    
    async def update_session_state(
        self,
        session_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update specific fields in session state.
        
        Args:
            session_id: Session identifier
            updates: Fields to update
            
        Returns:
            True if successful
        """
        await self.ensure_connected()
        
        try:
            current = await self.get_session_state(session_id) or {}
            current.update(updates)
            return await self.set_session_state(session_id, current)
        except Exception as e:
            logger.error(f"Failed to update session state: {e}")
            return False
    
    # =========================================================================
    # SKILL STATE OPERATIONS (for tracking active skills per session)
    # =========================================================================
    
    async def set_active_skills(
        self,
        session_id: str,
        skills: List[str],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set currently active skills for a session.
        
        Args:
            session_id: Session identifier
            skills: List of active skill names
            ttl: Optional TTL override
            
        Returns:
            True if successful
        """
        await self.ensure_connected()
        
        key = f"{self.SKILL_PREFIX}{session_id}"
        ttl = ttl or self.SESSION_TTL
        
        try:
            data = {
                'skills': skills,
                'updated_at': datetime.utcnow().isoformat()
            }
            await self._redis.setex(key, ttl, json.dumps(data))
            return True
        except Exception as e:
            logger.error(f"Failed to set active skills: {e}")
            return False
    
    async def get_active_skills(self, session_id: str) -> List[str]:
        """
        Get currently active skills for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of active skill names
        """
        await self.ensure_connected()
        
        key = f"{self.SKILL_PREFIX}{session_id}"
        
        try:
            data = await self._redis.get(key)
            if data:
                parsed = json.loads(data)
                return parsed.get('skills', [])
            return []
        except Exception as e:
            logger.error(f"Failed to get active skills: {e}")
            return []
    
    # =========================================================================
    # UTILITY OPERATIONS
    # =========================================================================
    
    async def delete_session_data(self, session_id: str) -> bool:
        """
        Delete all state data for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful
        """
        await self.ensure_connected()
        
        keys = [
            f"{self.EMOTION_PREFIX}{session_id}",
            f"{self.MOVEMENT_PREFIX}{session_id}",
            f"{self.SESSION_PREFIX}{session_id}",
            f"{self.MULTIMODAL_PREFIX}{session_id}",
            f"{self.SKILL_PREFIX}{session_id}",
        ]
        
        try:
            await self._redis.delete(*keys)
            logger.info(f"Deleted all state data for session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete session data: {e}")
            return False
    
    async def get_session_keys(self, session_id: str) -> List[str]:
        """
        Get all keys associated with a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of Redis keys
        """
        await self.ensure_connected()
        
        pattern = f"{self.KEY_PREFIX}*:{session_id}"
        
        try:
            keys = []
            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)
            return keys
        except Exception as e:
            logger.error(f"Failed to get session keys: {e}")
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Redis connection.
        
        Returns:
            Dict with health status
        """
        try:
            await self.ensure_connected()
            await self._redis.ping()
            
            info = await self._redis.info()
            
            return {
                'status': 'healthy',
                'connected': True,
                'redis_version': info.get('redis_version'),
                'connected_clients': info.get('connected_clients'),
                'used_memory_human': info.get('used_memory_human'),
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'connected': False,
                'error': str(e)
            }


# =========================================================================
# SINGLETON INSTANCE
# =========================================================================

_state_manager: Optional[RedisStateManager] = None


async def get_state_manager() -> RedisStateManager:
    """
    Get or create the singleton state manager instance.
    
    Returns:
        RedisStateManager instance
    """
    global _state_manager
    
    if _state_manager is None:
        _state_manager = RedisStateManager()
        await _state_manager.connect()
    
    return _state_manager


async def close_state_manager() -> None:
    """Close the singleton state manager"""
    global _state_manager
    
    if _state_manager:
        await _state_manager.disconnect()
        _state_manager = None


# =========================================================================
# CONTEXT MANAGER FOR TESTING
# =========================================================================

class StateManagerContext:
    """Context manager for state manager lifecycle"""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url
        self.manager: Optional[RedisStateManager] = None
    
    async def __aenter__(self) -> RedisStateManager:
        self.manager = RedisStateManager(self.redis_url)
        await self.manager.connect()
        return self.manager
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.manager:
            await self.manager.disconnect()

