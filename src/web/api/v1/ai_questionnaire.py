"""
AI Questionnaire Generation API
Handles file upload, text extraction, and AI-powered questionnaire generation
"""

from typing import Dict, Any, Optional
import base64

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.connection import get_sync_db
from src.database.models_questionnaire import QuestionnaireBank, QuestionnaireQuestion, QuestionOption
from src.database.models_multistage_questionnaire import (
    GeneratedQuestionCandidate,
    QuestionnaireAnalysis,
    QuestionnaireKnowledgeBase
)
from src.tools.ai_questionnaire_generator import AIQuestionnaireClient
from src.tools.file_parser import FileParser
from src.core.logging import get_logger
from uuid import UUID

logger = get_logger(__name__)
router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class FileUploadResponse(BaseModel):
    """Response model for file upload"""
    success: bool
    file_name: str
    file_size: int
    mime_type: str
    text: Optional[str] = None
    text_length: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class QuestionnaireGenerateRequest(BaseModel):
    """Request model for questionnaire generation"""
    content: str
    question_count: int = Field(default=10, ge=1, le=50)
    language: str = Field(default="en")
    purpose: str = Field(default="child-screening")
    title: Optional[str] = None
    save_to_db: bool = Field(default=True)


class QuestionnaireGenerateResponse(BaseModel):
    """Response model for questionnaire generation"""
    success: bool
    questionnaire: Optional[Dict[str, Any]] = None
    questionnaire_id: Optional[int] = None
    saved: bool = False
    truncated: bool = False
    error: Optional[str] = None


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/upload-file", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    use_ai_ocr: bool = Form(default=True)
) -> Dict[str, Any]:
    """
    Upload a file and extract text content
    
    Supports:
    - PDF, Excel, CSV, Word, TXT files (traditional parsing)
    - Images (JPG, PNG, etc.) - uses AI OCR with Amazon Nova
    
    Args:
        file: Uploaded file
        use_ai_ocr: Use AI OCR for images and PDFs (default: True)
        
    Returns:
        Extracted text and metadata
    """
    try:
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        file_name = file.filename
        mime_type = file.content_type
        
        logger.info(f"📤 Uploaded file: {file_name} ({file_size} bytes, {mime_type})")
        
        # Validate file
        validation = FileParser.validate_file(file_name, file_size)
        if not validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation["error"]
            )
        
        # Determine if this is an image file
        file_ext = file_name.split('.')[-1].lower()
        is_image = file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
        is_pdf = file_ext == 'pdf'
        
        # Try traditional parsing first for non-images
        text = ""
        metadata = {}
        
        if not is_image:
            try:
                parse_result = await FileParser.parse_file(file_content, file_name, mime_type)
                text = parse_result.get("text", "")
                metadata = parse_result.get("metadata", {})
                logger.info(f"✅ Traditional parsing extracted {len(text)} characters")
            except Exception as e:
                logger.warning(f"⚠️  Traditional parsing failed: {e}")
                if not use_ai_ocr:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to parse file: {str(e)}"
                    )
        
        # If text is empty or it's an image/PDF, use AI OCR
        if (not text or len(text.strip()) < 50) and use_ai_ocr and (is_image or is_pdf):
            try:
                logger.info(f"🤖 Using AI OCR for {file_name}")
                
                # Convert to base64
                file_base64 = base64.b64encode(file_content).decode('utf-8')
                
                # Call AI OCR
                ai_client = AIQuestionnaireClient()
                text = await ai_client.call_ai_with_file(
                    file_base64=file_base64,
                    mime_type=mime_type,
                    file_name=file_name
                )
                
                metadata["extraction_method"] = "ai_ocr"
                metadata["ai_model"] = "amazon.nova-lite-v1:0"
                logger.info(f"✅ AI OCR extracted {len(text)} characters")
                
            except Exception as e:
                logger.error(f"❌ AI OCR failed: {e}")
                if not text:  # Only raise if we have no text at all
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to extract text with AI OCR: {str(e)}"
                    )
        
        return {
            "success": True,
            "file_name": file_name,
            "file_size": file_size,
            "mime_type": mime_type,
            "text": text,
            "text_length": len(text),
            "metadata": metadata
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )


@router.post("/generate-questionnaire", response_model=QuestionnaireGenerateResponse)
async def generate_questionnaire(
    request: QuestionnaireGenerateRequest,
    db: Session = Depends(get_sync_db)
) -> Dict[str, Any]:
    """
    Generate a questionnaire using AI based on provided content
    
    Args:
        request: Generation request with content and parameters
        db: Database session
        
    Returns:
        Generated questionnaire
    """
    try:
        logger.info(f"🤖 Generating questionnaire from content ({len(request.content)} chars)")
        logger.info(f"📊 Parameters: {request.question_count} questions, lang={request.language}, purpose={request.purpose}")
        
        # Validate content
        if not request.content or len(request.content.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content is too short or empty"
            )
        
        # Generate questionnaire using AI
        ai_client = AIQuestionnaireClient()
        result = await ai_client.generate_questionnaire(
            content=request.content,
            question_count=request.question_count,
            language=request.language,
            purpose=request.purpose
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to generate questionnaire")
            )
        
        questionnaire = result.get("questionnaire")
        
        # Save to database if requested
        saved_questionnaire_id = None
        if request.save_to_db and questionnaire:
            try:
                saved_questionnaire_id = await _save_questionnaire_to_db(
                    questionnaire=questionnaire,
                    title=request.title,
                    language=request.language,
                    purpose=request.purpose,
                    db=db
                )
                logger.info(f"✅ Questionnaire saved to database: ID {saved_questionnaire_id}")
            except Exception as e:
                logger.error(f"❌ Failed to save questionnaire to database: {e}")
                # Continue even if save fails
        
        return {
            "success": True,
            "questionnaire": questionnaire,
            "questionnaire_id": saved_questionnaire_id,
            "saved": saved_questionnaire_id is not None,
            "truncated": result.get("truncated", False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating questionnaire: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate questionnaire: {str(e)}"
        )


@router.post("/summarize-content")
async def summarize_content(
    content: str = Form(...),
    summary_length: str = Form(default="medium"),
    language: str = Form(default="en")
) -> Dict[str, Any]:
    """
    Generate a summary of the provided content
    
    Args:
        content: Content to summarize
        summary_length: 'short', 'medium', or 'long'
        language: Language for summary
        
    Returns:
        Summary with key points and insights
    """
    try:
        logger.info(f"📝 Summarizing content ({len(content)} chars)")
        
        if not content or len(content.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content is too short or empty"
            )
        
        # Generate summary using AI
        ai_client = AIQuestionnaireClient()
        result = await ai_client.summarize_content(
            content=content,
            summary_length=summary_length,
            language=language
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to generate summary")
            )
        
        return result["summary"]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error summarizing content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to summarize content: {str(e)}"
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def _save_questionnaire_to_db(
    questionnaire: Dict[str, Any],
    title: Optional[str],
    language: str,
    purpose: str,
    db: Session,
    description: Optional[str] = None
) -> int:
    """
    Save generated questionnaire to database
    
    Args:
        questionnaire: Generated questionnaire data
        title: Optional custom title
        language: Questionnaire language
        purpose: Purpose of questionnaire
        db: Database session
        description: Optional custom description
        
    Returns:
        ID of saved questionnaire
    """
    try:
        # Map language codes to match database constraint (only English and Cantonese Hong Kong supported)
        language_map = {
            'zh': 'zh-HK',  # Default Chinese to Traditional Chinese (Hong Kong)
            'zh-hk': 'zh-HK',
            'en': 'en'
        }
        db_language = language_map.get(language.lower(), 'en')
        
        # Extract title
        questionnaire_title = title or questionnaire.get("title", "AI Generated Questionnaire")
        if language.startswith("zh") and questionnaire.get("title_zh"):
            questionnaire_title = questionnaire.get("title_zh")
        
        # Use provided description or fall back to questionnaire intro
        questionnaire_description = description or questionnaire.get("intro_en") or questionnaire.get("intro_zh")
        
        # Create questionnaire bank
        questionnaire_bank = QuestionnaireBank(
            title=questionnaire_title,
            description=questionnaire_description,
            language=db_language,
            total_questions=len(questionnaire.get("questions", [])),
            estimated_duration_minutes=len(questionnaire.get("questions", [])) * 2,  # Estimate 2 min per question
            source="ai_generated",
            category="mental_health",
            status="draft"
        )
        
        db.add(questionnaire_bank)
        db.flush()  # Get the ID
        
        # Create questions
        questions = questionnaire.get("questions", [])
        for idx, q in enumerate(questions):
            # Determine question type
            q_type = q.get("type", "")
            if q_type in ["likert5", "likert_5"]:
                question_type = "scale"
            elif q_type in ["yesno", "yes_no"]:
                question_type = "yes_no"
            elif q_type == "text":
                question_type = "short_answer"
            else:
                question_type = "scale"
            
            # Create question
            question = QuestionnaireQuestion(
                questionnaire_id=questionnaire_bank.id,
                question_code=q.get("id"),
                question_text=q.get("question_en", q.get("prompt_en", "")),
                question_text_zh=q.get("question_zh", q.get("prompt_zh")),
                question_type=question_type,
                category=q.get("category", "general"),
                sequence_order=idx + 1,
                is_required=q.get("required", True),
                help_text=None
            )
            db.add(question)
            db.flush()
            
            # Create options for scale questions
            if question_type == "scale" and q.get("scale_labels_en"):
                labels_en = q.get("scale_labels_en", [])
                labels_zh = q.get("scale_labels_zh", [])
                
                for opt_idx, (label_en, label_zh) in enumerate(zip(labels_en, labels_zh)):
                    option = QuestionOption(
                        question_id=question.id,
                        option_text=label_en,
                        option_text_zh=label_zh,
                        option_value=opt_idx + 1,
                        sequence_order=opt_idx + 1
                    )
                    db.add(option)
            elif question_type == "yes_no":
                # Add Yes/No options
                yes_no_options = [
                    ("Yes", "是", 1),
                    ("No", "否", 0)
                ]
                for opt_text_en, opt_text_zh, opt_value in yes_no_options:
                    option = QuestionOption(
                        question_id=question.id,
                        option_text=opt_text_en,
                        option_text_zh=opt_text_zh,
                        option_value=opt_value,
                        sequence_order=opt_value + 1
                    )
                    db.add(option)
        
        db.commit()
        db.refresh(questionnaire_bank)
        
        logger.info(f"✅ Saved questionnaire to database: ID {questionnaire_bank.id}, {len(questions)} questions")
        
        return questionnaire_bank.id
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error saving questionnaire to database: {e}")
        raise


# =============================================================================
# =============================================================================
# MULTI-STAGE ASYNC GENERATION ENDPOINTS
# =============================================================================

@router.post("/generate-async")
async def generate_questionnaire_async(
    file: Optional[UploadFile] = File(None),
    content: Optional[str] = Form(None),
    question_count: int = Form(10),
    language: str = Form("en"),
    purpose: str = Form("child-screening"),
    generation_mode: str = Form("auto"),
    use_ai_vision: bool = Form(True),
    db: Session = Depends(get_sync_db)
):
    """
    Start multi-stage questionnaire generation (returns immediately with job_id)
    """
    try:
        logger.info(f"🚀 Starting multi-stage generation job (vision mode: {use_ai_vision})")
        
        # Extract text from file if provided
        document_text = content
        
        if file:
            logger.info(f"📄 Processing file: {file.filename} (AI vision mode: {use_ai_vision})")
            try:
                # Read file content
                file_content = await file.read()
                file_name = file.filename
                mime_type = file.content_type or "application/octet-stream"
                
                # Validate file size
                if len(file_content) > 50 * 1024 * 1024:  # 50MB limit
                    raise HTTPException(
                        status_code=400,
                        detail="File too large. Maximum size is 50MB."
                    )
                
                # Determine file type
                file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
                is_image = file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
                
                # Try traditional parsing first for non-images
                text = ""
                if not is_image:
                    try:
                        # 修正这里的调用 - 确保参数正确
                        parse_result = await FileParser.parse_file(
                            file_content=file_content,
                            file_name=file_name,
                            mime_type=mime_type
                        )
                        text = parse_result.get("text", "")
                        logger.info(f"✅ Traditional parsing extracted {len(text)} characters")
                    except Exception as e:
                        logger.warning(f"⚠️ Traditional parsing failed: {e}")
                        # Don't raise yet - try AI OCR as fallback
                
                # If text is empty or insufficient, use AI OCR as fallback
                if (not text or len(text.strip()) < 50) and use_ai_vision:
                    try:
                        logger.info(f"🤖 Using AI Vision OCR for {file_name} (traditional parsing yielded {len(text)} chars)")
                        logger.info(f"📊 File details: size={len(file_content)} bytes, type={mime_type}")
                        
                        # Convert to base64
                        file_base64 = base64.b64encode(file_content).decode('utf-8')
                        logger.info(f"✅ Base64 encoding completed: {len(file_base64)} chars")
                        
                        # Call AI OCR with improved multi-model fallback
                        ai_client = AIQuestionnaireClient()
                        text = await ai_client.call_ai_with_file(
                            file_base64=file_base64,
                            mime_type=mime_type,
                            file_name=file_name
                        )
                        
                        logger.info(f"✅ AI Vision OCR extracted {len(text)} characters")
                        
                        # Log first 200 chars for debugging
                        if text:
                            preview = text[:200].replace('\n', ' ')
                            logger.info(f"📝 Extracted text preview: {preview}...")
                        
                    except Exception as e:
                        logger.error(f"❌ AI Vision OCR failed: {e}", exc_info=True)
                        if not text:  # Only raise if we have no text at all
                            raise HTTPException(
                                status_code=400,
                                detail=f"Failed to extract text from file: {str(e)}"
                            )
                
                document_text = text
                
                # Final validation
                if not document_text or len(document_text.strip()) < 10:
                    logger.error(f"❌ Document text is empty or too short: {len(document_text)} characters")
                    logger.error(f"   File: {file_name}, Type: {mime_type}, Size: {len(file_content)} bytes")
                    logger.error(f"   Text preview: '{document_text[:100]}'")
                    raise HTTPException(
                        status_code=400,
                        detail=f"File appears to be empty or unreadable. Extracted only {len(document_text)} characters. Please ensure the file contains readable text or images with clear text content."
                    )
                
                logger.info(f"✅ File processing successful: {len(document_text)} characters extracted")
                logger.info(f"   Preview: {document_text[:150].replace(chr(10), ' ')}...")
                    
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"❌ File processing error: {e}", exc_info=True)  # 添加完整的堆栈信息
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to process file: {str(e)}"
                )
        
        if not document_text:
            raise HTTPException(
                status_code=400,
                detail="No content provided. Please upload a file or provide text content."
            )
        
        # Create job processor
        try:
            from src.services.job_processor import BackgroundJobProcessor
            processor = BackgroundJobProcessor(db)
        except ImportError as e:
            logger.error(f"❌ Failed to import BackgroundJobProcessor: {e}")
            raise HTTPException(
                status_code=500,
                detail="Background job processor not available"
            )
        
        # Start background job
        try:
            job_id = await processor.start_job(
                document_text=document_text,
                target_question_count=question_count,
                language=language,
                purpose=purpose,
                generation_mode=generation_mode
            )
        except Exception as e:
            logger.error(f"❌ Failed to start job: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start generation job: {str(e)}"
            )
        
        # Get job info to extract analysis_id
        job_status = processor.get_job_status(job_id)
        analysis_id = job_status.get('analysis_id') if job_status else None
        
        return {
            "success": True,
            "job_id": str(job_id),
            "analysis_id": analysis_id,
            "estimated_time": "6-11 minutes",
            "status_endpoint": f"/api/v1/ai-questionnaire/job-status/{job_id}",
            "message": "AI vision models processing your document directly. No text extraction needed!"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error starting generation job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start generation: {str(e)}"
        )


@router.get("/job-status/{job_id}")
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_sync_db)
):
    """
    Get generation job status and progress
    
    Returns:
    - status: queued, analyzing, generating, validating, assembling, completed, failed
    - progress: 0-100
    - stage: Current stage description
    - estimated_time_remaining: Estimate in minutes
    - questions_generated, questions_validated, questions_selected: Counts
    """
    try:
        job_uuid = UUID(job_id)
        from src.services.job_processor import BackgroundJobProcessor
        processor = BackgroundJobProcessor(db)
        
        status_data = processor.get_job_status(job_uuid)
        
        if not status_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        return status_data
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job_id format"
        )
    except Exception as e:
        logger.error(f"❌ Error getting job status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/review/{analysis_id}")
async def delete_pending_generation(
    analysis_id: int,
    db: Session = Depends(get_sync_db)
):
    """
    Discard/Delete a pending AI generation (analysis and candidates)
    """
    try:
        # Get analysis
        analysis = db.query(QuestionnaireAnalysis).filter(
            QuestionnaireAnalysis.id == analysis_id
        ).first()
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis {analysis_id} not found"
            )
            
        # Delete candidates first (if no cascade delete)
        db.query(GeneratedQuestionCandidate).filter(
            GeneratedQuestionCandidate.analysis_id == analysis_id
        ).delete()
        
        # Delete analysis
        db.delete(analysis)
        db.commit()
        
        return {"success": True, "message": "Generation discarded successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error discarding generation: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/review/{analysis_id}")
async def get_candidates_for_review(
    analysis_id: int,
    db: Session = Depends(get_sync_db)
):
    """
    Get all question candidates for human review
    
    Shows:
    - All generated candidates with scores
    - Validation feedback from AI
    - Which model generated each question
    - Recommendations (keep/reject)
    
    Use this for human oversight before creating final questionnaire.
    """
    try:
        # Get analysis
        analysis = db.query(QuestionnaireAnalysis).filter(
            QuestionnaireAnalysis.id == analysis_id
        ).first()
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis {analysis_id} not found"
            )
        
        # Get all candidates
        candidates = db.query(GeneratedQuestionCandidate).filter(
            GeneratedQuestionCandidate.analysis_id == analysis_id
        ).order_by(GeneratedQuestionCandidate.overall_score.desc()).all()
        
        # Extract suggested title
        suggested_title = None
        if analysis.domain_analysis and isinstance(analysis.domain_analysis, dict):
            suggested_title = analysis.domain_analysis.get('suggested_title')
        
        return {
            "success": True,
            "analysis_id": analysis_id,
            "suggested_title": suggested_title,
            "document_filename": analysis.document_filename or "Unknown Document",
            "analysis_summary": analysis.analysis_map,
            "total_candidates": len(candidates),
            "candidates": [
                {
                    "id": c.id,
                    "question_data": c.question_data,
                    "generator_instance": c.generator_instance,
                    "model_used": c.model_used,
                    "focus_area": c.focus_area,
                    "scores": {
                        "quality": float(c.quality_score) if c.quality_score else None,
                        "relevance": float(c.relevance_score) if c.relevance_score else None,
                        "uniqueness": float(c.uniqueness_score) if c.uniqueness_score else None,
                        "overall": float(c.overall_score) if c.overall_score else None
                    },
                    "validation_feedback": c.validation_feedback,
                    "status": c.status
                }
                for c in candidates
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting candidates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


def _validate_question_bilingual(question_data: dict) -> tuple[bool, str]:
    """
    Validate that a question has proper bilingual content
    Returns: (is_valid, reason)
    """
    en = question_data.get("question_en", "").strip()
    zh = question_data.get("question_zh", "").strip()
    
    # Check if both fields exist
    if not en or not zh:
        return False, "Missing question_en or question_zh"
    
    # Check if English field contains Chinese characters
    has_chinese_in_en = any('\u4e00' <= char <= '\u9fff' for char in en)
    if has_chinese_in_en:
        return False, f"English field contains Chinese: {en[:50]}..."
    
    # Check if Chinese field has sufficient Chinese content
    chinese_char_count = sum(1 for char in zh if '\u4e00' <= char <= '\u9fff')
    if len(zh) > 10 and chinese_char_count < len(zh) * 0.3:
        return False, f"Chinese field lacks Chinese characters: {zh[:50]}..."
    
    # Note: Question marks are optional - many assessment items are statements, not questions
    # Examples: "Feeling down, depressed, or hopeless" or "Little interest or pleasure in doing things"
    
    return True, "Valid"


class ApproveQuestionsRequest(BaseModel):
    """Request model for approving questions"""
    selected_question_ids: list[int]
    questionnaire_title: Optional[str] = None
    questionnaire_description: Optional[str] = None
    auto_activate: bool = False


@router.post("/review/{analysis_id}/approve")
async def approve_questions(
    analysis_id: int,
    request: ApproveQuestionsRequest,
    db: Session = Depends(get_sync_db)
):
    """
    Human approves specific questions and creates final questionnaire
    
    Args:
        analysis_id: The analysis ID
        request: Request containing selected question IDs and optional title
    
    Returns:
        Created questionnaire ID
    """
    try:
        # Get analysis
        analysis = db.query(QuestionnaireAnalysis).filter(
            QuestionnaireAnalysis.id == analysis_id
        ).first()
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis {analysis_id} not found"
            )
        
        # Get selected candidates
        selected_candidates = db.query(GeneratedQuestionCandidate).filter(
            GeneratedQuestionCandidate.id.in_(request.selected_question_ids)
        ).all()
        
        if len(selected_candidates) != len(request.selected_question_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Some question IDs not found"
            )
        
        # ✨ NEW: Validate questions for bilingual quality
        valid_questions = []
        rejected_questions = []
        
        for c in selected_candidates:
            is_valid, reason = _validate_question_bilingual(c.question_data)
            if is_valid:
                valid_questions.append(c.question_data)
            else:
                rejected_questions.append({
                    "id": c.id,
                    "question_data": c.question_data,
                    "reason": reason
                })
                logger.warning(f"❌ Rejected question {c.id}: {reason}")
        
        # If all questions were rejected, fail
        if not valid_questions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"All {len(rejected_questions)} selected questions failed validation. Reasons: {', '.join(r['reason'] for r in rejected_questions[:3])}"
            )
        
        # Log validation results
        if rejected_questions:
            logger.warning(f"📊 Validation filtered out {len(rejected_questions)}/{len(selected_candidates)} questions")
        
        # Create questionnaire from selected questions
        title = request.questionnaire_title or "AI-Generated Questionnaire"
        description = request.questionnaire_description
        
        # Build questionnaire structure
        questionnaire = {
            "title": title,
            "questions": valid_questions
        }
        
        # Save to database
        questionnaire_id = await _save_questionnaire_to_db(
            questionnaire, title, "en", "child-screening", db, description
        )
        
        # Link knowledge base to questionnaire
        kb = db.query(QuestionnaireKnowledgeBase).filter(
            QuestionnaireKnowledgeBase.analysis_id == analysis_id
        ).first()
        if kb:
            kb.questionnaire_id = questionnaire_id
            db.commit()
        
        # Auto-activate if requested
        if request.auto_activate:
            try:
                from src.database.models_questionnaire import QuestionnaireBank
                questionnaire_record = db.query(QuestionnaireBank).filter(
                    QuestionnaireBank.id == questionnaire_id
                ).first()
                if questionnaire_record:
                    questionnaire_record.status = "active"
                    from datetime import datetime
                    questionnaire_record.published_at = datetime.now()
                    db.commit()
                    logger.info(f"✅ Auto-activated questionnaire #{questionnaire_id}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to auto-activate questionnaire: {e}")
                # Don't fail the whole request if activation fails
        
        status_msg = "activated" if request.auto_activate else "created as draft"
        
        # Build response message
        message = f"Questionnaire {status_msg} successfully"
        if rejected_questions:
            message += f". Note: {len(rejected_questions)} questions were filtered out due to validation issues (e.g., Chinese text in English fields)"
        
        return {
            "success": True,
            "questionnaire_id": questionnaire_id,
            "questions_selected": len(selected_candidates),
            "questions_included": len(valid_questions),
            "questions_rejected": len(rejected_questions),
            "status": "active" if request.auto_activate else "draft",
            "message": message,
            "rejected_reasons": [r["reason"] for r in rejected_questions[:5]] if rejected_questions else []
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating questionnaire: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/pending")
async def get_pending_generations(db: Session = Depends(get_sync_db)):
    """
    Get all pending AI generations awaiting approval
    
    Returns:
        List of pending generations with summary statistics
    """
    try:
        from sqlalchemy import desc
        
        # Get all analyses that have selected candidates
        # Use a simpler approach - just get all analyses and filter in Python
        all_analyses = db.query(QuestionnaireAnalysis).order_by(
            desc(QuestionnaireAnalysis.created_at)
        ).all()
        
        pending_generations = []
        for analysis in all_analyses:
            # Get ALL candidates for this analysis (regardless of status)
            all_candidates = db.query(GeneratedQuestionCandidate).filter(
                GeneratedQuestionCandidate.analysis_id == analysis.id
            ).all()
            
            # Skip analyses with no candidates at all
            if not all_candidates:
                continue
            
            # Check if this analysis has already been converted to a questionnaire
            # If it has a linked questionnaire, skip it (already approved)
            kb = db.query(QuestionnaireKnowledgeBase).filter(
                QuestionnaireKnowledgeBase.analysis_id == analysis.id,
                QuestionnaireKnowledgeBase.questionnaire_id.isnot(None)
            ).first()
            if kb:
                continue  # Already approved and saved
            
            # Count candidates by status
            selected_candidates = [c for c in all_candidates if c.status == 'selected']
            candidate_status = [c for c in all_candidates if c.status == 'candidate']
            rejected_candidates = [c for c in all_candidates if c.status == 'rejected']
            
            # Use selected if available, otherwise use candidate status, otherwise use ALL (including rejected)
            candidates_to_show = selected_candidates if selected_candidates else (candidate_status if candidate_status else all_candidates)
            
            # Always show if there are ANY candidates
            if not candidates_to_show:
                continue
            
            # Get total candidates
            total_candidates = len(all_candidates)

            # Get sample questions (first 3) and calculate average fidelity
            sample_candidates = candidates_to_show[:3] if candidates_to_show else []
            
            # Calculate average fidelity from candidates to show
            fidelity_scores = [
                c.question_data.get('fidelity_score', 0) * 100 
                for c in candidates_to_show 
                if c.question_data.get('fidelity_score') is not None
            ]
            avg_fidelity = sum(fidelity_scores) / len(fidelity_scores) if fidelity_scores else 0
            
            sample_questions = [
                {
                    'question_en': c.question_data.get('question_en', 'N/A'),
                    'question_zh': c.question_data.get('question_zh', 'N/A'),
                    'category': c.question_data.get('category', 'N/A')
                }
                for c in sample_candidates
            ]
            
            pending_generations.append({
                'analysis_id': analysis.id,
                'created_at': analysis.created_at.isoformat() if analysis.created_at else None,
                'document_filename': analysis.document_filename or 'Unknown Document',
                'total_candidates': total_candidates,
                'selected_count': len(candidates_to_show),
                'avg_fidelity': round(avg_fidelity, 1),
                'sample_questions': sample_questions,
                'analysis_summary': analysis.analysis_map
            })
        
        return {
            'success': True,
            'pending_generations': pending_generations,
            'count': len(pending_generations)
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching pending generations: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Export router
__all__ = ["router"]

