"""
SQLAlchemy Models for Social Worker Hub

Defines ORM models for:
- CaseFile: Core case management
- Alert: Real-time alerts with debouncing
- ProfessionalReport: Generated reports
- Intervention: Interventions for cases
- SafetyPlan: Crisis safety plans
- CaseNote: Detailed case notes
"""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer, 
    String, Text, CheckConstraint
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship

from ..database.connection import Base


class CaseFile(Base):
    """
    Core case management model.
    
    Tracks cases for children being supported, including
    risk assessment, goals, interventions, and notes.
    """
    
    __tablename__ = 'case_files'
    
    id = Column(Integer, primary_key=True)
    case_number = Column(String(50), unique=True, nullable=False)
    
    # Parties
    child_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    social_worker_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    supervisor_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    
    # Status
    status = Column(String(20), default='open', nullable=False)
    priority = Column(String(20), default='medium', nullable=False)
    
    # Risk
    risk_level = Column(Integer)
    risk_category = Column(String(50))
    last_risk_assessment = Column(DateTime(timezone=True))
    
    # Content
    summary = Column(Text)
    presenting_concerns = Column(Text)
    
    # Goals and Interventions
    goals = Column(JSONB, default=[])
    interventions = Column(JSONB, default=[])
    notes = Column(JSONB, default=[])
    outcomes = Column(JSONB, default={})
    
    # Family
    family_composition = Column(JSONB, default={})
    emergency_contacts = Column(JSONB, default=[])
    
    # Dates
    opened_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_review = Column(DateTime(timezone=True))
    next_review = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))
    closure_reason = Column(Text)
    
    # Assignment
    assigned_at = Column(DateTime(timezone=True))
    reassignment_history = Column(JSONB, default=[])
    
    # Extra Data
    tags = Column(ARRAY(Text), default=[])
    extra_data = Column('metadata', JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    alerts = relationship('Alert', back_populates='case', foreign_keys='Alert.case_id')
    reports = relationship('ProfessionalReport', back_populates='case')
    interventions_rel = relationship('Intervention', back_populates='case')
    safety_plans = relationship('SafetyPlan', back_populates='case')
    case_notes = relationship('CaseNote', back_populates='case')
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'monitoring', 'review', 'escalated', 'closed', 'pending_assignment')",
            name='chk_case_status'
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent', 'critical')",
            name='chk_case_priority'
        ),
        CheckConstraint(
            "risk_category IN ('low_risk', 'moderate_risk', 'high_risk', 'critical_risk') OR risk_category IS NULL",
            name='chk_risk_category'
        ),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'case_number': self.case_number,
            'child_id': self.child_id,
            'social_worker_id': self.social_worker_id,
            'status': self.status,
            'priority': self.priority,
            'risk_level': self.risk_level,
            'risk_category': self.risk_category,
            'summary': self.summary,
            'presenting_concerns': self.presenting_concerns,
            'goals': self.goals,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'next_review': self.next_review.isoformat() if self.next_review else None,
            'tags': self.tags,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Alert(Base):
    """
    Real-time alerts for social workers.
    
    Supports debouncing to prevent alert spam and
    includes severity/priority levels for triage.
    """
    
    __tablename__ = 'alerts'
    
    id = Column(Integer, primary_key=True)
    
    # Source
    session_id = Column(String(255), nullable=False)
    case_id = Column(Integer, ForeignKey('case_files.id', ondelete='SET NULL'))
    child_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    
    # Classification
    alert_type = Column(String(50), nullable=False)
    severity = Column(Integer, nullable=False)  # 1-5
    priority = Column(String(20), default='medium', nullable=False)
    
    # Content
    title = Column(String(255))
    message = Column(Text, nullable=False)
    context = Column(JSONB, default={})
    
    # Detection
    detected_by = Column(String(100))
    skill_involved = Column(String(50))
    trigger_reason = Column(Text)
    trigger_data = Column(JSONB, default={})
    
    # Action
    recommended_action = Column(Text)
    action_urgency = Column(String(20))
    
    # Resolution
    resolved = Column(Boolean, default=False)
    resolved_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    resolved_at = Column(DateTime(timezone=True))
    resolution_notes = Column(Text)
    resolution_action = Column(String(100))
    
    # Assignment
    assigned_to = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    assigned_at = Column(DateTime(timezone=True))
    
    # Debouncing
    debounce_key = Column(String(255))
    parent_alert_id = Column(Integer, ForeignKey('alerts.id', ondelete='SET NULL'))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    case = relationship('CaseFile', back_populates='alerts', foreign_keys=[case_id])
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "alert_type IN ('emotion_concern', 'behavior_concern', 'risk_detected', 'emergency', "
            "'safety_flag', 'session_flag', 'questionnaire_flag', 'pattern_detected', "
            "'intervention_needed', 'follow_up_required', 'milestone_reached')",
            name='chk_alert_type'
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent')",
            name='chk_alert_priority'
        ),
        CheckConstraint(
            "severity >= 1 AND severity <= 5",
            name='chk_alert_severity'
        ),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'case_id': self.case_id,
            'child_id': self.child_id,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'priority': self.priority,
            'title': self.title,
            'message': self.message,
            'context': self.context,
            'detected_by': self.detected_by,
            'recommended_action': self.recommended_action,
            'resolved': self.resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'assigned_to': self.assigned_to,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ProfessionalReport(Base):
    """
    Generated professional reports for cases.
    
    Supports PDF and DOCX generation with various
    report types (progress, initial, final, etc.)
    """
    
    __tablename__ = 'professional_reports'
    
    id = Column(Integer, primary_key=True)
    
    # Association
    case_id = Column(Integer, ForeignKey('case_files.id', ondelete='CASCADE'), nullable=False)
    child_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    
    # Identification
    report_number = Column(String(50), unique=True)
    
    # Classification
    report_type = Column(String(50), nullable=False)
    report_category = Column(String(50))
    
    # Content
    title = Column(String(500), nullable=False)
    summary = Column(Text)
    content = Column(Text)  # Markdown/HTML
    
    # Files
    pdf_path = Column(String(1000))
    docx_path = Column(String(1000))
    file_size = Column(Integer)
    
    # Features
    includes_charts = Column(Boolean, default=False)
    includes_recommendations = Column(Boolean, default=False)
    includes_assessment_scores = Column(Boolean, default=False)
    includes_timeline = Column(Boolean, default=False)
    
    # Period
    period_start = Column(Date)
    period_end = Column(Date)
    
    # Language
    language = Column(String(10), default='en')
    
    # Generation
    generated_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=False)
    generation_method = Column(String(50), default='manual')
    template_used = Column(String(100))
    
    # Review
    review_status = Column(String(50), default='draft')
    reviewed_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    reviewed_at = Column(DateTime(timezone=True))
    review_notes = Column(Text)
    
    # Distribution
    shared_with = Column(JSONB, default=[])
    distribution_date = Column(DateTime(timezone=True))
    
    # Extra Data
    extra_data = Column('metadata', JSONB, default={})
    
    # Timestamps
    generated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    case = relationship('CaseFile', back_populates='reports')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'report_number': self.report_number,
            'report_type': self.report_type,
            'title': self.title,
            'summary': self.summary,
            'pdf_path': self.pdf_path,
            'review_status': self.review_status,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
        }


class Intervention(Base):
    """
    Tracks interventions for cases.
    
    Includes therapy sessions, support programs,
    and other intervention types.
    """
    
    __tablename__ = 'interventions'
    
    id = Column(Integer, primary_key=True)
    
    # Association
    case_id = Column(Integer, ForeignKey('case_files.id', ondelete='CASCADE'), nullable=False)
    child_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    
    # Details
    intervention_type = Column(String(100), nullable=False)
    title = Column(String(255))
    description = Column(Text)
    
    # Goals
    goals = Column(JSONB, default=[])
    target_outcomes = Column(JSONB, default=[])
    
    # Schedule
    frequency = Column(String(50))
    duration_minutes = Column(Integer)
    total_sessions_planned = Column(Integer)
    sessions_completed = Column(Integer, default=0)
    
    # Timeline
    start_date = Column(Date)
    end_date = Column(Date)
    next_session = Column(Date)
    
    # Status
    status = Column(String(20), default='planned')
    
    # Provider
    provider_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    provider_name = Column(String(255))
    provider_organization = Column(String(255))
    external_provider = Column(Boolean, default=False)
    
    # Effectiveness
    effectiveness_rating = Column(Integer)
    progress_notes = Column(JSONB, default=[])
    outcomes = Column(JSONB, default={})
    
    # Barriers
    barriers = Column(Text)
    adjustments_made = Column(Text)
    
    # Extra Data
    extra_data = Column('metadata', JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    case = relationship('CaseFile', back_populates='interventions_rel')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'intervention_type': self.intervention_type,
            'title': self.title,
            'status': self.status,
            'frequency': self.frequency,
            'sessions_completed': self.sessions_completed,
            'total_sessions_planned': self.total_sessions_planned,
            'next_session': self.next_session.isoformat() if self.next_session else None,
        }


class SafetyPlan(Base):
    """
    Crisis safety plans for high-risk cases.
    
    Includes warning signs, coping strategies,
    support contacts, and safety measures.
    """
    
    __tablename__ = 'safety_plans'
    
    id = Column(Integer, primary_key=True)
    
    # Association
    case_id = Column(Integer, ForeignKey('case_files.id', ondelete='CASCADE'), nullable=False)
    child_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    
    # Version
    plan_version = Column(Integer, default=1)
    is_current = Column(Boolean, default=True)
    
    # Risk Factors
    risk_factors = Column(JSONB, default=[])
    protective_factors = Column(JSONB, default=[])
    
    # Warning Signs
    warning_signs = Column(JSONB, default=[])
    
    # Coping
    coping_strategies = Column(JSONB, default={})
    
    # Support
    support_contacts = Column(JSONB, default=[])
    emergency_contacts = Column(JSONB, default=[])
    professional_contacts = Column(JSONB, default=[])
    
    # Safety
    safety_measures = Column(JSONB, default=[])
    environment_assessment = Column(JSONB, default={})
    means_restriction = Column(JSONB, default={})
    
    # Reasons for Living
    reasons_for_living = Column(JSONB, default=[])
    
    # Management
    created_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=False)
    approved_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    approved_at = Column(DateTime(timezone=True))
    
    # Review
    last_reviewed = Column(DateTime(timezone=True))
    next_review = Column(DateTime(timezone=True))
    review_frequency = Column(String(50), default='monthly')
    
    # Status
    status = Column(String(20), default='active')
    
    # Acknowledgment
    child_acknowledged = Column(Boolean, default=False)
    child_acknowledged_at = Column(DateTime(timezone=True))
    parent_acknowledged = Column(Boolean, default=False)
    parent_acknowledged_at = Column(DateTime(timezone=True))
    
    # Notes
    additional_notes = Column(Text)
    
    # Extra Data
    extra_data = Column('metadata', JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    case = relationship('CaseFile', back_populates='safety_plans')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'child_id': self.child_id,
            'plan_version': self.plan_version,
            'is_current': self.is_current,
            'status': self.status,
            'warning_signs': self.warning_signs,
            'coping_strategies': self.coping_strategies,
            'support_contacts': self.support_contacts,
            'emergency_contacts': self.emergency_contacts,
            'next_review': self.next_review.isoformat() if self.next_review else None,
        }


class CaseNote(Base):
    """
    Detailed case notes and contact logs.
    """
    
    __tablename__ = 'case_notes'
    
    id = Column(Integer, primary_key=True)
    
    # Association
    case_id = Column(Integer, ForeignKey('case_files.id', ondelete='CASCADE'), nullable=False)
    
    # Content
    note_type = Column(String(50), nullable=False)
    title = Column(String(255))
    content = Column(Text, nullable=False)
    
    # Contact Info
    contact_type = Column(String(50))
    contact_with = Column(String(255))
    contact_date = Column(DateTime(timezone=True))
    contact_duration_minutes = Column(Integer)
    
    # Follow-up
    requires_follow_up = Column(Boolean, default=False)
    follow_up_date = Column(Date)
    follow_up_notes = Column(Text)
    follow_up_completed = Column(Boolean, default=False)
    
    # Visibility
    is_confidential = Column(Boolean, default=False)
    visible_to_roles = Column(ARRAY(Text), default=['social_worker', 'supervisor', 'admin'])
    
    # Author
    author_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=False)
    
    # Attachments
    attachments = Column(JSONB, default=[])
    
    # Timestamps
    note_date = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    case = relationship('CaseFile', back_populates='case_notes')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'note_type': self.note_type,
            'title': self.title,
            'content': self.content,
            'contact_type': self.contact_type,
            'requires_follow_up': self.requires_follow_up,
            'follow_up_date': self.follow_up_date.isoformat() if self.follow_up_date else None,
            'note_date': self.note_date.isoformat() if self.note_date else None,
        }

