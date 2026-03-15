"""
Main AI service for Healthcare AI V2
Integrates Nova Bedrock client, model manager, and cost optimizer
"""

from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass

from src.ai.unified_ai_client import AIRequest, AIResponse, select_model_tier
from src.ai.providers.nova_bedrock_client import NovaBedrockClient, get_nova_client
from src.ai.model_manager import (
    ModelManager, ModelSelectionCriteria, TaskComplexity, UrgencyLevel, get_model_manager
)
from src.ai.cost_optimizer import CostOptimizer, get_cost_optimizer
from src.core.logging import get_logger
from src.core.config import settings


logger = get_logger(__name__)


@dataclass
class ServiceAIRequest:
    """
    Service-level AI request structure (wrapper for unified AIRequest)
    Provides backward compatibility with existing service layer
    """
    user_input: str
    system_prompt: str
    agent_type: str
    content_type: Optional[str] = None
    urgency_level: str = "medium"
    user_id: Optional[int] = None
    conversation_context: Optional[Dict] = None
    cost_constraints: Optional[Dict] = None
    performance_requirements: Optional[Dict] = None
    
    def to_unified_request(self, task_type: Optional[str] = None) -> AIRequest:
        """Convert to unified AIRequest format"""
        return AIRequest(
            system_prompt=self.system_prompt,
            user_prompt=self.user_input,
            task_type=task_type or self.agent_type,
            user_id=self.user_id,
            session_id=self.conversation_context.get('session_id') if self.conversation_context else None
        )


@dataclass
class ServiceAIResponse:
    """
    Service-level AI response structure (wrapper for unified AIResponse)
    Provides backward compatibility with existing service layer
    """
    content: str
    model_used: str
    model_tier: str
    agent_type: str
    processing_time_ms: int
    cost: Decimal
    usage_stats: Dict[str, Any]
    success: bool = True
    error_message: Optional[str] = None
    confidence_score: Optional[float] = None
    
    @classmethod
    def from_unified_response(
        cls, 
        unified_response: AIResponse, 
        agent_type: str,
        confidence_score: Optional[float] = None
    ) -> 'ServiceAIResponse':
        """Create from unified AIResponse"""
        return cls(
            content=unified_response.content,
            model_used=unified_response.model,
            model_tier=unified_response.model_tier,
            agent_type=agent_type,
            processing_time_ms=unified_response.processing_time_ms,
            cost=unified_response.cost,
            usage_stats=unified_response.usage,
            success=unified_response.success,
            error_message=unified_response.error_message,
            confidence_score=confidence_score
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "content": self.content,
            "model_used": self.model_used,
            "model_tier": self.model_tier,
            "agent_type": self.agent_type,
            "processing_time_ms": self.processing_time_ms,
            "cost": float(self.cost),
            "usage_stats": self.usage_stats,
            "success": self.success,
            "error_message": self.error_message,
            "confidence_score": self.confidence_score
        }


class HealthcareAIService:
    """
    Main AI service that orchestrates all AI operations for Healthcare AI V2
    Provides unified interface for agent interactions with intelligent model selection and cost optimization
    """
    
    def __init__(self):
        self.nova_client: Optional[NovaBedrockClient] = None
        self.model_manager: Optional[ModelManager] = None
        self.cost_optimizer: Optional[CostOptimizer] = None
        self._initialized = False
        
    async def initialize(self):
        """Initialize all AI service components"""
        if self._initialized:
            return
            
        try:
            # Initialize Nova Bedrock client
            self.nova_client = get_nova_client()
            self.model_manager = get_model_manager()
            self.cost_optimizer = get_cost_optimizer()
            
            self._initialized = True
            logger.info("Healthcare AI Service initialized successfully with Nova Bedrock")
            
        except Exception as e:
            logger.error(f"Failed to initialize Healthcare AI Service: {e}")
            raise
            
    async def process_request(self, request: ServiceAIRequest) -> ServiceAIResponse:
        """
        Process AI request with intelligent model selection and cost optimization
        
        Args:
            request: ServiceAIRequest object containing user input and configuration
            
        Returns:
            ServiceAIResponse object with generated content and metadata
        """
        if not self._initialized:
            await self.initialize()
            
        start_time = datetime.utcnow()
        
        try:
            # Analyze task complexity and urgency
            task_complexity = self.model_manager.analyze_task_complexity(
                user_input=request.user_input,
                agent_type=request.agent_type,
                conversation_context=request.conversation_context
            )
            
            urgency_level = self._parse_urgency_level(request.urgency_level)
            
            # Build session-scoped history for prompt injection (privacy-friendly)
            history_text = ""
            if request.conversation_context:
                history_items = request.conversation_context.get("history") or []
                if history_items:
                    formatted = []
                    for h in history_items[-5:]:
                        role = h.get("role", "user").capitalize()
                        content = h.get("content", "")
                        formatted.append(f"{role}: {content}")
                    history_text = "\n".join(formatted)

            # Inject history into user prompt (session-only, not persisted long-term)
            user_prompt = request.user_input
            system_prompt = request.system_prompt
            if history_text:
                system_prompt = (
                    f"{system_prompt}\nUse the provided session history to keep context. "
                    "Do not claim you cannot recall prior messages in this session."
                )
                user_prompt = (
                    "Session conversation history (not stored permanently):\n"
                    f"{history_text}\n\nUser: {request.user_input}"
                )

            # MIGRATION: Create unified AI request
            task_type = self._map_agent_to_task_type(request.agent_type, urgency_level)
            unified_request = AIRequest(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                task_type=task_type,
                user_id=request.user_id,
                session_id=request.conversation_context.get('session_id') if request.conversation_context else None
            )
            
            # MIGRATION: Make request through Nova client
            unified_response = await self.nova_client.make_request(request=unified_request)
            
            # Record usage for cost optimization
            self.cost_optimizer.record_usage(
                model_tier=unified_response.model_tier,
                model_name=unified_response.model,
                agent_type=request.agent_type,
                content_type=request.content_type or "general",
                urgency_level=request.urgency_level,
                prompt_tokens=unified_response.usage.get("prompt_tokens", 0),
                completion_tokens=unified_response.usage.get("completion_tokens", 0),
                cost=unified_response.cost,
                processing_time_ms=unified_response.processing_time_ms,
                success=unified_response.success,
                user_id=request.user_id,
                error_message=unified_response.error_message
            )
            
            # Calculate total processing time
            total_processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Calculate confidence score based on model performance
            confidence_score = self._calculate_confidence_score(
                unified_response, task_complexity, urgency_level
            )
            
            # Convert to service response format
            response = ServiceAIResponse.from_unified_response(
                unified_response=unified_response,
                agent_type=request.agent_type,
                confidence_score=confidence_score
            )
            # Update processing time to include overhead
            response.processing_time_ms = total_processing_time
            
            logger.info(
                "AI request processed successfully",
                extra={
                    "agent_type": request.agent_type,
                    "model_used": response.model_used,
                    "cost": float(response.cost),
                    "processing_time_ms": response.processing_time_ms,
                    "user_id": request.user_id,
                    "task_complexity": task_complexity.value,
                    "urgency_level": urgency_level.value
                }
            )
            
            return response
            
        except Exception as e:
            total_processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            logger.error(
                f"AI request failed: {e}",
                extra={
                    "agent_type": request.agent_type,
                    "user_id": request.user_id,
                    "error": str(e)
                }
            )
            
            return ServiceAIResponse(
                content="",
                model_used="unknown",
                model_tier="unknown",
                agent_type=request.agent_type,
                processing_time_ms=total_processing_time,
                cost=Decimal('0.0'),
                usage_stats={},
                success=False,
                error_message=str(e)
            )

    async def chat_completion(
        self,
        messages: list,
        max_tokens: int = 300,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Lightweight chat completion wrapper for internal utilities (summary/translation).
        Uses unified Nova client for consistent routing.
        """
        if not self._initialized:
            await self.initialize()
            
        # Extract system prompt and build conversation history
        system_prompt = ""
        conversation_history = []
        
        for msg in messages or []:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                system_prompt = content
            elif role in ["user", "assistant"]:
                conversation_history.append(f"{role.capitalize()}: {content}")
        
        # Build user prompt with conversation history
        if conversation_history:
            user_prompt = "\n\n".join(conversation_history)
        else:
            user_prompt = str(messages[-1].get("content", "")).strip() if messages else ""
        
        if not system_prompt:
            system_prompt = "You are a helpful assistant."

        # Make request through Nova client
        unified_response = await self.nova_client.make_request(
            model_tier="lite",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            task_type="chat"
        )
        
        return {
            "content": unified_response.content,
            "model_used": unified_response.model,
            "success": unified_response.success,
            "error_message": unified_response.error_message,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
    
    def _map_agent_to_task_type(self, agent_type: str, urgency_level: UrgencyLevel) -> str:
        """
        Map agent type and urgency to task type for model selection
        
        Args:
            agent_type: Type of agent (e.g., 'wellness_coach', 'huixin_agent')
            urgency_level: Urgency level of the request
            
        Returns:
            Task type string for model selection
        """
        # Emergency/critical urgency always maps to emergency task type
        if urgency_level in [UrgencyLevel.EMERGENCY, UrgencyLevel.CRITICAL]:
            return "emergency"
        
        # Map agent types to task types
        agent_task_mapping = {
            "wellness_coach": "chat",
            "huixin_agent": "chat",
            "xiaoxingxing_agent": "chat",
            "questionnaire_agent": "questionnaire",
            "video_analysis": "video_analysis",
            "report_generator": "report_generation",
            "emotion_analyzer": "emotion_analysis"
        }
        
        return agent_task_mapping.get(agent_type, "chat")
            
    def _parse_urgency_level(self, urgency_input) -> UrgencyLevel:
        """Parse urgency level string or enum to enum"""
        # If already a UrgencyLevel enum, return as-is
        if isinstance(urgency_input, UrgencyLevel):
            return urgency_input
        
        # If it's a string, convert to lowercase and map
        if isinstance(urgency_input, str):
            urgency_mapping = {
                "low": UrgencyLevel.LOW,
                "medium": UrgencyLevel.MEDIUM,
                "high": UrgencyLevel.HIGH,
                "emergency": UrgencyLevel.EMERGENCY,
                "critical": UrgencyLevel.CRITICAL
            }
            return urgency_mapping.get(urgency_input.lower(), UrgencyLevel.MEDIUM)
        
        # Default fallback
        return UrgencyLevel.MEDIUM
        
    def _calculate_confidence_score(
        self, 
        unified_response: AIResponse, 
        task_complexity: TaskComplexity,
        urgency_level: UrgencyLevel
    ) -> float:
        """Calculate confidence score based on various factors"""
        base_confidence = 0.8  # Base confidence for successful responses
        
        if not unified_response.success:
            return 0.0
            
        # Adjust based on task complexity
        complexity_adjustments = {
            TaskComplexity.SIMPLE: 0.1,
            TaskComplexity.MODERATE: 0.0,
            TaskComplexity.COMPLEX: -0.1,
            TaskComplexity.CRITICAL: -0.2
        }
        
        # Adjust based on urgency level
        urgency_adjustments = {
            UrgencyLevel.LOW: 0.0,
            UrgencyLevel.MEDIUM: 0.0,
            UrgencyLevel.HIGH: -0.05,
            UrgencyLevel.EMERGENCY: -0.1
        }
        
        # Adjust based on response length (very short responses might be incomplete)
        response_length_penalty = 0.0
        if len(unified_response.content) < 50:
            response_length_penalty = -0.2
        elif len(unified_response.content) < 100:
            response_length_penalty = -0.1
            
        final_confidence = (
            base_confidence +
            complexity_adjustments.get(task_complexity, 0.0) +
            urgency_adjustments.get(urgency_level, 0.0) +
            response_length_penalty
        )
        
        return max(0.0, min(1.0, final_confidence))  # Clamp between 0 and 1
        
    async def get_usage_analytics(
        self, 
        user_id: Optional[int] = None,
        agent_type: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get comprehensive usage analytics"""
        if not self._initialized:
            await self.initialize()
            
        # Get cost summary
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        cost_summary = self.cost_optimizer.get_cost_summary(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            agent_type=agent_type
        )
        
        # Get performance metrics
        performance_report = self.model_manager.get_performance_report()
        
        # Get optimization recommendations
        recommendations = self.cost_optimizer.get_optimization_recommendations()
        
        # Get model efficiency report
        efficiency_report = self.cost_optimizer.get_model_efficiency_report()
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days
            },
            "cost_summary": cost_summary.to_dict(),
            "performance_metrics": performance_report,
            "optimization_recommendations": recommendations,
            "model_efficiency": efficiency_report,
            "active_alerts": self.cost_optimizer.get_active_alerts()
        }
        
    async def set_budget_limit(
        self,
        amount: float,
        period: str = "daily",
        user_id: Optional[int] = None,
        agent_type: Optional[str] = None
    ) -> str:
        """Set budget limit for cost control"""
        if not self._initialized:
            await self.initialize()
            
        from src.ai.cost_optimizer import BudgetPeriod
        
        period_mapping = {
            "daily": BudgetPeriod.DAILY,
            "weekly": BudgetPeriod.WEEKLY,
            "monthly": BudgetPeriod.MONTHLY,
            "yearly": BudgetPeriod.YEARLY
        }
        
        budget_period = period_mapping.get(period.lower(), BudgetPeriod.DAILY)
        
        budget_id = self.cost_optimizer.set_budget_limit(
            amount=Decimal(str(amount)),
            period=budget_period,
            user_id=user_id,
            agent_type=agent_type
        )
        
        logger.info(
            f"Budget limit set: ${amount} per {period}",
            extra={
                "budget_id": budget_id,
                "amount": amount,
                "period": period,
                "user_id": user_id,
                "agent_type": agent_type
            }
        )
        
        return budget_id
        
    async def update_user_satisfaction(
        self, 
        model_tier: str, 
        satisfaction_score: float
    ):
        """Update user satisfaction score for model performance tracking"""
        if not self._initialized:
            await self.initialize()
            
        self.model_manager.update_user_satisfaction(model_tier, satisfaction_score)
        
        logger.info(
            f"User satisfaction updated for {model_tier}: {satisfaction_score}",
            extra={
                "model_tier": model_tier,
                "satisfaction_score": satisfaction_score
            }
        )
        
    async def get_model_recommendations(
        self, 
        agent_type: str,
        urgency_level: str = "medium"
    ) -> Dict[str, Any]:
        """Get model recommendations for specific agent and urgency"""
        if not self._initialized:
            await self.initialize()
            
        # Map agent type to task type
        urgency = self._parse_urgency_level(urgency_level)
        task_type = self._map_agent_to_task_type(agent_type, urgency)
        
        # Get recommended model tier
        recommended_tier = select_model_tier(task_type)
        
        # Get Nova model specifications
        nova_specs = {
            "lite": {
                "model_id": "amazon.nova-lite-v1:0",
                "input_cost_per_1k": 0.00006,
                "output_cost_per_1k": 0.00024,
                "description": "Fast, cost-effective model for simple tasks"
            },
            "pro": {
                "model_id": "amazon.nova-pro-v1:0",
                "input_cost_per_1k": 0.0008,
                "output_cost_per_1k": 0.0032,
                "description": "Advanced model for complex reasoning and analysis"
            }
        }
        
        return {
            "recommended_model": recommended_tier,
            "model_specs": nova_specs.get(recommended_tier, {}),
            "alternative_models": [
                tier for tier in nova_specs.keys() 
                if tier != recommended_tier
            ],
            "selection_criteria": {
                "agent_type": agent_type,
                "urgency_level": urgency_level,
                "task_type": task_type
            }
        }
        
    async def cleanup(self):
        """Cleanup AI service resources"""
        # Nova client doesn't require explicit cleanup
        logger.info("Healthcare AI Service cleaned up")


# Global AI service instance
_ai_service: Optional[HealthcareAIService] = None


async def get_ai_service() -> HealthcareAIService:
    """Get or create the global AI service instance"""
    global _ai_service
    if _ai_service is None:
        _ai_service = HealthcareAIService()
        await _ai_service.initialize()
    return _ai_service


async def cleanup_ai_service():
    """Cleanup the global AI service"""
    global _ai_service
    if _ai_service:
        await _ai_service.cleanup()
        _ai_service = None
