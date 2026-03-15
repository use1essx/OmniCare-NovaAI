"""
Healthcare AI V2 - Movement Analysis Service
Business logic for movement analysis operations
"""

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.database.models_comprehensive import User
from .models import Assessment, AssessmentResult
from .schemas import (
    AssessmentStatus,
    AssessmentHistoryItem,
)
from .video_processor import get_video_processor, VideoProcessingError
from .access_control import (
    can_view_assessment,
    can_view_user_assessments,
    can_view_staff_report,
    get_assessment_query_filter,
    is_super_admin,
    is_org_admin,
    is_healthcare_staff,
)

logger = logging.getLogger(__name__)


class AssessmentService:
    """
    Service for managing assessments and processing video analysis
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.video_processor = get_video_processor()
        self.upload_folder = settings.upload_path / "assessments"
        self.upload_folder.mkdir(parents=True, exist_ok=True)
    
    async def create_assessment(
        self,
        user: User,
        rule_id: Optional[int],
        video_filename: str,
        video_path: str,
        video_type: str = "local",
        youtube_url: Optional[str] = None,
        age_value: Optional[float] = None,
        age_unit: Optional[str] = None,
        age_group: Optional[str] = None,
        child_description: Optional[str] = None,
        language_preference: str = "en"
    ) -> Assessment:
        """
        Create a new assessment record
        
        Args:
            user: User creating the assessment
            rule_id: Assessment rule ID
            video_filename: Original video filename
            video_path: Path to uploaded video
            video_type: Type of video (local/youtube)
            youtube_url: YouTube URL if applicable
            age_value: Child's age
            age_unit: Age unit (year/month)
            age_group: Optional manual age group override (infant_toddler, child, teen, adult, elderly)
            child_description: Optional notes
            language_preference: Response language (en or zh-HK)
            
        Returns:
            Created Assessment object
        """
        # SECURITY: Validate language parameter
        if language_preference not in ["en", "zh-HK"]:
            language_preference = "en"
        
        # VALIDATION: Validate age_group if provided
        valid_age_groups = ["infant_toddler", "child", "teen", "adult", "elderly"]
        if age_group and age_group not in valid_age_groups:
            age_group = None  # Ignore invalid age group
        
        assessment = Assessment(
            user_id=user.id,
            rule_id=rule_id,
            video_filename=video_filename,
            video_path=video_path,
            video_type=video_type,
            youtube_url=youtube_url,
            age_value=age_value,
            age_unit=age_unit,
            age_group=age_group,
            child_description=child_description,
            language_preference=language_preference,
            status="pending",
            organization_id=getattr(user, "organization_id", None)
        )
        
        self.db.add(assessment)
        await self.db.commit()
        await self.db.refresh(assessment)
        
        logger.info(f"Created assessment {assessment.id} for user {user.id} with language {language_preference}, age_group {age_group}")
        return assessment
    
    async def process_assessment(self, assessment_id: int) -> AssessmentResult:
        """
        Process an assessment: extract frames, analyze with AI, store results
        
        Args:
            assessment_id: ID of assessment to process
            
        Returns:
            AssessmentResult with analysis
            
        Raises:
            ValueError: If assessment not found or already processed
            VideoProcessingError: If processing fails
        """
        # Get assessment with rule
        result = await self.db.execute(
            select(Assessment)
            .options(selectinload(Assessment.rule))
            .where(Assessment.id == assessment_id)
        )
        assessment = result.scalar_one_or_none()
        
        if not assessment:
            raise ValueError(f"Assessment {assessment_id} not found")
        
        if assessment.status == "completed":
            raise ValueError(f"Assessment {assessment_id} already processed")
        
        # Update status to processing
        assessment.status = "processing"
        await self.db.commit()
        
        try:
            # Get video path
            video_path = assessment.video_path
            if not video_path or not os.path.exists(video_path):
                raise VideoProcessingError(f"Video file not found: {video_path}")
            
            # Extract frames
            frames, total_frames = self.video_processor.extract_frames(video_path)
            
            if not frames:
                raise VideoProcessingError("No frames extracted from video")
            
            # Build prompt from rule
            rule_data = {}
            if assessment.rule:
                rule_data = {
                    "ai_role": assessment.rule.ai_role,
                    "category": assessment.rule.category,
                    "description": assessment.rule.description,
                    "reference_description": assessment.rule.reference_description,
                    "text_standards": assessment.rule.text_standards,
                    "analysis_instruction": assessment.rule.analysis_instruction,
                    "response_template": assessment.rule.response_template,
                }
            
            # Pass manual age_group if provided, otherwise will be calculated from age_value
            prompt = self.video_processor.build_assessment_prompt(
                rule_data=rule_data,
                age_value=float(assessment.age_value) if assessment.age_value else None,
                age_unit=assessment.age_unit,
                age_group=assessment.age_group,  # Pass manual age_group selection
                child_description=assessment.child_description,
                language=assessment.language_preference or "en"
            )
            
            # DEBUG: Log what was passed to prompt builder
            logger.info(f"📋 PROMPT BUILDER INPUT for assessment {assessment_id}:")
            logger.info(f"  - age_value from DB: {assessment.age_value}")
            logger.info(f"  - age_unit from DB: {assessment.age_unit}")
            logger.info(f"  - age_group from DB: {assessment.age_group}")
            logger.info(f"  - language: {assessment.language_preference or 'en'}")
            
            # Stage 1: Initial AI Analysis
            logger.info(f"🎬 Stage 1: Initial analysis for assessment {assessment_id}")
            ai_result = await self.video_processor.analyze_video_with_ai(frames, prompt)
            
            if not ai_result.get("success"):
                raise VideoProcessingError(ai_result.get("error", "AI analysis failed"))
            
            initial_content = ai_result.get("content", "")
            
            # Stage 2: Fact-Checking & Refinement
            logger.info(f"🔍 Stage 2: Fact-checking analysis for assessment {assessment_id}")
            fact_check_result = await self.video_processor.fact_check_analysis(
                frames=frames,
                initial_analysis=initial_content,
                language=assessment.language_preference or "en"
            )
            
            # Use fact-checked content if available, otherwise use initial
            if fact_check_result.get("fact_checked"):
                content = fact_check_result.get("content", initial_content)
                logger.info(f"✅ Using fact-checked analysis for assessment {assessment_id}")
            else:
                content = initial_content
                logger.warning(f"⚠️ Fact-check unavailable, using initial analysis for assessment {assessment_id}")
            
            # Parse response into role-based views
            user_view, staff_view, storage_json_text = self.video_processor.split_role_report(content)
            storage_json = self.video_processor.parse_storage_json(storage_json_text)
            
            # Create result record
            assessment_result = AssessmentResult(
                assessment_id=assessment.id,
                user_view_md=user_view,
                staff_view_md=staff_view,
                storage_json=storage_json,
                full_response=content,
                processing_time_ms=ai_result.get("processing_time_ms") + fact_check_result.get("processing_time_ms", 0),
                model_used=ai_result.get("model"),
                frames_analyzed=ai_result.get("frames_analyzed")
            )
            
            self.db.add(assessment_result)
            
            # Update assessment status
            assessment.status = "completed"
            await self.db.commit()
            await self.db.refresh(assessment_result)
            
            logger.info(f"✅ Completed processing assessment {assessment_id} (fact-checked: {fact_check_result.get('fact_checked', False)})")
            return assessment_result
            
        except Exception as e:
            logger.error(f"Error processing assessment {assessment_id}: {e}")
            assessment.status = "failed"
            assessment.error_message = str(e)
            await self.db.commit()
            raise
    
    async def get_assessment(
        self,
        assessment_id: int,
        current_user: User
    ) -> Optional[Dict[str, Any]]:
        """
        Get assessment by ID with access control
        
        Args:
            assessment_id: Assessment ID
            current_user: User requesting access
            
        Returns:
            Assessment data dict or None if not found/unauthorized
        """
        result = await self.db.execute(
            select(Assessment)
            .options(selectinload(Assessment.rule), selectinload(Assessment.result))
            .where(Assessment.id == assessment_id)
        )
        assessment = result.scalar_one_or_none()
        
        if not assessment:
            return None
        
        # Check access
        if not await can_view_assessment(current_user, assessment, self.db):
            return None
        
        # Build response
        data = assessment.to_dict(include_result=True)
        
        # Include staff view only if authorized
        if assessment.result:
            include_staff = can_view_staff_report(current_user, assessment)
            data["result"] = assessment.result.to_dict(include_staff_view=include_staff)
        
        return data
    
    async def get_assessment_status(
        self,
        assessment_id: int,
        current_user: User
    ) -> Optional[Dict[str, Any]]:
        """
        Get assessment status (for polling during processing)
        """
        result = await self.db.execute(
            select(Assessment)
            .options(selectinload(Assessment.result))
            .where(Assessment.id == assessment_id)
        )
        assessment = result.scalar_one_or_none()
        
        if not assessment:
            return None
        
        if not await can_view_assessment(current_user, assessment, self.db):
            return None
        
        response = {
            "id": assessment.id,
            "status": assessment.status,
            "error_message": assessment.error_message
        }
        
        if assessment.status == "completed" and assessment.result:
            include_staff = can_view_staff_report(current_user, assessment)
            response["result"] = assessment.result.to_dict(include_staff_view=include_staff)
        
        return response
    
    async def list_assessments(
        self,
        current_user: User,
        page: int = 1,
        limit: int = 20,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        rule_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        List assessments with access control and pagination
        
        Args:
            current_user: User making the request
            page: Page number (1-indexed)
            limit: Items per page
            user_id: Filter by specific user (if authorized)
            status: Filter by status
            rule_id: Filter by rule
            
        Returns:
            Paginated list of assessments
        """
        # Build base query with relationships
        query = select(Assessment).options(
            selectinload(Assessment.rule),
            selectinload(Assessment.result),
            selectinload(Assessment.user)
        )
        
        # Apply access control filter
        query = get_assessment_query_filter(current_user, query)
        
        # Apply additional filters
        if user_id is not None:
            # Check if user can view this specific user's assessments
            if await can_view_user_assessments(current_user, user_id, self.db):
                query = query.where(Assessment.user_id == user_id)
            else:
                # Return empty result if not authorized
                return {
                    "assessments": [],
                    "total": 0,
                    "page": page,
                    "limit": limit,
                    "pages": 0
                }
        
        if status:
            query = query.where(Assessment.status == status)
        
        if rule_id:
            query = query.where(Assessment.rule_id == rule_id)
        
        # Order by creation date (newest first)
        query = query.order_by(Assessment.created_at.desc())
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        
        # Execute query
        result = await self.db.execute(query)
        assessments = result.scalars().all()
        
        # Format response
        assessment_list = []
        for assessment in assessments:
            data = assessment.to_dict(include_result=True)
            
            # Add user info for staff views
            if assessment.user and (is_super_admin(current_user) or is_org_admin(current_user) or is_healthcare_staff(current_user)):
                data["username"] = assessment.user.username
                data["user_display_name"] = assessment.user.full_name
            
            # Include staff view only if authorized
            if assessment.result:
                include_staff = can_view_staff_report(current_user, assessment)
                data["result"] = assessment.result.to_dict(include_staff_view=include_staff)
            
            assessment_list.append(data)
        
        return {
            "assessments": assessment_list,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if total > 0 else 0
        }
    
    async def get_assessment_history(
        self,
        current_user: User,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get assessment history for current user or assigned users
        
        Returns simplified history items for display
        """
        result = await self.list_assessments(current_user, page, limit)
        
        # Convert to history items
        history_items = []
        for assessment in result["assessments"]:
            item = AssessmentHistoryItem(
                id=assessment["id"],
                rule_category=assessment.get("rule_category"),
                age_value=assessment.get("age_value"),
                age_unit=assessment.get("age_unit"),
                status=AssessmentStatus(assessment["status"]),
                created_at=datetime.fromisoformat(assessment["created_at"]),
                user_view_summary=None
            )
            
            # Add truncated summary
            if assessment.get("result") and assessment["result"].get("user_view_md"):
                summary = assessment["result"]["user_view_md"][:200]
                if len(assessment["result"]["user_view_md"]) > 200:
                    summary += "..."
                item.user_view_summary = summary
            
            # Add user info for staff
            if "username" in assessment:
                item.user_id = assessment.get("user_id")
                item.username = assessment.get("username")
                item.user_display_name = assessment.get("user_display_name")
            
            history_items.append(item)
        
        return {
            "history": [item.model_dump() for item in history_items],
            "total": result["total"],
            "page": result["page"],
            "limit": result["limit"],
            "pages": result["pages"]
        }
    
    async def delete_assessment(
        self,
        assessment_id: int,
        current_user: User
    ) -> bool:
        """
        Delete an assessment (only owner or admin)
        
        Args:
            assessment_id: Assessment to delete
            current_user: User making the request
            
        Returns:
            True if deleted, False if not found/unauthorized
        """
        result = await self.db.execute(
            select(Assessment).where(Assessment.id == assessment_id)
        )
        assessment = result.scalar_one_or_none()
        
        if not assessment:
            return False
        
        # Only owner, org admin, or super admin can delete
        can_delete = (
            assessment.user_id == current_user.id or
            is_super_admin(current_user) or
            (is_org_admin(current_user) and current_user.organization_id == assessment.organization_id)
        )
        
        if not can_delete:
            return False
        
        # Delete video file if exists
        if assessment.video_path and os.path.exists(assessment.video_path):
            try:
                os.remove(assessment.video_path)
            except Exception as e:
                logger.warning(f"Failed to delete video file: {e}")
        
        await self.db.delete(assessment)
        await self.db.commit()
        
        logger.info(f"Deleted assessment {assessment_id} by user {current_user.id}")
        return True
    
    async def get_stats(
        self,
        current_user: User,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get assessment statistics
        
        Args:
            current_user: User making the request
            user_id: Optional specific user ID
            
        Returns:
            Statistics dict
        """
        # Build base query with access control
        query = select(Assessment)
        query = get_assessment_query_filter(current_user, query)
        
        if user_id and await can_view_user_assessments(current_user, user_id, self.db):
            query = query.where(Assessment.user_id == user_id)
        
        # Get counts by status
        result = await self.db.execute(query)
        assessments = result.scalars().all()
        
        total = len(assessments)
        completed = sum(1 for a in assessments if a.status == "completed")
        pending = sum(1 for a in assessments if a.status == "pending")
        processing = sum(1 for a in assessments if a.status == "processing")
        failed = sum(1 for a in assessments if a.status == "failed")
        
        # Count by rule
        rule_counts = {}
        for a in assessments:
            if a.rule:
                category = a.rule.category
                rule_counts[category] = rule_counts.get(category, 0) + 1
        
        return {
            "total_assessments": total,
            "completed_assessments": completed,
            "pending_assessments": pending,
            "processing_assessments": processing,
            "failed_assessments": failed,
            "assessments_by_rule": rule_counts
        }


def save_uploaded_video(
    file_content: bytes,
    original_filename: str,
    upload_folder: Path
) -> Tuple[str, str]:
    """
    Save uploaded video file
    
    Args:
        file_content: Video file bytes
        original_filename: Original filename
        upload_folder: Folder to save to
        
    Returns:
        Tuple of (saved_filename, full_path)
    """
    upload_folder.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    ext = Path(original_filename).suffix.lower() or ".mp4"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    filename = f"assessment_{timestamp}_{unique_id}{ext}"
    
    filepath = upload_folder / filename
    
    with open(filepath, "wb") as f:
        f.write(file_content)
    
    logger.info(f"Saved uploaded video: {filename}")
    return filename, str(filepath)

