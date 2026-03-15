"""
Budget Protection Middleware for AI Requests
============================================

Enforces $50 hard budget limit on all AI requests.

CRITICAL: This is the primary budget protection mechanism.
All AI requests MUST go through this middleware.

Features:
- Real-time cost tracking
- Pre-request budget validation
- $50 hard limit enforcement
- Alert system at thresholds
- Database persistence
"""

from decimal import Decimal
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.core.logging import get_logger
from src.core.exceptions import BudgetExceededError
from src.database.models.ai_usage import AIUsageTracking

logger = get_logger(__name__)

# BUDGET: Hard-coded $50 limit (DO NOT MODIFY)
BUDGET_LIMIT_USD = Decimal('50.00')

# BUDGET: Alert thresholds
BUDGET_WARNING_THRESHOLDS = {
    'warning': Decimal('40.00'),      # 80% - Warning
    'critical': Decimal('45.00'),     # 90% - Critical warning
    'final': Decimal('47.50'),        # 95% - Final warning
    'exceeded': Decimal('50.00'),     # 100% - BLOCK ALL REQUESTS
}


class BudgetProtectionMiddleware:
    """
    Enforces $50 budget limit on AI requests.
    
    CRITICAL: This is the primary budget protection mechanism.
    All AI requests MUST be validated through this middleware.
    
    Workflow:
    1. Check current total from database
    2. Verify not at limit ($50)
    3. Estimate request cost
    4. Verify projected total won't exceed limit
    5. Allow or block request
    """
    
    def __init__(self, db: Session):
        """
        Initialize budget protection middleware.
        
        Args:
            db: Database session for cost tracking
        """
        self.db = db
        self.budget_limit = BUDGET_LIMIT_USD
        self._last_alert_level: Optional[str] = None
    
    async def check_budget_before_request(
        self,
        estimated_cost: Decimal,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> bool:
        """
        Check if request would exceed budget.
        
        SECURITY: Blocks request if budget limit reached or would be exceeded.
        
        Args:
            estimated_cost: Estimated cost of the request in USD
            user_id: Optional user ID for logging
            session_id: Optional session ID for logging
        
        Returns:
            True if request allowed
        
        Raises:
            BudgetExceededError: If budget limit reached or would be exceeded
        """
        # BUDGET: Get current total from database
        current_total = self._get_current_total()
        
        # BUDGET: Check if already at limit
        if current_total >= self.budget_limit:
            logger.error(
                "Budget limit reached - blocking request",
                extra={
                    "current_total_usd": float(current_total),
                    "budget_limit_usd": float(self.budget_limit),
                    "user_id": user_id,
                    "session_id": session_id
                }
            )
            # AUDIT: Log budget limit reached
            raise BudgetExceededError(
                f"Budget limit of ${self.budget_limit} reached. "
                f"Current total: ${current_total:.2f}",
                context={
                    "current_total": float(current_total),
                    "budget_limit": float(self.budget_limit),
                    "user_id": user_id
                }
            )
        
        # BUDGET: Check if request would exceed limit
        projected_total = current_total + estimated_cost
        if projected_total > self.budget_limit:
            logger.error(
                "Request would exceed budget - blocking",
                extra={
                    "current_total_usd": float(current_total),
                    "estimated_cost_usd": float(estimated_cost),
                    "projected_total_usd": float(projected_total),
                    "budget_limit_usd": float(self.budget_limit),
                    "user_id": user_id,
                    "session_id": session_id
                }
            )
            # AUDIT: Log budget exceeded attempt
            raise BudgetExceededError(
                f"Request would exceed budget limit. "
                f"Current: ${current_total:.2f}, "
                f"Estimated cost: ${estimated_cost:.4f}, "
                f"Limit: ${self.budget_limit}",
                context={
                    "current_total": float(current_total),
                    "estimated_cost": float(estimated_cost),
                    "projected_total": float(projected_total),
                    "budget_limit": float(self.budget_limit),
                    "user_id": user_id
                }
            )
        
        # Check alert thresholds
        self._check_alert_thresholds(projected_total, user_id)
        
        logger.info(
            "Budget check passed",
            extra={
                "current_total_usd": float(current_total),
                "estimated_cost_usd": float(estimated_cost),
                "projected_total_usd": float(projected_total),
                "budget_remaining_usd": float(self.budget_limit - projected_total),
                "user_id": user_id
            }
        )
        
        return True
    
    def _get_current_total(self) -> Decimal:
        """
        Get current total cost from database.
        
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
                "Failed to get current budget total",
                extra={"error": str(e)},
                exc_info=True
            )
            # PRIVACY: Don't expose database errors to user
            raise BudgetExceededError(
                "Unable to verify budget status. Request blocked for safety.",
                context={"error_type": "database_error"},
                original_error=e
            )
    
    def _check_alert_thresholds(
        self,
        projected_total: Decimal,
        user_id: Optional[int] = None
    ):
        """
        Check if projected total crosses alert thresholds.
        
        AUDIT: Logs warnings at 80%, 90%, 95% thresholds.
        
        Args:
            projected_total: Projected total after request
            user_id: Optional user ID for logging
        """
        alert_level = None
        
        if projected_total >= BUDGET_WARNING_THRESHOLDS['exceeded']:
            alert_level = 'exceeded'
        elif projected_total >= BUDGET_WARNING_THRESHOLDS['final']:
            alert_level = 'final'
        elif projected_total >= BUDGET_WARNING_THRESHOLDS['critical']:
            alert_level = 'critical'
        elif projected_total >= BUDGET_WARNING_THRESHOLDS['warning']:
            alert_level = 'warning'
        
        # Only log if we've crossed a new threshold
        if alert_level and alert_level != self._last_alert_level:
            percentage = (projected_total / self.budget_limit) * 100
            
            logger.warning(
                f"Budget alert: {alert_level.upper()} - {percentage:.1f}% of limit",
                extra={
                    "alert_level": alert_level,
                    "projected_total_usd": float(projected_total),
                    "budget_limit_usd": float(self.budget_limit),
                    "percentage": float(percentage),
                    "threshold_usd": float(BUDGET_WARNING_THRESHOLDS[alert_level]),
                    "user_id": user_id
                }
            )
            
            self._last_alert_level = alert_level
    
    def get_budget_status(self) -> Dict[str, Any]:
        """
        Get current budget status.
        
        Returns:
            Dictionary with budget information:
            - current_total: Current cumulative cost
            - budget_limit: Hard budget limit
            - remaining: Remaining budget
            - percentage_used: Percentage of budget used
            - alert_level: Current alert level (if any)
        """
        current_total = self._get_current_total()
        remaining = self.budget_limit - current_total
        percentage_used = (current_total / self.budget_limit) * 100
        
        # Determine alert level
        alert_level = None
        if current_total >= BUDGET_WARNING_THRESHOLDS['exceeded']:
            alert_level = 'exceeded'
        elif current_total >= BUDGET_WARNING_THRESHOLDS['final']:
            alert_level = 'final'
        elif current_total >= BUDGET_WARNING_THRESHOLDS['critical']:
            alert_level = 'critical'
        elif current_total >= BUDGET_WARNING_THRESHOLDS['warning']:
            alert_level = 'warning'
        
        return {
            'current_total': float(current_total),
            'budget_limit': float(self.budget_limit),
            'remaining': float(remaining),
            'percentage_used': float(percentage_used),
            'alert_level': alert_level,
            'thresholds': {
                'warning': float(BUDGET_WARNING_THRESHOLDS['warning']),
                'critical': float(BUDGET_WARNING_THRESHOLDS['critical']),
                'final': float(BUDGET_WARNING_THRESHOLDS['final']),
                'exceeded': float(BUDGET_WARNING_THRESHOLDS['exceeded'])
            }
        }
    
    def get_usage_history(
        self,
        limit: int = 100,
        user_id: Optional[int] = None
    ) -> list[Dict[str, Any]]:
        """
        Get recent AI usage history.
        
        Args:
            limit: Maximum number of records to return
            user_id: Optional filter by user ID
        
        Returns:
            List of usage records
        """
        query = self.db.query(AIUsageTracking).order_by(
            AIUsageTracking.timestamp.desc()
        )
        
        if user_id:
            query = query.filter(AIUsageTracking.user_id == user_id)
        
        records = query.limit(limit).all()
        
        return [
            {
                'timestamp': record.timestamp.isoformat(),
                'model_tier': record.model_tier,
                'model_id': record.model_id,
                'input_tokens': record.input_tokens,
                'output_tokens': record.output_tokens,
                'cost_usd': float(record.cost_usd),
                'cumulative_cost_usd': float(record.cumulative_cost_usd),
                'task_type': record.task_type,
                'request_id': record.request_id
            }
            for record in records
        ]
