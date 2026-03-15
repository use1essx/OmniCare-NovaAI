"""
Smart model selection and management for Healthcare AI V2
Based on _enhanced_model_selection() patterns from healthcare_ai_system
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal

from src.ai.unified_ai_client import AIRequest, AIResponse, select_model_tier
from src.ai.providers.nova_bedrock_client import NovaBedrockClient, get_nova_client
from src.core.exceptions import AgentError
from src.core.logging import get_logger


logger = get_logger(__name__)


class TaskComplexity(Enum):
    """Task complexity levels for model selection"""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    CRITICAL = "critical"


class UrgencyLevel(Enum):
    """Urgency levels for model selection"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class ModelPerformanceMetrics:
    """Track performance metrics for each model"""
    total_requests: int = 0
    successful_requests: int = 0
    average_response_time_ms: float = 0.0
    average_cost: Decimal = Decimal('0.0')
    user_satisfaction_score: float = 0.0
    error_rate: float = 0.0
    last_used: Optional[datetime] = None
    
    def update_metrics(
        self, 
        success: bool, 
        response_time_ms: int, 
        cost: Decimal,
        satisfaction_score: Optional[float] = None
    ):
        """Update performance metrics with new data"""
        self.total_requests += 1
        
        if success:
            self.successful_requests += 1
            
        # Update average response time
        if self.total_requests == 1:
            self.average_response_time_ms = float(response_time_ms)
        else:
            self.average_response_time_ms = (
                (self.average_response_time_ms * (self.total_requests - 1) + response_time_ms) 
                / self.total_requests
            )
            
        # Update average cost
        if self.total_requests == 1:
            self.average_cost = cost
        else:
            self.average_cost = (
                (self.average_cost * (self.total_requests - 1) + cost) 
                / self.total_requests
            )
            
        # Update satisfaction score if provided
        if satisfaction_score is not None:
            if self.user_satisfaction_score == 0.0:
                self.user_satisfaction_score = satisfaction_score
            else:
                self.user_satisfaction_score = (
                    (self.user_satisfaction_score * 0.8) + (satisfaction_score * 0.2)
                )
                
        # Calculate error rate
        self.error_rate = 1.0 - (self.successful_requests / self.total_requests)
        self.last_used = datetime.utcnow()


@dataclass
class ModelSelectionCriteria:
    """Criteria for model selection"""
    agent_type: str
    content_type: str
    urgency_level: UrgencyLevel
    task_complexity: TaskComplexity
    user_id: Optional[int] = None
    conversation_context: Optional[Dict] = None
    cost_constraints: Optional[Dict] = None
    performance_requirements: Optional[Dict] = None


class ModelManager:
    """
    Smart model selection and management system
    Based on _enhanced_model_selection() logic from healthcare_ai_system
    """
    
    def __init__(self):
        self.client: Optional[NovaBedrockClient] = None
        self.performance_metrics: Dict[str, ModelPerformanceMetrics] = {}
        self.usage_rotation: Dict[str, datetime] = {}
        self.fallback_chain: Dict[str, List[str]] = {}
        self._initialize_performance_tracking()
        self._setup_fallback_chains()
        
    def _initialize_performance_tracking(self):
        """Initialize performance tracking for all models"""
        # Initialize tracking for Nova model tiers
        model_tiers = ["lite", "premium"]
        for tier in model_tiers:
            self.performance_metrics[tier] = ModelPerformanceMetrics()
            
    def _setup_fallback_chains(self):
        """Setup fallback chains for different scenarios"""
        self.fallback_chain = {
            "emergency": ["premium", "lite"],
            "critical": ["premium", "lite"],
            "standard": ["lite", "premium"],
            "cost_optimized": ["lite", "premium"],
            "quality_optimized": ["premium", "lite"]
        }
        
    async def get_client(self) -> NovaBedrockClient:
        """Get or initialize Nova Bedrock client"""
        if self.client is None:
            self.client = get_nova_client()
        return self.client
        
    def analyze_task_complexity(
        self, 
        user_input: str, 
        agent_type: str,
        conversation_context: Optional[Dict] = None
    ) -> TaskComplexity:
        """
        Analyze task complexity based on input content and context
        Based on complexity analysis patterns from healthcare_ai_system
        """
        lower_input = user_input.lower().strip()
        input_length = len(user_input)
        
        # Emergency scenarios are always critical
        emergency_keywords = [
            "emergency", "緊急", "urgent", "急", "help", "救命", "911", "999",
            "heart attack", "心臟病", "stroke", "中風", "unconscious", "暈倒"
        ]
        
        if any(keyword in lower_input for keyword in emergency_keywords):
            return TaskComplexity.CRITICAL
            
        # Complex medical scenarios
        complex_medical_keywords = [
            "diagnosis", "診斷", "treatment plan", "治療計劃", "medication interaction", "藥物相互作用",
            "chronic condition", "慢性病", "multiple symptoms", "多種症狀", "specialist", "專科醫生"
        ]
        
        if any(keyword in lower_input for keyword in complex_medical_keywords):
            return TaskComplexity.COMPLEX
            
        # Agent-specific complexity analysis
        if agent_type == "illness_monitor":
            illness_complexity_indicators = [
                "several", "multiple", "different", "various", "combined", "together",
                "幾個", "多個", "不同", "各種", "一齊", "同時"
            ]
            if any(indicator in lower_input for indicator in illness_complexity_indicators):
                return TaskComplexity.COMPLEX
                
        elif agent_type == "mental_health":
            mental_health_complexity = [
                "depression", "anxiety", "panic", "trauma", "suicidal", "self-harm",
                "抑鬱", "焦慮", "恐慌", "創傷", "自殺", "自我傷害"
            ]
            if any(keyword in lower_input for keyword in mental_health_complexity):
                return TaskComplexity.COMPLEX
                
        # Length-based complexity
        if input_length > 500:  # Long, detailed queries
            return TaskComplexity.COMPLEX
        elif input_length > 200:  # Medium queries
            return TaskComplexity.MODERATE
        else:  # Short queries
            return TaskComplexity.SIMPLE
            
    def determine_urgency_level(
        self, 
        user_input: str, 
        agent_type: str,
        conversation_context: Optional[Dict] = None
    ) -> UrgencyLevel:
        """
        Determine urgency level based on content and context
        Based on urgency detection from healthcare_ai_system
        """
        lower_input = user_input.lower().strip()
        
        # Emergency keywords (highest priority)
        emergency_keywords = [
            "emergency", "緊急", "urgent", "急", "help", "救命", "call ambulance", "叫救護車",
            "heart attack", "心臟病", "stroke", "中風", "can't breathe", "唔能夠呼吸",
            "severe pain", "劇痛", "unconscious", "暈倒", "bleeding heavily", "大量出血"
        ]
        
        if any(keyword in lower_input for keyword in emergency_keywords):
            return UrgencyLevel.EMERGENCY
            
        # High urgency indicators
        high_urgency_keywords = [
            "severe", "serious", "worried", "scared", "急", "嚴重", "擔心", "驚",
            "getting worse", "惡化", "can't sleep", "瞓唔著", "very painful", "好痛"
        ]
        
        if any(keyword in lower_input for keyword in high_urgency_keywords):
            return UrgencyLevel.HIGH
            
        # Medium urgency indicators
        medium_urgency_keywords = [
            "concerned", "uncomfortable", "不舒服", "關心", "bothering", "煩",
            "should I", "我應該", "what if", "如果", "is this normal", "係咪正常"
        ]
        
        if any(keyword in lower_input for keyword in medium_urgency_keywords):
            return UrgencyLevel.MEDIUM
            
        return UrgencyLevel.LOW
        
    def select_optimal_model(self, criteria: ModelSelectionCriteria) -> str:
        """
        Select optimal model based on criteria and performance metrics
        Uses unified AI client's select_model_tier() for Nova integration
        """
        # Map task complexity and urgency to task_type for select_model_tier()
        task_type = self._map_criteria_to_task_type(criteria)
        
        # Use unified client's model selection
        selected_tier = select_model_tier(task_type)
        
        # Check performance metrics and fallback if needed
        metrics = self.performance_metrics.get(selected_tier)
        if metrics and metrics.error_rate > 0.2 and metrics.total_requests > 10:
            logger.warning(f"Selected tier {selected_tier} has high error rate, using fallback")
            # Use opposite tier as fallback
            selected_tier = 'lite' if selected_tier == 'pro' else 'pro'
        
        # Update usage rotation
        self.usage_rotation[selected_tier] = datetime.utcnow()
        
        return selected_tier
    
    def _map_criteria_to_task_type(self, criteria: ModelSelectionCriteria) -> str:
        """Map ModelSelectionCriteria to task_type for select_model_tier()"""
        # Emergency scenarios
        if criteria.urgency_level == UrgencyLevel.EMERGENCY:
            return "emergency"
        
        # Critical tasks
        if criteria.task_complexity == TaskComplexity.CRITICAL:
            return "critical"
        
        # Agent-specific mappings
        if criteria.agent_type == "safety":
            return "emergency"
        elif criteria.agent_type == "mental_health" and criteria.task_complexity == TaskComplexity.COMPLEX:
            return "complex_reasoning"
        elif criteria.agent_type == "illness_monitor":
            if criteria.urgency_level in [UrgencyLevel.HIGH, UrgencyLevel.MEDIUM]:
                return "video_analysis"  # Use pro for medical monitoring
            return "chat"
        
        # Complexity-based mapping
        if criteria.task_complexity == TaskComplexity.COMPLEX:
            return "complex_reasoning"
        elif criteria.task_complexity == TaskComplexity.MODERATE:
            return "chat"
        else:
            return "simple_chat"
            
    async def make_request_with_fallback(
        self,
        criteria: ModelSelectionCriteria,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3
    ) -> AIResponse:
        """
        Make request with automatic fallback on failure
        Uses unified AI client interface with Nova
        """
        client = await self.get_client()
        primary_model = self.select_optimal_model(criteria)
        
        # Try primary model first
        try:
            response = await client.make_request(
                model_tier=primary_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                user_id=criteria.user_id,
                task_type=self._map_criteria_to_task_type(criteria)
            )
            
            # Update performance metrics
            self.performance_metrics[primary_model].update_metrics(
                success=response.success,
                response_time_ms=response.processing_time_ms,
                cost=response.cost
            )
            
            if response.success:
                logger.info(f"Request successful with primary model: {primary_model}")
                return response
                
        except Exception as e:
            logger.warning(f"Primary model {primary_model} failed: {e}")
            self.performance_metrics[primary_model].update_metrics(
                success=False,
                response_time_ms=0,
                cost=Decimal('0.0')
            )
            
        # Try fallback model (opposite tier)
        fallback_model = 'lite' if primary_model == 'pro' else 'pro'
        
        try:
            response = await client.make_request(
                model_tier=fallback_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                user_id=criteria.user_id,
                task_type=self._map_criteria_to_task_type(criteria)
            )
            
            # Update performance metrics
            self.performance_metrics[fallback_model].update_metrics(
                success=response.success,
                response_time_ms=response.processing_time_ms,
                cost=response.cost
            )
            
            if response.success:
                logger.info(f"Request successful with fallback model: {fallback_model}")
                return response
                
        except Exception as e:
            logger.warning(f"Fallback model {fallback_model} failed: {e}")
            self.performance_metrics[fallback_model].update_metrics(
                success=False,
                response_time_ms=0,
                cost=Decimal('0.0')
            )
                
        # If all models failed, raise error
        raise AgentError(
            f"All models failed for agent_type: {criteria.agent_type}",
            agent_type=criteria.agent_type
        )
            
    def update_user_satisfaction(self, model_tier: str, satisfaction_score: float):
        """Update user satisfaction score for a model"""
        if model_tier in self.performance_metrics:
            metrics = self.performance_metrics[model_tier]
            if metrics.user_satisfaction_score == 0.0:
                metrics.user_satisfaction_score = satisfaction_score
            else:
                # Weighted average with more weight on recent feedback
                metrics.user_satisfaction_score = (
                    (metrics.user_satisfaction_score * 0.7) + (satisfaction_score * 0.3)
                )
                
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "models": {},
            "recommendations": []
        }
        
        for tier, metrics in self.performance_metrics.items():
            if metrics.total_requests > 0:
                report["models"][tier] = {
                    "total_requests": metrics.total_requests,
                    "success_rate": (metrics.successful_requests / metrics.total_requests) * 100,
                    "error_rate": metrics.error_rate * 100,
                    "average_response_time_ms": metrics.average_response_time_ms,
                    "average_cost": float(metrics.average_cost),
                    "user_satisfaction_score": metrics.user_satisfaction_score,
                    "last_used": metrics.last_used.isoformat() if metrics.last_used else None
                }
                
        # Generate recommendations
        report["recommendations"] = self._generate_recommendations()
        
        return report
        
    def _generate_recommendations(self) -> List[str]:
        """Generate performance-based recommendations"""
        recommendations = []
        
        for tier, metrics in self.performance_metrics.items():
            if metrics.total_requests < 10:
                continue
                
            if metrics.error_rate > 0.15:
                recommendations.append(
                    f"Model '{tier}' has high error rate ({metrics.error_rate:.2%}). "
                    "Consider investigating or reducing usage."
                )
                
            if metrics.user_satisfaction_score < 3.0 and metrics.user_satisfaction_score > 0:
                recommendations.append(
                    f"Model '{tier}' has low user satisfaction ({metrics.user_satisfaction_score:.1f}/5). "
                    "Consider adjusting usage patterns."
                )
                
            if metrics.average_response_time_ms > 10000:  # 10 seconds
                recommendations.append(
                    f"Model '{tier}' has slow response times ({metrics.average_response_time_ms:.0f}ms). "
                    "Consider using for non-urgent requests only."
                )
                
        return recommendations
        
    def reset_performance_metrics(self):
        """Reset all performance metrics"""
        self._initialize_performance_tracking()
        self.usage_rotation.clear()
        logger.info("Performance metrics reset")


# Global model manager instance
_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get or create the global model manager instance"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
