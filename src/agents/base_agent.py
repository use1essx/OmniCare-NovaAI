"""
Base Agent Class for Healthcare AI V2
=====================================

Abstract base class that defines the interface and core functionality
for all healthcare AI agents in the system.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime
from decimal import Decimal

from ..ai.ai_service import HealthcareAIService, ServiceAIRequest as AIRequest, ServiceAIResponse as AIResponse
from ..ai.model_manager import UrgencyLevel, TaskComplexity


class AgentCapability(Enum):
    """Agent capabilities for routing and selection."""
    ILLNESS_MONITORING = "illness_monitoring"
    MENTAL_HEALTH_SUPPORT = "mental_health_support"
    EMERGENCY_RESPONSE = "emergency_response"
    WELLNESS_COACHING = "wellness_coaching"
    MEDICATION_GUIDANCE = "medication_guidance"
    CHRONIC_DISEASE_MANAGEMENT = "chronic_disease_management"
    CRISIS_INTERVENTION = "crisis_intervention"
    EDUCATIONAL_SUPPORT = "educational_support"


class AgentPersonality(Enum):
    """Agent personality types for cultural and age adaptation."""
    CARING_ELDER_COMPANION = "caring_elder_companion"  # 慧心助手
    VTUBER_FRIEND = "vtuber_friend"  # 小星星
    PROFESSIONAL_RESPONDER = "professional_responder"  # Safety Guardian
    WELLNESS_MOTIVATOR = "wellness_motivator"  # Wellness Coach


@dataclass
class AgentResponse:
    """Structured response from an agent."""
    content: str
    confidence: float  # 0.0 - 1.0
    urgency_level: UrgencyLevel
    requires_followup: bool
    suggested_actions: List[str]
    professional_alert_needed: bool
    alert_details: Optional[Dict[str, Any]] = None
    conversation_context: Optional[Dict[str, Any]] = None


@dataclass
class AgentContext:
    """Context information for agent processing."""
    user_id: str
    session_id: str
    conversation_history: List[Dict[str, Any]]
    user_profile: Dict[str, Any]
    cultural_context: Dict[str, Any]
    language_preference: str  # "en", "zh", "auto"
    timestamp: datetime


class BaseAgent(ABC):
    """
    Abstract base class for all healthcare AI agents.
    
    Provides standard interface and core functionality for:
    - Agent capability assessment
    - Response generation with confidence scoring
    - Context management
    - Emergency detection
    - Professional alert generation
    """
    
    def __init__(
        self,
        agent_id: str,
        ai_service: HealthcareAIService,
        capabilities: List[AgentCapability],
        personality: AgentPersonality,
        primary_language: str = "zh",
    ):
        """
        Initialize base agent.
        
        Args:
            agent_id: Unique identifier for this agent
            ai_service: AI service for model interactions
            capabilities: List of agent capabilities
            personality: Agent personality type
            primary_language: Primary language for responses
        """
        self.agent_id = agent_id
        self.ai_service = ai_service
        self.capabilities = capabilities
        self.personality = personality
        self.primary_language = primary_language
        self.logger = logging.getLogger(f"agent.{agent_id}")
        
        # Agent-specific configuration
        self._confidence_threshold = 0.7
        self._emergency_keywords = []
        self._cultural_adaptations = {}
        
    @abstractmethod
    def can_handle(self, user_input: str, context: AgentContext) -> Tuple[bool, float]:
        """
        Determine if this agent can handle the user input.
        
        Args:
            user_input: User's message/question
            context: Conversation context
            
        Returns:
            Tuple of (can_handle: bool, confidence: float)
        """
        pass
    
    @abstractmethod
    async def generate_response(
        self, 
        user_input: str, 
        context: AgentContext
    ) -> AgentResponse:
        """
        Generate a response to user input.
        
        Args:
            user_input: User's message/question
            context: Conversation context
            
        Returns:
            AgentResponse with content and metadata
        """
        pass
    
    @abstractmethod
    def get_system_prompt(self, context: AgentContext) -> str:
        """
        Get the system prompt for this agent.
        
        Args:
            context: Conversation context for personalization
            
        Returns:
            System prompt string
        """
        pass
    
    # Core functionality methods
    
    def detect_urgency(self, user_input: str, context: AgentContext) -> UrgencyLevel:
        """
        Detect urgency level of user input.
        
        Args:
            user_input: User's message
            context: Conversation context
            
        Returns:
            Detected urgency level
        """
        user_input_lower = user_input.lower()
        
        # Emergency keywords
        emergency_keywords = [
            "emergency", "緊急", "urgent", "急", "help", "救命",
            "chest pain", "胸痛", "can't breathe", "唔可以呼吸",
            "suicide", "自殺", "kill myself", "hurt myself", "傷害自己",
            "overdose", "服藥過量", "unconscious", "失去知覺"
        ]
        
        if any(keyword in user_input_lower for keyword in emergency_keywords):
            return UrgencyLevel.CRITICAL
        
        # High urgency indicators
        high_urgency_keywords = [
            "severe", "嚴重", "intense", "劇烈", "very worried", "好擔心",
            "getting worse", "惡化", "can't sleep", "瞓唔到",
            "haven't eaten", "冇食野", "can't function", "做唔到野"
        ]
        
        if any(keyword in user_input_lower for keyword in high_urgency_keywords):
            return UrgencyLevel.HIGH
        
        # Medium urgency indicators
        medium_urgency_keywords = [
            "concerned", "關心", "worried", "擔心", "uncomfortable", "唔舒服",
            "pain", "痛", "tired", "攰", "stressed", "壓力"
        ]
        
        if any(keyword in user_input_lower for keyword in medium_urgency_keywords):
            return UrgencyLevel.MEDIUM
        
        return UrgencyLevel.LOW
    
    def detect_complexity(self, user_input: str, context: AgentContext) -> TaskComplexity:
        """
        Detect task complexity based on user input and context.
        
        Args:
            user_input: User's message
            context: Conversation context
            
        Returns:
            Detected task complexity
        """
        # Multiple symptoms or conditions
        if len(user_input.split()) > 50:
            return TaskComplexity.COMPLEX
        
        # Multiple questions or concerns
        question_count = user_input.count("?") + user_input.count("？")
        if question_count > 2:
            return TaskComplexity.COMPLEX
        
        # Complex medical terminology
        medical_terms = [
            "diagnosis", "診斷", "medication", "藥物", "treatment", "治療",
            "chronic", "慢性", "syndrome", "症候群", "disorder", "失調"
        ]
        
        if sum(1 for term in medical_terms if term in user_input.lower()) > 2:
            return TaskComplexity.MODERATE
        
        return TaskComplexity.SIMPLE
    
    def should_alert_professional(
        self, 
        user_input: str, 
        context: AgentContext,
        response: str
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Determine if professional alert is needed.
        
        Args:
            user_input: User's message
            context: Conversation context
            response: Generated response
            
        Returns:
            Tuple of (needs_alert: bool, alert_details: Optional[Dict])
        """
        urgency = self.detect_urgency(user_input, context)
        
        if urgency == UrgencyLevel.CRITICAL:
            return True, {
                "alert_type": "emergency",
                "urgency": "critical",
                "reason": "Emergency keywords detected",
                "user_input_summary": user_input[:200],
                "recommended_action": "Immediate professional intervention",
                "timestamp": datetime.now().isoformat()
            }
        
        # Agent-specific alert conditions (to be overridden by subclasses)
        return False, None
    
    def adapt_to_culture(self, response: str, context: AgentContext) -> str:
        """
        Adapt response to cultural context.
        
        Args:
            response: Generated response
            context: Conversation context
            
        Returns:
            Culturally adapted response
        """
        cultural_context = context.cultural_context
        
        # Hong Kong specific adaptations
        if cultural_context.get("region") == "hong_kong":
            # Add appropriate honorifics for elderly
            if context.user_profile.get("age_group") == "elderly":
                # Use more respectful language
                response = response.replace("你", "您")
            
            # Add local emergency information
            if "emergency" in response.lower():
                response += "\n\n🚨 香港緊急電話：999"
        
        return response
    
    def _build_ai_request(
        self, 
        user_input: str, 
        context: AgentContext,
        system_prompt: str
    ) -> AIRequest:
        """
        Build AI request with agent-specific configuration.
        
        Args:
            user_input: User's message
            context: Conversation context
            system_prompt: System prompt for the agent
            
        Returns:
            Configured AI request
        """
        urgency = self.detect_urgency(user_input, context)
        self.detect_complexity(user_input, context)
        
        # Inject language instruction into system prompt
        system_prompt = self._inject_language_instruction(system_prompt, user_input, context)

        # Inject knowledge base context if available (RAG)
        knowledge_context = getattr(context, "knowledge_context", None)
        if knowledge_context and knowledge_context.get("results"):
            excerpts = []
            for idx, item in enumerate(knowledge_context.get("results", [])[:3], start=1):
                meta = item.get("metadata") or {}
                title = meta.get("title") or "Untitled document"
                location = ""
                if meta.get("page") is not None:
                    location = f" (p.{meta.get('page')})"
                elif meta.get("timestamp_start") is not None:
                    location = f" (t+{int(meta.get('timestamp_start'))}s)"
                snippet = item.get("content", "")
                if len(snippet) > 500:
                    snippet = snippet[:500] + "..."
                excerpts.append(f"[{idx}] {title}{location}\n{snippet}")
            if excerpts:
                system_prompt = (
                    f"{system_prompt}\n\n"
                    "Use the following knowledge base excerpts if relevant. "
                    "If they are not relevant, ignore them.\n\n"
                    + "\n\n".join(excerpts)
                )
        if knowledge_context:
            guidance = [
                "Do not mention document IDs, retrieval, or RAG.",
                "When you answer with knowledge base info, first state which document title you used.",
                "Refer to sources by document title only."
            ]
            other_titles = knowledge_context.get("other_titles") or []
            if other_titles:
                guidance.append(
                    "If multiple documents could match, answer using the most relevant one and ask a short follow-up about whether the user meant another document."
                )
                guidance.append(
                    "Other possible titles: " + ", ".join(str(t) for t in other_titles[:3])
                )
            if knowledge_context.get("no_results") or not knowledge_context.get("results"):
                guidance.append(
                    "If no relevant excerpts were found, ask a concise clarification question instead of guessing."
                )
            system_prompt = f"{system_prompt}\n\n" + " ".join(guidance)
        
        # Ensure no sensitive data (like API keys) gets logged in context
        safe_context = {
            "history": context.conversation_history[-5:],  # Last 5 exchanges
            "user_profile": {k: v for k, v in context.user_profile.items() if not k.lower().endswith('_key')},
            "cultural_context": context.cultural_context
        }
        if knowledge_context:
            safe_context["knowledge_context"] = {
                "query": knowledge_context.get("query"),
                "total_results": knowledge_context.get("total_results", 0)
            }
        
        return AIRequest(
            user_input=user_input,
            system_prompt=system_prompt,
            agent_type=self.agent_id,
            conversation_context=safe_context,
            urgency_level=urgency.value if hasattr(urgency, 'value') else str(urgency)
        )
    
    def _inject_language_instruction(
        self,
        system_prompt: str,
        user_input: str,
        context: AgentContext
    ) -> str:
        """
        Inject language instruction into system prompt based on user preference.
        
        Priority:
        1. Context language_preference (from AgentContext)
        2. User profile language_preference
        3. Auto-detect from message
        
        Args:
            system_prompt: Original system prompt
            user_input: User's message
            context: Conversation context
            
        Returns:
            System prompt with language instruction
        """
        try:
            from src.core.language_manager import get_language_manager
            
            manager = get_language_manager()
            
            # Get language preference from context (highest priority)
            context_language = getattr(context, 'language_preference', None)
            
            # Get user profile language preference
            user_language = context.user_profile.get("language_preference") if context.user_profile else None
            
            # Resolve the language to use
            language = manager.resolve_language(
                request_language=context_language,
                user_preference=user_language,
                message=user_input
            )
            
            self.logger.info(f"🌐 Language resolved: {language} (context={context_language}, user_pref={user_language})")
            
            # Inject language instruction
            return manager.inject_language_instruction(system_prompt, language)
            
        except Exception as e:
            self.logger.warning(f"Failed to inject language instruction: {e}")
            return system_prompt
    
    async def _generate_ai_response(
        self, 
        ai_request: AIRequest,
        language: str = "en"
    ) -> AIResponse:
        """
        Generate AI response using the AI service.
        
        Args:
            ai_request: Configured AI request
            language: Language for fallback response
            
        Returns:
            AI response
        """
        try:
            return await self.ai_service.process_request(ai_request)
        except Exception as e:
            self.logger.error(f"AI service error: {e}")
            # Return language-aware friendly fallback response (not error message)
            if language == "zh-HK":
                fallback_content = "🌟 歡迎使用 OmniCare！我係你嘅健康助手，有咩可以幫到你？（注意：AI 系統暫時使用備用模式）"
            else:
                fallback_content = "🌟 Welcome to OmniCare! I'm here to help with your health questions. How can I assist you today? (Note: AI system is temporarily using fallback mode)"
            
            return AIResponse(
                content=fallback_content,
                model_used="fallback",
                model_tier="fallback",
                agent_type=self.agent_id,
                processing_time_ms=0,
                cost=Decimal('0.0'),
                usage_stats={"total_tokens": 0},
                success=False,
                error_message=str(e),
                confidence_score=0.5
            )
    
    def get_activation_message(self, context: AgentContext) -> str:
        """
        Get agent activation message.
        
        Args:
            context: Conversation context
            
        Returns:
            Activation message for this agent
        """
        # Default activation message (to be overridden by subclasses)
        return f"🤖 {self.agent_id} activated to assist you."
