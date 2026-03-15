"""
Healthcare AI V2 - Reference Video Service
Business logic for managing reference/standard videos
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.database.models_comprehensive import User
from .models import ReferenceVideo, AssessmentRule
from .access_control import can_manage_assessment_rules, is_super_admin
from .document_processor import extract_document_text, is_document_supported
from .video_processor import get_video_processor

logger = logging.getLogger(__name__)


class ReferenceVideoService:
    """
    Service for managing reference/standard videos
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.video_processor = get_video_processor()
        self.upload_folder = settings.upload_path / "reference_videos"
        self.upload_folder.mkdir(parents=True, exist_ok=True)
    
    async def create_reference_video(
        self,
        title: str,
        current_user: User,
        video_content: Optional[bytes] = None,
        video_filename: Optional[str] = None,
        document_content: Optional[bytes] = None,
        document_filename: Optional[str] = None,
        auto_generate_rule: bool = True
    ) -> Tuple[ReferenceVideo, Optional[AssessmentRule]]:
        """
        Create a new reference video with optional document
        
        Args:
            title: Title for the reference video
            current_user: User creating the reference
            video_content: Video file bytes
            video_filename: Original video filename
            document_content: Document file bytes (PDF/DOCX)
            document_filename: Original document filename
            auto_generate_rule: Whether to auto-generate assessment rule
            
        Returns:
            Tuple of (ReferenceVideo, Optional[AssessmentRule])
            
        Raises:
            PermissionError: If user cannot create references
            ValueError: If neither video nor document provided
        """
        if not can_manage_assessment_rules(current_user):
            raise PermissionError("You don't have permission to create reference videos")
        
        if not video_content and not document_content:
            raise ValueError("Must provide either video or document (or both)")
        
        # Save video file if provided
        video_path = None
        frames = []
        if video_content and video_filename:
            video_path, frames = await self._save_video_file(video_content, video_filename)
        
        # Save and extract document if provided
        document_path = None
        document_text = ""
        if document_content and document_filename:
            if not is_document_supported(document_filename):
                raise ValueError(f"Unsupported document type: {document_filename}")
            
            document_path = await self._save_document_file(document_content, document_filename)
            document_text = extract_document_text(str(document_path), max_chars=4000)
        
        # Generate AI description
        description = await self._generate_description(
            frames=frames,
            document_text=document_text,
            title=title
        )
        
        # Determine organization_id
        org_id = None
        if not is_super_admin(current_user):
            org_id = getattr(current_user, "organization_id", None)
        
        # Create reference video record
        ref_video = ReferenceVideo(
            title=title,
            video_path=str(video_path) if video_path else None,
            description=description,
            document_path=str(document_path) if document_path else None,
            document_text=document_text if document_text else None,
            created_by=current_user.id,
            organization_id=org_id,
            is_active=True
        )
        
        self.db.add(ref_video)
        await self.db.flush()  # Get ref_video.id
        
        # Auto-generate assessment rule if requested
        assessment_rule = None
        if auto_generate_rule:
            try:
                assessment_rule = await self._generate_assessment_rule(
                    ref_video=ref_video,
                    frames=frames,
                    document_text=document_text,
                    current_user=current_user
                )
                if assessment_rule:
                    self.db.add(assessment_rule)
            except Exception as e:
                logger.error(f"Failed to auto-generate assessment rule: {e}")
                # Continue without rule - user can create manually later
        
        await self.db.commit()
        await self.db.refresh(ref_video)
        if assessment_rule:
            await self.db.refresh(assessment_rule)
        
        logger.info(f"Created reference video {ref_video.id}: {title} by user {current_user.id}")
        return ref_video, assessment_rule
    
    async def _save_video_file(
        self,
        content: bytes,
        original_filename: str
    ) -> Tuple[Path, List[str]]:
        """Save video file and extract frames"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        ext = Path(original_filename).suffix.lower() or ".mp4"
        filename = f"ref_{timestamp}_{unique_id}{ext}"
        
        filepath = self.upload_folder / filename
        
        with open(filepath, "wb") as f:
            f.write(content)
        
        # Extract frames for AI analysis
        frames, _ = self.video_processor.extract_frames(str(filepath), max_frames=5)
        
        logger.info(f"Saved reference video: {filename}, extracted {len(frames)} frames")
        return filepath, frames
    
    async def _save_document_file(
        self,
        content: bytes,
        original_filename: str
    ) -> Path:
        """Save document file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        ext = Path(original_filename).suffix.lower()
        filename = f"doc_{timestamp}_{unique_id}{ext}"
        
        filepath = self.upload_folder / filename
        
        with open(filepath, "wb") as f:
            f.write(content)
        
        logger.info(f"Saved reference document: {filename}")
        return filepath
    
    async def _generate_description(
        self,
        frames: List[str],
        document_text: str,
        title: str
    ) -> str:
        """
        Generate AI description from video frames and/or document
        Uses the old system's proven method for accurate standard generation
        """
        # Build prompt - exactly as in old system
        prompt_parts = [
            "你是一位專業的物理治療師和運動分析專家。",
            "請分析這段標準示範影片中的人物動作。",
            "請生成一段詳細的動作描述，重點關注：",
            "1. 肢體角度 (手臂、腿部的弯曲程度)。",
            "2. 動作力度和速度感。",
            "3. 身體的平衡性。",
            "4. 動作的具體步驟。",
            "描述時請對照規範，確保與評估標準一致。"
        ]
        
        # Add document text as reference standards (old system method)
        if document_text:
            prompt_parts.append("")
            prompt_parts.append("請參考以下評估標準：")
            prompt_parts.append(document_text)
        
        prompt = "\n".join(prompt_parts)
        
        # Call AI
        if frames:
            result = await self.video_processor.analyze_video_with_ai(frames, prompt)
            return result.get("content", "")
        else:
            # Text-only analysis (document without video)
            # Use unified AI client for document-only case
            from src.ai.unified_ai_client import AIRequest
            from src.ai.providers.nova_bedrock_client import get_nova_client
            
            try:
                client = get_nova_client()
                request = AIRequest(
                    system_prompt="You are a healthcare AI assistant analyzing reference video documentation.",
                    user_prompt=prompt,
                    task_type="document_analysis"
                )
                response = await client.make_request(request=request)
                return response.content
            except Exception as e:
                logger.error(f"Failed to generate description from document: {e}")
                return document_text[:500] if document_text else "No description available"
    
    async def _generate_assessment_rule(
        self,
        ref_video: ReferenceVideo,
        frames: List[str],
        document_text: str,
        current_user: User
    ) -> Optional[AssessmentRule]:
        """
        Auto-generate assessment rule from reference video
        Uses the old system's proven standard.md template method
        """
        # Load standard.md template from prompts directory
        from pathlib import Path
        standard_prompt_path = Path(__file__).parent.parent.parent / "prompts" / "movement_analysis" / "standard.md"
        
        standard_prompt_text = ""
        if standard_prompt_path.exists():
            try:
                standard_prompt_text = standard_prompt_path.read_text(encoding='utf-8')
                logger.info("Loaded standard.md template for rule generation")
            except Exception as e:
                logger.warning(f"Failed to load standard.md: {e}")
        
        # Build prompt using old system's method
        video_token = ref_video.video_path or f"ref_video_{ref_video.id}"
        
        if standard_prompt_text:
            # Replace placeholder with actual video identifier
            nova_prompt = standard_prompt_text.replace(
                "VIDEO_URL_OR_ID: {REPLACE_WITH_CURRENT_VIDEO_URL_OR_BACKEND_ID}",
                f"VIDEO_URL_OR_ID: {video_token}"
            )
        else:
            # Fallback prompt if standard.md not found
            nova_prompt = f"""VIDEO_URL_OR_ID: {video_token}

Please generate a movement assessment standard rule in JSON format following this structure:
{{
  "index": "REF_{ref_video.id}",
  "category": "Movement Assessment Category",
  "description": "Description of what this assesses",
  "ai_role": "Clinical Movement Evaluator",
  "reference_video_url": "{video_token}",
  "reference_description": "Detailed movement description",
  "text_standards": {{
    "source_files": "auto_generated",
    "rubric": "Assessment rubric with 5-12 rules"
  }},
  "analysis_instruction": "Instructions for AI analysis",
  "response_formatting_template": {{
    "instruction": "Output format instructions",
    "structure": {{
      "User_View": "Parent-friendly summary template",
      "Storage_JSON": "Machine-readable JSON structure"
    }}
  }}
}}
"""
        
        # Add document text if available (old system method)
        if document_text:
            nova_prompt = f"{nova_prompt}\n\n【附加文字標準說明】\n{document_text}"
        
        try:
            # Call AI with frames or text
            if frames:
                result = await self.video_processor.analyze_video_with_ai(frames, nova_prompt)
                response_text = result.get("content", "")
            else:
                # Text-only for document without video
                from src.ai.unified_ai_client import AIRequest
                from src.ai.providers.nova_bedrock_client import get_nova_client
                
                client = get_nova_client()
                request = AIRequest(
                    system_prompt="You are a healthcare AI assistant generating assessment rules from reference video documentation.",
                    user_prompt=nova_prompt,
                    task_type="report_generation"
                )
                response = await client.make_request(request=request)
                response_text = response.content
            
            # Parse JSON response (using old system's extract_json_body logic)
            clean_json = self._extract_json_body(response_text)
            rule_obj = json.loads(clean_json)
            
            if not isinstance(rule_obj, dict):
                logger.warning("Generated rule is not a JSON object")
                return None
            
            # Extract fields from parsed JSON (old system structure)
            ts = rule_obj.get("text_standards") or {}
            rft = rule_obj.get("response_formatting_template") or {}
            structure = rft.get("structure") or {}
            
            # Create AssessmentRule with parsed data
            rule = AssessmentRule(
                index_code=self._clean_index_prefix(rule_obj.get("index", f"REF_{ref_video.id}")),
                category=rule_obj.get("category", ref_video.title),
                description=rule_obj.get("description", "")[:500],  # Limit length
                ai_role=rule_obj.get("ai_role", "Movement Analysis Specialist"),
                reference_video_url=rule_obj.get("reference_video_url", video_token),
                reference_description=rule_obj.get("reference_description", ref_video.description),
                text_standards={
                    "source_files": ts.get("source_files", "auto_generated"),
                    "rubric": ts.get("rubric", "")
                },
                analysis_instruction=rule_obj.get("analysis_instruction", ""),
                response_template={
                    "instruction": rft.get("instruction", ""),
                    "structure": {
                        "User_View": structure.get("User_View", ""),
                        "Staff_View": structure.get("Staff_View", ""),
                        "Storage_JSON": structure.get("Storage_JSON", "")
                    }
                },
                is_active=False,  # Require manual review before activation
                created_by=current_user.id,
                organization_id=ref_video.organization_id
            )
            
            logger.info(f"Successfully generated assessment rule from reference video {ref_video.id}")
            return rule
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse rule JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to generate assessment rule: {e}")
            return None
    
    def _extract_json_body(self, raw_text: str) -> str:
        """
        Extract JSON from AI response (old system method)
        Removes markdown code fences and extracts JSON object
        """
        if not isinstance(raw_text, str):
            return str(raw_text)
        
        text = raw_text.strip()
        if not text:
            return text
        
        # Remove Markdown code fence (```json ... ```)
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        
        # Extract content between first { and last }
        first = text.find("{")
        last = text.rfind("}")
        if first != -1 and last != -1 and last > first:
            text = text[first:last + 1]
        
        return text.strip()
    
    def _clean_index_prefix(self, index_value: str) -> str:
        """
        Remove numeric prefix from index (old system method)
        e.g., '01_Foo' -> 'Foo'
        """
        if not isinstance(index_value, str):
            return str(index_value)
        
        import re
        return re.sub(r"^\d+_", "", index_value)
    
    async def list_reference_videos(
        self,
        current_user: Optional[User] = None,
        page: int = 1,
        limit: int = 20,
        active_only: bool = True
    ) -> Dict[str, Any]:
        """List reference videos with pagination"""
        query = select(ReferenceVideo)
        
        # Apply filters
        conditions = []
        
        if active_only:
            conditions.append(ReferenceVideo.is_active)
        
        # Apply organization scoping
        if current_user and not is_super_admin(current_user):
            from sqlalchemy import or_
            org_id = getattr(current_user, "organization_id", None)
            conditions.append(
                or_(
                    ReferenceVideo.organization_id.is_(None),
                    ReferenceVideo.organization_id == org_id
                )
            )
        elif not current_user:
            conditions.append(ReferenceVideo.organization_id.is_(None))
        
        for condition in conditions:
            query = query.where(condition)
        
        query = query.order_by(ReferenceVideo.created_at.desc())
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        videos = result.scalars().all()
        
        return {
            "videos": [video.to_dict() for video in videos],
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if total > 0 else 0
        }
    
    async def get_reference_video(
        self,
        video_id: int,
        current_user: Optional[User] = None
    ) -> Optional[ReferenceVideo]:
        """Get a single reference video by ID"""
        result = await self.db.execute(
            select(ReferenceVideo).where(ReferenceVideo.id == video_id)
        )
        video = result.scalar_one_or_none()
        
        if not video:
            return None
        
        # Check visibility
        if current_user and not is_super_admin(current_user):
            if video.organization_id is not None:
                user_org = getattr(current_user, "organization_id", None)
                if video.organization_id != user_org:
                    return None
        
        return video
    
    async def delete_reference_video(
        self,
        video_id: int,
        current_user: User
    ) -> bool:
        """Delete a reference video"""
        if not can_manage_assessment_rules(current_user):
            raise PermissionError("You don't have permission to delete reference videos")
        
        video = await self.get_reference_video(video_id, current_user)
        if not video:
            return False
        
        # Delete files
        if video.video_path and os.path.exists(video.video_path):
            try:
                os.remove(video.video_path)
            except Exception as e:
                logger.warning(f"Failed to delete video file: {e}")
        
        if video.document_path and os.path.exists(video.document_path):
            try:
                os.remove(video.document_path)
            except Exception as e:
                logger.warning(f"Failed to delete document file: {e}")
        
        await self.db.delete(video)
        await self.db.commit()
        
        logger.info(f"Deleted reference video {video_id} by user {current_user.id}")
        return True
