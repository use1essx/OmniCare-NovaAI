"""
Unified Agent Bridge for Live2D Integration

Connects the UnifiedAgent (小星星) with the Live2D chat interface,
handling multimodal context, emotion mapping, and gesture selection.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ....agents.unified_agent import UnifiedAgent, UnifiedAgentResponse, create_unified_agent
from ....integrations.state_manager import RedisStateManager
from ....social_worker import get_alert_manager
from .questionnaire_integration import QuestionnaireIntegration

logger = logging.getLogger(__name__)


class UnifiedAgentBridge:
    """
    Bridge between UnifiedAgent and Live2D frontend.
    
    Handles:
    - Multimodal context aggregation (emotion, movement from video)
    - Unified agent processing
    - Live2D response formatting
    - Alert triggering for social workers
    """
    
    # Emotion to Live2D expression mapping
    EMOTION_MAPPING = {
        'neutral': 'normal',
        'happy': 'happy',
        'sad': 'sad',
        'concerned': 'worried',
        'supportive': 'gentle',
        'calm': 'relaxed',
        'energetic': 'excited',
        'warm': 'smile',
        'serious': 'focused',
        'empathetic': 'caring',
        'encouraging': 'cheerful',
        'protective': 'determined',
    }
    
    # Gesture to Live2D motion mapping
    GESTURE_MAPPING = {
        'idle': 'Idle',
        'talking': 'TapBody',
        'thinking': 'Shake',
        'nodding': 'FlickHead',
        'waving': 'Wave',
        'comforting': 'TapBody',
        'celebrating': 'FlickHead',
        'apologetic': 'Shake',
        'listening': 'Idle',
    }
    
    def __init__(self, ai_service=None):
        """
        Initialize the unified agent bridge.
        
        Args:
            ai_service: AI service for generating responses
        """
        self.ai_service = ai_service
        self.unified_agent: Optional[UnifiedAgent] = None
        self.state_manager: Optional[RedisStateManager] = None
        self.alert_manager = get_alert_manager()
        self.questionnaire_integration = QuestionnaireIntegration()
        self._initialized = False
    
    async def initialize(self, ai_service=None) -> None:
        """Initialize the bridge components"""
        if self._initialized:
            return
        
        try:
            if ai_service:
                self.ai_service = ai_service
            
            # Initialize state manager for multimodal context
            self.state_manager = RedisStateManager()
            
            # Create unified agent
            if self.ai_service:
                self.unified_agent = create_unified_agent(
                    ai_service=self.ai_service
                )
            
            self._initialized = True
            logger.info("UnifiedAgentBridge initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize UnifiedAgentBridge: {e}")
            raise
    
    async def process_chat_message(
        self,
        user_message: str,
        session_id: str,
        user_id: Optional[int] = None,
        language: str = "auto",
        emotion_data: Optional[Dict] = None,
        movement_data: Optional[Dict] = None,
        user_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Process a chat message through the unified agent.
        
        Args:
            user_message: User's message text
            session_id: Session identifier
            user_id: Optional user ID
            language: Preferred language
            emotion_data: Emotion detection from video
            movement_data: Movement analysis from video
            user_context: Additional user context
            
        Returns:
            Live2D formatted response
        """
        start_time = datetime.utcnow()
        
        try:
            # Check for active questionnaire assignments
            questionnaire_context = None
            if user_id:
                questionnaire_context = await self._check_questionnaire_assignment(user_id)
            
            # Build multimodal context
            multimodal_context = await self._build_multimodal_context(
                session_id, emotion_data, movement_data
            )
            
            # Add questionnaire context if available
            if questionnaire_context:
                multimodal_context['questionnaire'] = questionnaire_context
            
            # Process through unified agent
            if self.unified_agent:
                response = await self.unified_agent.process_message(
                    message=user_message,
                    session_id=session_id,
                    user_id=user_id,
                    multimodal_context=multimodal_context,
                    language=language
                )
            else:
                # Fallback if unified agent not initialized
                response = await self._get_fallback_response(user_message, language)
            
            # Inject questionnaire question if needed
            if questionnaire_context and questionnaire_context.get('next_question'):
                response = await self._inject_questionnaire_question(
                    response, questionnaire_context, user_id
                )
            
            # Handle crisis alerts
            if response.crisis_detected or response.alert_triggered:
                await self._handle_crisis_alert(
                    session_id=session_id,
                    user_id=user_id,
                    user_message=user_message,
                    response=response
                )
            
            # Format for Live2D
            live2d_response = self._format_live2d_response(response, multimodal_context)
            
            # Calculate processing time
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            live2d_response['processing_time_ms'] = processing_time
            
            logger.info(
                f"Processed message via UnifiedAgent: skills={response.active_skills}, "
                f"emotion={live2d_response['emotion']}, crisis={response.crisis_detected}, "
                f"questionnaire={'yes' if questionnaire_context else 'no'}"
            )
            
            return live2d_response
            
        except Exception as e:
            logger.error(f"Error processing chat message: {e}", exc_info=True)
            return self._get_error_response(user_message, language)
    
    async def _build_multimodal_context(
        self,
        session_id: str,
        emotion_data: Optional[Dict],
        movement_data: Optional[Dict]
    ) -> Dict[str, Any]:
        """Build multimodal context from video analysis"""
        context = {}
        
        # Get cached state if available
        if self.state_manager:
            cached_emotion = await self.state_manager.get_session_emotion(session_id)
            cached_movement = await self.state_manager.get_session_movement(session_id)
            
            # Use provided data or fall back to cached
            if emotion_data:
                context['emotion'] = emotion_data
                await self.state_manager.set_session_emotion(session_id, emotion_data)
            elif cached_emotion:
                context['emotion'] = cached_emotion
            
            if movement_data:
                context['movement'] = movement_data
                await self.state_manager.set_session_movement(session_id, movement_data)
            elif cached_movement:
                context['movement'] = cached_movement
        else:
            if emotion_data:
                context['emotion'] = emotion_data
            if movement_data:
                context['movement'] = movement_data
        
        return context if context else None
    
    async def _handle_crisis_alert(
        self,
        session_id: str,
        user_id: Optional[int],
        user_message: str,
        response: UnifiedAgentResponse
    ) -> None:
        """Handle crisis situations by creating alerts"""
        try:
            await self.alert_manager.create_alert(
                session_id=session_id,
                alert_type='safety_flag' if response.crisis_detected else 'risk_detected',
                message=f"Crisis detected in conversation: {user_message[:100]}...",
                severity=5 if response.crisis_detected else 4,
                child_id=user_id,
                detected_by='unified_agent',
                skill_involved='safety_crisis',
                trigger_reason='Crisis keywords or severe distress detected',
                recommended_action='Immediate contact required. Review conversation history.',
                force_create=True  # Bypass debouncing for crisis
            )
            
            logger.warning(f"Crisis alert created for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to create crisis alert: {e}")
    
    def _format_live2d_response(
        self,
        response: UnifiedAgentResponse,
        multimodal_context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Format unified agent response for Live2D frontend"""
        
        # Map emotion to Live2D expression
        live2d_emotion = self.EMOTION_MAPPING.get(
            response.emotion, 'normal'
        )
        
        # Map gesture to Live2D motion
        live2d_gesture = self.GESTURE_MAPPING.get(
            response.gesture, 'Idle'
        )
        
        # Determine agent name (always 小星星 for unified agent)
        agent_name = "小星星"
        agent_type = "unified"
        
        # Get primary skill for context
        primary_skill = response.active_skills[0] if response.active_skills else 'general'
        
        # Build voice settings based on emotion
        voice_settings = self._get_voice_settings(response.emotion, primary_skill)
        
        # Build animation cues
        animation_cues = self._get_animation_cues(
            response.emotion,
            response.gesture,
            response.crisis_detected
        )
        
        return {
            'message': response.message,
            'agent_type': agent_type,
            'agent_name': agent_name,
            'emotion': live2d_emotion,
            'gesture': live2d_gesture,
            'urgency': 'high' if response.crisis_detected else 'normal',
            'language': 'zh-HK' if self._is_chinese(response.message) else 'en',
            'confidence': 0.9,
            'processing_time_ms': response.processing_time_ms,
            'hk_facilities': [],  # Can be populated from RAG
            'avatar_state': {
                'expression': live2d_emotion,
                'motion': live2d_gesture,
                'eye_state': 'open',
                'mouth_state': 'talking' if len(response.message) > 0 else 'closed'
            },
            'voice_settings': voice_settings,
            'animation_cues': animation_cues,
            'session_id': response.session_id,
            'timestamp': datetime.utcnow().isoformat(),
            'active_skills': response.active_skills,
            'citations': response.citations,
            'crisis_detected': response.crisis_detected,
            'function_calls': [fc.get('function', '') for fc in response.function_calls]
        }
    
    def _get_voice_settings(self, emotion: str, skill: str) -> Dict[str, Any]:
        """Get TTS voice settings based on emotion and skill"""
        
        # Base settings
        settings = {
            'pitch': 1.0,
            'speed': 1.0,
            'volume': 1.0,
            'style': 'friendly'
        }
        
        # Adjust based on emotion
        if emotion in ['sad', 'concerned', 'empathetic']:
            settings['pitch'] = 0.95
            settings['speed'] = 0.9
            settings['style'] = 'gentle'
        elif emotion in ['happy', 'energetic', 'encouraging']:
            settings['pitch'] = 1.05
            settings['speed'] = 1.1
            settings['style'] = 'cheerful'
        elif emotion in ['serious', 'protective']:
            settings['pitch'] = 0.9
            settings['speed'] = 0.85
            settings['style'] = 'calm'
        
        # Adjust for safety skill
        if skill == 'safety_crisis':
            settings['speed'] = 0.85
            settings['style'] = 'calm_supportive'
        
        return settings
    
    def _get_animation_cues(
        self,
        emotion: str,
        gesture: str,
        crisis: bool
    ) -> List[str]:
        """Get animation cues for Live2D"""
        cues = []
        
        # Expression cue
        cues.append(f"expression:{emotion}")
        
        # Gesture cue
        cues.append(f"motion:{gesture}")
        
        # Special cues
        if crisis:
            cues.append("priority:high")
            cues.append("attention:focus")
        
        if emotion in ['happy', 'encouraging']:
            cues.append("effect:sparkle")
        elif emotion in ['sad', 'concerned']:
            cues.append("effect:subtle")
        
        return cues
    
    def _is_chinese(self, text: str) -> bool:
        """Check if text is primarily Chinese"""
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        return chinese_chars > len(text) * 0.3
    
    async def _get_fallback_response(
        self,
        user_message: str,
        language: str
    ) -> UnifiedAgentResponse:
        """Get fallback response when unified agent not available"""
        if language == "zh-HK" or self._is_chinese(user_message):
            message = "你好！我係小星星。我暫時遇到少少問題，請稍等一陣再試。"
        else:
            message = "Hello! I'm Little Star. I'm having a small issue right now. Please try again in a moment."
        
        return UnifiedAgentResponse(
            message=message,
            session_id="fallback",
            emotion="apologetic",
            gesture="apologetic",
            active_skills=["general"]
        )
    
    def _get_error_response(self, user_message: str, language: str) -> Dict[str, Any]:
        """Get error response in Live2D format"""
        if language == "zh-HK" or self._is_chinese(user_message):
            message = "對不起，我遇到了一些問題。如果你有緊急情況，請致電999或撒瑪利亞熱線 2389 2222。"
        else:
            message = "I'm sorry, I encountered an issue. If you have an emergency, please call 999 or Samaritans at 2389 2222."
        
        return {
            'message': message,
            'agent_type': 'unified',
            'agent_name': '小星星',
            'emotion': 'concerned',
            'gesture': 'apologetic',
            'urgency': 'normal',
            'language': language,
            'confidence': 1.0,
            'processing_time_ms': 0,
            'hk_facilities': [],
            'avatar_state': {'expression': 'worried', 'motion': 'Shake'},
            'voice_settings': {'pitch': 0.95, 'speed': 0.9, 'style': 'gentle'},
            'animation_cues': ['expression:worried', 'motion:apologetic'],
            'session_id': 'error',
            'timestamp': datetime.utcnow().isoformat(),
            'active_skills': [],
            'citations': [],
            'crisis_detected': False,
            'function_calls': []
        }
    
    async def update_emotion_state(
        self,
        session_id: str,
        emotion: str,
        intensity: int
    ) -> None:
        """Update emotion state from video analysis"""
        if self.state_manager:
            await self.state_manager.set_session_emotion(session_id, {
                'emotion': emotion,
                'intensity': intensity,
                'timestamp': datetime.utcnow().isoformat()
            })
    
    async def update_movement_state(
        self,
        session_id: str,
        energy_level: str,
        posture: str
    ) -> None:
        """Update movement state from video analysis"""
        if self.state_manager:
            await self.state_manager.set_session_movement(session_id, {
                'energy_level': energy_level,
                'posture': posture,
                'timestamp': datetime.utcnow().isoformat()
            })
    
    async def _check_questionnaire_assignment(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Check if user has active questionnaire assignment and get next question
        
        Returns:
            Dictionary with assignment and question info, or None
        """
        try:
            # Check for active assignment
            assignment = await self.questionnaire_integration.check_active_assignment(user_id)
            
            if not assignment:
                return None
            
            # Get next unanswered question
            next_question = await self.questionnaire_integration.get_next_question(
                assignment['assignment_id'],
                assignment['questionnaire_id']
            )
            
            if next_question:
                logger.info(
                    f"📝 Found questionnaire question for user {user_id}: "
                    f"assignment={assignment['assignment_id']}, question={next_question['question_id']}"
                )
                return {
                    'assignment': assignment,
                    'next_question': next_question
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking questionnaire assignment: {e}")
            return None
    
    async def _inject_questionnaire_question(
        self,
        response: UnifiedAgentResponse,
        questionnaire_context: Dict[str, Any],
        user_id: int
    ) -> UnifiedAgentResponse:
        """
        Inject questionnaire question into AI response
        
        Args:
            response: Original AI response
            questionnaire_context: Questionnaire context with next question
            user_id: User ID
            
        Returns:
            Modified response with questionnaire question
        """
        try:
            question_data = questionnaire_context['next_question']
            assignment_data = questionnaire_context['assignment']
            
            # Get question text
            question_text = question_data.get('question_text', '')
            
            # Calculate progress
            total = assignment_data.get('total_questions', 0)
            answered = assignment_data.get('questions_answered', 0)
            progress = f"({answered + 1}/{total})" if total > 0 else ""
            
            # Inject question naturally into response
            if response.message:
                # Add question after the response
                response.message = (
                    f"{response.message}\n\n"
                    f"By the way, I'd like to ask you something {progress}: {question_text}"
                )
            else:
                # Use question as the main message
                response.message = f"I'd like to ask you something {progress}: {question_text}"
            
            # Store question context in response metadata
            if not hasattr(response, 'metadata'):
                response.metadata = {}
            
            response.metadata['questionnaire'] = {
                'assignment_id': assignment_data['assignment_id'],
                'question_id': question_data['question_id'],
                'question_text': question_text,
                'awaiting_answer': True
            }
            
            logger.info(f"✅ Injected questionnaire question into response for user {user_id}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error injecting questionnaire question: {e}")
            return response
    
    async def get_session_context(self, session_id: str) -> Dict[str, Any]:
        """Get full session context including multimodal state"""
        if not self.state_manager:
            return {}
        
        return await self.state_manager.get_multimodal_context(session_id)
    
    async def close(self) -> None:
        """Close connections"""
        if self.state_manager:
            await self.state_manager.close()


# Singleton instance
_bridge_instance: Optional[UnifiedAgentBridge] = None


def get_unified_agent_bridge() -> UnifiedAgentBridge:
    """Get or create unified agent bridge singleton"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = UnifiedAgentBridge()
    return _bridge_instance


async def initialize_unified_agent_bridge(ai_service) -> UnifiedAgentBridge:
    """Initialize the unified agent bridge with AI service"""
    bridge = get_unified_agent_bridge()
    await bridge.initialize(ai_service)
    return bridge

