"""
SQLAlchemy models for multi-stage AI questionnaire generation
"""
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, DECIMAL, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database.models_comprehensive import Base


class QuestionnaireAnalysis(Base):
    """Store AI analysis results for document processing"""
    
    __tablename__ = "questionnaire_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    document_hash = Column(String(64), unique=True, nullable=False, index=True)
    structure_analysis = Column(JSONB)
    domain_analysis = Column(JSONB)
    analysis_map = Column(JSONB)
    models_used = Column(ARRAY(Text))
    processing_time_seconds = Column(Integer)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    
    # NEW: Summary and document metadata fields
    document_summary = Column(Text)  # Executive summary for AI agent
    document_filename = Column(String(255))  # Original filename
    document_type = Column(String(50))  # PDF, DOCX, image, etc.
    document_size_bytes = Column(Integer)  # File size
    key_insights = Column(JSONB)  # Structured insights for AI agent
    
    # Relationships
    candidates = relationship("GeneratedQuestionCandidate", back_populates="analysis", cascade="all, delete-orphan")
    knowledge_bases = relationship("QuestionnaireKnowledgeBase", back_populates="analysis", cascade="all, delete-orphan")
    jobs = relationship("AIGenerationJob", back_populates="analysis")
    
    def __repr__(self):
        return f"<QuestionnaireAnalysis(id={self.id}, hash='{self.document_hash[:8]}...')>"


class GeneratedQuestionCandidate(Base):
    """Store question candidates before validation and selection"""
    
    __tablename__ = "generated_question_candidates"
    
    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("questionnaire_analyses.id"), nullable=False, index=True)
    question_data = Column(JSONB, nullable=False)
    generator_instance = Column(String(50))  # "nova-lite-1", "nova-pro-1", etc.
    model_used = Column(String(100))
    focus_area = Column(String(50))
    quality_score = Column(DECIMAL(5, 2))
    relevance_score = Column(DECIMAL(5, 2))
    uniqueness_score = Column(DECIMAL(5, 2))
    overall_score = Column(DECIMAL(5, 2))
    validation_feedback = Column(JSONB)
    status = Column(String(20), nullable=False, server_default="candidate")  # candidate, validated, rejected, selected
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    
    # Relationships
    analysis = relationship("QuestionnaireAnalysis", back_populates="candidates")
    
    __table_args__ = (
        Index('idx_candidates_status', 'status'),
        Index('idx_candidates_overall_score', 'overall_score'),
    )
    
    def __repr__(self):
        return f"<QuestionCandidate(id={self.id}, instance='{self.generator_instance}', score={self.overall_score})>"


class QuestionnaireKnowledgeBase(Base):
    """Link knowledge base entries to questionnaires"""
    
    __tablename__ = "questionnaire_knowledge_bases"
    
    id = Column(Integer, primary_key=True, index=True)
    questionnaire_id = Column(Integer, ForeignKey("questionnaire_banks.id"), index=True)
    analysis_id = Column(Integer, ForeignKey("questionnaire_analyses.id"), nullable=False, index=True)
    knowledge_base_data = Column(JSONB, nullable=False)
    summary = Column(Text)
    key_concepts = Column(JSONB)
    scoring_guidelines = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    
    # Relationships
    analysis = relationship("QuestionnaireAnalysis", back_populates="knowledge_bases")
    
    def __repr__(self):
        return f"<QuestionnaireKnowledgeBase(id={self.id}, questionnaire_id={self.questionnaire_id})>"


class AIGenerationJob(Base):
    """Track AI generation jobs for progress monitoring"""
    
    __tablename__ = "ai_generation_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(UUID, unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, server_default="queued")  # queued, analyzing, generating, validating, completed, failed
    current_stage = Column(String(50))
    progress_percentage = Column(Integer, nullable=False, server_default="0")
    analysis_id = Column(Integer, ForeignKey("questionnaire_analyses.id"), index=True)
    total_tokens_used = Column(Integer)
    estimated_cost_usd = Column(DECIMAL(10, 6))
    models_used = Column(JSONB)
    logs = Column(JSONB, server_default='[]')  # Detailed execution logs
    error_message = Column(Text)
    started_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    
    # Relationships
    analysis = relationship("QuestionnaireAnalysis", back_populates="jobs")
    
    __table_args__ = (
        Index('idx_jobs_status', 'status'),
        Index('idx_jobs_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<AIGenerationJob(job_id='{self.job_id}', status='{self.status}', progress={self.progress_percentage}%)>"

