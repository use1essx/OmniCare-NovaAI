"""
Live2D Client Integration Utilities - Healthcare AI V2
======================================================

Comprehensive utilities for integrating with Live2D frontend applications.
Provides message formatting, client communication, avatar coordination,
and seamless healthcare AI system integration.

Features:
- Live2D message formatting and serialization
- Frontend client communication utilities
- Avatar state synchronization
- Emotion and gesture coordination
- Performance optimization for real-time interaction
- Error handling and fallback mechanisms
"""

import asyncio
import aiohttp
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

from src.core.logging import get_logger
from src.agents.emotion_mapper import EmotionMapper
from src.agents.gesture_library import GestureLibrary


logger = get_logger(__name__)


# ============================================================================
# LIVE2D MESSAGE TYPES AND FORMATS
# ============================================================================

class Live2DMessageType(str, Enum):
    """Live2D specific message types"""
    # Avatar Control
    AVATAR_EMOTION = "avatar_emotion"
    AVATAR_GESTURE = "avatar_gesture"
    AVATAR_SPEECH = "avatar_speech"
    AVATAR_STATE = "avatar_state"
    
    # Healthcare Specific
    AGENT_RESPONSE = "agent_response"
    HEALTH_DATA = "health_data"
    EMERGENCY_ALERT = "emergency_alert"
    
    # System Messages
    SYSTEM_STATUS = "system_status"
    CONNECTION_STATUS = "connection_status"
    ERROR_MESSAGE = "error_message"


@dataclass
class Live2DAvatarState:
    """Complete avatar state for Live2D"""
    agent_type: str
    emotion: str
    gesture: str
    voice_tone: str
    energy_level: float  # 0.0 - 1.0
    urgency_level: str
    is_speaking: bool
    last_updated: str
    custom_properties: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.custom_properties is None:
            self.custom_properties = {}
        if not self.last_updated:
            self.last_updated = datetime.now().isoformat()


@dataclass
class Live2DAgentResponse:
    """Healthcare agent response formatted for Live2D"""
    message_id: str
    type: str = Live2DMessageType.AGENT_RESPONSE
    agent_type: str = ""
    agent_name: str = ""
    message: str = ""
    emotion: str = "neutral"
    gesture: str = "default"
    urgency: str = "low"
    language: str = "en"
    confidence: float = 1.0
    processing_time_ms: int = 0
    
    # Healthcare specific
    hk_facilities: List[Dict[str, Any]] = None
    medical_advice: Optional[Dict[str, Any]] = None
    emergency_info: Optional[Dict[str, Any]] = None
    
    # Live2D specific
    avatar_state: Optional[Live2DAvatarState] = None
    voice_settings: Optional[Dict[str, Any]] = None
    animation_cues: List[str] = None
    
    # Metadata
    session_id: str = ""
    timestamp: str = ""
    
    def __post_init__(self):
        if self.hk_facilities is None:
            self.hk_facilities = []
        if self.animation_cues is None:
            self.animation_cues = []
        if not self.message_id:
            self.message_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class Live2DHealthData:
    """Health data formatted for Live2D visualization"""
    data_type: str
    title: str
    description: str
    value: Union[str, int, float]
    unit: str
    urgency: str
    visualization_type: str  # "chart", "indicator", "text", "map"
    display_options: Dict[str, Any]
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


# ============================================================================
# MESSAGE FORMATTER
# ============================================================================

class Live2DMessageFormatter:
    """
    Formats healthcare AI responses for Live2D frontend consumption
    
    Handles:
    - Message structure standardization
    - Avatar state synchronization
    - Cultural adaptation
    - Performance optimization
    """
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.Live2DMessageFormatter")
        self.emotion_mapper = EmotionMapper()
        self.gesture_library = GestureLibrary()
        
        # Message formatting cache
        self.format_cache: Dict[str, Dict[str, Any]] = {}
        
        # Agent-specific voice settings
        self.voice_settings = {
            "illness_monitor": {
                "tone": "professional_warm",
                "pace": "moderate",
                "pitch": "medium",
                "volume": "normal"
            },
            "mental_health": {
                "tone": "gentle_supportive",
                "pace": "slow",
                "pitch": "soft_high",
                "volume": "quiet"
            },
            "safety_guardian": {
                "tone": "authoritative_clear",
                "pace": "fast",
                "pitch": "strong_medium",
                "volume": "loud"
            },
            "wellness_coach": {
                "tone": "energetic_positive",
                "pace": "upbeat",
                "pitch": "bright_high",
                "volume": "cheerful"
            }
        }
    
    def format_agent_response(
        self,
        agent_response: Dict[str, Any],
        session_id: str,
        language: str = "en",
        user_context: Optional[Dict[str, Any]] = None
    ) -> Live2DAgentResponse:
        """
        Format agent response for Live2D consumption
        
        Args:
            agent_response: Raw agent response data
            session_id: Session identifier
            language: Response language
            user_context: User context for personalization
            
        Returns:
            Formatted Live2D agent response
        """
        try:
            # Extract core response data
            agent_type = agent_response.get("agent_type", "wellness_coach")
            message = agent_response.get("message", "")
            urgency = agent_response.get("urgency_level", "low")
            confidence = agent_response.get("confidence", 1.0)
            
            # Map emotion and gesture
            emotion = self.emotion_mapper.map_agent_to_emotion(
                agent_type=agent_type,
                response=message,
                urgency=urgency,
                confidence=confidence,
                language=language,
                context=user_context
            )
            
            gesture = self.gesture_library.get_cultural_gesture(
                agent_type=agent_type,
                context=message,
                language=language,
                urgency=urgency,
                user_age_group=user_context.get("age_group") if user_context else None,
                cultural_preference="modern_hk"
            )
            
            # Create avatar state
            avatar_state = Live2DAvatarState(
                agent_type=agent_type,
                emotion=emotion,
                gesture=gesture,
                voice_tone=self._get_voice_tone(agent_type, urgency),
                energy_level=self._calculate_energy_level(urgency, confidence),
                urgency_level=urgency,
                is_speaking=True,
                last_updated=datetime.now().isoformat()
            )
            
            # Generate animation cues
            animation_cues = self._generate_animation_cues(
                agent_type, emotion, gesture, urgency, message
            )
            
            # Format healthcare data
            hk_facilities = self._format_hk_facilities(
                agent_response.get("hk_data_used", [])
            )
            
            # Create formatted response
            formatted_response = Live2DAgentResponse(
                message_id=str(uuid.uuid4()),
                agent_type=agent_type,
                agent_name=agent_response.get("agent_name", self._get_agent_display_name(agent_type, language)),
                message=message,
                emotion=emotion,
                gesture=gesture,
                urgency=urgency,
                language=language,
                confidence=confidence,
                processing_time_ms=agent_response.get("processing_time_ms", 0),
                hk_facilities=hk_facilities,
                avatar_state=avatar_state,
                voice_settings=self._get_voice_settings(agent_type, urgency),
                animation_cues=animation_cues,
                session_id=session_id,
                timestamp=datetime.now().isoformat()
            )
            
            # Add emergency information if needed
            if urgency in ["high", "emergency"]:
                formatted_response.emergency_info = self._format_emergency_info(
                    agent_response, language
                )
            
            self.logger.debug(f"Formatted response for {agent_type} with emotion '{emotion}' and gesture '{gesture}'")
            return formatted_response
            
        except Exception as e:
            self.logger.error(f"Error formatting agent response: {e}")
            return self._create_fallback_response(session_id, language)
    
    def _get_voice_tone(self, agent_type: str, urgency: str) -> str:
        """Get voice tone based on agent type and urgency"""
        base_tone = self.voice_settings.get(agent_type, {}).get("tone", "professional_warm")
        
        # Modify based on urgency
        if urgency == "emergency":
            return f"{base_tone}_urgent"
        elif urgency == "high":
            return f"{base_tone}_serious"
        elif urgency == "low":
            return f"{base_tone}_relaxed"
        
        return base_tone
    
    def _calculate_energy_level(self, urgency: str, confidence: float) -> float:
        """Calculate energy level for avatar"""
        base_energy = {
            "emergency": 1.0,
            "high": 0.8,
            "medium": 0.6,
            "low": 0.4
        }.get(urgency, 0.5)
        
        # Adjust based on confidence
        energy_adjustment = (confidence - 0.5) * 0.2
        
        return max(0.0, min(1.0, base_energy + energy_adjustment))
    
    def _generate_animation_cues(
        self,
        agent_type: str,
        emotion: str,
        gesture: str,
        urgency: str,
        message: str
    ) -> List[str]:
        """Generate animation cues for Live2D"""
        cues = []
        
        # Add emotion-based cues
        cues.append(f"emotion_{emotion}")
        
        # Add gesture cues
        cues.append(f"gesture_{gesture}")
        
        # Add urgency-based cues
        if urgency == "emergency":
            cues.extend(["alert_posture", "urgent_expression"])
        elif urgency == "high":
            cues.append("attentive_posture")
        
        # Add agent-specific cues
        agent_cues = {
            "illness_monitor": ["medical_consultation_mode", "professional_stance"],
            "mental_health": ["supportive_mode", "gentle_expression"],
            "safety_guardian": ["alert_mode", "authoritative_stance"],
            "wellness_coach": ["energetic_mode", "encouraging_expression"]
        }
        
        cues.extend(agent_cues.get(agent_type, []))
        
        # Add message-specific cues
        if any(word in message.lower() for word in ["pain", "hurt", "ache", "痛"]):
            cues.append("concern_expression")
        
        if any(word in message.lower() for word in ["good", "better", "improving", "好"]):
            cues.append("positive_expression")
        
        return cues
    
    def _format_hk_facilities(self, hk_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format Hong Kong healthcare facility data for Live2D"""
        formatted_facilities = []
        
        for facility in hk_data:
            formatted_facility = {
                "id": facility.get("id", ""),
                "name_en": facility.get("name_en", ""),
                "name_zh": facility.get("name_zh", ""),
                "type": facility.get("type", "hospital"),
                "district": facility.get("district", ""),
                "address": facility.get("address", ""),
                "phone": facility.get("phone", ""),
                "waiting_time": facility.get("waiting_time", ""),
                "services": facility.get("services", []),
                "accessibility": facility.get("accessibility", {}),
                "live2d_display": {
                    "icon": self._get_facility_icon(facility.get("type", "hospital")),
                    "color": self._get_facility_color(facility.get("type", "hospital")),
                    "urgency_indicator": self._get_urgency_indicator(facility.get("waiting_time", "")),
                    "display_priority": self._calculate_display_priority(facility)
                }
            }
            formatted_facilities.append(formatted_facility)
        
        # Sort by display priority
        formatted_facilities.sort(key=lambda x: x["live2d_display"]["display_priority"], reverse=True)
        
        return formatted_facilities
    
    def _get_facility_icon(self, facility_type: str) -> str:
        """Get icon for facility type"""
        icon_map = {
            "hospital": "🏥",
            "clinic": "🏪",
            "emergency": "🚨",
            "pharmacy": "💊",
            "specialist": "👨‍⚕️"
        }
        return icon_map.get(facility_type, "🏥")
    
    def _get_facility_color(self, facility_type: str) -> str:
        """Get color theme for facility type"""
        color_map = {
            "hospital": "#e74c3c",    # Red
            "clinic": "#3498db",      # Blue
            "emergency": "#f39c12",   # Orange
            "pharmacy": "#2ecc71",    # Green
            "specialist": "#9b59b6"   # Purple
        }
        return color_map.get(facility_type, "#95a5a6")
    
    def _get_urgency_indicator(self, waiting_time: str) -> str:
        """Get urgency indicator based on waiting time"""
        if not waiting_time:
            return "unknown"
        
        if "< 30" in waiting_time or "短" in waiting_time:
            return "low"
        elif "30-60" in waiting_time or "中" in waiting_time:
            return "medium"
        else:
            return "high"
    
    def _calculate_display_priority(self, facility: Dict[str, Any]) -> float:
        """Calculate display priority for facility"""
        priority = 0.5
        
        # Emergency facilities get higher priority
        if facility.get("type") == "emergency":
            priority += 0.3
        
        # Shorter waiting times get higher priority
        waiting_time = facility.get("waiting_time", "")
        if "< 30" in waiting_time or "短" in waiting_time:
            priority += 0.2
        
        # Facilities with more services get higher priority
        services = facility.get("services", [])
        priority += min(len(services) * 0.05, 0.2)
        
        return priority
    
    def _get_voice_settings(self, agent_type: str, urgency: str) -> Dict[str, Any]:
        """Get voice settings for agent and urgency"""
        base_settings = self.voice_settings.get(agent_type, self.voice_settings["illness_monitor"])
        
        # Clone settings
        voice_settings = base_settings.copy()
        
        # Modify based on urgency
        if urgency == "emergency":
            voice_settings["pace"] = "fast"
            voice_settings["volume"] = "loud"
        elif urgency == "high":
            voice_settings["pace"] = "moderate_fast"
            voice_settings["volume"] = "normal_high"
        elif urgency == "low":
            voice_settings["pace"] = "slow"
            voice_settings["volume"] = "quiet"
        
        return voice_settings
    
    def _get_agent_display_name(self, agent_type: str, language: str) -> str:
        """Get agent display name in specified language"""
        names = {
            "illness_monitor": {"en": "Health Assistant", "zh-HK": "慧心助手"},
            "mental_health": {"en": "Little Star", "zh-HK": "小星星"},
            "safety_guardian": {"en": "Emergency Expert", "zh-HK": "緊急專家"},
            "wellness_coach": {"en": "Wellness Coach", "zh-HK": "健康教練"}
        }
        
        return names.get(agent_type, {}).get(language, "Healthcare Assistant")
    
    def _format_emergency_info(self, agent_response: Dict[str, Any], language: str) -> Dict[str, Any]:
        """Format emergency information for Live2D"""
        emergency_info = {
            "type": "emergency_alert",
            "severity": "high",
            "immediate_actions": [],
            "emergency_contacts": {
                "ambulance": "999",
                "police": "999",
                "fire": "999"
            },
            "nearest_facilities": [],
            "safety_instructions": []
        }
        
        # Add language-specific instructions
        if language == "zh-HK":
            emergency_info["message"] = "緊急情況，請立即致電999或前往最近的急症室"
            emergency_info["safety_instructions"] = [
                "保持冷靜",
                "致電999求助",
                "前往最近的醫院",
                "如有需要，通知家人"
            ]
        else:
            emergency_info["message"] = "Emergency situation detected. Please call 999 or go to the nearest emergency room immediately."
            emergency_info["safety_instructions"] = [
                "Stay calm",
                "Call 999 for help",
                "Go to nearest hospital",
                "Notify family if needed"
            ]
        
        return emergency_info
    
    def _create_fallback_response(self, session_id: str, language: str) -> Live2DAgentResponse:
        """Create fallback response when formatting fails"""
        message = (
            "我現在遇到一些技術問題，請稍後再試或聯繫我們的支援團隊。" if language == "zh-HK"
            else "I'm experiencing some technical difficulties. Please try again or contact our support team."
        )
        
        return Live2DAgentResponse(
            message_id=str(uuid.uuid4()),
            agent_type="wellness_coach",
            agent_name=self._get_agent_display_name("wellness_coach", language),
            message=message,
            emotion="professional_caring",
            gesture="reassuring_nod",
            urgency="low",
            language=language,
            confidence=0.5,
            session_id=session_id,
            avatar_state=Live2DAvatarState(
                agent_type="wellness_coach",
                emotion="professional_caring",
                gesture="reassuring_nod",
                voice_tone="professional_warm",
                energy_level=0.5,
                urgency_level="low",
                is_speaking=True,
                last_updated=datetime.now().isoformat()
            )
        )
    
    def format_system_status(self, status_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format system status for Live2D"""
        return {
            "type": Live2DMessageType.SYSTEM_STATUS,
            "timestamp": datetime.now().isoformat(),
            "system_health": status_data.get("status", "unknown"),
            "available_agents": status_data.get("available_agents", []),
            "features_enabled": status_data.get("features", []),
            "performance_metrics": {
                "response_time_ms": status_data.get("avg_response_time", 0),
                "success_rate": status_data.get("success_rate", 0.0),
                "active_connections": status_data.get("active_connections", 0)
            },
            "live2d_specific": {
                "avatar_states_synced": True,
                "emotion_system_active": True,
                "gesture_library_loaded": True,
                "voice_synthesis_ready": True
            }
        }
    
    def format_health_data_visualization(
        self,
        health_data: List[Dict[str, Any]],
        visualization_type: str = "dashboard"
    ) -> List[Live2DHealthData]:
        """Format health data for Live2D visualization"""
        formatted_data = []
        
        for data_item in health_data:
            formatted_item = Live2DHealthData(
                data_type=data_item.get("type", "general"),
                title=data_item.get("title", "Health Information"),
                description=data_item.get("description", ""),
                value=data_item.get("value", "N/A"),
                unit=data_item.get("unit", ""),
                urgency=data_item.get("urgency", "low"),
                visualization_type=self._determine_visualization_type(data_item),
                display_options=self._get_display_options(data_item, visualization_type)
            )
            formatted_data.append(formatted_item)
        
        return formatted_data
    
    def _determine_visualization_type(self, data_item: Dict[str, Any]) -> str:
        """Determine appropriate visualization type for data"""
        data_type = data_item.get("type", "").lower()
        value_type = type(data_item.get("value", ""))
        
        if data_type in ["location", "facility", "address"]:
            return "map"
        elif value_type in [int, float] and "trend" in data_item:
            return "chart"
        elif data_type in ["status", "alert", "warning"]:
            return "indicator"
        else:
            return "text"
    
    def _get_display_options(self, data_item: Dict[str, Any], visualization_type: str) -> Dict[str, Any]:
        """Get display options for visualization"""
        base_options = {
            "color_scheme": "healthcare_blue",
            "animation": "fade_in",
            "priority": 1,
            "size": "medium"
        }
        
        # Customize based on urgency
        urgency = data_item.get("urgency", "low")
        if urgency == "emergency":
            base_options.update({
                "color_scheme": "emergency_red",
                "animation": "pulse",
                "priority": 5,
                "size": "large"
            })
        elif urgency == "high":
            base_options.update({
                "color_scheme": "warning_orange",
                "animation": "highlight",
                "priority": 3
            })
        
        # Customize based on visualization type
        if visualization_type == "chart":
            base_options.update({
                "chart_type": "line",
                "show_legend": True,
                "interactive": True
            })
        elif visualization_type == "map":
            base_options.update({
                "zoom_level": 15,
                "show_markers": True,
                "center_on_user": True
            })
        
        return base_options


# ============================================================================
# LIVE2D CLIENT COMMUNICATION
# ============================================================================

class Live2DClient:
    """
    Client for communicating with Live2D frontend applications
    
    Handles:
    - HTTP and WebSocket communication
    - Message queuing and delivery
    - Connection management
    - Error handling and retry logic
    """
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or "http://localhost:3000"
        self.logger = get_logger(f"{__name__}.Live2DClient")
        self.message_formatter = Live2DMessageFormatter()
        
        # Connection state
        self.is_connected = False
        self.connection_retries = 0
        self.max_retries = 3
        
        # Message queue for failed sends
        self.message_queue: List[Dict[str, Any]] = []
        self.queue_max_size = 100
        
        # Performance tracking
        self.total_messages_sent = 0
        self.failed_sends = 0
        self.average_response_time = 0.0
    
    async def send_agent_response(
        self,
        agent_response: Dict[str, Any],
        session_id: str,
        language: str = "en",
        user_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send agent response to Live2D frontend
        
        Args:
            agent_response: Agent response data
            session_id: Session identifier
            language: Response language
            user_context: User context for personalization
            
        Returns:
            True if sent successfully
        """
        try:
            # Format response for Live2D
            formatted_response = self.message_formatter.format_agent_response(
                agent_response, session_id, language, user_context
            )
            
            # Convert to dict for sending
            message_data = asdict(formatted_response)
            
            # Send to frontend
            success = await self._send_message("/api/live2d/agent-response", message_data)
            
            if success:
                self.logger.debug(f"Sent agent response to Live2D: {formatted_response.message_id}")
            else:
                self.logger.error(f"Failed to send agent response: {formatted_response.message_id}")
                await self._queue_message(message_data)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error sending agent response to Live2D: {e}")
            return False
    
    async def send_system_status(self, status_data: Dict[str, Any]) -> bool:
        """Send system status update to Live2D frontend"""
        try:
            formatted_status = self.message_formatter.format_system_status(status_data)
            return await self._send_message("/api/live2d/system-status", formatted_status)
        except Exception as e:
            self.logger.error(f"Error sending system status: {e}")
            return False
    
    async def send_emergency_alert(
        self,
        alert_data: Dict[str, Any],
        session_id: str,
        language: str = "en"
    ) -> bool:
        """Send emergency alert to Live2D frontend"""
        try:
            emergency_message = {
                "type": Live2DMessageType.EMERGENCY_ALERT,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "severity": alert_data.get("severity", "high"),
                "message": alert_data.get("message", ""),
                "immediate_actions": alert_data.get("actions", []),
                "emergency_contacts": alert_data.get("contacts", {}),
                "language": language,
                "avatar_response": {
                    "emotion": "urgent",
                    "gesture": "emergency_stance",
                    "voice_tone": "urgent_authoritative",
                    "animation_cues": ["alert_posture", "urgent_expression", "attention_grabbing"]
                }
            }
            
            return await self._send_message("/api/live2d/emergency-alert", emergency_message)
        except Exception as e:
            self.logger.error(f"Error sending emergency alert: {e}")
            return False
    
    async def send_health_data_visualization(
        self,
        health_data: List[Dict[str, Any]],
        session_id: str,
        visualization_type: str = "dashboard"
    ) -> bool:
        """Send health data for Live2D visualization"""
        try:
            formatted_data = self.message_formatter.format_health_data_visualization(
                health_data, visualization_type
            )
            
            message = {
                "type": Live2DMessageType.HEALTH_DATA,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "visualization_type": visualization_type,
                "data": [asdict(item) for item in formatted_data]
            }
            
            return await self._send_message("/api/live2d/health-data", message)
        except Exception as e:
            self.logger.error(f"Error sending health data visualization: {e}")
            return False
    
    async def update_avatar_state(
        self,
        session_id: str,
        agent_type: str,
        emotion: str,
        gesture: str,
        additional_properties: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update Live2D avatar state"""
        try:
            avatar_state = Live2DAvatarState(
                agent_type=agent_type,
                emotion=emotion,
                gesture=gesture,
                voice_tone=self.message_formatter._get_voice_tone(agent_type, "medium"),
                energy_level=0.7,
                urgency_level="medium",
                is_speaking=False,
                last_updated=datetime.now().isoformat(),
                custom_properties=additional_properties or {}
            )
            
            message = {
                "type": Live2DMessageType.AVATAR_STATE,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "avatar_state": asdict(avatar_state)
            }
            
            return await self._send_message("/api/live2d/avatar-state", message)
        except Exception as e:
            self.logger.error(f"Error updating avatar state: {e}")
            return False
    
    async def _send_message(self, endpoint: str, message_data: Dict[str, Any]) -> bool:
        """Send message to Live2D frontend via HTTP"""
        start_time = datetime.now()
        
        try:
            url = f"{self.base_url}{endpoint}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=message_data,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Healthcare-AI-V2/2.0.0"
                    },
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    success = response.status == 200
                    
                    if success:
                        self.is_connected = True
                        self.connection_retries = 0
                        self.total_messages_sent += 1
                    else:
                        self.logger.warning(f"HTTP {response.status} from Live2D frontend: {endpoint}")
                        success = False
            
            # Update performance metrics
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            self.average_response_time = (
                (self.average_response_time * self.total_messages_sent + response_time) /
                (self.total_messages_sent + 1)
            )
            
            return success
            
        except aiohttp.ClientError as e:
            self.logger.error(f"Network error sending to Live2D: {e}")
            self.is_connected = False
            self.failed_sends += 1
            return False
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout sending to Live2D: {endpoint}")
            self.is_connected = False
            self.failed_sends += 1
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending to Live2D: {e}")
            self.failed_sends += 1
            return False
    
    async def _queue_message(self, message_data: Dict[str, Any]):
        """Queue message for retry when connection is restored"""
        if len(self.message_queue) >= self.queue_max_size:
            # Remove oldest message to make room
            self.message_queue.pop(0)
            self.logger.warning("Message queue full, removing oldest message")
        
        message_data["queued_at"] = datetime.now().isoformat()
        self.message_queue.append(message_data)
        self.logger.info(f"Queued message for retry. Queue size: {len(self.message_queue)}")
    
    async def process_message_queue(self) -> int:
        """Process queued messages when connection is restored"""
        if not self.message_queue:
            return 0
        
        processed = 0
        failed_messages = []
        
        for message in self.message_queue:
            # Determine endpoint based on message type
            message_type = message.get("type", "")
            endpoint = self._get_endpoint_for_message_type(message_type)
            
            if await self._send_message(endpoint, message):
                processed += 1
            else:
                failed_messages.append(message)
        
        # Keep failed messages in queue
        self.message_queue = failed_messages
        
        if processed > 0:
            self.logger.info(f"Processed {processed} queued messages. {len(self.message_queue)} remaining.")
        
        return processed
    
    def _get_endpoint_for_message_type(self, message_type: str) -> str:
        """Get appropriate endpoint for message type"""
        endpoint_map = {
            Live2DMessageType.AGENT_RESPONSE: "/api/live2d/agent-response",
            Live2DMessageType.SYSTEM_STATUS: "/api/live2d/system-status",
            Live2DMessageType.EMERGENCY_ALERT: "/api/live2d/emergency-alert",
            Live2DMessageType.HEALTH_DATA: "/api/live2d/health-data",
            Live2DMessageType.AVATAR_STATE: "/api/live2d/avatar-state"
        }
        return endpoint_map.get(message_type, "/api/live2d/message")
    
    async def test_connection(self) -> bool:
        """Test connection to Live2D frontend"""
        try:
            test_message = {
                "type": "connection_test",
                "timestamp": datetime.now().isoformat(),
                "message": "Healthcare AI V2 connection test"
            }
            
            return await self._send_message("/api/live2d/test", test_message)
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            "is_connected": self.is_connected,
            "base_url": self.base_url,
            "total_messages_sent": self.total_messages_sent,
            "failed_sends": self.failed_sends,
            "success_rate": (
                (self.total_messages_sent / (self.total_messages_sent + self.failed_sends))
                if (self.total_messages_sent + self.failed_sends) > 0 else 0.0
            ),
            "average_response_time_ms": self.average_response_time,
            "queued_messages": len(self.message_queue),
            "connection_retries": self.connection_retries
        }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def send_to_live2d_frontend(
    message_type: str,
    data: Dict[str, Any],
    session_id: str,
    client: Optional[Live2DClient] = None
) -> bool:
    """
    Utility function to send data to Live2D frontend
    
    Args:
        message_type: Type of message to send
        data: Message data
        session_id: Session identifier
        client: Live2D client instance (optional)
        
    Returns:
        True if sent successfully
    """
    if client is None:
        client = Live2DClient()
    
    try:
        if message_type == "agent_response":
            return await client.send_agent_response(data, session_id)
        elif message_type == "system_status":
            return await client.send_system_status(data)
        elif message_type == "emergency_alert":
            return await client.send_emergency_alert(data, session_id)
        elif message_type == "health_data":
            return await client.send_health_data_visualization(data.get("health_data", []), session_id)
        else:
            logger.warning(f"Unknown message type for Live2D: {message_type}")
            return False
    except Exception as e:
        logger.error(f"Error sending {message_type} to Live2D: {e}")
        return False


def create_live2d_message(
    message_type: str,
    content: Dict[str, Any],
    session_id: str,
    additional_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create standardized Live2D message format
    
    Args:
        message_type: Type of message
        content: Message content
        session_id: Session identifier
        additional_metadata: Additional metadata
        
    Returns:
        Formatted Live2D message
    """
    message = {
        "type": message_type,
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "message_id": str(uuid.uuid4()),
        "content": content
    }
    
    if additional_metadata:
        message.update(additional_metadata)
    
    return message


# ============================================================================
# GLOBAL CLIENT INSTANCE
# ============================================================================

# Global Live2D client instance
live2d_client = Live2DClient()
