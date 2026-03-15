"""
Questionnaire Management Models
For integrating with teammate's questionnaire generation function
"""

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DECIMAL, 
    ForeignKey, TIMESTAMP, CheckConstraint, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from src.database.models_comprehensive import Base, TimestampMixin


class QuestionnaireBank(Base, TimestampMixin):
    """Questionnaire template storage"""
    
    __tablename__ = "questionnaire_banks"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    status = Column(String(20), default="draft", index=True)
    category = Column(String(50), index=True)
    target_age_min = Column(Integer)
    target_age_max = Column(Integer)
    language = Column(String(10), default="en")
    total_questions = Column(Integer, default=0)
    estimated_duration_minutes = Column(Integer)
    source = Column(String(50))  # manual, ai_generated, imported
    published_at = Column(TIMESTAMP)
    
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'active', 'archived')", name='ck_questionnaire_status'),
        CheckConstraint("language IN ('en', 'zh-HK')", name='ck_questionnaire_language'),
    )
    
    # Relationships
    questions = relationship("QuestionnaireQuestion", back_populates="questionnaire", cascade="all, delete-orphan")
    responses = relationship("QuestionnaireResponse", back_populates="questionnaire")
    scoring_rules = relationship("ScoringRule", back_populates="questionnaire", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<QuestionnaireBank(id={self.id}, title='{self.title}', status='{self.status}')>"


class QuestionnaireQuestion(Base, TimestampMixin):
    """Individual questions in questionnaires"""
    
    __tablename__ = "questionnaire_questions"
    
    id = Column(Integer, primary_key=True, index=True)
    questionnaire_id = Column(Integer, ForeignKey("questionnaire_banks.id", ondelete="CASCADE"), index=True)
    question_code = Column(String(50))
    question_text = Column(Text, nullable=False)
    question_text_zh = Column(Text)
    question_type = Column(String(20), nullable=False)
    category = Column(String(50), index=True)
    sequence_order = Column(Integer, nullable=False)
    is_required = Column(Boolean, default=True)
    help_text = Column(Text)
    
    __table_args__ = (
        CheckConstraint("question_type IN ('scale', 'yes_no', 'multiple_choice', 'short_answer', 'rating')", 
                       name='ck_question_type'),
    )
    
    # Relationships
    questionnaire = relationship("QuestionnaireBank", back_populates="questions")
    options = relationship("QuestionOption", back_populates="question", cascade="all, delete-orphan")
    answers = relationship("QuestionAnswer", back_populates="question")
    
    def __repr__(self):
        return f"<QuestionnaireQuestion(id={self.id}, code='{self.question_code}', type='{self.question_type}')>"


class QuestionOption(Base, TimestampMixin):
    """Options for multiple choice and scale questions"""
    
    __tablename__ = "question_options"
    
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questionnaire_questions.id", ondelete="CASCADE"), index=True)
    option_text = Column(String(255), nullable=False)
    option_text_zh = Column(String(255))
    option_value = Column(Integer, nullable=False)
    sequence_order = Column(Integer, nullable=False)
    
    # Relationships
    question = relationship("QuestionnaireQuestion", back_populates="options")
    
    def __repr__(self):
        return f"<QuestionOption(id={self.id}, value={self.option_value}, text='{self.option_text}')>"


class QuestionnaireResponse(Base, TimestampMixin):
    """User's questionnaire session"""
    
    __tablename__ = "questionnaire_responses"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    questionnaire_id = Column(Integer, ForeignKey("questionnaire_banks.id"), index=True)
    session_id = Column(String(255), index=True)
    started_at = Column(TIMESTAMP, server_default=func.now())
    completed_at = Column(TIMESTAMP)
    status = Column(String(20), default="in_progress")
    total_score = Column(DECIMAL(5, 2))
    confidence_level = Column(DECIMAL(3, 2))
    
    __table_args__ = (
        CheckConstraint("status IN ('in_progress', 'completed', 'abandoned')", 
                       name='ck_response_status'),
    )
    
    # Relationships
    questionnaire = relationship("QuestionnaireBank", back_populates="responses")
    answers = relationship("QuestionAnswer", back_populates="response", cascade="all, delete-orphan")
    category_scores = relationship("CategoryScore", back_populates="response", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<QuestionnaireResponse(id={self.id}, user_id={self.user_id}, status='{self.status}')>"


class QuestionAnswer(Base, TimestampMixin):
    """Individual answers to questions"""
    
    __tablename__ = "question_answers"
    
    id = Column(Integer, primary_key=True, index=True)
    response_id = Column(Integer, ForeignKey("questionnaire_responses.id", ondelete="CASCADE"), index=True)
    question_id = Column(Integer, ForeignKey("questionnaire_questions.id"), index=True)
    answer_text = Column(Text)
    answer_value = Column(Integer)
    answered_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relationships
    response = relationship("QuestionnaireResponse", back_populates="answers")
    question = relationship("QuestionnaireQuestion", back_populates="answers")
    
    def __repr__(self):
        return f"<QuestionAnswer(id={self.id}, question_id={self.question_id}, value={self.answer_value})>"


class ScoringRule(Base, TimestampMixin):
    """Scoring rules for questionnaires"""
    
    __tablename__ = "scoring_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    questionnaire_id = Column(Integer, ForeignKey("questionnaire_banks.id", ondelete="CASCADE"))
    category = Column(String(50), nullable=False)
    category_name_en = Column(String(100))
    category_name_zh = Column(String(100))
    weight = Column(DECIMAL(3, 2), default=1.0)
    threshold_excellent = Column(DECIMAL(5, 2))
    threshold_good = Column(DECIMAL(5, 2))
    threshold_moderate = Column(DECIMAL(5, 2))
    threshold_concerning = Column(DECIMAL(5, 2))
    flag_if_below = Column(DECIMAL(5, 2))
    alert_if_below = Column(DECIMAL(5, 2))
    
    # Relationships
    questionnaire = relationship("QuestionnaireBank", back_populates="scoring_rules")
    
    def __repr__(self):
        return f"<ScoringRule(id={self.id}, category='{self.category}', weight={self.weight})>"


class CategoryScore(Base, TimestampMixin):
    """Calculated scores by category"""
    
    __tablename__ = "category_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    response_id = Column(Integer, ForeignKey("questionnaire_responses.id", ondelete="CASCADE"), index=True)
    category = Column(String(50), nullable=False)
    raw_score = Column(DECIMAL(5, 2))
    weighted_score = Column(DECIMAL(5, 2))
    max_possible_score = Column(DECIMAL(5, 2))
    percentage = Column(DECIMAL(5, 2))
    interpretation = Column(String(50))
    flagged = Column(Boolean, default=False)
    calculated_at = Column(TIMESTAMP, server_default=func.now())
    
    # Relationships
    response = relationship("QuestionnaireResponse", back_populates="category_scores")
    
    def __repr__(self):
        return f"<CategoryScore(id={self.id}, category='{self.category}', score={self.raw_score})>"


class QuestionnaireAssignment(Base, TimestampMixin):
    """Assignment of questionnaires to users for Live2D conversation"""
    
    __tablename__ = "questionnaire_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    questionnaire_id = Column(Integer, ForeignKey("questionnaire_banks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Status tracking
    status = Column(String(20), nullable=False, server_default="active", index=True)
    
    # Progress tracking
    total_questions = Column(Integer, nullable=False, server_default="0")
    questions_asked = Column(Integer, server_default="0")
    questions_answered = Column(Integer, server_default="0")
    current_question_index = Column(Integer, server_default="0")
    
    # Timing
    assigned_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    started_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)
    expires_at = Column(TIMESTAMP)
    
    # Settings
    questions_per_conversation = Column(Integer, server_default="2")
    ask_naturally = Column(Boolean, server_default="true")
    priority = Column(Integer, server_default="5")
    
    # Notes
    admin_notes = Column(Text)
    
    __table_args__ = (
        CheckConstraint("status IN ('active', 'paused', 'completed', 'cancelled')", name='ck_assignment_status'),
        CheckConstraint("priority >= 1 AND priority <= 10", name='ck_assignment_priority'),
    )
    
    # Relationships
    questionnaire = relationship("QuestionnaireBank")
    conversation_answers = relationship("ConversationAnswer", back_populates="assignment", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<QuestionnaireAssignment(id={self.id}, user_id={self.user_id}, status='{self.status}')>"


class ConversationAnswer(Base, TimestampMixin):
    """Answers extracted from natural conversation in Live2D chat"""
    
    __tablename__ = "conversation_answers"
    
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("questionnaire_assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questionnaire_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Conversation context
    conversation_id = Column(Integer)  # Optional FK to conversations
    message_id = Column(Integer)  # Optional FK to messages
    session_id = Column(String(255), index=True)
    
    # Question and answer
    question_asked = Column(Text, nullable=False)
    user_message = Column(Text, nullable=False)
    
    # Extracted answer
    extracted_answer_text = Column(Text)
    extracted_answer_value = Column(Integer)
    
    # AI extraction metadata
    extraction_confidence = Column(DECIMAL(3, 2))
    extraction_method = Column(String(50))
    extraction_notes = Column(Text)
    needs_clarification = Column(Boolean, server_default="false")
    
    # Validation
    validated_by = Column(Integer, ForeignKey("users.id"))
    validated_at = Column(TIMESTAMP)
    validation_status = Column(String(20), server_default="pending")
    
    # Timestamps
    asked_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    answered_at = Column(TIMESTAMP, nullable=True)  # Set when user actually answers
    
    # Context storage
    conversation_context = Column(JSONB)
    
    # Emotion analysis fields
    emotion_analysis_result = Column(JSONB)
    dominant_emotion = Column(String(20))
    emotion_intensity = Column(DECIMAL(5, 2))
    anxiety_risk_score = Column(DECIMAL(5, 2))
    emotional_regulation_score = Column(DECIMAL(5, 2))
    overall_wellbeing_score = Column(DECIMAL(5, 2))
    analysis_summary = Column(Text)
    
    __table_args__ = (
        CheckConstraint("validation_status IN ('pending', 'validated', 'rejected', 'needs_review')", name='ck_validation_status'),
    )
    
    # Relationships
    assignment = relationship("QuestionnaireAssignment", back_populates="conversation_answers")
    question = relationship("QuestionnaireQuestion")
    
    def __repr__(self):
        return f"<ConversationAnswer(id={self.id}, question_id={self.question_id}, user_message='{self.user_message[:30]}...')>"

