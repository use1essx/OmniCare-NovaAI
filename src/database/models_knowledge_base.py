"""
Knowledge Base Database Models

Models for storing documents, chunks, and question bank for the AI system.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, ARRAY, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.connection import Base


class KnowledgeDocument(Base):
    """Documents uploaded to the knowledge base"""
    
    __tablename__ = "knowledge_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    filename = Column(String(255))
    file_path = Column(Text)
    file_size = Column(Integer)  # in bytes
    file_type = Column(String(50))  # pdf, docx, txt, etc.
    
    # Categorization
    category = Column(String(100), index=True)
    language = Column(String(10), default='en')
    tags = Column(ARRAY(String))
    
    # Processing status
    status = Column(String(50), default='pending', index=True)  # pending, processing, approved, rejected, failed
    processing_error = Column(Text)
    
    # Content metadata
    total_chunks = Column(Integer, default=0)
    total_characters = Column(Integer, default=0)
    doc_metadata = Column(JSON)  # Additional metadata extracted from document
    
    # Review and approval
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    upload_date = Column(DateTime, default=func.now())
    review_date = Column(DateTime)
    review_notes = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    chunks = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan")
    questions = relationship("QuestionBankItem", back_populates="source_document")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    
    def __repr__(self):
        return f"<KnowledgeDocument(id={self.id}, title='{self.title}', status='{self.status}')>"


class KnowledgeChunk(Base):
    """Text chunks from documents for vector search"""
    
    __tablename__ = "knowledge_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False)
    
    # Chunk content
    chunk_index = Column(Integer, nullable=False)  # Position in document
    content = Column(Text, nullable=False)
    content_hash = Column(String(64))  # For deduplication
    
    # Chunk metadata
    chunk_metadata = Column(JSON)  # page_number, section, etc.
    token_count = Column(Integer)
    
    # Vector store reference
    vector_id = Column(String(255), unique=True, index=True)  # ID in vector database
    embedding_model = Column(String(100))  # Model used for embedding
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    document = relationship("KnowledgeDocument", back_populates="chunks")
    
    def __repr__(self):
        return f"<KnowledgeChunk(id={self.id}, doc_id={self.document_id}, index={self.chunk_index})>"


class QuestionBankItem(Base):
    """Assessment questions for conversational AI"""
    
    __tablename__ = "question_bank"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Question content
    question_text = Column(Text, nullable=False)
    question_type = Column(String(50), default='open_ended')  # open_ended, multiple_choice, scale, yes_no
    
    # Categorization
    category = Column(String(100), index=True)  # mental_health, physical_health, lifestyle, etc.
    subcategory = Column(String(100))
    difficulty = Column(String(20), default='medium')  # easy, medium, hard
    tags = Column(ARRAY(String))
    keywords = Column(ARRAY(String))  # Trigger keywords for this question
    
    # Conversation integration
    context_required = Column(Boolean, default=False)  # Needs specific context to ask
    conversation_triggers = Column(JSON)  # Conditions for asking this question
    follow_up_questions = Column(JSON)  # Related question IDs
    natural_variations = Column(ARRAY(Text))  # Different ways to ask the same question
    
    # Assessment metadata
    assessment_weight = Column(Float, default=1.0)  # Importance for assessment
    scoring_criteria = Column(JSON)  # How to score responses
    expected_response_type = Column(String(50))  # text, numeric, sentiment, etc.
    
    # Source tracking
    source_document_id = Column(Integer, ForeignKey("knowledge_documents.id"))
    source_reference = Column(Text)  # Page/section reference
    
    # Usage statistics
    times_asked = Column(Integer, default=0)
    avg_response_quality = Column(Float)
    avg_response_length = Column(Float)
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    requires_review = Column(Boolean, default=False)
    
    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    source_document = relationship("KnowledgeDocument", back_populates="questions")
    creator = relationship("User", foreign_keys=[created_by])
    responses = relationship("UserAssessmentResponse", back_populates="question")
    
    def __repr__(self):
        return f"<QuestionBankItem(id={self.id}, category='{self.category}', type='{self.question_type}')>"


class UserAssessmentResponse(Base):
    """User responses to assessment questions"""
    
    __tablename__ = "user_assessment_responses"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # References
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("question_bank.id"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    
    # Response data
    response_text = Column(Text)
    response_metadata = Column(JSON)  # sentiment, keywords, entities, etc.
    
    # Context
    context_before = Column(Text)  # Conversation context before question
    context_after = Column(Text)  # User's response context
    question_as_asked = Column(Text)  # How the question was actually phrased
    
    # Quality metrics
    quality_score = Column(Float)  # How good/complete the response is
    relevance_score = Column(Float)  # How relevant to the question
    sentiment_score = Column(Float)  # Sentiment analysis
    
    # Timestamps
    asked_at = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User")
    question = relationship("QuestionBankItem", back_populates="responses")
    conversation = relationship("Conversation")
    
    def __repr__(self):
        return f"<UserAssessmentResponse(id={self.id}, user_id={self.user_id}, question_id={self.question_id})>"


class UserAssessmentProfile(Base):
    """Extended user profile for assessment and personalization"""
    
    __tablename__ = "user_assessment_profiles"
    
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    
    # Demographics (for personalization)
    age_group = Column(String(20))  # 18-24, 25-34, etc.
    gender = Column(String(20))
    occupation = Column(String(100))
    location = Column(String(100))
    
    # Health context
    health_concerns = Column(ARRAY(String))
    medications = Column(JSON)
    chronic_conditions = Column(ARRAY(String))
    allergies = Column(ARRAY(String))
    
    # Assessment progress
    questions_answered = Column(JSON)  # {question_id: {answer, timestamp, context}}
    assessment_scores = Column(JSON)  # {category: score}
    last_assessment_date = Column(DateTime)
    assessment_completion = Column(Float, default=0.0)  # 0-100%
    
    # Conversation preferences
    preferred_topics = Column(ARRAY(String))
    avoided_topics = Column(ARRAY(String))
    communication_style = Column(String(50), default='balanced')  # formal, casual, empathetic, balanced
    language_preference = Column(String(10), default='en')
    
    # Engagement metrics
    avg_session_length = Column(Float)  # in minutes
    total_conversations = Column(Integer, default=0)
    total_messages = Column(Integer, default=0)
    engagement_score = Column(Float, default=0.0)  # 0-100
    last_active = Column(DateTime)
    
    # Privacy settings
    data_sharing_consent = Column(Boolean, default=False)
    assessment_consent = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", backref="assessment_profile")
    
    def __repr__(self):
        return f"<UserAssessmentProfile(user_id={self.user_id}, completion={self.assessment_completion}%)>"


class ConversationContext(Base):
    """Track conversation state for intelligent question selection"""
    
    __tablename__ = "conversation_contexts"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Current state
    current_topic = Column(String(100))
    current_sentiment = Column(String(50))  # positive, neutral, negative
    engagement_level = Column(String(50))  # high, medium, low
    
    # Question tracking
    questions_asked_this_session = Column(ARRAY(Integer))  # Question IDs
    last_question_at = Column(DateTime)
    messages_since_last_question = Column(Integer, default=0)
    
    # Context data
    topics_discussed = Column(ARRAY(String))
    keywords_mentioned = Column(ARRAY(String))
    entities_mentioned = Column(JSON)  # {entity_type: [entities]}
    
    # Assessment progress
    assessment_areas_covered = Column(ARRAY(String))
    assessment_areas_needed = Column(ARRAY(String))
    
    # Metadata
    session_start = Column(DateTime, default=func.now())
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    conversation = relationship("Conversation")
    user = relationship("User")
    
    def __repr__(self):
        return f"<ConversationContext(id={self.id}, conversation_id={self.conversation_id})>"
