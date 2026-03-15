"""
Load Testing Models

SQLAlchemy models for load testing tables.
These tables store test execution data, user simulations, messages, and quality issues.

IMPORTANT: These are temporary tables for QA testing and will be removed after
testing is complete and improvements are implemented.
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean,
    ForeignKey, CheckConstraint, Index, ARRAY, Numeric
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.connection import Base


class LoadTestRun(Base):
    """
    Load test execution metadata and results.
    
    Tracks overall test configuration, execution status, and summary metrics.
    
    Security Notes:
    - PRIVACY: No PII stored, only test metadata
    - AUDIT: All test runs logged for tracking
    - ISOLATION: Test data separate from production
    """
    
    __tablename__ = "load_test_runs"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Test identification
    test_name = Column(String(255), nullable=False)
    environment = Column(String(50), nullable=False)
    
    # Configuration
    concurrent_users = Column(Integer, nullable=False)
    messages_per_user = Column(Integer, nullable=False)
    scenario_categories = Column(ARRAY(Text), nullable=False)
    
    # Execution
    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    status = Column(String(50), nullable=False, index=True)
    
    # Results summary
    total_messages = Column(Integer, server_default="0", nullable=False)
    successful_messages = Column(Integer, server_default="0", nullable=False)
    failed_messages = Column(Integer, server_default="0", nullable=False)
    avg_response_time_ms = Column(Integer, nullable=True)
    
    # Metadata
    config_json = Column(JSONB, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled')",
            name='ck_load_test_runs_status'
        ),
    )
    
    # Relationships
    users = relationship("LoadTestUser", back_populates="test_run", cascade="all, delete-orphan")
    messages = relationship("LoadTestMessage", back_populates="test_run", cascade="all, delete-orphan")
    quality_issues = relationship("LoadTestQualityIssue", back_populates="test_run", cascade="all, delete-orphan")
    
    def __repr__(self):
        return (
            f"<LoadTestRun(id={self.id}, test_name='{self.test_name}', "
            f"status='{self.status}', users={self.concurrent_users})>"
        )


class LoadTestUser(Base):
    """
    Simulated test user instance.
    
    Represents a single user in the load test with connection tracking,
    message counts, and execution status.
    
    Security Notes:
    - PRIVACY: No real user data, only test user IDs
    - ORGANIZATION: Distributed across organizations for isolation testing
    """
    
    __tablename__ = "load_test_users"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    test_run_id = Column(Integer, ForeignKey("load_test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_index = Column(Integer, nullable=False)
    
    # User configuration
    scenario_category = Column(String(100), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    language = Column(String(10), nullable=False)
    
    # Connection
    session_id = Column(String(255), nullable=False)
    connected_at = Column(DateTime(timezone=True), nullable=True)
    disconnected_at = Column(DateTime(timezone=True), nullable=True)
    connection_duration_seconds = Column(Integer, nullable=True)
    
    # Execution
    messages_sent = Column(Integer, server_default="0", nullable=False)
    messages_received = Column(Integer, server_default="0", nullable=False)
    errors_encountered = Column(Integer, server_default="0", nullable=False)
    
    # Status
    status = Column(String(50), nullable=False, index=True)
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('connecting', 'active', 'completed', 'failed')",
            name='ck_load_test_users_status'
        ),
    )
    
    # Relationships
    test_run = relationship("LoadTestRun", back_populates="users")
    messages = relationship("LoadTestMessage", back_populates="test_user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return (
            f"<LoadTestUser(id={self.id}, user_index={self.user_index}, "
            f"status='{self.status}', messages={self.messages_sent})>"
        )


class LoadTestMessage(Base):
    """
    Individual message exchange in load test.
    
    Captures complete message data including user message, chatbot response,
    timing, RAG documents, downloads, and safety validation.
    
    Security Notes:
    - PRIVACY: Test messages only, no real patient data
    - AUDIT: All messages logged for quality analysis
    """
    
    __tablename__ = "load_test_messages"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    test_run_id = Column(Integer, ForeignKey("load_test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    test_user_id = Column(Integer, ForeignKey("load_test_users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Message content
    message_index = Column(Integer, nullable=False)
    user_message = Column(Text, nullable=False)
    agent_response = Column(Text, nullable=True)
    
    # Agent information
    agent_name = Column(String(100), nullable=True)
    agent_type = Column(String(50), nullable=True)
    
    # Timing
    sent_at = Column(DateTime(timezone=True), nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    
    # RAG information
    rag_documents = Column(JSONB, nullable=True)
    rag_query_time_ms = Column(Integer, nullable=True)
    
    # Document downloads
    download_links = Column(JSONB, nullable=True)
    
    # Safety validation
    safety_triggered = Column(Boolean, server_default="false", nullable=False)
    risk_level = Column(String(20), nullable=True)
    risk_assessment = Column(JSONB, nullable=True)
    
    # Error handling
    is_error = Column(Boolean, server_default="false", nullable=False)
    error_message = Column(Text, nullable=True)
    is_fallback = Column(Boolean, server_default="false", nullable=False)
    
    # Relationships
    test_run = relationship("LoadTestRun", back_populates="messages")
    test_user = relationship("LoadTestUser", back_populates="messages")
    quality_issues = relationship("LoadTestQualityIssue", back_populates="message", cascade="all, delete-orphan")
    
    def __repr__(self):
        return (
            f"<LoadTestMessage(id={self.id}, user_id={self.test_user_id}, "
            f"index={self.message_index}, response_time={self.response_time_ms}ms)>"
        )


class LoadTestQualityIssue(Base):
    """
    Quality issue identified in chatbot response.
    
    Tracks quality problems, severity, and recommendations for improvement.
    
    Security Notes:
    - PRIVACY: Contains test data only
    - AUDIT: All issues logged for quality tracking
    """
    
    __tablename__ = "load_test_quality_issues"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    test_run_id = Column(Integer, ForeignKey("load_test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("load_test_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Issue classification
    issue_type = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    
    # Issue details
    description = Column(Text, nullable=False)
    example_text = Column(Text, nullable=True)
    
    # Quality scores
    clarity_score = Column(Numeric(precision=3, scale=2), nullable=True)
    completeness_score = Column(Numeric(precision=3, scale=2), nullable=True)
    appropriateness_score = Column(Numeric(precision=3, scale=2), nullable=True)
    
    # Recommendations
    recommendation = Column(Text, nullable=True)
    
    # Metadata
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low')",
            name='ck_load_test_quality_issues_severity'
        ),
    )
    
    # Relationships
    test_run = relationship("LoadTestRun", back_populates="quality_issues")
    message = relationship("LoadTestMessage", back_populates="quality_issues")
    
    def __repr__(self):
        return (
            f"<LoadTestQualityIssue(id={self.id}, type='{self.issue_type}', "
            f"severity='{self.severity}')>"
        )
