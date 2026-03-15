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
from src.tools.ai_questionnaire_generator import AIQuestionnaireClient
from src.tools.file_parser import FileParser
from src.core.logging import get_logger

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
    - Images (JPG, PNG, etc.) - uses AI OCR with Gemini
    
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
                metadata["ai_model"] = "gemini-2.0-flash"
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
    db: Session
) -> int:
    """
    Save generated questionnaire to database
    
    Args:
        questionnaire: Generated questionnaire data
        title: Optional custom title
        language: Questionnaire language
        purpose: Purpose of questionnaire
        db: Database session
        
    Returns:
        ID of saved questionnaire
    """
    try:
        # Extract title
        questionnaire_title = title or questionnaire.get("title", "AI Generated Questionnaire")
        if language == "zh" and questionnaire.get("title_zh"):
            questionnaire_title = questionnaire.get("title_zh")
        
        # Create questionnaire bank
        questionnaire_bank = QuestionnaireBank(
            title=questionnaire_title,
            description=questionnaire.get("intro_en") or questionnaire.get("intro_zh"),
            language=language,
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


# Export router
__all__ = ["router"]

