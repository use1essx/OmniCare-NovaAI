"""
Healthcare AI V2 - Video Processor Service
Handles video frame extraction and AI analysis for Movement Analysis using AWS Bedrock Nova
"""

import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import cv2
from jinja2 import Template

from src.core.config import settings

logger = logging.getLogger(__name__)

# Prompts directory
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts" / "movement_analysis"


def load_prompt_template(filename: str) -> str:
    """Load a prompt template from the prompts/movement_analysis directory"""
    prompt_path = PROMPTS_DIR / filename
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    logger.warning(f"Prompt template not found: {prompt_path}")
    return ""


class VideoProcessingError(Exception):
    """Custom exception for video processing errors"""
    pass


class VideoProcessor:
    """
    Service for processing video files and analyzing movement using AI vision models
    """
    
    def __init__(
        self,
        upload_folder: Optional[Path] = None
    ):
        """
        Initialize the video processor
        
        Args:
            upload_folder: Path to video upload folder
        """
        # Load prompt templates
        self.base_system_prompt = load_prompt_template("base_system.txt")
        self.default_response_format = load_prompt_template("default_response_format.txt")
        self.analysis_template = load_prompt_template("analysis_template.txt")
        self.language_instruction_en = load_prompt_template("language_instruction_en.txt")
        self.language_instruction_zh_hk = load_prompt_template("language_instruction_zh_hk.txt")
        self.response_format_en = load_prompt_template("response_format_en.txt")
        self.response_format_zh_hk = load_prompt_template("response_format_zh_hk.txt")
        self.upload_folder = upload_folder or settings.upload_path / "assessments"
        
        # Ensure upload folder exists
        self.upload_folder.mkdir(parents=True, exist_ok=True)
    
    def extract_frames(
        self,
        video_path: str,
        max_frames: int = 10,
        target_width: int = 384
    ) -> Tuple[List[str], int]:
        """
        Extract frames from video file for AI analysis
        
        Args:
            video_path: Path to the video file
            max_frames: Maximum number of frames to extract
            target_width: Target width for resized frames
            
        Returns:
            Tuple of (list of base64-encoded frame images, total frames in video)
            
        Raises:
            VideoProcessingError: If video cannot be opened or processed
        """
        frames = []
        
        if not os.path.exists(video_path):
            raise VideoProcessingError(f"Video file not found: {video_path}")
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise VideoProcessingError(f"Could not open video file: {video_path}")
        
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            logger.info(f"Processing video: {total_frames} frames, {fps:.1f} FPS")
            
            # Calculate step size to evenly sample frames
            if total_frames > 0:
                step = max(1, total_frames // max_frames)
            else:
                step = 30  # Default interval
            
            count = 0
            extracted_count = 0
            
            while cap.isOpened() and extracted_count < max_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if count % step == 0:
                    # Resize frame to reduce payload size
                    height, width = frame.shape[:2]
                    new_width = target_width
                    new_height = int(height * (new_width / width))
                    frame_resized = cv2.resize(frame, (new_width, new_height))
                    
                    # Encode as JPEG and convert to base64 with lower quality
                    _, buffer = cv2.imencode('.jpg', frame_resized, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                    frames.append(jpg_as_text)
                    extracted_count += 1
                
                count += 1
            
            logger.info(f"Extracted {extracted_count} frames from video")
            return frames, total_frames
            
        finally:
            cap.release()
    
    async def analyze_video_with_ai(
        self,
        frames: List[str],
        prompt: str,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """
        Send extracted frames to AI vision model for analysis
        Uses AWS Bedrock Nova Pro for video analysis

        Args:
            frames: List of base64-encoded frame images
            prompt: Analysis prompt/instructions
            timeout: Request timeout in seconds

        Returns:
            Dict with analysis result and metadata

        Raises:
            VideoProcessingError: If analysis fails
        """
        if not frames:
            raise VideoProcessingError("No frames provided for analysis")

        # Use Nova Bedrock client directly for video analysis
        from src.ai.providers.nova_bedrock_client import get_nova_client
        import base64
        
        try:
            client = get_nova_client()
            
            # Get model spec
            model_spec = client.NOVA_MODELS["pro"]
            
            # Build messages with images for Converse API
            content_parts = [{"text": prompt}]
            for frame_b64 in frames:
                # Decode base64 string to bytes for Nova
                frame_bytes = base64.b64decode(frame_b64)
                content_parts.append({
                    "image": {
                        "format": "jpeg",
                        "source": {
                            "bytes": frame_bytes
                        }
                    }
                })
            
            messages = [{
                "role": "user",
                "content": content_parts
            }]
            
            # Call Bedrock Converse API directly with images
            start_time = time.time()
            response = client.client.converse(
                modelId=model_spec.model_id,
                messages=messages,
                inferenceConfig={
                    "maxTokens": 2000,
                    "temperature": 0.7
                }
            )
            
            # Extract response
            output_message = response['output']['message']
            content = output_message['content'][0]['text']
            
            # Extract usage stats
            usage = response.get('usage', {})
            input_tokens = usage.get('inputTokens', 0)
            output_tokens = usage.get('outputTokens', 0)
            
            # Calculate cost
            cost = client._calculate_cost(input_tokens, output_tokens, model_spec)
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"✅ Successfully analyzed with Nova Pro")
            return {
                "success": True,
                "content": content,
                "model": "nova-pro",
                "model_display": "AWS Bedrock Nova Pro",
                "processing_time_ms": processing_time_ms,
                "frames_analyzed": len(frames),
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                },
                "cost_usd": float(cost)
            }
            
        except Exception as e:
            error_msg = f"Nova Pro video analysis failed: {str(e)}"
            logger.error(error_msg)
            raise VideoProcessingError(error_msg)

    async def fact_check_analysis(
        self,
        frames: List[str],
        initial_analysis: str,
        language: str = "en",
        timeout: int = 120
    ) -> Dict[str, Any]:
        """
        Fact-check and refine the initial analysis by re-watching the video
        
        Args:
            frames: List of base64-encoded frame images (same as initial analysis)
            initial_analysis: The initial AI analysis to verify
            language: Response language (en or zh-HK)
            timeout: Request timeout in seconds
            
        Returns:
            Dict with refined analysis result and metadata
            
        Raises:
            VideoProcessingError: If fact-checking fails
        """
        if not frames:
            raise VideoProcessingError("No frames provided for fact-checking")
        
        # Load fact-checker prompt template
        fact_checker_template = load_prompt_template("fact_checker_prompt.txt")
        if not fact_checker_template:
            logger.warning("Fact-checker template not found, skipping fact-check")
            return {
                "success": True,
                "content": initial_analysis,
                "fact_checked": False
            }
        
        # Build fact-checking prompt
        prompt = fact_checker_template.format(
            initial_analysis=initial_analysis,
            language=language
        )
        
        logger.info(f"🔍 Starting fact-check analysis (language: {language})")
        
        # Use the same analyze_video_with_ai method but with fact-checking prompt
        try:
            result = await self.analyze_video_with_ai(frames, prompt, timeout)
            result["fact_checked"] = True
            logger.info("✅ Fact-check completed successfully")
            return result
        except Exception as e:
            logger.error(f"❌ Fact-check failed: {e}, returning original analysis")
            # If fact-checking fails, return original analysis
            return {
                "success": True,
                "content": initial_analysis,
                "fact_checked": False,
                "fact_check_error": str(e)
            }


    
    @staticmethod
    def split_role_report(report_text: str) -> Tuple[str, str, str]:
        """
        Parse AI response to extract User_View, Staff_View, and Storage_JSON sections
        
        Args:
            report_text: Raw AI response text
            
        Returns:
            Tuple of (user_view, staff_view, storage_json)
        """
        if not isinstance(report_text, str):
            return str(report_text), "", ""
        
        user_view = ""
        staff_view = ""
        storage_json = ""
        
        lower = report_text.lower()
        
        try:
            def extract_section(label_keywords: List[str]) -> int:
                for key in label_keywords:
                    idx = lower.find(key)
                    if idx != -1:
                        return idx
                return -1
            
            # Find section markers (English and Traditional Chinese - Hong Kong)
            u_idx = extract_section([
                "## user view", "[user_view]", "user_view:", "**user view**",
                "## 用戶視圖", "用戶視圖"
            ])
            s_idx = extract_section([
                "## staff view", "[staff_view]", "staff_view:", "**staff view**",
                "## 專業人員視圖", "專業人員視圖",
                "## professional", "professional"
            ])
            j_idx = extract_section([
                "## storage json", "[storage_json]", "storage_json:", "**storage json**",
                "## 儲存json", "儲存json"
            ])
            
            # Build sorted list of found sections
            indices = [("user", u_idx), ("staff", s_idx), ("json", j_idx)]
            indices = [(name, i) for name, i in indices if i != -1]
            indices.sort(key=lambda x: x[1])
            
            # Extract section content
            if indices:
                for idx, (name, start) in enumerate(indices):
                    end = len(report_text)
                    if idx + 1 < len(indices):
                        end = indices[idx + 1][1]
                    section_text = report_text[start:end].strip()
                    
                    if name == "user":
                        user_view = section_text
                    elif name == "staff":
                        staff_view = section_text
                    elif name == "json":
                        storage_json = section_text
            
            # If no user view found, use entire response
            if not user_view:
                user_view = report_text.strip()
                
        except Exception as e:
            logger.warning(f"Error parsing role report: {e}")
            user_view = report_text.strip()
        
        # Clean up section headers from user view (English and Traditional Chinese)
        if user_view:
            lines = user_view.splitlines()
            if lines and any(marker in lines[0].lower() for marker in [
                'user view', 'user_view', '用戶視圖', 'parent-friendly'
            ]):
                user_view = "\n".join(lines[1:]).lstrip()
        
        # Clean up section headers from staff view (English and Traditional Chinese)
        if staff_view:
            lines = staff_view.splitlines()
            if lines and any(marker in lines[0].lower() for marker in [
                'staff view', 'staff_view', '專業人員視圖', 'professional'
            ]):
                staff_view = "\n".join(lines[1:]).lstrip()
        
        return user_view, staff_view, storage_json
    
    @staticmethod
    def parse_storage_json(storage_json_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse the storage JSON section from AI response
        
        Args:
            storage_json_text: Raw storage JSON text
            
        Returns:
            Parsed JSON dict or None if parsing fails
        """
        if not storage_json_text:
            return None
        
        try:
            # Try to find JSON object in the text
            # Remove markdown code blocks if present
            text = storage_json_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            
            # Find JSON object boundaries
            start_idx = text.find("{")
            end_idx = text.rfind("}") + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = text[start_idx:end_idx]
                return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse storage JSON: {e}")
        except Exception as e:
            logger.warning(f"Error processing storage JSON: {e}")
        
        return None
    
    @staticmethod
    def get_age_group(age_value: Optional[float], age_unit: Optional[str] = "year") -> Optional[str]:
        """
        Determine age group from age value and unit
        
        Age Groups:
        - infant_toddler: 0-5 years
        - child: 6-13 years
        - teen: 14-19 years
        - adult: 20-64 years
        - elderly: 65+ years
        
        Args:
            age_value: Age value
            age_unit: Age unit (year or month)
            
        Returns:
            Age group identifier (infant_toddler, child, teen, adult, elderly) or None if age should be auto-detected
        """
        if age_value is None:
            return None  # Return None to signal AI should detect age from video
        
        # Convert to years
        age_in_years = age_value
        if age_unit and age_unit.lower() in ["month", "months", "月"]:
            age_in_years = age_value / 12.0
        
        # Determine age group
        if age_in_years < 6:
            return "infant_toddler"
        elif age_in_years < 14:
            return "child"
        elif age_in_years < 20:
            return "teen"
        elif age_in_years < 65:
            return "adult"
        else:
            return "elderly"
    
    def load_age_group_template(self, age_group: Optional[str], language: str = "en") -> str:
        """
        Load age-group-specific template from prompts/movement_analysis/age_groups/
        
        Args:
            age_group: Age group identifier (infant_toddler, child, teen, adult, elderly) or None for auto-detect
            language: Language code (en or zh-HK)
            
        Returns:
            Age group template content or empty string if not found or age_group is None
        """
        # If age_group is None (auto-detect mode), return empty string
        if age_group is None:
            return ""
        
        # SECURITY: Validate language parameter
        if language not in ["en", "zh-HK"]:
            language = "en"
        
        # Map language to file suffix
        lang_suffix = "zh_hk" if language == "zh-HK" else "en"
        
        # Build filename
        filename = f"{age_group}_{lang_suffix}.txt"
        template_path = PROMPTS_DIR / "age_groups" / filename
        
        if template_path.exists():
            logger.info(f"Loading age group template: {filename}")
            return template_path.read_text(encoding="utf-8")
        else:
            logger.warning(f"Age group template not found: {template_path}")
            return ""
    
    def build_analysis_prompt(
        self,
        rule_data: Dict[str, Any],
        age_value: Optional[float] = None,
        age_unit: Optional[str] = None,
        age_group: Optional[str] = None,
        child_description: Optional[str] = None,
        language: str = "en"
    ) -> str:
        """
        Build the analysis prompt from rule data and child information
        Uses Jinja2 templates from prompts/movement_analysis/
        
        Args:
            rule_data: Movement analysis rule configuration
            age_value: Child's age value
            age_unit: Age unit (year/month)
            age_group: Optional manual age group override (infant_toddler, child, teen, adult, elderly)
            child_description: Optional description of the child
            language: Response language (en or zh-HK)
            
        Returns:
            Formatted prompt string
        """
        # SECURITY: Validate language parameter
        if language not in ["en", "zh-HK"]:
            language = "en"  # Default to English if invalid
        
        # Use manual age_group if provided, otherwise calculate from age_value
        if age_group:
            # VALIDATION: Ensure age_group is valid
            valid_age_groups = ["infant_toddler", "child", "teen", "adult", "elderly"]
            if age_group not in valid_age_groups:
                logger.warning(f"Invalid age_group '{age_group}', calculating from age_value")
                age_group = self.get_age_group(age_value, age_unit)
        else:
            age_group = self.get_age_group(age_value, age_unit)
        
        # DEBUG: Log age calculation details
        logger.info(f"🔍 AGE GROUP CALCULATION DEBUG:")
        logger.info(f"  - Input age_value: {age_value}")
        logger.info(f"  - Input age_unit: {age_unit}")
        logger.info(f"  - Manual age_group provided: {age_group if age_group else 'None (auto-detect)'}")
        logger.info(f"  - Calculated age_group: {age_group if age_group else 'None (AI will detect from video)'}")
        logger.info(f"  - Language: {language}")
        
        # Load age group template (will be empty if age_group is None)
        age_group_template = self.load_age_group_template(age_group, language)
        
        # DEBUG: Log template loading
        if age_group:
            if age_group_template:
                logger.info(f"✅ Loaded age group template for {age_group} ({language}), length: {len(age_group_template)} chars")
            else:
                logger.warning(f"⚠️ Age group template NOT loaded for {age_group} ({language})")
        else:
            logger.info(f"ℹ️ No age group specified - AI will detect age from video")
        
        logger.info(f"Building prompt for age group: {age_group if age_group else 'auto-detect'}, language: {language}")
        
        # Load language instruction from template files
        if language == "zh-HK":
            language_instruction = self.language_instruction_zh_hk or """
## IMPORTANT: Response Language
Please provide your ENTIRE response in Traditional Chinese (繁體中文/香港粵語).
All sections (User View, Staff View, and Storage JSON field descriptions) must be in Traditional Chinese.
Use Hong Kong Cantonese terminology and phrasing appropriate for Hong Kong families and healthcare professionals.
"""
        else:
            language_instruction = self.language_instruction_en or """
## IMPORTANT: Response Language and Tone
Please provide your ENTIRE response in English with detailed, parent-friendly guidance.
"""
        
        # If we have a template file, use it
        if self.analysis_template:
            try:
                template = Template(self.analysis_template)
                
                # Prepare template context
                text_standards = rule_data.get("text_standards", {})
                response_template = rule_data.get("response_template", {})
                
                context = {
                    "ai_role": rule_data.get("ai_role", "Pediatric Movement Screener"),
                    "category": rule_data.get("category", "General Movement Analysis"),
                    "description": rule_data.get("description", ""),
                    "reference_description": rule_data.get("reference_description", ""),
                    "rubric": text_standards.get("rubric", "") if text_standards else "",
                    "analysis_instruction": rule_data.get("analysis_instruction", ""),
                    "age_value": age_value,
                    "age_unit": age_unit or "year",
                    "age_group": age_group,
                    "age_group_template": age_group_template,
                    "child_description": child_description,
                    "response_instruction": response_template.get("instruction", "") if response_template else "",
                    "response_structure": response_template.get("structure", {}) if response_template else {},
                    "language_instruction": language_instruction,
                }
                
                return template.render(**context)
            except Exception as e:
                logger.warning(f"Error rendering prompt template: {e}, falling back to inline")
        
        # Fallback to inline prompt building
        prompt_parts = []
        
        # Base system prompt if available
        if self.base_system_prompt:
            prompt_parts.append(self.base_system_prompt)
            prompt_parts.append("\n---\n")
        
        # Language instruction (add early in prompt for emphasis)
        prompt_parts.append(language_instruction)
        
        # Age group specific guidance (if available)
        if age_group_template:
            prompt_parts.append("\n---\n")
            prompt_parts.append(age_group_template)
            prompt_parts.append("\n---\n")
        
        # AI Role
        ai_role = rule_data.get("ai_role", "Pediatric Movement Screener")
        prompt_parts.append(f"You are a {ai_role}.")
        
        # Category and description
        category = rule_data.get("category", "General Movement Analysis")
        description = rule_data.get("description", "")
        prompt_parts.append(f"\n## Analysis Category: {category}")
        if description:
            prompt_parts.append(f"Description: {description}")
        
        # Reference information
        ref_desc = rule_data.get("reference_description", "")
        if ref_desc:
            prompt_parts.append(f"\n## Reference Standard\n{ref_desc}")
        
        # Text standards/rubric
        text_standards = rule_data.get("text_standards", {})
        if text_standards:
            rubric = text_standards.get("rubric", "")
            if rubric:
                prompt_parts.append(f"\n## Analysis Criteria\n{rubric}")
        
        # Analysis instructions
        analysis_instruction = rule_data.get("analysis_instruction", "")
        if analysis_instruction:
            prompt_parts.append(f"\n## Analysis Instructions\n{analysis_instruction}")
        
        # Child information
        if age_value is not None:
            age_str = f"{age_value} {age_unit or 'year'}(s)"
            prompt_parts.append(f"\n## Child Information\nAge: {age_str}")
        if child_description:
            prompt_parts.append(f"Additional notes: {child_description}")
        
        # Response template
        response_template = rule_data.get("response_template", {})
        if response_template:
            instruction = response_template.get("instruction", "")
            structure = response_template.get("structure", {})
            
            if instruction:
                prompt_parts.append(f"\n## Response Format\n{instruction}")
            
            if structure:
                prompt_parts.append("\nProvide your response in the following sections:")
                prompt_parts.append("## User View")
                if "User_View" in structure:
                    prompt_parts.append(f"({structure['User_View']})")
                prompt_parts.append("\n## Staff View")
                if "Staff_View" in structure:
                    prompt_parts.append(f"({structure['Staff_View']})")
                prompt_parts.append("\n## Storage JSON")
                if "Storage_JSON" in structure:
                    prompt_parts.append(f"({structure['Storage_JSON']})")
        elif self.default_response_format:
            prompt_parts.append(f"\n{self.default_response_format}")
        else:
            # Load language-specific response format from templates
            if language == "zh-HK" and self.response_format_zh_hk:
                prompt_parts.append(f"\n{self.response_format_zh_hk}")
            elif self.response_format_en:
                prompt_parts.append(f"\n{self.response_format_en}")
            else:
                # Final fallback if no templates available
                prompt_parts.append("""
## Response Format
Provide your analysis in three sections:
1. User View (parent-friendly summary)
2. Staff View (professional assessment)
3. Storage JSON (structured data)
""")
        
        prompt_parts.append("\nPlease analyze the following video frames and provide your movement analysis:")
        
        return "\n".join(prompt_parts)
    
    # Alias for backward compatibility
    def build_assessment_prompt(
        self,
        rule_data: Dict[str, Any],
        age_value: Optional[float] = None,
        age_unit: Optional[str] = None,
        age_group: Optional[str] = None,
        child_description: Optional[str] = None,
        language: str = "en"
    ) -> str:
        """Alias for build_analysis_prompt (backward compatibility)"""
        return self.build_analysis_prompt(
            rule_data=rule_data,
            age_value=age_value,
            age_unit=age_unit,
            age_group=age_group,
            child_description=child_description,
            language=language
        )


async def download_youtube_video(url: str, upload_folder: Path) -> str:
    """
    Download a YouTube video for analysis
    
    Args:
        url: YouTube video URL
        upload_folder: Folder to save the video
        
    Returns:
        Path to downloaded video file
        
    Raises:
        VideoProcessingError: If download fails
    """
    try:
        import yt_dlp
    except ImportError:
        raise VideoProcessingError("yt-dlp not installed. Install with: pip install yt-dlp")
    
    timestamp = int(time.time())
    filename = f"yt_{timestamp}.mp4"
    filepath = upload_folder / filename
    
    ydl_opts = {
        'format': 'best[ext=mp4][filesize<50M]/best[ext=mp4]',
        'outtmpl': str(filepath),
        'quiet': True,
        'max_filesize': 50 * 1024 * 1024  # 50MB limit
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        if filepath.exists():
            logger.info(f"Downloaded YouTube video: {filename}")
            return str(filepath)
        else:
            raise VideoProcessingError("Video download completed but file not found")
            
    except Exception as e:
        logger.error(f"Failed to download YouTube video: {e}")
        raise VideoProcessingError(f"Failed to download video: {str(e)}")


# Create a default processor instance
_default_processor: Optional[VideoProcessor] = None


def get_video_processor() -> VideoProcessor:
    """Get the default video processor instance"""
    global _default_processor
    if _default_processor is None:
        _default_processor = VideoProcessor()
    return _default_processor

