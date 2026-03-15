"""
Cost optimization and analytics for Healthcare AI V2
Usage tracking, budget management, and cost reporting
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from decimal import Decimal
from enum import Enum
import json

from src.core.logging import get_logger


logger = get_logger(__name__)


class BudgetPeriod(Enum):
    """Budget period types"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class CostCategory(Enum):
    """Cost categorization for analytics"""
    EMERGENCY = "emergency"
    ROUTINE = "routine"
    TRAINING = "training"
    DEVELOPMENT = "development"
    RESEARCH = "research"


@dataclass
class BudgetLimit:
    """Budget limit configuration"""
    amount: Decimal
    period: BudgetPeriod
    category: Optional[CostCategory] = None
    user_id: Optional[int] = None
    agent_type: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['amount'] = float(self.amount)
        data['period'] = self.period.value
        data['category'] = self.category.value if self.category else None
        return data


@dataclass
class UsageRecord:
    """Individual usage record for detailed tracking"""
    timestamp: datetime
    model_tier: str
    model_name: str
    agent_type: str
    content_type: str
    urgency_level: str
    user_id: Optional[int]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: Decimal
    processing_time_ms: int
    success: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['cost'] = float(self.cost)
        return data


@dataclass
class CostSummary:
    """Cost summary for a specific period"""
    period_start: datetime
    period_end: datetime
    total_cost: Decimal
    total_requests: int
    total_tokens: int
    average_cost_per_request: Decimal
    model_breakdown: Dict[str, Decimal]
    agent_breakdown: Dict[str, Decimal]
    category_breakdown: Dict[str, Decimal]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['period_start'] = self.period_start.isoformat()
        data['period_end'] = self.period_end.isoformat()
        data['total_cost'] = float(self.total_cost)
        data['average_cost_per_request'] = float(self.average_cost_per_request)
        data['model_breakdown'] = {k: float(v) for k, v in self.model_breakdown.items()}
        data['agent_breakdown'] = {k: float(v) for k, v in self.agent_breakdown.items()}
        data['category_breakdown'] = {k: float(v) for k, v in self.category_breakdown.items()}
        return data


class CostOptimizer:
    """
    Comprehensive cost optimization and analytics system
    Provides budget management, usage tracking, and optimization recommendations
    """
    
    def __init__(self):
        self.usage_records: List[UsageRecord] = []
        self.budget_limits: Dict[str, BudgetLimit] = {}
        self.cost_alerts: List[Dict[str, Any]] = []
        self.optimization_rules: Dict[str, Any] = {}
        self._setup_default_optimization_rules()
        
    def _setup_default_optimization_rules(self):
        """Setup default cost optimization rules"""
        self.optimization_rules = {
            "emergency_threshold": 0.50,  # Use premium models for emergency
            "routine_cost_limit": 0.01,   # Max cost per routine request
            "daily_budget_alert": 0.80,   # Alert at 80% of daily budget
            "model_rotation_enabled": True,  # Enable model rotation for cost savings
            "peak_hours": {  # Use cheaper models during peak hours
                "enabled": False,
                "start_hour": 9,
                "end_hour": 17,
                "preferred_tiers": ["lite", "free"]
            },
            "bulk_discount_threshold": 1000,  # Consider bulk pricing after 1000 requests
            "auto_downgrade": {  # Automatically downgrade models for non-critical tasks
                "enabled": True,
                "conditions": {
                    "low_urgency": True,
                    "simple_tasks": True,
                    "routine_checkups": True
                }
            }
        }
        
    def set_budget_limit(
        self, 
        amount: Decimal, 
        period: BudgetPeriod,
        category: Optional[CostCategory] = None,
        user_id: Optional[int] = None,
        agent_type: Optional[str] = None
    ) -> str:
        """Set budget limit with optional constraints"""
        budget_id = self._generate_budget_id(period, category, user_id, agent_type)
        
        budget_limit = BudgetLimit(
            amount=amount,
            period=period,
            category=category,
            user_id=user_id,
            agent_type=agent_type
        )
        
        self.budget_limits[budget_id] = budget_limit
        
        logger.info(
            f"Budget limit set: {budget_id} = ${float(amount)} per {period.value}",
            extra={
                "budget_id": budget_id,
                "amount": float(amount),
                "period": period.value,
                "category": category.value if category else None,
                "user_id": user_id,
                "agent_type": agent_type
            }
        )
        
        return budget_id
        
    def _generate_budget_id(
        self, 
        period: BudgetPeriod, 
        category: Optional[CostCategory],
        user_id: Optional[int],
        agent_type: Optional[str]
    ) -> str:
        """Generate unique budget ID"""
        parts = [period.value]
        
        if category:
            parts.append(category.value)
        if user_id:
            parts.append(f"user_{user_id}")
        if agent_type:
            parts.append(f"agent_{agent_type}")
            
        return "_".join(parts)
        
    def record_usage(
        self,
        model_tier: str,
        model_name: str,
        agent_type: str,
        content_type: str,
        urgency_level: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost: Decimal,
        processing_time_ms: int,
        success: bool,
        user_id: Optional[int] = None,
        error_message: Optional[str] = None
    ):
        """Record individual usage for cost tracking"""
        usage_record = UsageRecord(
            timestamp=datetime.utcnow(),
            model_tier=model_tier,
            model_name=model_name,
            agent_type=agent_type,
            content_type=content_type,
            urgency_level=urgency_level,
            user_id=user_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost=cost,
            processing_time_ms=processing_time_ms,
            success=success,
            error_message=error_message
        )
        
        self.usage_records.append(usage_record)
        
        # Check budget limits after recording usage
        self._check_budget_limits(usage_record)
        
        logger.debug(
            f"Usage recorded: {model_tier} - ${float(cost)}",
            extra={
                "model_tier": model_tier,
                "agent_type": agent_type,
                "cost": float(cost),
                "tokens": prompt_tokens + completion_tokens,
                "user_id": user_id
            }
        )
        
    def _check_budget_limits(self, usage_record: UsageRecord):
        """Check if usage exceeds budget limits and generate alerts"""
        for budget_id, budget_limit in self.budget_limits.items():
            # Check if budget applies to this usage
            if not self._budget_applies_to_usage(budget_limit, usage_record):
                continue
                
            # Calculate current period usage
            period_start = self._get_period_start(budget_limit.period)
            current_usage = self._calculate_period_usage(
                period_start, 
                datetime.utcnow(),
                budget_limit
            )
            
            # Check if approaching or exceeding budget
            usage_percentage = (current_usage / budget_limit.amount) * 100
            
            if usage_percentage >= 100:
                self._create_budget_alert(
                    budget_id=budget_id,
                    alert_type="BUDGET_EXCEEDED",
                    current_usage=current_usage,
                    budget_limit=budget_limit.amount,
                    usage_percentage=usage_percentage
                )
            elif usage_percentage >= (self.optimization_rules["daily_budget_alert"] * 100):
                self._create_budget_alert(
                    budget_id=budget_id,
                    alert_type="BUDGET_WARNING",
                    current_usage=current_usage,
                    budget_limit=budget_limit.amount,
                    usage_percentage=usage_percentage
                )
                
    def _budget_applies_to_usage(self, budget_limit: BudgetLimit, usage_record: UsageRecord) -> bool:
        """Check if budget limit applies to specific usage record"""
        if budget_limit.user_id and budget_limit.user_id != usage_record.user_id:
            return False
        if budget_limit.agent_type and budget_limit.agent_type != usage_record.agent_type:
            return False
        if budget_limit.category:
            # Map urgency level to cost category
            category_mapping = {
                "emergency": CostCategory.EMERGENCY,
                "high": CostCategory.EMERGENCY,
                "medium": CostCategory.ROUTINE,
                "low": CostCategory.ROUTINE
            }
            usage_category = category_mapping.get(usage_record.urgency_level, CostCategory.ROUTINE)
            if budget_limit.category != usage_category:
                return False
        return True
        
    def _get_period_start(self, period: BudgetPeriod) -> datetime:
        """Get start datetime for budget period"""
        now = datetime.utcnow()
        
        if period == BudgetPeriod.DAILY:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == BudgetPeriod.WEEKLY:
            days_since_monday = now.weekday()
            return (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == BudgetPeriod.MONTHLY:
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == BudgetPeriod.YEARLY:
            return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
            
    def _calculate_period_usage(
        self, 
        period_start: datetime, 
        period_end: datetime,
        budget_limit: BudgetLimit
    ) -> Decimal:
        """Calculate total usage for specific period and budget constraints"""
        total_cost = Decimal('0.0')
        
        for record in self.usage_records:
            if (record.timestamp >= period_start and 
                record.timestamp <= period_end and
                self._budget_applies_to_usage(budget_limit, record)):
                total_cost += record.cost
                
        return total_cost
        
    def _create_budget_alert(
        self,
        budget_id: str,
        alert_type: str,
        current_usage: Decimal,
        budget_limit: Decimal,
        usage_percentage: float
    ):
        """Create budget alert"""
        alert = {
            "timestamp": datetime.utcnow().isoformat(),
            "budget_id": budget_id,
            "alert_type": alert_type,
            "current_usage": float(current_usage),
            "budget_limit": float(budget_limit),
            "usage_percentage": usage_percentage,
            "severity": "HIGH" if alert_type == "BUDGET_EXCEEDED" else "MEDIUM"
        }
        
        self.cost_alerts.append(alert)
        
        logger.warning(
            f"Budget alert: {alert_type} for {budget_id}",
            extra=alert
        )
        
    def get_cost_summary(
        self, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[int] = None,
        agent_type: Optional[str] = None
    ) -> CostSummary:
        """Generate comprehensive cost summary for specified period"""
        if start_date is None:
            start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        if end_date is None:
            end_date = datetime.utcnow()
            
        # Filter records for the period
        filtered_records = [
            record for record in self.usage_records
            if (record.timestamp >= start_date and 
                record.timestamp <= end_date and
                (user_id is None or record.user_id == user_id) and
                (agent_type is None or record.agent_type == agent_type))
        ]
        
        if not filtered_records:
            return CostSummary(
                period_start=start_date,
                period_end=end_date,
                total_cost=Decimal('0.0'),
                total_requests=0,
                total_tokens=0,
                average_cost_per_request=Decimal('0.0'),
                model_breakdown={},
                agent_breakdown={},
                category_breakdown={}
            )
            
        # Calculate totals
        total_cost = sum(record.cost for record in filtered_records)
        total_requests = len(filtered_records)
        total_tokens = sum(record.total_tokens for record in filtered_records)
        average_cost_per_request = total_cost / total_requests if total_requests > 0 else Decimal('0.0')
        
        # Calculate breakdowns
        model_breakdown = {}
        agent_breakdown = {}
        category_breakdown = {}
        
        for record in filtered_records:
            # Model breakdown
            if record.model_tier not in model_breakdown:
                model_breakdown[record.model_tier] = Decimal('0.0')
            model_breakdown[record.model_tier] += record.cost
            
            # Agent breakdown
            if record.agent_type not in agent_breakdown:
                agent_breakdown[record.agent_type] = Decimal('0.0')
            agent_breakdown[record.agent_type] += record.cost
            
            # Category breakdown (based on urgency level)
            category_mapping = {
                "emergency": "Emergency",
                "high": "Emergency", 
                "medium": "Routine",
                "low": "Routine"
            }
            category = category_mapping.get(record.urgency_level, "Routine")
            if category not in category_breakdown:
                category_breakdown[category] = Decimal('0.0')
            category_breakdown[category] += record.cost
            
        return CostSummary(
            period_start=start_date,
            period_end=end_date,
            total_cost=total_cost,
            total_requests=total_requests,
            total_tokens=total_tokens,
            average_cost_per_request=average_cost_per_request,
            model_breakdown=model_breakdown,
            agent_breakdown=agent_breakdown,
            category_breakdown=category_breakdown
        )
        
    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """Generate cost optimization recommendations based on usage patterns"""
        recommendations = []
        
        # Analyze last 7 days of usage
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        summary = self.get_cost_summary(start_date, end_date)
        
        if summary.total_requests == 0:
            return recommendations
            
        # Check for high-cost models being overused
        for model_tier, cost in summary.model_breakdown.items():
            cost_percentage = (cost / summary.total_cost) * 100
            if cost_percentage > 50 and model_tier == "premium":
                recommendations.append({
                    "type": "MODEL_OPTIMIZATION",
                    "priority": "HIGH",
                    "title": f"High usage of expensive model: {model_tier}",
                    "description": f"{model_tier} accounts for {cost_percentage:.1f}% of costs",
                    "suggestion": "Consider using lite models for routine queries to reduce costs",
                    "potential_savings": float(cost * Decimal('0.3'))  # Estimated 30% savings
                })
                
        # Check for inefficient agent usage
        for agent_type, cost in summary.agent_breakdown.items():
            agent_records = [r for r in self.usage_records if r.agent_type == agent_type]
            if len(agent_records) > 0:
                avg_cost = cost / len(agent_records)
                if avg_cost > Decimal('0.02'):  # High average cost per request
                    recommendations.append({
                        "type": "AGENT_OPTIMIZATION",
                        "priority": "MEDIUM",
                        "title": f"High average cost for {agent_type} agent",
                        "description": f"Average cost per request: ${float(avg_cost):.4f}",
                        "suggestion": "Review prompt complexity and model selection for this agent",
                        "potential_savings": float(cost * Decimal('0.2'))  # Estimated 20% savings
                    })
                    
        # Check for peak hour usage
        if self.optimization_rules["peak_hours"]["enabled"]:
            peak_usage = self._analyze_peak_hour_usage()
            if peak_usage["cost_percentage"] > 40:
                recommendations.append({
                    "type": "SCHEDULING_OPTIMIZATION",
                    "priority": "LOW",
                    "title": "High peak hour usage detected",
                    "description": f"Peak hours account for {peak_usage['cost_percentage']:.1f}% of costs",
                    "suggestion": "Consider deferring non-urgent requests to off-peak hours",
                    "potential_savings": float(summary.total_cost * Decimal('0.15'))  # Estimated 15% savings
                })
                
        # Budget utilization recommendations
        for budget_id, budget_limit in self.budget_limits.items():
            period_start = self._get_period_start(budget_limit.period)
            current_usage = self._calculate_period_usage(period_start, end_date, budget_limit)
            utilization = (current_usage / budget_limit.amount) * 100
            
            if utilization > 90:
                recommendations.append({
                    "type": "BUDGET_ALERT",
                    "priority": "HIGH",
                    "title": f"Budget nearly exhausted: {budget_id}",
                    "description": f"Current utilization: {utilization:.1f}%",
                    "suggestion": "Consider using cheaper models or reducing non-essential requests",
                    "remaining_budget": float(budget_limit.amount - current_usage)
                })
                
        return recommendations
        
    def _analyze_peak_hour_usage(self) -> Dict[str, float]:
        """Analyze usage during peak hours"""
        peak_start = self.optimization_rules["peak_hours"]["start_hour"]
        peak_end = self.optimization_rules["peak_hours"]["end_hour"]
        
        total_cost = Decimal('0.0')
        peak_cost = Decimal('0.0')
        
        for record in self.usage_records:
            total_cost += record.cost
            hour = record.timestamp.hour
            if peak_start <= hour <= peak_end:
                peak_cost += record.cost
                
        cost_percentage = (peak_cost / total_cost * 100) if total_cost > 0 else 0
        
        return {
            "peak_cost": float(peak_cost),
            "total_cost": float(total_cost),
            "cost_percentage": cost_percentage
        }
        
    def get_model_efficiency_report(self) -> Dict[str, Any]:
        """Generate model efficiency report"""
        model_stats = {}
        
        for record in self.usage_records:
            if record.model_tier not in model_stats:
                model_stats[record.model_tier] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "total_cost": Decimal('0.0'),
                    "total_tokens": 0,
                    "total_time_ms": 0
                }
                
            stats = model_stats[record.model_tier]
            stats["total_requests"] += 1
            if record.success:
                stats["successful_requests"] += 1
            stats["total_cost"] += record.cost
            stats["total_tokens"] += record.total_tokens
            stats["total_time_ms"] += record.processing_time_ms
            
        # Calculate efficiency metrics
        efficiency_report = {}
        for model_tier, stats in model_stats.items():
            if stats["total_requests"] > 0:
                efficiency_report[model_tier] = {
                    "success_rate": (stats["successful_requests"] / stats["total_requests"]) * 100,
                    "average_cost_per_request": float(stats["total_cost"] / stats["total_requests"]),
                    "average_tokens_per_request": stats["total_tokens"] / stats["total_requests"],
                    "average_response_time_ms": stats["total_time_ms"] / stats["total_requests"],
                    "cost_per_token": float(stats["total_cost"] / stats["total_tokens"]) if stats["total_tokens"] > 0 else 0,
                    "total_requests": stats["total_requests"]
                }
                
        return efficiency_report
        
    def export_usage_data(self, format: str = "json") -> str:
        """Export usage data in specified format"""
        if format.lower() == "json":
            data = {
                "export_timestamp": datetime.utcnow().isoformat(),
                "total_records": len(self.usage_records),
                "usage_records": [record.to_dict() for record in self.usage_records],
                "budget_limits": {k: v.to_dict() for k, v in self.budget_limits.items()},
                "cost_alerts": self.cost_alerts,
                "optimization_rules": self.optimization_rules
            }
            return json.dumps(data, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported export format: {format}")
            
    def clear_old_records(self, days_to_keep: int = 90):
        """Clear usage records older than specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        old_count = len(self.usage_records)
        self.usage_records = [
            record for record in self.usage_records 
            if record.timestamp >= cutoff_date
        ]
        new_count = len(self.usage_records)
        
        logger.info(f"Cleared {old_count - new_count} old usage records")
        
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active cost alerts"""
        # Return alerts from last 24 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        return [
            alert for alert in self.cost_alerts
            if datetime.fromisoformat(alert["timestamp"]) >= cutoff_time
        ]


# Global cost optimizer instance
_cost_optimizer: Optional[CostOptimizer] = None


def get_cost_optimizer() -> CostOptimizer:
    """Get or create the global cost optimizer instance"""
    global _cost_optimizer
    if _cost_optimizer is None:
        _cost_optimizer = CostOptimizer()
    return _cost_optimizer
