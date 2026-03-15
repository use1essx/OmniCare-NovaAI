"""
Healthcare AI V2 - Movement Analysis Pydantic Schemas
Request/Response models for movement analysis API endpoints
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field, field_validator, ConfigDict


class AssessmentStatus(str, Enum):
    """Assessment processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoType(str, Enum):
    """Video source type"""
    LOCAL = "local"
    YOUTUBE = "youtube"


class AgeUnit(str, Enum):
    """Age unit for child"""
    YEAR = "year"
    MONTH = "month"


# ============================================================================
# Movement Analysis Rule Schemas
# ============================================================================

class TextStandards(BaseModel):
    """Text standards for assessment rule"""
    source_files: Optional[str] = None
    rubric: Optional[str] = None


class ResponseTemplate(BaseModel):
    """Response formatting template"""
    instruction: Optional[str] = None
    structure: Optional[Dict[str, str]] = None


class AssessmentRuleBase(BaseModel):
    """Base schema for assessment rule"""
    index_code: Optional[str] = Field(None, max_length=100)
    category: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    ai_role: Optional[str] = Field(None, max_length=255)
    reference_video_url: Optional[str] = None
    reference_description: Optional[str] = None
    text_standards: Optional[Dict[str, Any]] = None
    analysis_instruction: Optional[str] = None
    response_template: Optional[Dict[str, Any]] = None
    is_active: bool = True


class AssessmentRuleCreate(AssessmentRuleBase):
    """Schema for creating an assessment rule"""
    pass


class AssessmentRuleUpdate(BaseModel):
    """Schema for updating an assessment rule"""
    index_code: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    ai_role: Optional[str] = Field(None, max_length=255)
    reference_video_url: Optional[str] = None
    reference_description: Optional[str] = None
    text_standards: Optional[Dict[str, Any]] = None
    analysis_instruction: Optional[str] = None
    response_template: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class AssessmentRuleResponse(AssessmentRuleBase):
    """Schema for assessment rule response"""
    id: int
    created_by: Optional[int] = None
    organization_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AssessmentRuleListResponse(BaseModel):
    """Paginated list of assessment rules"""
    rules: List[AssessmentRuleResponse]
    total: int
    page: int
    limit: int
    pages: int


# ============================================================================
# Assessment Schemas
# ============================================================================

class AssessmentBase(BaseModel):
    """Base schema for assessment"""
    rule_id: Optional[int] = None
    video_type: VideoType = VideoType.LOCAL
    youtube_url: Optional[str] = None
    age_value: Optional[float] = Field(None, ge=0, le=150)
    age_unit: Optional[AgeUnit] = None
    child_description: Optional[str] = None


class AssessmentCreate(AssessmentBase):
    """Schema for creating an assessment (video upload)"""
    
    @field_validator('youtube_url')
    @classmethod
    def validate_youtube_url(cls, v, info):
        if info.data.get('video_type') == VideoType.YOUTUBE and not v:
            raise ValueError('YouTube URL is required when video_type is youtube')
        return v


class AssessmentResponse(BaseModel):
    """Schema for assessment response"""
    id: int
    user_id: int
    rule_id: Optional[int] = None
    rule_category: Optional[str] = None
    video_filename: Optional[str] = None
    video_type: str
    youtube_url: Optional[str] = None
    age_value: Optional[float] = None
    age_unit: Optional[str] = None
    child_description: Optional[str] = None
    status: AssessmentStatus
    error_message: Optional[str] = None
    organization_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    result: Optional["AssessmentResultResponse"] = None
    
    model_config = ConfigDict(from_attributes=True)


class AssessmentListResponse(BaseModel):
    """Paginated list of assessments"""
    assessments: List[AssessmentResponse]
    total: int
    page: int
    limit: int
    pages: int


class AssessmentStatusResponse(BaseModel):
    """Assessment status check response"""
    id: int
    status: AssessmentStatus
    error_message: Optional[str] = None
    result: Optional["AssessmentResultResponse"] = None


# ============================================================================
# Assessment Result Schemas
# ============================================================================

class AssessmentResultResponse(BaseModel):
    """Schema for assessment result response"""
    id: int
    assessment_id: int
    user_view_md: Optional[str] = None
    staff_view_md: Optional[str] = None  # Only included for authorized staff
    storage_json: Optional[Dict[str, Any]] = None  # Only included for authorized staff
    processing_time_ms: Optional[int] = None
    model_used: Optional[str] = None
    frames_analyzed: Optional[int] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AssessmentResultUserView(BaseModel):
    """Simplified result view for parents/users"""
    id: int
    assessment_id: int
    user_view_md: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Video Upload Schemas
# ============================================================================

class VideoUploadResponse(BaseModel):
    """Response after video upload"""
    assessment_id: int
    status: AssessmentStatus
    message: str


class VideoProcessingProgress(BaseModel):
    """Progress update during video processing"""
    assessment_id: int
    status: AssessmentStatus
    progress_percent: int = Field(ge=0, le=100)
    current_step: Optional[str] = None
    message: Optional[str] = None


# ============================================================================
# History and Statistics Schemas
# ============================================================================

class AssessmentHistoryItem(BaseModel):
    """Single item in assessment history"""
    id: int
    rule_category: Optional[str] = None
    age_value: Optional[float] = None
    age_unit: Optional[str] = None
    status: AssessmentStatus
    created_at: datetime
    user_view_summary: Optional[str] = None  # Truncated preview
    
    # Additional fields for staff view
    user_id: Optional[int] = None
    username: Optional[str] = None
    user_display_name: Optional[str] = None


class AssessmentHistoryResponse(BaseModel):
    """Paginated assessment history"""
    history: List[AssessmentHistoryItem]
    total: int
    page: int
    limit: int
    pages: int


class AssessmentStatsResponse(BaseModel):
    """Assessment statistics"""
    total_assessments: int
    completed_assessments: int
    pending_assessments: int
    failed_assessments: int
    assessments_by_rule: Dict[str, int]
    recent_assessments: List[AssessmentHistoryItem]


# Update forward references
AssessmentResponse.model_rebuild()
AssessmentStatusResponse.model_rebuild()

