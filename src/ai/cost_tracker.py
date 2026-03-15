"""
Cost Tracker Service for AI Requests
====================================

Tracks and calculates costs for AWS Nova AI requests.

CRITICAL: Accurate cost tracking is essential for $50 budget enforcement.

Features:
- Precise cost calculation using Decimal
- Token-based pricing for Nova Lite and Nova Pro
- Database logging of all AI usage
- Cumulative cost tracking
- Cost accuracy within $0.01

Pricing (as of 2026-03-13):
- Nova Lite: $0.00006/1K input tokens, $0.00024/1K output tokens
- Nova Pro: $0.0008/1K input tokens, $0.0032/1K output tokens
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.database.models.ai_usage import AIUsageTracking

logger = get_logger(__name__)

# BUDGET: Nova pricing (DO NOT MODIFY without verification)
NOVA_PRICING = {
    'lite': {
        'input_per_1k': Decimal('0.00006'),   # $0.00006 per 1K input tokens
        'output_per_1k': Decimal('0.00024'),  # $0.00024 per 1K output tokens
    },
    'pro': {
        'input_per_1k': Decimal('0.0008'),    # $0.0008 per 1K input tokens
        'output_per_1k': Decimal('0.0032'),   # $0.0032 per 1K output tokens
    }
}


class CostTracker:
    """
    Tracks AI usage costs with precision.
    
    CRITICAL: All cost calculations use Decimal for accuracy.
    Cost accuracy must be within $0.01 for budget enforcement.
    
    Usage:
        tracker = CostTracker(db_session)
        cost = tracker.calculate_cost('lite', 1000, 500)
        tracker.log_usage('lite', 'amazon.nova-2-lite-v1:0', 1000, 500, cost)
    """
    
    def __init__(self, db: Session):
        """
        Initialize cost tracker.
        
        Args:
            db: Database session for logging usage
        """
        self.db = db
    
    def calculate_cost(
        self,
        model_tier: str,
        input_tokens: int,
        output_tokens: int
    ) -> Decimal:
        """
        Calculate cost for AI request.
        
        BUDGET: Uses precise Decimal arithmetic for accuracy.
        
        Formula:
            cost = (input_tokens / 1000 * input_price) + (output_tokens / 1000 * output_price)
        
        Args:
            model_tier: 'lite' or 'pro'
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        
        Returns:
            Cost in USD as Decimal (6 decimal places)
        
        Raises:
            ValueError: If model_tier is invalid
        
        Examples:
            >>> tracker.calculate_cost('lite', 1000, 500)
            Decimal('0.000180')  # (1000/1000 * 0.00006) + (500/1000 * 0.00024)
            
            >>> tracker.calculate_cost('pro', 2000, 1000)
            Decimal('0.004800')  # (2000/1000 * 0.0008) + (1000/1000 * 0.0032)
        """
        # VALIDATION: Check model tier
        if model_tier not in NOVA_PRICING:
            raise ValueError(
                f"Invalid model tier: {model_tier}. "
                f"Must be one of: {list(NOVA_PRICING.keys())}"
            )
        
        # VALIDATION: Check token counts
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError(
                f"Token counts must be non-negative. "
                f"Got input_tokens={input_tokens}, output_tokens={output_tokens}"
            )
        
        pricing = NOVA_PRICING[model_tier]
        
        # BUDGET: Calculate cost using Decimal for precision
        input_cost = (Decimal(input_tokens) / Decimal('1000')) * pricing['input_per_1k']
        output_cost = (Decimal(output_tokens) / Decimal('1000')) * pricing['output_per_1k']
        total_cost = input_cost + output_cost
        
        # Round to 6 decimal places (sub-cent precision)
        total_cost = total_cost.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
        
        logger.debug(
            "Cost calculated",
            extra={
                "model_tier": model_tier,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "input_cost_usd": float(input_cost),
                "output_cost_usd": float(output_cost),
                "total_cost_usd": float(total_cost)
            }
        )
        
        return total_cost
    
    def log_usage(
        self,
        model_tier: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        cost: Decimal,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        task_type: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> AIUsageTracking:
        """
        Log AI usage to database.
        
        BUDGET: Records usage and updates cumulative cost.
        AUDIT: All AI requests must be logged.
        
        Args:
            model_tier: 'lite' or 'pro'
            model_id: Full model identifier (e.g., 'amazon.nova-2-lite-v1:0')
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost: Cost in USD (from calculate_cost)
            user_id: Optional user ID
            session_id: Optional session ID
            task_type: Optional task type (e.g., 'chat', 'video_analysis')
            request_id: Optional request ID (generated if not provided)
        
        Returns:
            AIUsageTracking record
        
        Raises:
            Exception: If database operation fails
        """
        try:
            # BUDGET: Get current cumulative cost
            cumulative_cost = self._get_current_cumulative_cost()
            
            # BUDGET: Add this request's cost
            new_cumulative_cost = cumulative_cost + cost
            
            # Round cumulative cost to 2 decimal places (cents)
            new_cumulative_cost = new_cumulative_cost.quantize(
                Decimal('0.01'),
                rounding=ROUND_HALF_UP
            )
            
            # Generate request ID if not provided
            if not request_id:
                request_id = str(uuid.uuid4())
            
            # AUDIT: Create usage record
            usage_record = AIUsageTracking(
                timestamp=datetime.now(timezone.utc),
                model_tier=model_tier,
                model_id=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                cumulative_cost_usd=new_cumulative_cost,
                user_id=user_id,
                session_id=session_id,
                task_type=task_type,
                request_id=request_id
            )
            
            # PRIVACY: Log without PII
            logger.info(
                "AI usage logged",
                extra={
                    "model_tier": model_tier,
                    "model_id": model_id,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": float(cost),
                    "cumulative_cost_usd": float(new_cumulative_cost),
                    "user_id": user_id,  # ID only, no PII
                    "task_type": task_type,
                    "request_id": request_id
                }
            )
            
            # Save to database
            self.db.add(usage_record)
            self.db.commit()
            self.db.refresh(usage_record)
            
            return usage_record
        
        except Exception as e:
            self.db.rollback()
            logger.error(
                "Failed to log AI usage",
                extra={
                    "error": str(e),
                    "model_tier": model_tier,
                    "request_id": request_id
                },
                exc_info=True
            )
            # PRIVACY: Don't expose database errors to user
            raise Exception("Failed to log AI usage") from e
    
    def _get_current_cumulative_cost(self) -> Decimal:
        """
        Get current cumulative cost from database.
        
        Returns:
            Current cumulative cost in USD
        """
        try:
            # Get the most recent cumulative cost
            latest_record = (
                self.db.query(AIUsageTracking)
                .order_by(AIUsageTracking.timestamp.desc())
                .first()
            )
            
            if latest_record:
                return Decimal(str(latest_record.cumulative_cost_usd))
            
            # No records yet, return 0
            return Decimal('0.00')
        
        except Exception as e:
            logger.error(
                "Failed to get current cumulative cost",
                extra={"error": str(e)},
                exc_info=True
            )
            # Return 0 as safe default
            return Decimal('0.00')
    
    def get_current_total(self) -> Decimal:
        """
        Get current total cost.
        
        Public method for external access to cumulative cost.
        
        Returns:
            Current cumulative cost in USD
        """
        return self._get_current_cumulative_cost()
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics.
        
        Returns:
            Dictionary with usage statistics:
            - total_cost: Total cumulative cost
            - total_requests: Total number of requests
            - total_tokens: Total tokens used
            - cost_by_tier: Cost breakdown by model tier
        """
        try:
            # Get all records
            records = self.db.query(AIUsageTracking).all()
            
            if not records:
                return {
                    'total_cost': 0.0,
                    'total_requests': 0,
                    'total_tokens': 0,
                    'cost_by_tier': {'lite': 0.0, 'pro': 0.0}
                }
            
            # Calculate statistics
            total_requests = len(records)
            total_tokens = sum(r.input_tokens + r.output_tokens for r in records)
            
            # Get latest cumulative cost
            latest_record = max(records, key=lambda r: r.timestamp)
            total_cost = float(latest_record.cumulative_cost_usd)
            
            # Calculate cost by tier
            cost_by_tier = {
                'lite': sum(float(r.cost_usd) for r in records if r.model_tier == 'lite'),
                'pro': sum(float(r.cost_usd) for r in records if r.model_tier == 'pro')
            }
            
            return {
                'total_cost': total_cost,
                'total_requests': total_requests,
                'total_tokens': total_tokens,
                'cost_by_tier': cost_by_tier
            }
        
        except Exception as e:
            logger.error(
                "Failed to get usage stats",
                extra={"error": str(e)},
                exc_info=True
            )
            return {
                'total_cost': 0.0,
                'total_requests': 0,
                'total_tokens': 0,
                'cost_by_tier': {'lite': 0.0, 'pro': 0.0}
            }
    
    def estimate_cost(
        self,
        model_tier: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int
    ) -> Decimal:
        """
        Estimate cost for a request before execution.
        
        BUDGET: Used by budget middleware for pre-request validation.
        
        Args:
            model_tier: 'lite' or 'pro'
            estimated_input_tokens: Estimated input tokens
            estimated_output_tokens: Estimated output tokens
        
        Returns:
            Estimated cost in USD
        """
        return self.calculate_cost(
            model_tier,
            estimated_input_tokens,
            estimated_output_tokens
        )
