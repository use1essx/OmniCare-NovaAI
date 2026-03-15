"""
Healthcare AI V2 - Health Profile Schemas
Pydantic models for health profile requests and responses
"""

from datetime import datetime, date
from typing import Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field


class GenderEnum(str, Enum):
    """Gender options"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class BloodTypeEnum(str, Enum):
    """Blood type options"""
    A_POSITIVE = "A+"
    A_NEGATIVE = "A-"
    B_POSITIVE = "B+"
    B_NEGATIVE = "B-"
    AB_POSITIVE = "AB+"
    AB_NEGATIVE = "AB-"
    O_POSITIVE = "O+"
    O_NEGATIVE = "O-"
    UNKNOWN = "unknown"


class HealthProfileCreateRequest(BaseModel):
    """Health profile creation request"""
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    gender: Optional[GenderEnum] = Field(None, description="Gender")
    height_cm: Optional[float] = Field(None, ge=50, le=300, description="Height in centimeters")
    weight_kg: Optional[float] = Field(None, ge=20, le=500, description="Weight in kilograms")
    blood_type: Optional[BloodTypeEnum] = Field(None, description="Blood type")
    
    # Health conditions
    chronic_conditions: Optional[List[str]] = Field(default=[], description="Chronic medical conditions")
    allergies: Optional[List[str]] = Field(default=[], description="Allergies and sensitivities")
    current_medications: Optional[List[Dict]] = Field(default=[], description="Current medications")
    past_surgeries: Optional[List[Dict]] = Field(default=[], description="Past surgical procedures")
    family_medical_history: Optional[List[Dict]] = Field(default=[], description="Family medical history")
    
    # Lifestyle
    smoking_status: Optional[str] = Field(None, description="Smoking status")
    alcohol_consumption: Optional[str] = Field(None, description="Alcohol consumption level")
    exercise_frequency: Optional[str] = Field(None, description="Exercise frequency")
    diet_type: Optional[str] = Field(None, description="Diet type")
    sleep_hours_avg: Optional[float] = Field(None, ge=0, le=24, description="Average sleep hours")
    
    # Emergency contact
    emergency_contact_name: Optional[str] = Field(None, max_length=255, description="Emergency contact name")
    emergency_contact_phone: Optional[str] = Field(None, max_length=50, description="Emergency contact phone")
    emergency_contact_relationship: Optional[str] = Field(None, max_length=100, description="Relationship to emergency contact")
    
    # Healthcare preferences
    preferred_language: Optional[str] = Field("en", description="Preferred language")
    preferred_hospital: Optional[str] = Field(None, max_length=255, description="Preferred hospital")
    preferred_doctor: Optional[str] = Field(None, max_length=255, description="Preferred doctor")
    insurance_provider: Optional[str] = Field(None, max_length=255, description="Insurance provider")
    insurance_number: Optional[str] = Field(None, max_length=100, description="Insurance number")
    
    # Goals and preferences
    health_goals: Optional[List[str]] = Field(default=[], description="Health goals")
    notification_preferences: Optional[Dict] = Field(default={}, description="Notification preferences")
    privacy_level: Optional[str] = Field("standard", description="Privacy level")
    
    # AI preferences
    preferred_agent_types: Optional[List[str]] = Field(default=[], description="Preferred AI agent types")
    interaction_style: Optional[str] = Field("professional", description="Interaction style preference")
    urgency_sensitivity: Optional[str] = Field("normal", description="Urgency sensitivity level")


class HealthProfileUpdateRequest(HealthProfileCreateRequest):
    """Health profile update request (same as create but all optional)"""
    pass


class HealthProfileResponse(BaseModel):
    """Health profile response"""
    id: int
    user_id: int
    
    # Basic information
    date_of_birth: Optional[date] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    blood_type: Optional[str] = None
    bmi: Optional[float] = None
    
    # Health conditions
    chronic_conditions: List[str] = []
    allergies: List[str] = []
    current_medications: List[Dict] = []
    past_surgeries: List[Dict] = []
    family_medical_history: List[Dict] = []
    
    # Lifestyle
    smoking_status: Optional[str] = None
    alcohol_consumption: Optional[str] = None
    exercise_frequency: Optional[str] = None
    diet_type: Optional[str] = None
    sleep_hours_avg: Optional[float] = None
    
    # Emergency contact
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None
    
    # Healthcare preferences
    preferred_language: str = "en"
    preferred_hospital: Optional[str] = None
    preferred_doctor: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_number: Optional[str] = None
    
    # Goals and preferences
    health_goals: List[str] = []
    notification_preferences: Dict = {}
    privacy_level: str = "standard"
    
    # AI preferences
    preferred_agent_types: List[str] = []
    interaction_style: str = "professional"
    urgency_sensitivity: str = "normal"
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MedicationRequest(BaseModel):
    """Medication schedule request"""
    medication_name: str = Field(..., max_length=255, description="Medication name")
    dosage: str = Field(..., max_length=100, description="Dosage amount")
    frequency: str = Field(..., max_length=100, description="Frequency description")
    route: Optional[str] = Field("oral", max_length=50, description="Route of administration")
    
    start_date: date = Field(..., description="Start date")
    end_date: Optional[date] = Field(None, description="End date (if applicable)")
    times_per_day: int = Field(1, ge=1, le=24, description="Times per day")
    specific_times: Optional[List[str]] = Field(default=[], description="Specific times (HH:MM format)")
    
    instructions: Optional[str] = Field(None, description="Special instructions")
    side_effects: Optional[str] = Field(None, description="Known side effects")
    prescribing_doctor: Optional[str] = Field(None, max_length=255, description="Prescribing doctor")
    pharmacy: Optional[str] = Field(None, max_length=255, description="Pharmacy")
    
    reminder_enabled: bool = Field(True, description="Enable reminders")
    reminder_advance_minutes: int = Field(15, ge=0, le=1440, description="Reminder advance time in minutes")
    is_critical: bool = Field(False, description="Is this a critical medication")


class MedicationResponse(BaseModel):
    """Medication schedule response"""
    id: int
    health_profile_id: int
    medication_name: str
    dosage: str
    frequency: str
    route: Optional[str] = None
    
    start_date: date
    end_date: Optional[date] = None
    times_per_day: int
    specific_times: List[str] = []
    
    instructions: Optional[str] = None
    side_effects: Optional[str] = None
    prescribing_doctor: Optional[str] = None
    pharmacy: Optional[str] = None
    
    reminder_enabled: bool
    reminder_advance_minutes: int
    is_active: bool
    is_critical: bool
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class HealthMetricRequest(BaseModel):
    """Health metric recording request"""
    metric_type: str = Field(..., max_length=100, description="Type of metric")
    value: float = Field(..., description="Metric value")
    unit: str = Field(..., max_length=20, description="Unit of measurement")
    
    systolic: Optional[float] = Field(None, description="Systolic pressure (for blood pressure)")
    diastolic: Optional[float] = Field(None, description="Diastolic pressure (for blood pressure)")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    recorded_at: Optional[datetime] = Field(None, description="When recorded (defaults to now)")
    device_info: Optional[Dict] = Field(None, description="Device information")


class HealthMetricResponse(BaseModel):
    """Health metric response"""
    id: int
    health_profile_id: int
    metric_type: str
    value: float
    unit: str
    
    systolic: Optional[float] = None
    diastolic: Optional[float] = None
    notes: Optional[str] = None
    
    recorded_at: datetime
    recorded_by: str = "user"
    device_info: Optional[Dict] = None
    
    is_validated: bool = False
    validation_source: Optional[str] = None
    
    created_at: datetime
    
    class Config:
        from_attributes = True


class HealthGoalRequest(BaseModel):
    """Health goal creation/update request"""
    goal_type: str = Field(..., max_length=100, description="Type of goal")
    title: str = Field(..., max_length=255, description="Goal title")
    description: Optional[str] = Field(None, description="Goal description")
    
    target_value: Optional[float] = Field(None, description="Target value")
    unit: Optional[str] = Field(None, max_length=20, description="Unit of measurement")
    target_date: Optional[date] = Field(None, description="Target completion date")
    
    milestones: Optional[List[Dict]] = Field(default=[], description="Progress milestones")
    rewards: Optional[List[Dict]] = Field(default=[], description="Rewards for achieving milestones")
    
    coaching_enabled: bool = Field(True, description="Enable AI coaching")
    reminder_frequency: str = Field("weekly", description="Reminder frequency")
    motivation_style: str = Field("encouraging", description="Motivation style")


class HealthGoalResponse(BaseModel):
    """Health goal response"""
    id: int
    health_profile_id: int
    goal_type: str
    title: str
    description: Optional[str] = None
    
    target_value: Optional[float] = None
    current_value: Optional[float] = None
    unit: Optional[str] = None
    target_date: Optional[date] = None
    
    status: str = "active"
    progress_percentage: float = 0.0
    
    milestones: List[Dict] = []
    rewards: List[Dict] = []
    
    coaching_enabled: bool = True
    reminder_frequency: str = "weekly"
    motivation_style: str = "encouraging"
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PersonalizedChatRequest(BaseModel):
    """Personalized chat request with user context"""
    message: str = Field(..., max_length=5000, description="User message")
    session_id: Optional[str] = Field(None, description="Session ID for context")
    
    # Context hints
    urgency_override: Optional[str] = Field(None, description="Override urgency detection")
    agent_preference: Optional[str] = Field(None, description="Preferred agent type")
    include_health_context: bool = Field(True, description="Include user's health profile in context")
    include_medication_context: bool = Field(True, description="Include current medications in context")
    include_goal_context: bool = Field(True, description="Include health goals in context")


class PersonalizedChatResponse(BaseModel):
    """Personalized chat response with user context"""
    reply: str
    agent_type: str
    agent_name: str
    confidence: float
    urgency_level: str
    
    # Personalization context used
    health_context_used: bool = False
    medications_referenced: List[str] = []
    goals_referenced: List[str] = []
    conditions_considered: List[str] = []
    
    # Live2D data
    live2d_data: Optional[Dict] = None
    
    # Follow-up suggestions
    follow_up_suggestions: List[str] = []
    recommended_actions: List[str] = []
    
    # Context for next interaction
    conversation_context: Dict
    session_id: str
    timestamp: datetime


class UserDashboardResponse(BaseModel):
    """User dashboard summary response"""
    user_info: Dict
    health_summary: Dict
    recent_metrics: List[HealthMetricResponse] = []
    active_medications: List[MedicationResponse] = []
    active_goals: List[HealthGoalResponse] = []
    recent_conversations: List[Dict] = []
    upcoming_reminders: List[Dict] = []
    health_insights: List[str] = []


# Export all schemas
__all__ = [
    "GenderEnum",
    "BloodTypeEnum",
    "HealthProfileCreateRequest",
    "HealthProfileUpdateRequest", 
    "HealthProfileResponse",
    "MedicationRequest",
    "MedicationResponse",
    "HealthMetricRequest",
    "HealthMetricResponse",
    "HealthGoalRequest",
    "HealthGoalResponse",
    "PersonalizedChatRequest",
    "PersonalizedChatResponse",
    "UserDashboardResponse",
]
