"""
Healthcare AI V2 - Movement Analysis SQLAlchemy Models
Database models for pediatric movement analysis system
"""

from typing import Dict, Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    DECIMAL,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.connection import Base


class ReferenceVideo(Base):
    """
    Reference/Standard Video Library
    Stores standard movement demonstration videos uploaded by staff
    """
    
    __tablename__ = "reference_videos"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    video_path = Column(String(500), nullable=True)  # Path to video file or document
    description = Column(Text, nullable=True)  # AI-generated movement description
    
    # Document support (PDF/DOCX)
    document_path = Column(String(500), nullable=True)  # Path to reference document
    document_text = Column(Text, nullable=True)  # Extracted text from document
    
    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    organization_id = Column(Integer, nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    
    # Indexes
    __table_args__ = (
        Index('idx_reference_videos_org_active', 'organization_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<ReferenceVideo(id={self.id}, title='{self.title}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "title": self.title,
            "video_path": self.video_path,
            "description": self.description,
            "document_path": self.document_path,
            "created_by": self.created_by,
            "organization_id": self.organization_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AssessmentRule(Base):
    """
    AI Assessment Rule Definition
    Defines the criteria and prompts for different types of movement assessments
    """
    
    __tablename__ = "assessment_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    index_code = Column(String(100), unique=True, nullable=True, index=True)  # e.g., "01_Core_Gait_and_Alignment"
    category = Column(String(255), nullable=False, index=True)  # e.g., "Walking and Leg Alignment"
    description = Column(Text, nullable=True)  # Detailed description of what this rule assesses
    ai_role = Column(String(255), nullable=True)  # e.g., "Pediatric Gait and Alignment Screener"
    
    # Reference materials
    reference_video_url = Column(Text, nullable=True)  # URL(s) to reference videos
    reference_description = Column(Text, nullable=True)  # Description of the reference standard
    
    # Assessment criteria and instructions
    text_standards = Column(JSONB, nullable=True)  # {"source_files": "...", "rubric": "..."}
    analysis_instruction = Column(Text, nullable=True)  # Instructions for AI analysis
    response_template = Column(JSONB, nullable=True)  # Template for structured response
    
    # Status and metadata
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    organization_id = Column(Integer, nullable=True, index=True)  # NULL = system-wide rule
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    assessments = relationship("Assessment", back_populates="rule")
    creator = relationship("User", foreign_keys=[created_by])
    
    # Indexes
    __table_args__ = (
        Index('idx_assessment_rules_org_active', 'organization_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<AssessmentRule(id={self.id}, category='{self.category}', active={self.is_active})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "index_code": self.index_code,
            "category": self.category,
            "description": self.description,
            "ai_role": self.ai_role,
            "reference_video_url": self.reference_video_url,
            "reference_description": self.reference_description,
            "text_standards": self.text_standards,
            "analysis_instruction": self.analysis_instruction,
            "response_template": self.response_template,
            "is_active": self.is_active,
            "created_by": self.created_by,
            "organization_id": self.organization_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Assessment(Base):
    """
    Movement Analysis Record
    Represents a single video assessment submission and its processing status
    """
    
    __tablename__ = "assessments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey("assessment_rules.id"), nullable=True, index=True)
    
    # Video information
    video_path = Column(String(500), nullable=True)  # Local file path
    video_filename = Column(String(255), nullable=True)  # Original filename
    video_type = Column(String(20), default="local", nullable=False)  # local, youtube
    youtube_url = Column(Text, nullable=True)  # YouTube URL if applicable
    
    # Child information
    age_value = Column(DECIMAL(5, 2), nullable=True)
    age_unit = Column(String(20), nullable=True)  # year, month
    age_group = Column(String(20), nullable=True)  # infant_toddler, child, teen, adult, elderly (optional manual override)
    child_description = Column(Text, nullable=True)  # Optional notes about the child
    
    # Language preference for AI response
    language_preference = Column(String(10), default="en", nullable=False)  # en, zh-HK
    
    # Processing status
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)  # Error details if failed
    
    # Organization scoping
    organization_id = Column(Integer, nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    rule = relationship("AssessmentRule", back_populates="assessments")
    result = relationship("AssessmentResult", back_populates="assessment", uselist=False, cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_assessments_user_status', 'user_id', 'status'),
        Index('idx_assessments_org_created', 'organization_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Assessment(id={self.id}, user_id={self.user_id}, status='{self.status}')>"
    
    def to_dict(self, include_result: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "rule_id": self.rule_id,
            "rule_category": self.rule.category if self.rule else None,
            "video_filename": self.video_filename,
            "video_type": self.video_type,
            "youtube_url": self.youtube_url,
            "age_value": float(self.age_value) if self.age_value else None,
            "age_unit": self.age_unit,
            "age_group": self.age_group,
            "child_description": self.child_description,
            "language_preference": self.language_preference,
            "status": self.status,
            "error_message": self.error_message,
            "organization_id": self.organization_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_result and self.result:
            data["result"] = self.result.to_dict()
        
        return data


class AssessmentResult(Base):
    """
    AI Analysis Result
    Stores the AI-generated assessment report with role-differentiated views
    """
    
    __tablename__ = "assessment_results"
    
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    # Role-differentiated reports
    user_view_md = Column(Text, nullable=True)  # Parent-friendly markdown report
    staff_view_md = Column(Text, nullable=True)  # Professional/detailed report
    storage_json = Column(JSONB, nullable=True)  # Structured data for analytics
    full_response = Column(Text, nullable=True)  # Raw AI response (for debugging)
    
    # Processing metadata
    processing_time_ms = Column(Integer, nullable=True)
    model_used = Column(String(100), nullable=True)  # e.g., "amazon.nova-lite-v1:0"
    frames_analyzed = Column(Integer, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    assessment = relationship("Assessment", back_populates="result")
    
    def __repr__(self):
        return f"<AssessmentResult(id={self.id}, assessment_id={self.assessment_id})>"
    
    def to_dict(self, include_staff_view: bool = False) -> Dict[str, Any]:
        """
        Convert to dictionary for API responses
        
        Args:
            include_staff_view: If True, include staff_view_md (only for authorized users)
        """
        data = {
            "id": self.id,
            "assessment_id": self.assessment_id,
            "user_view_md": self.user_view_md,
            "processing_time_ms": self.processing_time_ms,
            "model_used": self.model_used,
            "frames_analyzed": self.frames_analyzed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        
        if include_staff_view:
            data["staff_view_md"] = self.staff_view_md
            data["storage_json"] = self.storage_json
        
        return data

