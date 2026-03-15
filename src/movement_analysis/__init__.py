"""
Healthcare AI V2 - Movement Analysis Module
Pediatric Movement Analysis System

This module provides:
- Video-based movement analysis using AI (Gemini 2.5 Flash)
- Rule-based analysis framework
- Role-differentiated reporting (parent vs staff views)
- Assignment-based access control
- Reference video library with PDF/DOCX document support (old system method)
"""

import logging

logger = logging.getLogger(__name__)

# Core imports that don't require OpenCV
from .models import AssessmentRule, Assessment, AssessmentResult, ReferenceVideo  # noqa: E402
from .schemas import (  # noqa: E402
    AssessmentRuleCreate,
    AssessmentRuleUpdate,
    AssessmentRuleResponse,
    AssessmentRuleListResponse,
    AssessmentCreate,
    AssessmentResponse,
    AssessmentResultResponse,
    AssessmentStatus,
    AssessmentListResponse,
    AssessmentHistoryResponse,
    VideoUploadResponse,
)
from .rules_service import AssessmentRulesService  # noqa: E402
from .access_control import (  # noqa: E402
    can_view_assessment,
    can_view_user_assessments,
    can_view_staff_report,
    can_manage_assessment_rules,
    is_super_admin,
    is_org_admin,
    is_healthcare_staff,
)
from .document_processor import (  # noqa: E402
    extract_docx_text,
    extract_pdf_text,
    extract_document_text,
    is_document_supported,
)

# Try to import video processing (requires OpenCV/cv2)
# This may fail in environments without libGL
try:
    from .service import AssessmentService, save_uploaded_video
    from .video_processor import VideoProcessor, get_video_processor, VideoProcessingError
    from .reference_video_service import ReferenceVideoService
    VIDEO_PROCESSING_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Video processing unavailable (missing dependency): {e}")
    VIDEO_PROCESSING_AVAILABLE = False
    # Provide stub classes/functions
    AssessmentService = None
    save_uploaded_video = None
    VideoProcessor = None
    get_video_processor = None
    ReferenceVideoService = None
    class VideoProcessingError(Exception):
        pass

__all__ = [
    # Models
    "AssessmentRule",
    "Assessment",
    "AssessmentResult",
    "ReferenceVideo",
    # Schemas
    "AssessmentRuleCreate",
    "AssessmentRuleUpdate",
    "AssessmentRuleResponse",
    "AssessmentRuleListResponse",
    "AssessmentCreate",
    "AssessmentResponse",
    "AssessmentResultResponse",
    "AssessmentStatus",
    "AssessmentListResponse",
    "AssessmentHistoryResponse",
    "VideoUploadResponse",
    # Services
    "AssessmentService",
    "AssessmentRulesService",
    "ReferenceVideoService",
    "save_uploaded_video",
    # Video Processing
    "VideoProcessor",
    "get_video_processor",
    "VideoProcessingError",
    "VIDEO_PROCESSING_AVAILABLE",
    # Document Processing
    "extract_docx_text",
    "extract_pdf_text",
    "extract_document_text",
    "is_document_supported",
    # Access Control
    "can_view_assessment",
    "can_view_user_assessments",
    "can_view_staff_report",
    "can_manage_assessment_rules",
    "is_super_admin",
    "is_org_admin",
    "is_healthcare_staff",
]

