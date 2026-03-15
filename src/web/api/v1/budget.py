"""
Budget API Endpoints
===================

API endpoints for monitoring AI budget usage and cost tracking.

CRITICAL: These endpoints provide visibility into the $50 budget limit enforcement.

Features:
- Budget status endpoint (current usage, remaining, alerts)
- Usage history endpoint (paginated cost records)
- Admin-only access (requires admin authentication)

Security:
- Admin authentication required
- No PII in responses (user IDs only)
- Organization-scoped access for org admins
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from src.core.logging import get_logger
from src.database.connection import get_sync_db
from src.database.models.ai_usage import AIUsageTracking
from src.database.models_comprehensive import User
from src.web.auth.dependencies import require_admin
from src.ai.budget_middleware import BudgetProtectionMiddleware, BUDGET_LIMIT_USD

logger = get_logger(__name__)

# Create router
router = APIRouter(
    prefix="/budget",
    tags=["Budget Management"],
    responses={
        401: {"description": "Unauthorized - Authentication required"},
        403: {"description": "Forbidden - Admin access required"},
    }
)


# Response models (using dicts for simplicity)
class BudgetStatusResponse:
    """Budget status response model"""
    budget_limit: float
    current_total: float
    remaining: float
    percentage_used: float
    total_requests: int
    alert_level: Optional[str]


class UsageHistoryItem:
    """Usage history item model"""
    id: int
    timestamp: str
    model_tier: str
    model_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    cumulative_cost_usd: float
    task_type: Optional[str]
    request_id: str


@router.get(
    "/status",
    summary="Get budget status",
    description="Get current AI budget status including usage, remaining budget, and alert level",
    response_description="Budget status with current usage and alerts"
)
async def get_budget_status(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db)
) -> Dict[str, Any]:
    """
    Get current budget status.
    
    SECURITY: Admin authentication required.
    PRIVACY: No PII in response.
    
    Returns:
        Budget status including:
        - budget_limit: Hard budget limit ($50)
        - current_total: Current cumulative cost
        - remaining: Remaining budget
        - percentage_used: Percentage of budget used
        - total_requests: Total number of AI requests
        - alert_level: Current alert level (ok, warning, critical, final, exceeded)
    
    Raises:
        HTTPException: If database error occurs
    """
    try:
        # AUDIT: Log budget status access
        logger.info(
            "Budget status accessed",
            extra={
                "user_id": current_user.id,
                "user_role": current_user.role
            }
        )
        
        # Get budget middleware
        budget_middleware = BudgetProtectionMiddleware(db)
        
        # Get budget status
        status_data = budget_middleware.get_budget_status()
        
        # Get total requests count
        total_requests = db.query(func.count(AIUsageTracking.id)).scalar() or 0
        
        # Add total requests to response
        status_data['total_requests'] = total_requests
        
        # PRIVACY: Log without PII
        logger.info(
            "Budget status retrieved",
            extra={
                "current_total": status_data['current_total'],
                "percentage_used": status_data['percentage_used'],
                "alert_level": status_data['alert_level'],
                "user_id": current_user.id
            }
        )
        
        return status_data
    
    except Exception as e:
        logger.error(
            "Failed to get budget status",
            extra={
                "error": str(e),
                "user_id": current_user.id
            },
            exc_info=True
        )
        # PRIVACY: Don't expose internal errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve budget status"
        )


@router.get(
    "/history",
    summary="Get usage history",
    description="Get paginated AI usage history with optional date filtering",
    response_description="List of AI usage records"
)
async def get_usage_history(
    start_date: Optional[datetime] = Query(
        None,
        description="Filter by start date (ISO 8601 format)"
    ),
    end_date: Optional[datetime] = Query(
        None,
        description="Filter by end date (ISO 8601 format)"
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of records to return"
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of records to skip"
    ),
    model_tier: Optional[str] = Query(
        None,
        description="Filter by model tier (lite or pro)"
    ),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db)
) -> Dict[str, Any]:
    """
    Get AI usage history with pagination and filtering.
    
    SECURITY: Admin authentication required.
    PRIVACY: No PII in response (user IDs only).
    
    Args:
        start_date: Optional start date filter
        end_date: Optional end date filter
        limit: Maximum number of records (default 100, max 1000)
        offset: Number of records to skip (for pagination)
        model_tier: Optional filter by model tier (lite or pro)
        current_user: Current authenticated admin user
        db: Database session
    
    Returns:
        Dictionary with:
        - records: List of usage records
        - total: Total number of matching records
        - limit: Applied limit
        - offset: Applied offset
        - has_more: Whether more records are available
    
    Raises:
        HTTPException: If database error occurs
    """
    try:
        # AUDIT: Log usage history access
        logger.info(
            "Usage history accessed",
            extra={
                "user_id": current_user.id,
                "user_role": current_user.role,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "limit": limit,
                "offset": offset,
                "model_tier": model_tier
            }
        )
        
        # Build query
        query = db.query(AIUsageTracking)
        
        # Apply filters
        if start_date:
            query = query.filter(AIUsageTracking.timestamp >= start_date)
        
        if end_date:
            query = query.filter(AIUsageTracking.timestamp <= end_date)
        
        if model_tier:
            # VALIDATION: Check model tier
            if model_tier not in ['lite', 'pro']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid model_tier. Must be 'lite' or 'pro'"
                )
            query = query.filter(AIUsageTracking.model_tier == model_tier)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        records = (
            query
            .order_by(desc(AIUsageTracking.timestamp))
            .limit(limit)
            .offset(offset)
            .all()
        )
        
        # Convert to dict (PRIVACY: No PII)
        records_data = [
            {
                'id': record.id,
                'timestamp': record.timestamp.isoformat(),
                'model_tier': record.model_tier,
                'model_id': record.model_id,
                'input_tokens': record.input_tokens,
                'output_tokens': record.output_tokens,
                'total_tokens': record.total_tokens,
                'cost_usd': float(record.cost_usd),
                'cumulative_cost_usd': float(record.cumulative_cost_usd),
                'user_id': record.user_id,  # ID only, no PII
                'task_type': record.task_type,
                'request_id': record.request_id
            }
            for record in records
        ]
        
        # Calculate if more records available
        has_more = (offset + limit) < total
        
        # PRIVACY: Log without PII
        logger.info(
            "Usage history retrieved",
            extra={
                "records_returned": len(records_data),
                "total_records": total,
                "user_id": current_user.id
            }
        )
        
        return {
            'records': records_data,
            'total': total,
            'limit': limit,
            'offset': offset,
            'has_more': has_more
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        logger.error(
            "Failed to get usage history",
            extra={
                "error": str(e),
                "user_id": current_user.id
            },
            exc_info=True
        )
        # PRIVACY: Don't expose internal errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage history"
        )


@router.get(
    "/summary",
    summary="Get budget summary",
    description="Get aggregated budget summary with cost breakdown by model tier",
    response_description="Budget summary with cost breakdown"
)
async def get_budget_summary(
    days: int = Query(
        7,
        ge=1,
        le=90,
        description="Number of days to include in summary"
    ),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db)
) -> Dict[str, Any]:
    """
    Get budget summary with cost breakdown.
    
    SECURITY: Admin authentication required.
    PRIVACY: No PII in response.
    
    Args:
        days: Number of days to include (default 7, max 90)
        current_user: Current authenticated admin user
        db: Database session
    
    Returns:
        Dictionary with:
        - budget_limit: Hard budget limit
        - current_total: Current cumulative cost
        - remaining: Remaining budget
        - percentage_used: Percentage of budget used
        - cost_by_tier: Cost breakdown by model tier (lite, pro)
        - requests_by_tier: Request count by model tier
        - period_start: Start of summary period
        - period_end: End of summary period
        - period_cost: Cost during the period
        - period_requests: Requests during the period
    
    Raises:
        HTTPException: If database error occurs
    """
    try:
        # AUDIT: Log summary access
        logger.info(
            "Budget summary accessed",
            extra={
                "user_id": current_user.id,
                "user_role": current_user.role,
                "days": days
            }
        )
        
        # Calculate period
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=days)
        
        # Get overall budget status
        budget_middleware = BudgetProtectionMiddleware(db)
        status_data = budget_middleware.get_budget_status()
        
        # Get period records
        period_records = (
            db.query(AIUsageTracking)
            .filter(AIUsageTracking.timestamp >= period_start)
            .filter(AIUsageTracking.timestamp <= period_end)
            .all()
        )
        
        # Calculate period statistics
        period_cost = sum(float(r.cost_usd) for r in period_records)
        period_requests = len(period_records)
        
        # Calculate cost by tier
        cost_by_tier = {
            'lite': sum(float(r.cost_usd) for r in period_records if r.model_tier == 'lite'),
            'pro': sum(float(r.cost_usd) for r in period_records if r.model_tier == 'pro')
        }
        
        # Calculate requests by tier
        requests_by_tier = {
            'lite': sum(1 for r in period_records if r.model_tier == 'lite'),
            'pro': sum(1 for r in period_records if r.model_tier == 'pro')
        }
        
        # PRIVACY: Log without PII
        logger.info(
            "Budget summary retrieved",
            extra={
                "period_cost": period_cost,
                "period_requests": period_requests,
                "user_id": current_user.id
            }
        )
        
        return {
            'budget_limit': status_data['budget_limit'],
            'current_total': status_data['current_total'],
            'remaining': status_data['remaining'],
            'percentage_used': status_data['percentage_used'],
            'cost_by_tier': cost_by_tier,
            'requests_by_tier': requests_by_tier,
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'period_cost': period_cost,
            'period_requests': period_requests
        }
    
    except Exception as e:
        logger.error(
            "Failed to get budget summary",
            extra={
                "error": str(e),
                "user_id": current_user.id
            },
            exc_info=True
        )
        # PRIVACY: Don't expose internal errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve budget summary"
        )
