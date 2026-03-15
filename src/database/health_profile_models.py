"""
Healthcare AI V2 - Health Profile Models
Extended user profile models for teens/kids mental health and growth tracking
"""

from datetime import date
from typing import Optional
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Date,
    Float,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.connection import Base
from src.database.models_comprehensive import TimestampMixin


class GenderEnum(str, Enum):
    """Gender options"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class AgeGroupEnum(str, Enum):
    """Age group categories"""
    CHILD = "child"      # 6-12 years
    TEEN = "teen"        # 13-17 years
    ADULT = "adult"      # 18+ years


class SchoolLevelEnum(str, Enum):
    """School level options (Hong Kong system)"""
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"
    P6 = "P6"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"
    S5 = "S5"
    S6 = "S6"
    UNIVERSITY = "university"
    NOT_IN_SCHOOL = "not_in_school"


class HealthProfile(Base, TimestampMixin):
    """Extended health profile for teens/kids mental health and growth"""
    
    __tablename__ = "health_profiles"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # ============================================
    # BASIC INFORMATION
    # ============================================
    nickname = Column(String(100))  # Preferred name/nickname
    date_of_birth = Column(Date)
    age = Column(Integer)  # Calculated or entered age
    age_group = Column(SQLEnum(AgeGroupEnum, name='age_group_enum', create_type=False))  # child, teen, adult
    gender = Column(SQLEnum(GenderEnum, name='gender_enum', create_type=False))
    
    # ============================================
    # PHYSICAL GROWTH TRACKING
    # ============================================
    height_cm = Column(Float)  # Height in centimeters
    weight_kg = Column(Float)  # Weight in kilograms
    growth_history = Column(JSONB)  # Historical height/weight records for tracking
    sleep_hours_weekday = Column(Float)  # Average sleep on school nights
    sleep_hours_weekend = Column(Float)  # Average sleep on weekends
    sleep_quality = Column(String(50))  # good, fair, poor, varies
    physical_activity_level = Column(String(50))  # very_active, active, moderate, low, sedentary
    
    # ============================================
    # SCHOOL & EDUCATION
    # ============================================
    school_name = Column(String(255))
    school_level = Column(SQLEnum(SchoolLevelEnum, name='school_level_enum', create_type=False))  # P1-P6, S1-S6, university
    favorite_subjects = Column(JSONB)  # List of favorite subjects
    challenging_subjects = Column(JSONB)  # Subjects they find difficult
    learning_style = Column(String(50))  # visual, auditory, reading, kinesthetic
    special_educational_needs = Column(JSONB)  # SEN, ADHD, dyslexia, etc.
    academic_pressure_level = Column(Integer)  # 1-5 scale
    
    # ============================================
    # MENTAL HEALTH & EMOTIONAL WELLBEING
    # ============================================
    current_mood = Column(String(50))  # happy, okay, sad, anxious, stressed, angry
    mood_history = Column(JSONB)  # Historical mood tracking
    stress_level = Column(Integer)  # 1-5 scale
    stress_sources = Column(JSONB)  # school, family, friends, exams, future, etc.
    anxiety_triggers = Column(JSONB)  # Known anxiety triggers
    coping_strategies = Column(JSONB)  # What helps them feel better
    self_esteem_level = Column(Integer)  # 1-5 scale
    
    # Mental health concerns (age-appropriate)
    mental_health_concerns = Column(JSONB)  # anxiety, depression, adhd, etc.
    has_seen_counselor = Column(Boolean, default=False)
    counselor_details = Column(String(255))
    
    # ============================================
    # SOCIAL & RELATIONSHIPS
    # ============================================
    social_comfort_level = Column(Integer)  # 1-5 scale (shy to outgoing)
    friend_circle_size = Column(String(50))  # none, few, some, many
    relationship_with_parents = Column(String(50))  # excellent, good, okay, difficult, complicated
    relationship_with_siblings = Column(String(50))
    bullying_experience = Column(String(50))  # never, past, current, prefer_not_to_say
    social_media_usage = Column(String(50))  # none, light, moderate, heavy
    online_safety_concerns = Column(JSONB)
    
    # ============================================
    # INTERESTS & HOBBIES
    # ============================================
    hobbies = Column(JSONB)  # List of hobbies
    favorite_activities = Column(JSONB)  # Sports, arts, gaming, reading, etc.
    extracurricular_activities = Column(JSONB)  # Clubs, teams, lessons
    screen_time_daily = Column(Float)  # Hours per day
    creative_outlets = Column(JSONB)  # Drawing, music, writing, etc.
    
    # ============================================
    # GOALS & ASPIRATIONS
    # ============================================
    personal_goals = Column(JSONB)  # What they want to achieve
    academic_goals = Column(JSONB)  # School-related goals
    social_goals = Column(JSONB)  # Friendship/relationship goals
    dream_career = Column(String(255))  # What they want to be
    role_models = Column(JSONB)  # People they look up to
    
    # ============================================
    # FAMILY INFORMATION
    # ============================================
    family_structure = Column(String(100))  # two_parents, single_parent, guardian, etc.
    number_of_siblings = Column(Integer)
    birth_order = Column(String(50))  # only, oldest, middle, youngest
    parent_guardian_name = Column(String(255))
    parent_guardian_phone = Column(String(50))
    parent_guardian_email = Column(String(255))
    emergency_contact_name = Column(String(255))
    emergency_contact_phone = Column(String(50))
    emergency_contact_relationship = Column(String(100))
    
    # ============================================
    # HEALTH & MEDICAL (Simplified for kids)
    # ============================================
    allergies = Column(JSONB)  # Food, medicine, environmental
    medical_conditions = Column(JSONB)  # Asthma, diabetes, etc.
    current_medications = Column(JSONB)
    dietary_restrictions = Column(JSONB)  # Vegetarian, halal, allergies, etc.
    
    # ============================================
    # AI PERSONALIZATION
    # ============================================
    preferred_language = Column(String(10), default="zh-HK")  # en, zh-HK
    communication_style = Column(String(50), default="friendly")  # friendly, casual, supportive
    avatar_preference = Column(String(50))  # Which Live2D character they prefer
    notification_preferences = Column(JSONB)
    topics_to_avoid = Column(JSONB)  # Sensitive topics to avoid
    
    # ============================================
    # PRIVACY & CONSENT
    # ============================================
    privacy_level = Column(String(50), default="standard")
    parental_consent = Column(Boolean, default=False)
    data_sharing_consent = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="health_profile_record")
    mood_logs = relationship("MoodLog", back_populates="health_profile", cascade="all, delete-orphan")
    growth_records = relationship("GrowthRecord", back_populates="health_profile", cascade="all, delete-orphan")
    goal_tracking = relationship("GoalTracking", back_populates="health_profile", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<HealthProfile(user_id={self.user_id}, age={self.age}, age_group={self.age_group})>"
    
    def get_age(self) -> Optional[int]:
        """Calculate age from date of birth"""
        if self.age:
            return self.age
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
    
    def get_age_group(self) -> Optional[str]:
        """Determine age group from age"""
        age = self.get_age()
        if age is None:
            return self.age_group.value if self.age_group else None
        if age <= 12:
            return "child"
        if age <= 17:
            return "teen"
        return "adult"
    
    def get_profile_summary_for_ai(self) -> dict:
        """Get a summary of profile data for AI context"""
        return {
            "nickname": self.nickname,
            "age": self.get_age(),
            "age_group": self.get_age_group(),
            "gender": self.gender.value if self.gender else None,
            "school_level": self.school_level.value if self.school_level else None,
            "current_mood": self.current_mood,
            "stress_level": self.stress_level,
            "stress_sources": self.stress_sources,
            "hobbies": self.hobbies,
            "favorite_activities": self.favorite_activities,
            "personal_goals": self.personal_goals,
            "coping_strategies": self.coping_strategies,
            "communication_style": self.communication_style,
            "topics_to_avoid": self.topics_to_avoid,
            "mental_health_concerns": self.mental_health_concerns,
        }


class MoodLog(Base, TimestampMixin):
    """Daily mood tracking for teens/kids"""
    
    __tablename__ = "mood_logs"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    health_profile_id = Column(Integer, ForeignKey("health_profiles.id"), nullable=False)
    
    # Mood information
    log_date = Column(Date, nullable=False, index=True)
    mood = Column(String(50), nullable=False)  # happy, okay, sad, anxious, stressed, angry, excited, tired
    mood_intensity = Column(Integer)  # 1-5 scale
    
    # Context
    time_of_day = Column(String(20))  # morning, afternoon, evening, night
    location = Column(String(50))  # home, school, outside, other
    activity = Column(String(100))  # What were they doing
    
    # Triggers and factors
    triggers = Column(JSONB)  # What caused this mood
    sleep_quality_last_night = Column(String(50))  # good, okay, poor
    energy_level = Column(Integer)  # 1-5 scale
    
    # Social context
    with_whom = Column(String(100))  # alone, family, friends, classmates
    social_interaction_quality = Column(String(50))  # positive, neutral, negative
    
    # School-related (if applicable)
    school_day_rating = Column(Integer)  # 1-5 scale
    homework_stress = Column(Integer)  # 1-5 scale
    exam_stress = Column(Integer)  # 1-5 scale
    
    # Coping
    coping_strategy_used = Column(String(255))
    coping_effectiveness = Column(Integer)  # 1-5 scale
    
    # Notes
    journal_entry = Column(Text)  # Free-form journaling
    gratitude_note = Column(Text)  # What they're grateful for
    
    # AI interaction
    ai_response = Column(Text)  # AI's supportive response
    helpful_rating = Column(Integer)  # Was AI response helpful? 1-5
    
    # Relationships
    health_profile = relationship("HealthProfile", back_populates="mood_logs")
    
    def __repr__(self):
        return f"<MoodLog(date='{self.log_date}', mood='{self.mood}')>"


class GrowthRecord(Base, TimestampMixin):
    """Physical growth tracking for children/teens"""
    
    __tablename__ = "growth_records"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    health_profile_id = Column(Integer, ForeignKey("health_profiles.id"), nullable=False)
    
    # Measurement date
    record_date = Column(Date, nullable=False, index=True)
    age_at_record = Column(Float)  # Age in years (e.g., 12.5)
    
    # Physical measurements
    height_cm = Column(Float)
    weight_kg = Column(Float)
    bmi = Column(Float)  # Calculated BMI
    
    # Growth percentiles (compared to HK/WHO standards)
    height_percentile = Column(Float)
    weight_percentile = Column(Float)
    bmi_percentile = Column(Float)
    
    # Additional measurements
    head_circumference_cm = Column(Float)  # For younger children
    waist_circumference_cm = Column(Float)
    
    # Notes
    notes = Column(Text)
    measured_by = Column(String(100))  # self, parent, doctor, school
    
    # Relationships
    health_profile = relationship("HealthProfile", back_populates="growth_records")
    
    def __repr__(self):
        return f"<GrowthRecord(date='{self.record_date}', height={self.height_cm}cm, weight={self.weight_kg}kg)>"


class GoalTracking(Base, TimestampMixin):
    """Personal goals tracking for teens/kids"""
    
    __tablename__ = "goal_tracking"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    health_profile_id = Column(Integer, ForeignKey("health_profiles.id"), nullable=False)
    
    # Goal information
    goal_type = Column(String(50), nullable=False, index=True)  # personal, academic, social, health, hobby
    title = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Target and progress
    target_date = Column(Date)
    progress_percentage = Column(Float, default=0.0)
    status = Column(String(50), default="active")  # active, completed, paused, dropped
    
    # Milestones
    milestones = Column(JSONB)  # List of milestones with completion status
    
    # Motivation
    why_important = Column(Text)  # Why this goal matters to them
    reward_planned = Column(String(255))  # What they'll do when achieved
    
    # Support
    support_needed = Column(Text)  # What help they need
    accountability_partner = Column(String(100))  # Who's helping them
    
    # AI coaching
    ai_encouragement_enabled = Column(Boolean, default=True)
    last_check_in = Column(DateTime(timezone=True))
    
    # Relationships
    health_profile = relationship("HealthProfile", back_populates="goal_tracking")
    
    def __repr__(self):
        return f"<GoalTracking(title='{self.title}', progress={self.progress_percentage}%)>"


class ConversationContext(Base, TimestampMixin):
    """Enhanced conversation context for personalized responses"""
    
    __tablename__ = "conversation_contexts"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    
    # Teen/Kids specific context
    current_mood = Column(String(50))  # Mood at start of conversation
    stress_indicators = Column(JSONB)  # Detected stress signals
    topics_discussed = Column(JSONB)  # Topics covered in conversation
    
    # School-related context
    school_related = Column(Boolean, default=False)
    exam_stress_detected = Column(Boolean, default=False)
    homework_help_needed = Column(Boolean, default=False)
    
    # Social context
    social_issues_mentioned = Column(JSONB)  # Friendship, bullying, etc.
    family_issues_mentioned = Column(JSONB)
    
    # Mental health indicators
    emotional_state = Column(String(50))  # anxious, worried, calm, stressed, etc.
    urgency_level = Column(String(50))  # low, medium, high, crisis
    follow_up_needed = Column(Boolean, default=False)
    follow_up_reason = Column(Text)
    
    # AI response context
    communication_style_used = Column(String(50))  # friendly, supportive, encouraging
    age_appropriate_language = Column(Boolean, default=True)
    
    # Goals and progress mentioned
    goals_referenced = Column(JSONB)
    achievements_celebrated = Column(JSONB)
    
    # Safety flags
    safety_concern_detected = Column(Boolean, default=False)
    safety_concern_type = Column(String(100))  # self_harm, bullying, abuse, etc.
    escalation_triggered = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User")
    conversation = relationship("Conversation")
    
    def __repr__(self):
        return f"<ConversationContext(user_id={self.user_id}, conversation_id={self.conversation_id})>"


# Export all models
__all__ = [
    "HealthProfile",
    "MoodLog",
    "GrowthRecord",
    "GoalTracking",
    "ConversationContext",
    "GenderEnum",
    "AgeGroupEnum",
    "SchoolLevelEnum",
]
