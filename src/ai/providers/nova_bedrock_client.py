"""
Amazon Nova Bedrock Client for Healthcare AI V2 - Hackathon Implementation
Provides Nova 2 Lite, Nova 2 Pro, and Titan Embeddings integration

BUDGET: Integrated with budget protection middleware for $50 hard limit enforcement
"""

import time
import asyncio
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from decimal import Decimal
import json
import os

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.core.exceptions import ExternalAPIError, ValidationError, BudgetExceededError
from src.ai.budget_middleware import BudgetProtectionMiddleware
from src.ai.cost_tracker import CostTracker

logger = get_logger(__name__)


@dataclass
class NovaModelSpec:
    """Amazon Nova model specification"""
    model_id: str
    model_name: str
    tier: str
    cost_per_1k_input_tokens: Decimal
    cost_per_1k_output_tokens: Decimal
    max_tokens: int
    context_window: int
    description: str
    capabilities: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['cost_per_1k_input_tokens'] = float(self.cost_per_1k_input_tokens)
        data['cost_per_1k_output_tokens'] = float(self.cost_per_1k_output_tokens)
        return data


@dataclass
class NovaResponse:
    """Standardized response from Nova models"""
    content: str
    model: str
    usage: Dict[str, int]
    cost: Decimal
    processing_time_ms: int
    success: bool = True
    error_message: Optional[str] = None


class NovaBedrockClient:
    """
    Amazon Nova Bedrock client for Healthcare AI V2
    Supports Nova 2 Lite, Nova 2 Pro, and Titan Embeddings
    """
    
    # Amazon Nova model catalog
    NOVA_MODELS: Dict[str, NovaModelSpec] = {
        "lite": NovaModelSpec(
            model_id="amazon.nova-lite-v1:0",
            model_name="Amazon Nova Lite",
            tier="lite",
            cost_per_1k_input_tokens=Decimal('0.00006'),
            cost_per_1k_output_tokens=Decimal('0.00024'),
            max_tokens=5000,
            context_window=300000,
            description="Fast, cost-effective model for routine healthcare queries",
            capabilities=["general", "medical", "fast_response", "cantonese"]
        ),
        "pro": NovaModelSpec(
            model_id="amazon.nova-pro-v1:0",
            model_name="Amazon Nova Pro",
            tier="pro",
            cost_per_1k_input_tokens=Decimal('0.0008'),
            cost_per_1k_output_tokens=Decimal('0.0032'),
            max_tokens=5000,
            context_window=300000,
            description="Advanced reasoning model for complex medical analysis and video understanding",
            capabilities=["complex_reasoning", "medical", "video_analysis", "emergency", "critical_care"]
        )
    }
    
    def __init__(
        self,
        region: str = "us-east-1",
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        db: Optional[Session] = None
    ):
        """
        Initialize Nova Bedrock client
        
        Args:
            region: AWS region
            access_key_id: AWS access key ID (uses env if not provided)
            secret_access_key: AWS secret access key (uses env if not provided)
            db: Optional database session for budget protection and cost tracking
        """
        self.region = region
        self.access_key_id = access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_access_key = secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        
        # SECURITY: Validate credentials
        if not self.access_key_id or not self.secret_access_key:
            raise NoCredentialsError()
        
        # Initialize boto3 client
        try:
            self.client = boto3.client(
                service_name='bedrock-runtime',
                region_name=self.region,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key
            )
            logger.info(f"Nova Bedrock client initialized for region: {self.region}")
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {e}")
            raise
        
        # BUDGET: Initialize budget protection and cost tracking
        self.db = db
        self.budget_middleware: Optional[BudgetProtectionMiddleware] = None
        self.cost_tracker: Optional[CostTracker] = None
        
        if db:
            self.budget_middleware = BudgetProtectionMiddleware(db)
            self.cost_tracker = CostTracker(db)
            logger.info("Budget protection and cost tracking enabled")
        else:
            logger.warning("Budget protection disabled - no database session provided")
        
        # Usage tracking (in-memory, for backward compatibility)
        self.total_cost = Decimal('0.0')
        self.total_requests = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
    
    def _calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model_spec: NovaModelSpec
    ) -> Decimal:
        """Calculate cost based on token usage"""
        input_cost = (Decimal(input_tokens) / 1000) * model_spec.cost_per_1k_input_tokens
        output_cost = (Decimal(output_tokens) / 1000) * model_spec.cost_per_1k_output_tokens
        return input_cost + output_cost
    
    async def make_request(
        self,
        model_tier: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        task_type: Optional[str] = None,
        request: Optional['AIRequest'] = None,
        **kwargs
    ) -> NovaResponse:
        """
        Make request to Nova model using Converse API
        
        Supports two calling patterns:
        1. Individual parameters: make_request(model_tier="lite", system_prompt="...", user_prompt="...")
        2. AIRequest object: make_request(request=AIRequest(...))
        
        BUDGET: Checks budget before execution and logs cost after completion
        
        Args:
            model_tier: "lite" or "pro" (or None if using request object)
            system_prompt: System prompt (or None if using request object)
            user_prompt: User prompt (or None if using request object)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0-1.0)
            user_id: Optional user ID for cost tracking
            session_id: Optional session ID for cost tracking
            task_type: Optional task type (e.g., 'chat', 'video_analysis')
            request: Optional AIRequest object (alternative to individual parameters)
            
        Returns:
            NovaResponse with content and metadata
            
        Raises:
            BudgetExceededError: If budget limit reached or would be exceeded
        """
        # Handle AIRequest object if provided
        if request is not None:
            from src.ai.unified_ai_client import AIRequest, select_model_tier
            
            # Extract parameters from AIRequest
            model_tier = request.model_tier
            if not model_tier:
                # Auto-select based on task type
                model_tier = select_model_tier(request.task_type or "general")
            
            system_prompt = request.system_prompt
            user_prompt = request.user_prompt
            max_tokens = request.max_tokens
            temperature = request.temperature
            user_id = request.user_id
            session_id = request.session_id
            task_type = request.task_type
        
        # Validate required parameters
        if not model_tier:
            raise ValidationError("model_tier is required")
        if not system_prompt:
            raise ValidationError("system_prompt is required")
        if not user_prompt:
            raise ValidationError("user_prompt is required")
        
        # AUDIT: Generate unique request ID
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # VALIDATION: Get model specification
        if model_tier not in self.NOVA_MODELS:
            raise ValidationError(f"Unknown model tier: {model_tier}")
        
        model_spec = self.NOVA_MODELS[model_tier]
        
        # Set defaults
        max_tokens = max_tokens or model_spec.max_tokens
        temperature = temperature if temperature is not None else 0.7
        
        # BUDGET: Pre-request budget check
        if self.budget_middleware and self.cost_tracker:
            # Estimate cost based on typical token usage
            # Conservative estimate: assume max_tokens for output
            estimated_input_tokens = len(system_prompt.split()) + len(str(user_prompt).split()) * 2
            estimated_output_tokens = max_tokens
            
            estimated_cost = self.cost_tracker.estimate_cost(
                model_tier,
                estimated_input_tokens,
                estimated_output_tokens
            )
            
            # BUDGET: Check if request would exceed budget
            try:
                await self.budget_middleware.check_budget_before_request(
                    estimated_cost,
                    user_id=user_id,
                    session_id=session_id
                )
            except BudgetExceededError:
                # AUDIT: Log budget exceeded
                logger.error(
                    "Request blocked - budget exceeded",
                    extra={
                        "request_id": request_id,
                        "model_tier": model_tier,
                        "estimated_cost_usd": float(estimated_cost),
                        "user_id": user_id,
                        "session_id": session_id
                    }
                )
                raise
        
        # Prepare messages for Converse API
        messages = [
            {
                "role": "user",
                "content": [
                    {"text": f"{system_prompt}\n\n{user_prompt}"}
                ]
            }
        ]
        
        # Retry logic for transient failures
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Call Bedrock Converse API
                response = self.client.converse(
                    modelId=model_spec.model_id,
                    messages=messages,
                    inferenceConfig={
                        "maxTokens": max_tokens,
                        "temperature": temperature
                    }
                )
                
                # Extract response
                output_message = response['output']['message']
                content = output_message['content'][0]['text']
                
                # Extract usage stats
                usage = response.get('usage', {})
                input_tokens = usage.get('inputTokens', 0)
                output_tokens = usage.get('outputTokens', 0)
                
                # Calculate cost
                cost = self._calculate_cost(input_tokens, output_tokens, model_spec)
                
                # BUDGET: Log usage to database
                if self.cost_tracker:
                    try:
                        self.cost_tracker.log_usage(
                            model_tier=model_tier,
                            model_id=model_spec.model_id,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            cost=cost,
                            user_id=user_id,
                            session_id=session_id,
                            task_type=task_type,
                            request_id=request_id
                        )
                    except Exception as e:
                        # PRIVACY: Don't expose database errors to user
                        logger.error(
                            "Failed to log usage to database",
                            extra={
                                "error": str(e),
                                "request_id": request_id
                            },
                            exc_info=True
                        )
                        # Continue - don't fail request due to logging error
                
                # Update in-memory tracking (backward compatibility)
                self.total_cost += cost
                self.total_requests += 1
                self.total_input_tokens += input_tokens
                self.total_output_tokens += output_tokens
                
                processing_time_ms = int((time.time() - start_time) * 1000)
                
                # PRIVACY: Log without PII
                logger.info(
                    "Nova request successful",
                    extra={
                        "request_id": request_id,
                        "model": model_spec.model_id,
                        "tier": model_tier,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cost_usd": float(cost),
                        "processing_time_ms": processing_time_ms,
                        "user_id": user_id,  # ID only, no PII
                        "task_type": task_type
                    }
                )
                
                return NovaResponse(
                    content=content,
                    model=model_spec.model_id,
                    usage={"prompt_tokens": input_tokens, "completion_tokens": output_tokens},
                    cost=cost,
                    processing_time_ms=processing_time_ms,
                    success=True
                )
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                
                if error_code == 'ThrottlingException':
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            f"Throttled, retrying in {delay}s (attempt {attempt + 1})",
                            extra={"request_id": request_id}
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise ExternalAPIError(
                            f"Throttled after {max_retries} attempts",
                            service="bedrock"
                        )
                
                elif error_code == 'ValidationException':
                    raise ValidationError(f"Invalid request: {str(e)}")
                
                elif error_code == 'AccessDeniedException':
                    raise ExternalAPIError(
                        "Access denied - check IAM permissions",
                        service="bedrock"
                    )
                
                else:
                    logger.error(
                        f"Bedrock API error: {e}",
                        extra={"request_id": request_id}
                    )
                    raise ExternalAPIError(
                        f"Bedrock API error: {str(e)}",
                        service="bedrock"
                    )
            
            except (BotoCoreError, Exception) as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"Request failed, retrying in {delay}s: {e}",
                        extra={"request_id": request_id}
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(
                        f"Nova request failed after {max_retries} attempts: {e}",
                        extra={"request_id": request_id}
                    )
                    return NovaResponse(
                        content="",
                        model=model_spec.model_id,
                        usage={},
                        cost=Decimal('0.0'),
                        processing_time_ms=int((time.time() - start_time) * 1000),
                        success=False,
                        error_message=str(e)
                    )
        
        # Should not reach here
        raise ExternalAPIError("Unexpected error in retry logic", service="bedrock")
    async def make_request_from_ai_request(
        self,
        request: 'AIRequest'
    ) -> 'AIResponse':
        """
        Make request using AIRequest object (high-level interface)

        This method provides compatibility with the unified AI client interface.
        It converts an AIRequest to the low-level make_request parameters.

        Args:
            request: AIRequest object with all request parameters

        Returns:
            AIResponse object with standardized response format

        Raises:
            BudgetExceededError: If budget limit reached
            ValidationError: If request is invalid
        """
        from src.ai.unified_ai_client import AIRequest, AIResponse

        # Validate request
        if not isinstance(request, AIRequest):
            raise ValueError(f"Expected AIRequest, got {type(request)}")

        # Determine model tier
        model_tier = request.model_tier
        if not model_tier:
            # Auto-select based on task type
            from src.ai.unified_ai_client import select_model_tier
            model_tier = select_model_tier(request.task_type or "general")

        # Call low-level make_request
        nova_response = await self.make_request(
            model_tier=model_tier,
            system_prompt=request.system_prompt,
            user_prompt=request.user_prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            user_id=request.user_id,
            session_id=request.session_id,
            task_type=request.task_type
        )

        # Convert NovaResponse to AIResponse
        return AIResponse(
            content=nova_response.content,
            model=nova_response.model,
            model_tier=model_tier,
            usage={
                "prompt_tokens": nova_response.usage.get("prompt_tokens", 0),
                "completion_tokens": nova_response.usage.get("completion_tokens", 0)
            },
            cost=nova_response.cost,
            processing_time_ms=nova_response.processing_time_ms,
            success=nova_response.success,
            error_message=nova_response.error_message
        )

    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost": float(self.total_cost),
            "average_cost_per_request": float(self.total_cost / self.total_requests) if self.total_requests > 0 else 0.0
        }
    
    def get_model_specs(self) -> Dict[str, Dict[str, Any]]:
        """Get all model specifications"""
        return {tier: spec.to_dict() for tier, spec in self.NOVA_MODELS.items()}
    
    def reset_usage_stats(self):
        """Reset usage statistics"""
        self.total_cost = Decimal('0.0')
        self.total_requests = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0


# Global client instance
_nova_client: Optional[NovaBedrockClient] = None


def get_nova_client(region: str = "us-east-1") -> NovaBedrockClient:
    """Get or create the global Nova client instance"""
    global _nova_client
    if _nova_client is None:
        _nova_client = NovaBedrockClient(region=region)
    return _nova_client


def is_nova_available() -> bool:
    """Check if Nova is available and configured"""
    try:
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        use_bedrock = os.getenv("USE_BEDROCK", "false").lower() == "true"
        return bool(access_key and secret_key and use_bedrock)
    except Exception:
        return False
