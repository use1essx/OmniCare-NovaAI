"""
AI Usage Tracking Model
Tracks all AI API requests for budget monitoring and cost control
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Index
from sqlalchemy.orm import relationship

from src.database.connection import Base


class AIUsageTracking(Base):
    """
    Tracks AI API usage for budget monitoring
    
    BUDGET: Critical for $50 budget limit enforcement
    """
    __tablename__ = "ai_usage_tracking"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Timestamp
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Model information
    model_tier = Column(String(10), nullable=False)  # 'lite' or 'pro'
    model_id = Column(String(100), nullable=False)
    
    # Token usage
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    
    # BUDGET: Cost tracking
    cost_usd = Column(Numeric(10, 6), nullable=False)  # Cost for this request
    cumulative_cost_usd = Column(Numeric(10, 2), nullable=False, index=True)  # Running total
    
    # Context (optional)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(100), nullable=True)
    task_type = Column(String(50), nullable=True)
    
    # Request tracking
    request_id = Column(String(100), unique=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="ai_usage", foreign_keys=[user_id])
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_ai_usage_timestamp', 'timestamp'),
        Index('idx_ai_usage_cumulative', 'cumulative_cost_usd'),
        Index('idx_ai_usage_user', 'user_id'),
        Index('idx_ai_usage_session', 'session_id'),
    )
    
    def __repr__(self):
        return (
            f"<AIUsageTracking(id={self.id}, model_tier={self.model_tier}, "
            f"cost=${self.cost_usd}, cumulative=${self.cumulative_cost_usd})>"
        )
    
    @property
    def total_tokens(self) -> int:
        """Total tokens used in this request"""
        return self.input_tokens + self.output_tokens
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "model_tier": self.model_tier,
            "model_id": self.model_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": float(self.cost_usd),
            "cumulative_cost_usd": float(self.cumulative_cost_usd),
            "user_id": self.user_id,
            "session_id": self.session_id,
            "task_type": self.task_type,
            "request_id": self.request_id,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
