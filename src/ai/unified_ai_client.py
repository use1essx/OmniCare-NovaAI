"""
Unified AI Client Interface for Healthcare AI V2
================================================

Provides a standardized interface for all AI operations across the application.

This module defines:
- AIRequest: Standardized request format
- AIResponse: Standardized response format
- AIClientInterface: Abstract interface for AI providers
- select_model_tier: Intelligent model selection logic

CRITICAL: All AI requests MUST go through this unified interface.

Features:
- Provider-agnostic interface
- Automatic model tier selection
- Standardized request/response format
- Budget tracking integration
- Cost calculation support
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timezone

from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AIRequest:
    """
    Standardized AI request format.
    
    All AI requests across the application use this format for consistency.
    
    Attributes:
        system_prompt: System-level instructions for the AI
        user_prompt: User's actual query or input
        model_tier: Optional model tier ('lite', 'pro', or None for auto-selection)
        task_type: Optional task type for automatic model selection
        max_tokens: Optional maximum tokens in response
        temperature: Sampling temperature (0.0-1.0), default 0.7
        user_id: Optional user ID for tracking and logging
        session_id: Optional session ID for conversation tracking
    
    Examples:
        >>> # Simple chat request
        >>> request = AIRequest(
        ...     system_prompt="You are a helpful healthcare assistant",
        ...     user_prompt="What are the symptoms of flu?",
        ...     task_type="chat"
        ... )
        
        >>> # Emergency request (auto-selects Nova Pro)
        >>> request = AIRequest(
        ...     system_prompt="Emergency response protocol",
        ...     user_prompt="Patient experiencing chest pain",
        ...     task_type="emergency",
        ...     user_id=123
        ... )
    """
    system_prompt: str
    user_prompt: str
    model_tier: Optional[str] = None  # 'lite', 'pro', or None for auto
    task_type: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: float = 0.7
    user_id: Optional[int] = None
    session_id: Optional[str] = None
    
    def __post_init__(self):
        """Validate request parameters"""
        # Validate model_tier if provided
        if self.model_tier is not None:
            if self.model_tier not in ['lite', 'pro']:
                raise ValueError(
                    f"Invalid model_tier: {self.model_tier}. "
                    f"Must be 'lite', 'pro', or None for auto-selection."
                )
        
        # Validate temperature
        if not 0.0 <= self.temperature <= 1.0:
            raise ValueError(
                f"Invalid temperature: {self.temperature}. "
                f"Must be between 0.0 and 1.0."
            )
        
        # Validate max_tokens if provided
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError(
                f"Invalid max_tokens: {self.max_tokens}. "
                f"Must be positive integer."
            )
        
        # Auto-select model tier if not provided
        if self.model_tier is None and self.task_type is not None:
            self.model_tier = select_model_tier(self.task_type)
            logger.debug(
                "Auto-selected model tier",
                extra={
                    "task_type": self.task_type,
                    "selected_tier": self.model_tier
                }
            )


@dataclass
class AIResponse:
    """
    Standardized AI response format.
    
    All AI responses across the application use this format for consistency.
    
    Attributes:
        content: The AI-generated response text
        model: Full model identifier (e.g., 'amazon.nova-lite-v1:0')
        model_tier: Model tier used ('lite' or 'pro')
        usage: Token usage dictionary with 'prompt_tokens' and 'completion_tokens'
        cost: Cost of the request in USD (Decimal for precision)
        processing_time_ms: Processing time in milliseconds
        success: Whether the request was successful
        error_message: Error message if request failed
        request_id: Unique identifier for this request
    
    Examples:
        >>> response = AIResponse(
        ...     content="The flu typically causes fever, cough, and fatigue.",
        ...     model="amazon.nova-lite-v1:0",
        ...     model_tier="lite",
        ...     usage={"prompt_tokens": 50, "completion_tokens": 20},
        ...     cost=Decimal('0.000018'),
        ...     processing_time_ms=1250,
        ...     request_id="req_abc123"
        ... )
    """
    content: str
    model: str
    model_tier: str
    usage: Dict[str, int]
    cost: Decimal
    processing_time_ms: int
    success: bool = True
    error_message: Optional[str] = None
    request_id: Optional[str] = None
    
    def __post_init__(self):
        """Validate response parameters"""
        # Validate model_tier
        if self.model_tier not in ['lite', 'pro']:
            raise ValueError(
                f"Invalid model_tier: {self.model_tier}. "
                f"Must be 'lite' or 'pro'."
            )
        
        # Validate usage dictionary
        if 'prompt_tokens' not in self.usage or 'completion_tokens' not in self.usage:
            raise ValueError(
                "Usage dictionary must contain 'prompt_tokens' and 'completion_tokens'"
            )
        
        # Validate cost is Decimal
        if not isinstance(self.cost, Decimal):
            raise ValueError(
                f"Cost must be Decimal, got {type(self.cost).__name__}"
            )
    
    @property
    def total_tokens(self) -> int:
        """Total tokens used (prompt + completion)"""
        return self.usage.get('prompt_tokens', 0) + self.usage.get('completion_tokens', 0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary for serialization"""
        return {
            'content': self.content,
            'model': self.model,
            'model_tier': self.model_tier,
            'usage': self.usage,
            'total_tokens': self.total_tokens,
            'cost': float(self.cost),
            'processing_time_ms': self.processing_time_ms,
            'success': self.success,
            'error_message': self.error_message,
            'request_id': self.request_id
        }


class AIClientInterface(ABC):
    """
    Abstract interface for AI providers.
    
    All AI client implementations (Nova, future providers) must implement this interface.
    This ensures consistent behavior across different AI providers.
    
    Methods:
        make_request: Execute an AI request and return response
        get_usage_stats: Get usage statistics for this client
    
    Example Implementation:
        >>> class NovaClient(AIClientInterface):
        ...     async def make_request(self, request: AIRequest) -> AIResponse:
        ...         # Implementation here
        ...         pass
        ...     
        ...     def get_usage_stats(self) -> Dict[str, Any]:
        ...         # Implementation here
        ...         pass
    """
    
    @abstractmethod
    async def make_request(self, request: AIRequest) -> AIResponse:
        """
        Make an AI request.
        
        CRITICAL: Implementations MUST:
        - Validate budget before execution
        - Track costs accurately
        - Log usage to database
        - Handle errors gracefully
        - Return standardized AIResponse
        
        Args:
            request: Standardized AI request
        
        Returns:
            Standardized AI response
        
        Raises:
            BudgetExceededError: If budget limit reached
            AIServiceError: If AI service fails
            ValidationError: If request is invalid
        """
        pass
    
    @abstractmethod
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics for this client.
        
        Returns:
            Dictionary with usage statistics:
            - total_requests: Total number of requests
            - total_tokens: Total tokens used
            - total_cost: Total cost in USD
            - average_cost_per_request: Average cost per request
            - cost_by_tier: Cost breakdown by model tier (if applicable)
        
        Example:
            >>> stats = client.get_usage_stats()
            >>> print(f"Total cost: ${stats['total_cost']:.4f}")
            >>> print(f"Total requests: {stats['total_requests']}")
        """
        pass


def select_model_tier(task_type: str, complexity: Optional[str] = None) -> str:
    """
    Select appropriate Nova model tier based on task requirements.
    
    This function implements intelligent model routing to optimize cost and performance.
    
    Model Selection Rules:
    - Emergency/critical tasks → Nova Pro (high accuracy required)
    - Video analysis → Nova Pro (complex reasoning required)
    - Report generation → Nova Pro (detailed analysis required)
    - Complex reasoning → Nova Pro (advanced capabilities required)
    - Simple chat → Nova Lite (cost-effective)
    - Questionnaires → Nova Lite (structured output)
    - Emotion analysis → Nova Lite (fast response)
    - Default → Nova Lite (cost-effective for general use)
    
    Args:
        task_type: Type of task (e.g., 'chat', 'emergency', 'video_analysis')
        complexity: Optional complexity level ('low', 'medium', 'high')
    
    Returns:
        Model tier: 'lite' or 'pro'
    
    Examples:
        >>> select_model_tier('emergency')
        'pro'
        
        >>> select_model_tier('chat')
        'lite'
        
        >>> select_model_tier('video_analysis')
        'pro'
        
        >>> select_model_tier('questionnaire')
        'lite'
    
    Cost Comparison:
        Nova Lite: $0.00006/1K input, $0.00024/1K output (~4x cheaper)
        Nova Pro:  $0.0008/1K input,  $0.0032/1K output (better quality)
    """
    # Normalize task_type to lowercase for case-insensitive matching
    task_type_lower = task_type.lower() if task_type else ""
    
    # High-priority tasks requiring Nova Pro
    PRO_TASKS = {
        'emergency',
        'critical',
        'video_analysis',
        'video_processing',
        'report_generation',
        'report',
        'complex_reasoning',
        'medical_diagnosis',
        'crisis',
        'urgent'
    }
    
    # Cost-effective tasks suitable for Nova Lite
    LITE_TASKS = {
        'chat',
        'simple_chat',
        'simple_query',
        'questionnaire',
        'questionnaire_generation',
        'emotion_analysis',
        'emotion',
        'simple',
        'basic',
        'greeting',
        'small_talk'
    }
    
    # Check if task requires Nova Pro
    if task_type_lower in PRO_TASKS:
        logger.debug(
            "Selected Nova Pro for high-priority task",
            extra={"task_type": task_type}
        )
        return 'pro'
    
    # Check if task is suitable for Nova Lite
    if task_type_lower in LITE_TASKS:
        logger.debug(
            "Selected Nova Lite for cost-effective task",
            extra={"task_type": task_type}
        )
        return 'lite'
    
    # Use complexity if provided
    if complexity:
        complexity_lower = complexity.lower()
        if complexity_lower in ['high', 'complex']:
            logger.debug(
                "Selected Nova Pro based on high complexity",
                extra={"task_type": task_type, "complexity": complexity}
            )
            return 'pro'
        elif complexity_lower in ['low', 'simple']:
            logger.debug(
                "Selected Nova Lite based on low complexity",
                extra={"task_type": task_type, "complexity": complexity}
            )
            return 'lite'
    
    # Default to Nova Lite for cost efficiency
    logger.debug(
        "Selected Nova Lite as default (cost-effective)",
        extra={"task_type": task_type, "complexity": complexity}
    )
    return 'lite'


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.
    
    This is a rough estimation. Actual token count may vary.
    Rule of thumb: ~4 characters per token for English text.
    
    Args:
        text: Input text
    
    Returns:
        Estimated token count
    """
    # Rough estimation: 4 characters per token
    return max(1, len(text) // 4)


def validate_request(request: AIRequest) -> bool:
    """
    Validate AI request before execution.
    
    Args:
        request: AI request to validate
    
    Returns:
        True if valid
    
    Raises:
        ValidationError: If request is invalid
    """
    from src.core.exceptions import ValidationError
    
    # Check prompts are not empty
    if not request.system_prompt or not request.system_prompt.strip():
        raise ValidationError(
            "System prompt cannot be empty",
            context={"field": "system_prompt"}
        )
    
    if not request.user_prompt or not request.user_prompt.strip():
        raise ValidationError(
            "User prompt cannot be empty",
            context={"field": "user_prompt"}
        )
    
    # Check prompt lengths (reasonable limits)
    MAX_PROMPT_LENGTH = 100000  # ~25K tokens
    if len(request.system_prompt) > MAX_PROMPT_LENGTH:
        raise ValidationError(
            f"System prompt too long (max {MAX_PROMPT_LENGTH} characters)",
            context={"field": "system_prompt", "length": len(request.system_prompt)}
        )
    
    if len(request.user_prompt) > MAX_PROMPT_LENGTH:
        raise ValidationError(
            f"User prompt too long (max {MAX_PROMPT_LENGTH} characters)",
            context={"field": "user_prompt", "length": len(request.user_prompt)}
        )
    
    return True
