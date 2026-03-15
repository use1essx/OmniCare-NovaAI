"""
Healthcare AI V2 - Comprehensive Database Models
SQLAlchemy models for all database tables matching the SQL schema
"""


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
    ARRAY,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.connection import Base


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


# =============================================================================
# USER MANAGEMENT MODELS
# =============================================================================

class Organization(Base, TimestampMixin):
    """Organization/Healthcare facility model"""
    
    __tablename__ = "organizations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)
    description = Column(Text)
    
    # Contact Information
    email = Column(String(255), index=True)
    phone = Column(String(50))
    address = Column(Text)
    website = Column(String(255))
    
    # Capacity and Limits
    max_users = Column(Integer, default=50)
    max_admins = Column(Integer, default=10)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_verified = Column(Boolean, default=False)
    
    # Audit Fields
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_by = Column(Integer, ForeignKey("users.id"))
    
    def __repr__(self):
        return f"<Organization(id={self.id}, name='{self.name}', type='{self.type}')>"


class Live2DModel(Base, TimestampMixin):
    """Live2D Avatar Model"""
    
    __tablename__ = "live2d_models"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    model_path = Column(String(255), nullable=False)
    version = Column(String(20), default="1.0")
    description = Column(Text)
    
    # Configuration
    config = Column(JSONB)
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    is_default = Column(Boolean, default=False)
    
    # Audit Fields
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    
    def __repr__(self):
        return f"<Live2DModel(id={self.id}, name='{self.name}')>"


class User(Base, TimestampMixin):
    """Enhanced user model with comprehensive authentication and authorization"""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    
    # Account Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_super_admin = Column(Boolean, default=False)
    
    # Role and Department
    role = Column(String(50), default="user", nullable=False, index=True)
    department = Column(String(100), index=True)
    license_number = Column(String(100))
    organization = Column(String(255))  # Legacy field - use organization_id instead
    
    # Assignment (for healthcare staff to manage specific users)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    # Organization and Assignment (backward compatible - nullable)
    organization_id = Column(Integer, index=True, nullable=True)  # Will add FK after migration
    assigned_caregiver_id = Column(Integer, index=True, nullable=True)  # For patients: which doctor/nurse manages them
    
    # Security Fields
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    account_locked_until = Column(DateTime(timezone=True))
    last_login = Column(DateTime(timezone=True), index=True)
    password_changed_at = Column(DateTime(timezone=True), default=func.now())
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(255))
    
    # Preferences
    language_preference = Column(String(10), default="en")
    timezone = Column(String(50), default="Asia/Hong_Kong")
    notification_preferences = Column(JSONB, default={"email": True, "sms": False, "push": True})
    health_profile = Column(JSONB, default={})
    
    # Audit Fields
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_by = Column(Integer, ForeignKey("users.id"))
    
    # Constraints (keeping backward compatible - will update after migration)
    __table_args__ = (
        # CheckConstraint will be updated in database migration
        CheckConstraint("language_preference IN ('en', 'zh-HK')", name='ck_user_language'),
    )
    
    # Relationships (will work after migration)
    # org = relationship("Organization", back_populates="users", foreign_keys=[organization_id])
    # assigned_caregiver = relationship("User", remote_side=[id], foreign_keys=[assigned_caregiver_id])
    # assigned_patients = relationship("User", back_populates="assigned_caregiver", foreign_keys=[assigned_caregiver_id])
    
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    permissions = relationship("UserPermission", back_populates="user", foreign_keys="UserPermission.user_id", cascade="all, delete-orphan")
    uploaded_documents = relationship("UploadedDocument", back_populates="uploaded_by_user", foreign_keys="UploadedDocument.uploaded_by")
    conversations = relationship("Conversation", back_populates="user", foreign_keys="Conversation.user_id")
    
    # Health profile relationship (new teen/kids profile system)
    # Note: Uses string reference to avoid circular import - HealthProfile is in health_profile_models.py
    health_profile_record = relationship(
        "HealthProfile", 
        back_populates="user", 
        uselist=False,  # One-to-one relationship
        lazy="select"   # Lazy load to avoid mapper issues
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"


class UserSession(Base, TimestampMixin):
    """Enhanced user session tracking with comprehensive security features"""
    
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True)
    
    # Session Details
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    refresh_expires_at = Column(DateTime(timezone=True))
    ip_address = Column(INET, index=True)
    user_agent = Column(Text)
    device_info = Column(JSONB)
    
    # Session Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True))
    revoked_reason = Column(String(100))
    
    # Geolocation
    location_data = Column(JSONB)
    
    # Audit Fields
    last_activity = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.user_id}, active={self.is_active})>"


class Permission(Base, TimestampMixin):
    """Enhanced permission model with granular access control"""
    
    __tablename__ = "permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    category = Column(String(50), nullable=False, index=True)
    resource = Column(String(100), nullable=False, index=True)
    action = Column(String(50), nullable=False)
    
    # Permission Details
    conditions = Column(JSONB)
    is_active = Column(Boolean, default=True, index=True)
    
    # Relationships
    user_permissions = relationship("UserPermission", back_populates="permission", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Permission(id={self.id}, name='{self.name}', category='{self.category}')>"


class UserPermission(Base):
    """Enhanced user permission mapping with expiration and context"""
    
    __tablename__ = "user_permissions"
    
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permissions.id"), primary_key=True)
    
    # Permission Details
    granted_at = Column(DateTime(timezone=True), default=func.now())
    expires_at = Column(DateTime(timezone=True))
    granted_by = Column(Integer, ForeignKey("users.id"))
    revoked_at = Column(DateTime(timezone=True))
    revoked_by = Column(Integer, ForeignKey("users.id"))
    
    # Conditions and Context
    conditions = Column(JSONB)
    context = Column(JSONB)
    
    # Relationships
    user = relationship("User", back_populates="permissions", foreign_keys=[user_id])
    permission = relationship("Permission", back_populates="user_permissions")
    granted_by_user = relationship("User", foreign_keys=[granted_by])
    revoked_by_user = relationship("User", foreign_keys=[revoked_by])
    
    def __repr__(self):
        return f"<UserPermission(user_id={self.user_id}, permission_id={self.permission_id})>"


# =============================================================================
# CONVERSATION AND CHAT MODELS
# =============================================================================

class Conversation(Base, TimestampMixin):
    """Enhanced conversation model with comprehensive tracking and analysis"""
    
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    # Message Content
    user_input = Column(Text, nullable=False)
    agent_response = Column(Text, nullable=False)
    
    # Agent Information
    agent_type = Column(String(50), nullable=False, index=True)
    agent_name = Column(String(100))
    agent_confidence = Column(DECIMAL(3, 2))
    
    # Classification and Analysis
    intent_detected = Column(String(100))
    urgency_level = Column(String(20), default="low", index=True)
    domain_classification = Column(String(50))
    sentiment_score = Column(DECIMAL(3, 2))
    
    # Language and Cultural Context
    language = Column(String(10), default="en", index=True)
    cultural_context = Column(JSONB)
    
    # User Feedback and Quality Metrics
    user_satisfaction = Column(Integer, index=True)
    user_feedback = Column(Text)
    flagged_by_user = Column(Boolean, default=False, index=True)
    flag_reason = Column(String(255))
    
    # Performance Metrics
    processing_time_ms = Column(Integer)
    tokens_used = Column(Integer)
    api_cost = Column(DECIMAL(10, 6))
    
    # Data Sources Used
    hk_data_used = Column(JSONB)
    external_apis_used = Column(JSONB)
    
    # Context and Routing
    conversation_context = Column(JSONB)
    routing_decision = Column(JSONB)
    handoff_data = Column(JSONB)
    
    # Quality and Moderation
    content_flagged = Column(Boolean, default=False)
    content_flag_reason = Column(String(255))
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    review_status = Column(String(20), default="pending", index=True)
    
    # Constraints
    __table_args__ = (
        CheckConstraint("agent_type IN ('illness_monitor', 'mental_health', 'safety_guardian', 'wellness_coach')", name='ck_agent_type'),
        CheckConstraint("urgency_level IN ('low', 'medium', 'high', 'emergency')", name='ck_urgency_level'),
        CheckConstraint("language IN ('en', 'zh-HK')", name='ck_language'),
        CheckConstraint("user_satisfaction >= 1 AND user_satisfaction <= 5", name='ck_user_satisfaction'),
        CheckConstraint("review_status IN ('pending', 'approved', 'rejected', 'needs_review')", name='ck_review_status'),
        CheckConstraint("agent_confidence >= 0 AND agent_confidence <= 1", name='ck_agent_confidence'),
        CheckConstraint("sentiment_score >= -1 AND sentiment_score <= 1", name='ck_sentiment_score'),
    )
    
    # Relationships
    user = relationship("User", back_populates="conversations", foreign_keys=[user_id])
    routing_decisions = relationship("AgentRoutingDecision", back_populates="conversation", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, agent_type='{self.agent_type}', urgency='{self.urgency_level}')>"


# =============================================================================
# HONG KONG HEALTHCARE DATA MODELS
# =============================================================================

class HKHealthcareFacility(Base, TimestampMixin):
    """Comprehensive Hong Kong healthcare facility data model"""
    
    __tablename__ = "hk_healthcare_facilities"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Facility Identification
    facility_id = Column(String(50), unique=True, nullable=False, index=True)
    facility_code = Column(String(20))
    
    # Names (Multi-language support)
    name_en = Column(String(255), nullable=False)
    name_zh_hant = Column(String(255))
    name_zh_hans = Column(String(255))
    
    # Facility Type and Classification
    facility_type = Column(String(50), nullable=False, index=True)
    facility_subtype = Column(String(100))
    cluster = Column(String(50))
    
    # Services Offered
    services_offered = Column(ARRAY(Text))
    specialties = Column(ARRAY(Text))
    emergency_services = Column(Boolean, default=False, index=True)
    a_e_services = Column(Boolean, default=False)
    
    # Location Information
    address_en = Column(Text)
    address_zh = Column(Text)
    district = Column(String(50), index=True)
    region = Column(String(20), index=True)
    
    # Geographic Coordinates
    latitude = Column(DECIMAL(10, 8))
    longitude = Column(DECIMAL(11, 8))
    
    # Contact Information
    phone_main = Column(String(20))
    phone_appointment = Column(String(20))
    phone_emergency = Column(String(20))
    fax = Column(String(20))
    email = Column(String(255))
    website = Column(String(500))
    
    # Operating Information
    operating_hours = Column(JSONB)
    appointment_required = Column(Boolean, default=True)
    walk_in_available = Column(Boolean, default=False)
    online_booking_available = Column(Boolean, default=False)
    
    # Capacity and Resources
    total_beds = Column(Integer)
    available_beds = Column(Integer)
    icu_beds = Column(Integer)
    emergency_capacity = Column(Integer)
    
    # Real-time Data
    current_waiting_time = Column(Integer)
    queue_status = Column(String(20))
    last_updated = Column(DateTime(timezone=True), index=True)
    
    # Quality and Ratings
    government_rating = Column(Integer)
    patient_satisfaction_score = Column(DECIMAL(3, 2))
    
    # Data Source and Validation
    data_source = Column(String(100), nullable=False)
    data_source_url = Column(String(500))
    data_quality_score = Column(DECIMAL(3, 2), default=1.0)
    verified_by_admin = Column(Boolean, default=False)
    verification_date = Column(DateTime(timezone=True))
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    is_published = Column(Boolean, default=False)
    status_notes = Column(Text)
    
    # Audit Fields
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_by = Column(Integer, ForeignKey("users.id"))
    
    # Constraints
    __table_args__ = (
        CheckConstraint("facility_type IN ('hospital', 'clinic', 'health_center', 'emergency', 'specialist', 'dental', 'mental_health')", name='ck_facility_type'),
        CheckConstraint("region IN ('Hong Kong Island', 'Kowloon', 'New Territories')", name='ck_region'),
        CheckConstraint("queue_status IN ('normal', 'busy', 'full', 'closed')", name='ck_queue_status'),
        CheckConstraint("government_rating >= 1 AND government_rating <= 5", name='ck_government_rating'),
    )
    
    # Relationships
    updates = relationship("HKHealthcareUpdate", back_populates="facility", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<HKHealthcareFacility(id={self.id}, type='{self.facility_type}', name='{self.name_en}')>"


class HKHealthcareUpdate(Base, TimestampMixin):
    """Real-time updates to healthcare facility data"""
    
    __tablename__ = "hk_healthcare_updates"
    
    id = Column(Integer, primary_key=True, index=True)
    facility_id = Column(Integer, ForeignKey("hk_healthcare_facilities.id"), nullable=False, index=True)
    
    # Update Information
    update_type = Column(String(50), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    
    # Data Values
    old_value = Column(Text)
    new_value = Column(Text)
    value_type = Column(String(20), default="string")
    
    # Source Information
    data_source = Column(String(100), nullable=False)
    source_timestamp = Column(DateTime(timezone=True))
    confidence_score = Column(DECIMAL(3, 2), default=1.0)
    
    # Validation
    is_validated = Column(Boolean, default=False)
    validation_method = Column(String(100))
    validation_score = Column(DECIMAL(3, 2))
    
    # Processing
    processed = Column(Boolean, default=False, index=True)
    processing_error = Column(Text)
    processed_at = Column(DateTime(timezone=True))
    
    # Constraints
    __table_args__ = (
        CheckConstraint("value_type IN ('string', 'integer', 'decimal', 'boolean', 'json')", name='ck_value_type'),
    )
    
    # Relationships
    facility = relationship("HKHealthcareFacility", back_populates="updates")
    
    def __repr__(self):
        return f"<HKHealthcareUpdate(id={self.id}, type='{self.update_type}', processed={self.processed})>"


# =============================================================================
# AI AGENT PERFORMANCE MODELS
# =============================================================================

class AgentPerformance(Base, TimestampMixin):
    """Comprehensive AI agent performance tracking and analytics"""
    
    __tablename__ = "agent_performance"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Agent Information
    agent_type = Column(String(50), nullable=False, index=True)
    agent_version = Column(String(20), default="1.0")
    
    # Time Period
    measurement_period = Column(String(20), default="hourly", index=True)
    period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    period_end = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Conversation Metrics
    total_conversations = Column(Integer, default=0)
    successful_conversations = Column(Integer, default=0)
    failed_conversations = Column(Integer, default=0)
    escalated_conversations = Column(Integer, default=0)
    
    # Response Quality Metrics
    average_confidence_score = Column(DECIMAL(4, 3))
    average_user_satisfaction = Column(DECIMAL(3, 2))
    total_user_ratings = Column(Integer, default=0)
    flagged_responses = Column(Integer, default=0)
    
    # Performance Metrics
    average_response_time_ms = Column(Integer)
    median_response_time_ms = Column(Integer)
    max_response_time_ms = Column(Integer)
    
    # Token and Cost Metrics
    total_tokens_used = Column(Integer, default=0)
    total_api_cost = Column(DECIMAL(10, 6), default=0)
    average_cost_per_conversation = Column(DECIMAL(8, 6))
    
    # Accuracy Metrics
    correct_urgency_classifications = Column(Integer, default=0)
    total_urgency_classifications = Column(Integer, default=0)
    urgency_accuracy_rate = Column(DECIMAL(4, 3))
    
    correct_intent_detections = Column(Integer, default=0)
    total_intent_detections = Column(Integer, default=0)
    intent_accuracy_rate = Column(DECIMAL(4, 3))
    
    # Domain-specific Metrics
    domain_performance = Column(JSONB)
    language_performance = Column(JSONB)
    urgency_performance = Column(JSONB)
    
    # Learning and Improvement
    pattern_matches = Column(Integer, default=0)
    new_patterns_learned = Column(Integer, default=0)
    routing_improvements = Column(Integer, default=0)
    
    # Quality Assurance
    reviewed_conversations = Column(Integer, default=0)
    approved_conversations = Column(Integer, default=0)
    rejected_conversations = Column(Integer, default=0)
    
    # HK Data Integration
    hk_data_requests = Column(Integer, default=0)
    successful_hk_data_integrations = Column(Integer, default=0)
    failed_hk_data_integrations = Column(Integer, default=0)
    
    # Cultural Adaptation
    cultural_context_applied = Column(Integer, default=0)
    cultural_sensitivity_score = Column(DECIMAL(3, 2))
    
    # Error Tracking
    error_count = Column(Integer, default=0)
    error_types = Column(JSONB)
    
    # Constraints
    __table_args__ = (
        CheckConstraint("agent_type IN ('illness_monitor', 'mental_health', 'safety_guardian', 'wellness_coach')", name='ck_agent_performance_type'),
        CheckConstraint("measurement_period IN ('hourly', 'daily', 'weekly', 'monthly')", name='ck_measurement_period'),
    )
    
    def __repr__(self):
        return f"<AgentPerformance(agent='{self.agent_type}', period='{self.period_start}', conversations={self.total_conversations})>"


class AgentRoutingDecision(Base):
    """Agent routing decisions and analysis for optimization"""
    
    __tablename__ = "agent_routing_decisions"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    
    # Routing Information
    selected_agent = Column(String(50), nullable=False)
    routing_confidence = Column(DECIMAL(4, 3))
    routing_time_ms = Column(Integer)
    
    # Agent Scores
    agent_scores = Column(JSONB, nullable=False)
    
    # Decision Factors
    intent_analysis = Column(JSONB)
    urgency_analysis = Column(JSONB)
    domain_analysis = Column(JSONB)
    language_analysis = Column(JSONB)
    context_factors = Column(JSONB)
    
    # Alternative Agents
    alternative_agents = Column(ARRAY(String(50)))
    runner_up_agent = Column(String(50))
    runner_up_score = Column(DECIMAL(4, 3))
    
    # Performance Validation
    was_optimal = Column(Boolean)
    user_switched_agent = Column(Boolean, default=False)
    switched_to_agent = Column(String(50))
    switch_reason = Column(String(255))
    
    # Learning Data
    feedback_incorporated = Column(Boolean, default=False)
    improved_routing = Column(Boolean, default=False)
    
    # Audit Fields
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    conversation = relationship("Conversation", back_populates="routing_decisions")
    
    def __repr__(self):
        return f"<AgentRoutingDecision(id={self.id}, selected='{self.selected_agent}', confidence={self.routing_confidence})>"


# =============================================================================
# DOCUMENT MANAGEMENT MODELS
# =============================================================================

class UploadedDocument(Base, TimestampMixin):
    """Enhanced document management with comprehensive metadata and versioning"""
    
    __tablename__ = "uploaded_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # File Information
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_type = Column(String(50), nullable=False)
    mime_type = Column(String(100))
    file_hash = Column(String(64), unique=True, index=True)
    
    # Document Classification
    document_type = Column(String(50), nullable=False, index=True)
    category = Column(String(100))
    subcategory = Column(String(100))
    
    # Content Information
    title = Column(String(255))
    description = Column(Text)
    language = Column(String(10), default="en")
    
    # Extracted Content
    extracted_text = Column(Text)
    extraction_method = Column(String(50))
    extraction_confidence = Column(DECIMAL(3, 2))
    
    # Processing Status
    processing_status = Column(String(20), default="uploaded", index=True)
    processing_error = Column(Text)
    processing_started_at = Column(DateTime(timezone=True))
    processing_completed_at = Column(DateTime(timezone=True))
    
    # Quality Assessment
    content_quality_score = Column(DECIMAL(3, 2))
    medical_accuracy_score = Column(DECIMAL(3, 2))
    cultural_relevance_score = Column(DECIMAL(3, 2))
    overall_quality_score = Column(DECIMAL(3, 2))
    
    # Review and Approval
    review_status = Column(String(20), default="pending", index=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    review_date = Column(DateTime(timezone=True))
    review_notes = Column(Text)
    
    approved_by = Column(Integer, ForeignKey("users.id"))
    approval_date = Column(DateTime(timezone=True))
    approval_notes = Column(Text)
    
    # Usage and Integration
    is_active = Column(Boolean, default=False, index=True)
    is_searchable = Column(Boolean, default=False)
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime(timezone=True))
    
    # Metadata and Tags
    tags = Column(ARRAY(String(100)))
    document_metadata = Column(JSONB)  # Renamed to avoid conflict with SQLAlchemy metadata
    version_number = Column(Integer, default=1)
    superseded_by = Column(Integer, ForeignKey("uploaded_documents.id"))
    
    # Security and Access
    access_level = Column(String(20), default="internal")
    encryption_status = Column(String(20), default="none")
    
    # Retention and Compliance
    retention_period = Column(Integer, default=2555)
    compliance_flags = Column(ARRAY(String(100)))
    
    # Audit Fields
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    updated_by = Column(Integer, ForeignKey("users.id"))
    
    # Constraints
    __table_args__ = (
        CheckConstraint("document_type IN ('medical_guideline', 'treatment_protocol', 'medication_info', 'emergency_procedure', 'hk_health_policy', 'research_paper', 'training_material')", name='ck_document_type'),
        CheckConstraint("processing_status IN ('uploaded', 'processing', 'processed', 'failed', 'approved', 'rejected')", name='ck_processing_status'),
        CheckConstraint("review_status IN ('pending', 'under_review', 'approved', 'rejected', 'needs_revision')", name='ck_review_status'),
        CheckConstraint("access_level IN ('public', 'internal', 'restricted', 'confidential')", name='ck_access_level'),
        CheckConstraint("encryption_status IN ('none', 'at_rest', 'full')", name='ck_encryption_status'),
    )
    
    # Relationships
    uploaded_by_user = relationship("User", foreign_keys=[uploaded_by], back_populates="uploaded_documents")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<UploadedDocument(id={self.id}, filename='{self.original_filename}', status='{self.processing_status}')>"


class DocumentVersion(Base):
    """Document version history and management"""
    
    __tablename__ = "document_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("uploaded_documents.id"), nullable=False)
    
    # Version Information
    version_number = Column(Integer, nullable=False)
    version_description = Column(Text)
    
    # File Information
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=False)
    
    # Content Changes
    content_changes = Column(Text)
    change_summary = Column(Text)
    
    # Version Status
    is_current = Column(Boolean, default=False)
    
    # Audit Fields
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    document = relationship("UploadedDocument", back_populates="versions")
    
    __table_args__ = (
        Index('uq_document_version', 'document_id', 'version_number', unique=True),
    )
    
    def __repr__(self):
        return f"<DocumentVersion(id={self.id}, doc_id={self.document_id}, version={self.version_number})>"


# =============================================================================
# AUDIT AND SECURITY MODELS
# =============================================================================

class AuditLog(Base):
    """Comprehensive audit logging for security and compliance"""
    
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Event Information
    event_type = Column(String(50), nullable=False, index=True)
    event_category = Column(String(50), nullable=False, index=True)
    event_description = Column(Text, nullable=False)
    
    # Actor Information
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    username = Column(String(100))
    
    # Target Information
    target_type = Column(String(50), index=True)
    target_id = Column(String(100), index=True)
    target_details = Column(JSONB)
    
    # Request Information
    ip_address = Column(INET, index=True)
    user_agent = Column(Text)
    request_id = Column(String(255))
    session_id = Column(String(255))
    
    # Changes and Data
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    
    # Result and Status
    result = Column(String(20), default="success")
    error_message = Column(Text)
    
    # Security Classification
    severity_level = Column(String(20), default="info", index=True)
    security_impact = Column(String(20), default="low")
    
    # Compliance and Retention
    retention_period = Column(Integer, default=2555)
    compliance_tags = Column(ARRAY(String(255)))
    
    # Audit Fields
    created_at = Column(DateTime(timezone=True), default=func.now(), index=True)
    processed_at = Column(DateTime(timezone=True))
    archived_at = Column(DateTime(timezone=True))
    
    # Constraints
    __table_args__ = (
        CheckConstraint("result IN ('success', 'failure', 'error', 'partial')", name='ck_result'),
        CheckConstraint("severity_level IN ('debug', 'info', 'warning', 'error', 'critical')", name='ck_severity_level'),
        CheckConstraint("security_impact IN ('none', 'low', 'medium', 'high', 'critical')", name='ck_security_impact'),
    )
    
    # Relationships
    user = relationship("User")
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, event='{self.event_type}', user='{self.username}', severity='{self.severity_level}')>"


# =============================================================================
# COMPREHENSIVE INDEXES FOR PERFORMANCE
# =============================================================================

# Multi-column indexes for complex queries
Index('idx_conversations_session_agent_time', Conversation.session_id, Conversation.agent_type, Conversation.created_at)
Index('idx_conversations_user_urgency_time', Conversation.user_id, Conversation.urgency_level, Conversation.created_at)
Index('idx_hk_facilities_type_district_active', HKHealthcareFacility.facility_type, HKHealthcareFacility.district, HKHealthcareFacility.is_active)
Index('idx_hk_facilities_emergency_region', HKHealthcareFacility.emergency_services, HKHealthcareFacility.region)
Index('idx_documents_type_status_active', UploadedDocument.document_type, UploadedDocument.processing_status, UploadedDocument.is_active)
Index('idx_agent_performance_type_period', AgentPerformance.agent_type, AgentPerformance.measurement_period, AgentPerformance.period_start)
Index('idx_audit_logs_user_event_time', AuditLog.user_id, AuditLog.event_type, AuditLog.created_at)
Index('idx_audit_logs_severity_category', AuditLog.severity_level, AuditLog.event_category)

# GIN indexes for JSONB columns (for JSON queries)
Index('idx_conversations_hk_data_gin', Conversation.hk_data_used, postgresql_using='gin')
Index('idx_conversations_context_gin', Conversation.conversation_context, postgresql_using='gin')
Index('idx_hk_facilities_hours_gin', HKHealthcareFacility.operating_hours, postgresql_using='gin')
Index('idx_agent_performance_domain_gin', AgentPerformance.domain_performance, postgresql_using='gin')
Index('idx_documents_metadata_gin', UploadedDocument.document_metadata, postgresql_using='gin')
Index('idx_users_notification_prefs_gin', User.notification_preferences, postgresql_using='gin')

# Array indexes for array columns
Index('idx_hk_facilities_services_gin', HKHealthcareFacility.services_offered, postgresql_using='gin')
Index('idx_documents_tags_gin', UploadedDocument.tags, postgresql_using='gin')
