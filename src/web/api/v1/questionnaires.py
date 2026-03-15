"""
Questionnaire Management API
For receiving questionnaires from teammate's generation function and managing them
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.database.connection import get_sync_db
from src.database.models_questionnaire import (
    QuestionnaireBank,
    QuestionnaireQuestion,
    QuestionOption,
    QuestionnaireResponse,
    QuestionAnswer,
    ScoringRule,
    CategoryScore
)
from src.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class QuestionOptionCreate(BaseModel):
    """Option for a question"""
    option_text: str
    option_text_zh: Optional[str] = None
    option_value: int
    sequence_order: int


class QuestionCreate(BaseModel):
    """Question creation model"""
    question_code: Optional[str] = None
    question_text: str
    question_text_zh: Optional[str] = None
    question_type: str  # scale, yes_no, multiple_choice, short_answer, rating
    category: Optional[str] = None
    sequence_order: int
    is_required: bool = True
    help_text: Optional[str] = None
    options: List[QuestionOptionCreate] = []


class QuestionUpdate(BaseModel):
    """Question update model"""
    question_text: Optional[str] = None
    question_text_zh: Optional[str] = None
    question_type: Optional[str] = None
    category: Optional[str] = None
    is_required: Optional[bool] = None
    help_text: Optional[str] = None


class QuestionnaireUpdate(BaseModel):
    """Questionnaire update model"""
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    target_age_min: Optional[int] = None
    target_age_max: Optional[int] = None
    language: Optional[str] = None
    estimated_duration_minutes: Optional[int] = None
    status: Optional[str] = None


class ScoringRuleCreate(BaseModel):
    """Scoring rule creation model"""
    category: str
    category_name_en: Optional[str] = None
    category_name_zh: Optional[str] = None
    weight: float = 1.0
    threshold_excellent: Optional[float] = None
    threshold_good: Optional[float] = None
    threshold_moderate: Optional[float] = None
    threshold_concerning: Optional[float] = None
    flag_if_below: Optional[float] = None
    alert_if_below: Optional[float] = None


class QuestionnaireImport(BaseModel):
    """Model for importing questionnaire from teammate's generation function"""
    title: str
    description: Optional[str] = None
    category: Optional[str] = "mental_health"
    target_age_min: Optional[int] = None
    target_age_max: Optional[int] = None
    language: str = "en"
    estimated_duration_minutes: Optional[int] = None
    source: str = "ai_generated"  # ai_generated, manual, imported
    questions: List[QuestionCreate]
    scoring_rules: List[ScoringRuleCreate] = []


class AnswerSubmit(BaseModel):
    """Answer submission model"""
    question_id: int
    answer_text: Optional[str] = None
    answer_value: Optional[int] = None


class ResponseSubmit(BaseModel):
    """Questionnaire response submission"""
    questionnaire_id: int
    session_id: Optional[str] = None
    answers: List[AnswerSubmit]


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_questionnaire(
    questionnaire: QuestionnaireImport,
    db: Session = Depends(get_sync_db)
) -> Dict[str, Any]:
    """
    Import a questionnaire from teammate's generation function
    
    This endpoint receives the generated questionnaire and stores it in the database.
    """
    try:
        # Create questionnaire bank
        questionnaire_bank = QuestionnaireBank(
            title=questionnaire.title,
            description=questionnaire.description,
            category=questionnaire.category,
            target_age_min=questionnaire.target_age_min,
            target_age_max=questionnaire.target_age_max,
            language=questionnaire.language,
            total_questions=len(questionnaire.questions),
            estimated_duration_minutes=questionnaire.estimated_duration_minutes,
            source=questionnaire.source,
            status="draft"  # Start as draft, can be activated later
        )
        
        db.add(questionnaire_bank)
        db.flush()  # Get the ID
        
        # Create questions
        for q in questionnaire.questions:
            question = QuestionnaireQuestion(
                questionnaire_id=questionnaire_bank.id,
                question_code=q.question_code,
                question_text=q.question_text,
                question_text_zh=q.question_text_zh,
                question_type=q.question_type,
                category=q.category,
                sequence_order=q.sequence_order,
                is_required=q.is_required,
                help_text=q.help_text
            )
            db.add(question)
            db.flush()
            
            # Create options for this question
            for opt in q.options:
                option = QuestionOption(
                    question_id=question.id,
                    option_text=opt.option_text,
                    option_text_zh=opt.option_text_zh,
                    option_value=opt.option_value,
                    sequence_order=opt.sequence_order
                )
                db.add(option)
        
        # Create scoring rules
        for rule in questionnaire.scoring_rules:
            scoring_rule = ScoringRule(
                questionnaire_id=questionnaire_bank.id,
                category=rule.category,
                category_name_en=rule.category_name_en,
                category_name_zh=rule.category_name_zh,
                weight=rule.weight,
                threshold_excellent=rule.threshold_excellent,
                threshold_good=rule.threshold_good,
                threshold_moderate=rule.threshold_moderate,
                threshold_concerning=rule.threshold_concerning,
                flag_if_below=rule.flag_if_below,
                alert_if_below=rule.alert_if_below
            )
            db.add(scoring_rule)
        
        db.commit()
        db.refresh(questionnaire_bank)
        
        logger.info(f"Imported questionnaire: {questionnaire_bank.id} - {questionnaire_bank.title}")
        
        return {
            "success": True,
            "message": "Questionnaire imported successfully",
            "questionnaire_id": questionnaire_bank.id,
            "title": questionnaire_bank.title,
            "total_questions": questionnaire_bank.total_questions,
            "status": questionnaire_bank.status
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error importing questionnaire: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import questionnaire: {str(e)}"
        )


@router.get("/")
@router.get("/list")
async def list_questionnaires(
    status_filter: Optional[str] = None,
    category: Optional[str] = None,
    language: Optional[str] = None,
    db: Session = Depends(get_sync_db)
) -> Dict[str, Any]:
    """List all questionnaires with optional filters"""
    try:
        query = db.query(QuestionnaireBank)
        
        if status_filter:
            query = query.filter(QuestionnaireBank.status == status_filter)
        if category:
            query = query.filter(QuestionnaireBank.category == category)
        if language:
            query = query.filter(QuestionnaireBank.language == language)
        
        questionnaires = query.order_by(desc(QuestionnaireBank.created_at)).all()
        
        return {
            "success": True,
            "total": len(questionnaires),
            "questionnaires": [
                {
                    "id": q.id,
                    "title": q.title,
                    "description": q.description,
                    "category": q.category,
                    "status": q.status,
                    "language": q.language,
                    "total_questions": q.total_questions,
                    "estimated_duration_minutes": q.estimated_duration_minutes,
                    "target_age_min": q.target_age_min,
                    "target_age_max": q.target_age_max,
                    "source": q.source,
                    "created_at": q.created_at.isoformat() if q.created_at else None
                }
                for q in questionnaires
            ]
        }
    except Exception as e:
        logger.error(f"Error listing questionnaires: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list questionnaires"
        )


@router.get("/{questionnaire_id}")
async def get_questionnaire(
    questionnaire_id: int,
    db: Session = Depends(get_sync_db)
) -> Dict[str, Any]:
    """Get questionnaire details with all questions and options"""
    try:
        questionnaire = db.query(QuestionnaireBank).filter(
            QuestionnaireBank.id == questionnaire_id
        ).first()
        
        if not questionnaire:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questionnaire not found"
            )
        
        # Get questions with options
        questions = db.query(QuestionnaireQuestion).filter(
            QuestionnaireQuestion.questionnaire_id == questionnaire_id
        ).order_by(QuestionnaireQuestion.sequence_order).all()
        
        questions_data = []
        for q in questions:
            options = db.query(QuestionOption).filter(
                QuestionOption.question_id == q.id
            ).order_by(QuestionOption.sequence_order).all()
            
            questions_data.append({
                "id": q.id,
                "question_code": q.question_code,
                "question_text": q.question_text,
                "question_text_zh": q.question_text_zh,
                "question_type": q.question_type,
                "category": q.category,
                "sequence_order": q.sequence_order,
                "is_required": q.is_required,
                "help_text": q.help_text,
                "options": [
                    {
                        "id": opt.id,
                        "option_text": opt.option_text,
                        "option_text_zh": opt.option_text_zh,
                        "option_value": opt.option_value,
                        "sequence_order": opt.sequence_order
                    }
                    for opt in options
                ]
            })
        
        # Get scoring rules
        scoring_rules = db.query(ScoringRule).filter(
            ScoringRule.questionnaire_id == questionnaire_id
        ).all()
        
        return {
            "success": True,
            "questionnaire": {
                "id": questionnaire.id,
                "title": questionnaire.title,
                "description": questionnaire.description,
                "category": questionnaire.category,
                "status": questionnaire.status,
                "language": questionnaire.language,
                "total_questions": questionnaire.total_questions,
                "estimated_duration_minutes": questionnaire.estimated_duration_minutes,
                "target_age_min": questionnaire.target_age_min,
                "target_age_max": questionnaire.target_age_max,
                "source": questionnaire.source,
                "created_at": questionnaire.created_at.isoformat() if questionnaire.created_at else None,
                "questions": questions_data,
                "scoring_rules": [
                    {
                        "category": rule.category,
                        "category_name_en": rule.category_name_en,
                        "category_name_zh": rule.category_name_zh,
                        "weight": float(rule.weight) if rule.weight else None,
                        "threshold_excellent": float(rule.threshold_excellent) if rule.threshold_excellent else None,
                        "threshold_good": float(rule.threshold_good) if rule.threshold_good else None,
                        "threshold_moderate": float(rule.threshold_moderate) if rule.threshold_moderate else None,
                        "threshold_concerning": float(rule.threshold_concerning) if rule.threshold_concerning else None,
                        "flag_if_below": float(rule.flag_if_below) if rule.flag_if_below else None,
                        "alert_if_below": float(rule.alert_if_below) if rule.alert_if_below else None
                    }
                    for rule in scoring_rules
                ]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting questionnaire {questionnaire_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get questionnaire"
        )


@router.post("/{questionnaire_id}/activate")
async def activate_questionnaire(
    questionnaire_id: int,
    db: Session = Depends(get_sync_db)
) -> Dict[str, Any]:
    """Activate a questionnaire (change status from draft to active)"""
    try:
        questionnaire = db.query(QuestionnaireBank).filter(
            QuestionnaireBank.id == questionnaire_id
        ).first()
        
        if not questionnaire:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questionnaire not found"
            )
        
        questionnaire.status = "active"
        questionnaire.published_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": "Questionnaire activated successfully",
            "questionnaire_id": questionnaire.id,
            "status": questionnaire.status
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error activating questionnaire {questionnaire_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate questionnaire"
        )


@router.post("/{questionnaire_id}/archive")
async def archive_questionnaire(
    questionnaire_id: int,
    db: Session = Depends(get_sync_db)
) -> Dict[str, Any]:
    """Archive a questionnaire (change status to archived)"""
    try:
        questionnaire = db.query(QuestionnaireBank).filter(
            QuestionnaireBank.id == questionnaire_id
        ).first()
        
        if not questionnaire:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questionnaire not found"
            )
        
        old_status = questionnaire.status
        questionnaire.status = "archived"
        db.commit()
        
        logger.info(f"Archived questionnaire {questionnaire_id}: {questionnaire.title} (was {old_status})")
        
        return {
            "success": True,
            "message": "Questionnaire archived successfully",
            "questionnaire_id": questionnaire.id,
            "old_status": old_status,
            "new_status": questionnaire.status
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error archiving questionnaire {questionnaire_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to archive questionnaire"
        )


@router.post("/{questionnaire_id}/unarchive")
async def unarchive_questionnaire(
    questionnaire_id: int,
    db: Session = Depends(get_sync_db)
) -> Dict[str, Any]:
    """Unarchive a questionnaire (restore to draft status)"""
    try:
        questionnaire = db.query(QuestionnaireBank).filter(
            QuestionnaireBank.id == questionnaire_id
        ).first()
        
        if not questionnaire:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questionnaire not found"
            )
        
        if questionnaire.status != "archived":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only archived questionnaires can be unarchived"
            )
        
        questionnaire.status = "draft"
        db.commit()
        
        logger.info(f"Unarchived questionnaire {questionnaire_id}: {questionnaire.title}")
        
        return {
            "success": True,
            "message": "Questionnaire restored to draft status",
            "questionnaire_id": questionnaire.id,
            "status": questionnaire.status
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error unarchiving questionnaire {questionnaire_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unarchive questionnaire"
        )


@router.patch("/{questionnaire_id}")
async def update_questionnaire(
    questionnaire_id: int,
    questionnaire_update: QuestionnaireUpdate,
    db: Session = Depends(get_sync_db)
) -> Dict[str, Any]:
    """
    Update questionnaire metadata (title, description, etc.)
    """
    try:
        # Find the questionnaire
        questionnaire = db.query(QuestionnaireBank).filter(
            QuestionnaireBank.id == questionnaire_id
        ).first()
        
        if not questionnaire:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Questionnaire with ID {questionnaire_id} not found"
            )
        
        # Update fields if provided
        if questionnaire_update.title is not None:
            questionnaire.title = questionnaire_update.title
        if questionnaire_update.description is not None:
            questionnaire.description = questionnaire_update.description
        if questionnaire_update.category is not None:
            questionnaire.category = questionnaire_update.category
        if questionnaire_update.target_age_min is not None:
            questionnaire.target_age_min = questionnaire_update.target_age_min
        if questionnaire_update.target_age_max is not None:
            questionnaire.target_age_max = questionnaire_update.target_age_max
        if questionnaire_update.language is not None:
            questionnaire.language = questionnaire_update.language
        if questionnaire_update.estimated_duration_minutes is not None:
            questionnaire.estimated_duration_minutes = questionnaire_update.estimated_duration_minutes
        if questionnaire_update.status is not None:
            questionnaire.status = questionnaire_update.status
        
        questionnaire.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(questionnaire)
        
        logger.info(f"✅ Questionnaire {questionnaire_id} updated successfully")
        
        return {
            "success": True,
            "message": "Questionnaire updated successfully",
            "questionnaire": {
                "id": questionnaire.id,
                "title": questionnaire.title,
                "description": questionnaire.description,
                "category": questionnaire.category,
                "status": questionnaire.status,
                "language": questionnaire.language
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error updating questionnaire {questionnaire_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update questionnaire: {str(e)}"
        )


@router.put("/questions/{question_id}")
async def update_question(
    question_id: int,
    question_update: QuestionUpdate,
    db: Session = Depends(get_sync_db)
) -> Dict[str, Any]:
    """
    Update a questionnaire question
    """
    try:
        # Find the question
        question = db.query(QuestionnaireQuestion).filter(
            QuestionnaireQuestion.id == question_id
        ).first()
        
        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Question with ID {question_id} not found"
            )
        
        # Update fields if provided
        if question_update.question_text is not None:
            question.question_text = question_update.question_text
        if question_update.question_text_zh is not None:
            question.question_text_zh = question_update.question_text_zh
        if question_update.question_type is not None:
            question.question_type = question_update.question_type
        if question_update.category is not None:
            question.category = question_update.category
        if question_update.is_required is not None:
            question.is_required = question_update.is_required
        if question_update.help_text is not None:
            question.help_text = question_update.help_text
        
        question.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(question)
        
        logger.info(f"✅ Question {question_id} updated successfully")
        
        return {
            "success": True,
            "message": "Question updated successfully",
            "question": {
                "id": question.id,
                "question_text": question.question_text,
                "question_text_zh": question.question_text_zh,
                "question_type": question.question_type,
                "category": question.category,
                "is_required": question.is_required,
                "help_text": question.help_text
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error updating question {question_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update question: {str(e)}"
        )


@router.delete("/{questionnaire_id}")
async def delete_questionnaire(
    questionnaire_id: int,
    db: Session = Depends(get_sync_db)
) -> Dict[str, Any]:
    """
    Permanently delete a questionnaire and all associated data.
    
    WARNING: This is a destructive operation that cannot be undone.
    Deletes:
    - Questionnaire structure
    - All questions
    - Scoring rules
    - Category scores
    - All responses (if any)
    - Question answers
    - Knowledge base data (if linked)
    """
    try:
        # Check if questionnaire exists
        questionnaire = db.query(QuestionnaireBank).filter(
            QuestionnaireBank.id == questionnaire_id
        ).first()
        
        if not questionnaire:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questionnaire not found"
            )
        
        # Store info for logging before deletion
        title = questionnaire.title
        question_count = questionnaire.total_questions
        
        # Check if questionnaire has responses
        from src.database.models_questionnaire import (
            QuestionnaireResponse, QuestionAnswer, CategoryScore,
            ConversationAnswer, QuestionnaireAssignment
        )
        response_count = db.query(QuestionnaireResponse).filter(
            QuestionnaireResponse.questionnaire_id == questionnaire_id
        ).count()
        
        # Get all question IDs for this questionnaire (for deleting conversation answers)
        question_ids = [q.id for q in questionnaire.questions]
        
        # Delete conversation answers (Live2D chat answers) first
        if question_ids:
            conversation_answer_count = db.query(ConversationAnswer).filter(
                ConversationAnswer.question_id.in_(question_ids)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {conversation_answer_count} conversation answers")
        
        # Delete assignments
        assignment_count = db.query(QuestionnaireAssignment).filter(
            QuestionnaireAssignment.questionnaire_id == questionnaire_id
        ).delete(synchronize_session=False)
        logger.info(f"Deleted {assignment_count} questionnaire assignments")
        
        # Manually delete responses and their related data first
        # (since questionnaire_responses.questionnaire_id doesn't have CASCADE)
        if response_count > 0:
            logger.info(f"Deleting {response_count} responses for questionnaire {questionnaire_id}")
            
            # Get all response IDs
            response_ids = [r.id for r in db.query(QuestionnaireResponse.id).filter(
                QuestionnaireResponse.questionnaire_id == questionnaire_id
            ).all()]
            
            # Delete question answers (they reference response_id with CASCADE, so this should work)
            answer_count = db.query(QuestionAnswer).filter(
                QuestionAnswer.response_id.in_(response_ids)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {answer_count} question answers")
            
            # Delete category scores (they reference response_id with CASCADE, so this should work)
            score_count = db.query(CategoryScore).filter(
                CategoryScore.response_id.in_(response_ids)
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {score_count} category scores")
            
            # Delete responses
            db.query(QuestionnaireResponse).filter(
                QuestionnaireResponse.questionnaire_id == questionnaire_id
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {response_count} responses")
        
        # Delete knowledge base if linked
        try:
            from src.database.models_multistage_questionnaire import QuestionnaireKnowledgeBase
            kb = db.query(QuestionnaireKnowledgeBase).filter(
                QuestionnaireKnowledgeBase.questionnaire_id == questionnaire_id
            ).first()
            if kb:
                db.delete(kb)
                logger.info(f"Deleted knowledge base for questionnaire {questionnaire_id}")
        except Exception as e:
            logger.warning(f"Could not delete knowledge base: {e}")
        
        # Now delete the questionnaire (cascade will handle questions, options, scoring rules)
        db.delete(questionnaire)
        db.commit()
        
        logger.info(f"Deleted questionnaire {questionnaire_id}: {title} ({question_count} questions, {response_count} responses)")
        
        return {
            "success": True,
            "message": "Questionnaire deleted successfully",
            "questionnaire_id": questionnaire_id,
            "title": title,
            "questions_deleted": question_count,
            "responses_deleted": response_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting questionnaire {questionnaire_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete questionnaire: {str(e)}"
        )


@router.post("/responses/submit")
async def submit_response(
    response: ResponseSubmit,
    user_id: Optional[int] = None,
    db: Session = Depends(get_sync_db)
) -> Dict[str, Any]:
    """
    Submit a questionnaire response
    
    This saves user answers and calculates scores
    """
    try:
        # Create response record
        questionnaire_response = QuestionnaireResponse(
            user_id=user_id,
            questionnaire_id=response.questionnaire_id,
            session_id=response.session_id or f"session_{int(datetime.utcnow().timestamp())}",
            started_at=datetime.utcnow(),
            status="in_progress"
        )
        db.add(questionnaire_response)
        db.flush()
        
        # Save answers
        for answer in response.answers:
            question_answer = QuestionAnswer(
                response_id=questionnaire_response.id,
                question_id=answer.question_id,
                answer_text=answer.answer_text,
                answer_value=answer.answer_value,
                answered_at=datetime.utcnow()
            )
            db.add(question_answer)
        
        # Calculate scores
        scores = calculate_scores(questionnaire_response.id, response.questionnaire_id, db)
        
        # Update response
        questionnaire_response.status = "completed"
        questionnaire_response.completed_at = datetime.utcnow()
        questionnaire_response.total_score = scores.get("total_score")
        questionnaire_response.confidence_level = scores.get("confidence_level")
        
        db.commit()
        
        return {
            "success": True,
            "message": "Response submitted successfully",
            "response_id": questionnaire_response.id,
            "total_score": float(scores.get("total_score", 0)),
            "confidence_level": float(scores.get("confidence_level", 0)),
            "category_scores": scores.get("category_scores", [])
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error submitting response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit response: {str(e)}"
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_scores(response_id: int, questionnaire_id: int, db: Session) -> Dict[str, Any]:
    """
    Calculate scores for a questionnaire response
    
    Returns category scores and total score with confidence level
    """
    try:
        # Get all answers for this response
        answers = db.query(QuestionAnswer).filter(
            QuestionAnswer.response_id == response_id
        ).all()
        
        # Get scoring rules
        scoring_rules = db.query(ScoringRule).filter(
            ScoringRule.questionnaire_id == questionnaire_id
        ).all()
        
        # Group answers by category
        category_answers = {}
        for answer in answers:
            question = db.query(QuestionnaireQuestion).filter(
                QuestionnaireQuestion.id == answer.question_id
            ).first()
            
            if question and question.category:
                if question.category not in category_answers:
                    category_answers[question.category] = []
                category_answers[question.category].append(answer.answer_value or 0)
        
        # Calculate category scores
        category_scores_data = []
        total_weighted_score = 0
        total_weight = 0
        
        for rule in scoring_rules:
            if rule.category in category_answers:
                answers_for_category = category_answers[rule.category]
                raw_score = sum(answers_for_category) / len(answers_for_category) if answers_for_category else 0
                weighted_score = raw_score * float(rule.weight)
                
                # Determine interpretation
                interpretation = "moderate"
                if rule.threshold_excellent and raw_score >= float(rule.threshold_excellent):
                    interpretation = "excellent"
                elif rule.threshold_good and raw_score >= float(rule.threshold_good):
                    interpretation = "good"
                elif rule.threshold_concerning and raw_score < float(rule.threshold_concerning):
                    interpretation = "concerning"
                
                # Check if should be flagged
                flagged = False
                if rule.flag_if_below and raw_score < float(rule.flag_if_below):
                    flagged = True
                
                # Save category score
                category_score = CategoryScore(
                    response_id=response_id,
                    category=rule.category,
                    raw_score=raw_score,
                    weighted_score=weighted_score,
                    max_possible_score=5.0,  # Assuming 5-point scale
                    percentage=(raw_score / 5.0) * 100,
                    interpretation=interpretation,
                    flagged=flagged
                )
                db.add(category_score)
                
                category_scores_data.append({
                    "category": rule.category,
                    "raw_score": raw_score,
                    "weighted_score": weighted_score,
                    "percentage": (raw_score / 5.0) * 100,
                    "interpretation": interpretation,
                    "flagged": flagged
                })
                
                total_weighted_score += weighted_score
                total_weight += float(rule.weight)
        
        # Calculate total score
        total_score = total_weighted_score / total_weight if total_weight > 0 else 0
        
        # Calculate confidence level based on number of questions answered
        total_questions = db.query(QuestionnaireQuestion).filter(
            QuestionnaireQuestion.questionnaire_id == questionnaire_id
        ).count()
        
        questions_answered = len(answers)
        confidence_level = questions_answered / total_questions if total_questions > 0 else 0
        
        return {
            "total_score": total_score,
            "confidence_level": confidence_level,
            "category_scores": category_scores_data
        }
        
    except Exception as e:
        logger.error(f"Error calculating scores: {e}")
        return {
            "total_score": 0,
            "confidence_level": 0,
            "category_scores": []
        }


@router.get("/{questionnaire_id}/statistics")
async def get_questionnaire_statistics(
    questionnaire_id: int,
    db: Session = Depends(get_sync_db)
) -> Dict[str, Any]:
    """
    Get comprehensive statistics for a questionnaire
    
    Returns response counts, score distributions, and trends
    """
    try:
        from sqlalchemy import func
        
        # Get questionnaire
        questionnaire = db.query(QuestionnaireBank).filter(
            QuestionnaireBank.id == questionnaire_id
        ).first()
        
        if not questionnaire:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questionnaire not found"
            )
        
        # Get total responses
        total_responses = db.query(QuestionnaireResponse).filter(
            QuestionnaireResponse.questionnaire_id == questionnaire_id
        ).count()
        
        completed_responses = db.query(QuestionnaireResponse).filter(
            QuestionnaireResponse.questionnaire_id == questionnaire_id,
            QuestionnaireResponse.status == "completed"
        ).count()
        
        # Get average score
        avg_score = db.query(func.avg(QuestionnaireResponse.total_score)).filter(
            QuestionnaireResponse.questionnaire_id == questionnaire_id,
            QuestionnaireResponse.status == "completed"
        ).scalar()
        
        # Get category scores distribution
        category_stats = {}
        category_scores = db.query(CategoryScore).join(
            QuestionnaireResponse,
            CategoryScore.response_id == QuestionnaireResponse.id
        ).filter(
            QuestionnaireResponse.questionnaire_id == questionnaire_id
        ).all()
        
        for cat_score in category_scores:
            if cat_score.category not in category_stats:
                category_stats[cat_score.category] = {
                    "total": 0,
                    "sum": 0,
                    "flagged": 0,
                    "interpretations": {
                        "excellent": 0,
                        "good": 0,
                        "moderate": 0,
                        "concerning": 0
                    }
                }
            
            stats = category_stats[cat_score.category]
            stats["total"] += 1
            stats["sum"] += float(cat_score.raw_score or 0)
            if cat_score.flagged:
                stats["flagged"] += 1
            if cat_score.interpretation:
                stats["interpretations"][cat_score.interpretation] += 1
        
        # Calculate averages
        for category, stats in category_stats.items():
            stats["average"] = stats["sum"] / stats["total"] if stats["total"] > 0 else 0
            stats["flagged_percentage"] = (stats["flagged"] / stats["total"] * 100) if stats["total"] > 0 else 0
        
        # Get recent responses
        recent_responses = db.query(QuestionnaireResponse).filter(
            QuestionnaireResponse.questionnaire_id == questionnaire_id,
            QuestionnaireResponse.status == "completed"
        ).order_by(desc(QuestionnaireResponse.completed_at)).limit(10).all()
        
        # Get score trend (last 30 days)
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        trend_data = db.query(
            func.date(QuestionnaireResponse.completed_at).label("date"),
            func.avg(QuestionnaireResponse.total_score).label("avg_score"),
            func.count(QuestionnaireResponse.id).label("count")
        ).filter(
            QuestionnaireResponse.questionnaire_id == questionnaire_id,
            QuestionnaireResponse.status == "completed",
            QuestionnaireResponse.completed_at >= thirty_days_ago
        ).group_by(func.date(QuestionnaireResponse.completed_at)).all()
        
        return {
            "success": True,
            "questionnaire": {
                "id": questionnaire.id,
                "title": questionnaire.title,
                "total_questions": questionnaire.total_questions
            },
            "summary": {
                "total_responses": total_responses,
                "completed_responses": completed_responses,
                "in_progress": total_responses - completed_responses,
                "completion_rate": (completed_responses / total_responses * 100) if total_responses > 0 else 0,
                "average_score": float(avg_score) if avg_score else 0
            },
            "category_statistics": [
                {
                    "category": category,
                    "average_score": stats["average"],
                    "total_responses": stats["total"],
                    "flagged_count": stats["flagged"],
                    "flagged_percentage": stats["flagged_percentage"],
                    "interpretations": stats["interpretations"]
                }
                for category, stats in category_stats.items()
            ],
            "recent_responses": [
                {
                    "id": resp.id,
                    "user_id": resp.user_id,
                    "completed_at": resp.completed_at.isoformat() if resp.completed_at else None,
                    "total_score": float(resp.total_score) if resp.total_score else None,
                    "confidence_level": float(resp.confidence_level) if resp.confidence_level else None
                }
                for resp in recent_responses
            ],
            "score_trend": [
                {
                    "date": str(item.date),
                    "average_score": float(item.avg_score) if item.avg_score else 0,
                    "response_count": item.count
                }
                for item in trend_data
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting questionnaire statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get questionnaire statistics"
        )


# =============================================================================
# SUMMARY & KNOWLEDGE BASE ENDPOINTS
# =============================================================================

@router.get("/{questionnaire_id}/summary")
async def get_questionnaire_summary(
    questionnaire_id: int,
    db: Session = Depends(get_sync_db)
) -> Dict[str, Any]:
    """
    Get comprehensive summary linked to questionnaire
    
    Returns document summary, key insights, and knowledge base content
    for AI agent use
    """
    try:
        # Get questionnaire
        questionnaire = db.query(QuestionnaireBank).filter(
            QuestionnaireBank.id == questionnaire_id
        ).first()
        
        if not questionnaire:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questionnaire not found"
            )
        
        # Find knowledge base linked to this questionnaire
        from src.database.models_multistage_questionnaire import (
            QuestionnaireKnowledgeBase,
            QuestionnaireAnalysis
        )
        
        kb = db.query(QuestionnaireKnowledgeBase).filter(
            QuestionnaireKnowledgeBase.questionnaire_id == questionnaire_id
        ).first()
        
        if not kb:
            return {
                "questionnaire_id": questionnaire_id,
                "title": questionnaire.title,
                "summary_available": False,
                "message": "No summary available for this questionnaire"
            }
        
        # Get analysis with summary
        analysis = db.query(QuestionnaireAnalysis).filter(
            QuestionnaireAnalysis.id == kb.analysis_id
        ).first()
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis data not found"
            )
        
        return {
            "questionnaire_id": questionnaire_id,
            "title": questionnaire.title,
            "summary_available": True,
            "document_filename": analysis.document_filename,
            "document_type": analysis.document_type,
            "document_size_bytes": analysis.document_size_bytes,
            "summary": analysis.document_summary,
            "key_insights": analysis.key_insights,
            "key_concepts": kb.key_concepts,
            "scoring_guidelines": kb.scoring_guidelines,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting questionnaire summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get questionnaire summary: {str(e)}"
        )


@router.get("/{questionnaire_id}/summary/download")
async def download_summary_report(
    questionnaire_id: int,
    db: Session = Depends(get_sync_db)
):
    """
    Download summary as text report
    
    Generates a formatted text file with all summary information
    """
    try:
        from fastapi.responses import Response
        
        # Get summary data
        summary_data = await get_questionnaire_summary(questionnaire_id, db)
        
        if not summary_data.get('summary_available'):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No summary available for download"
            )
        
        # Generate formatted report
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("QUESTIONNAIRE SUMMARY REPORT")
        report_lines.append("=" * 80)
        report_lines.append("")
        report_lines.append(f"Title: {summary_data['title']}")
        report_lines.append(f"Questionnaire ID: {summary_data['questionnaire_id']}")
        report_lines.append(f"Document: {summary_data.get('document_filename', 'N/A')}")
        report_lines.append(f"Generated: {summary_data.get('created_at', 'N/A')}")
        report_lines.append("")
        report_lines.append("-" * 80)
        report_lines.append("EXECUTIVE SUMMARY")
        report_lines.append("-" * 80)
        report_lines.append("")
        report_lines.append(summary_data.get('summary', 'No summary available'))
        report_lines.append("")
        
        # Key insights
        if summary_data.get('key_insights'):
            report_lines.append("-" * 80)
            report_lines.append("KEY INSIGHTS")
            report_lines.append("-" * 80)
            report_lines.append("")
            for i, insight in enumerate(summary_data['key_insights'], 1):
                if isinstance(insight, dict):
                    report_lines.append(f"{i}. {insight.get('insight', '')}")
                    if insight.get('clinical_significance'):
                        report_lines.append(f"   Clinical Significance: {insight['clinical_significance']}")
                    if insight.get('agent_guidance'):
                        report_lines.append(f"   AI Agent Guidance: {insight['agent_guidance']}")
                    report_lines.append("")
        
        # Key concepts
        if summary_data.get('key_concepts'):
            report_lines.append("-" * 80)
            report_lines.append("KEY CONCEPTS")
            report_lines.append("-" * 80)
            report_lines.append("")
            concepts = summary_data['key_concepts']
            if isinstance(concepts, list):
                for concept in concepts:
                    if isinstance(concept, dict):
                        report_lines.append(f"• {concept.get('term', '')}: {concept.get('definition', '')}")
                    else:
                        report_lines.append(f"• {concept}")
            report_lines.append("")
        
        # Scoring guidelines
        if summary_data.get('scoring_guidelines'):
            report_lines.append("-" * 80)
            report_lines.append("SCORING GUIDELINES")
            report_lines.append("-" * 80)
            report_lines.append("")
            guidelines = summary_data['scoring_guidelines']
            if isinstance(guidelines, dict):
                for key, value in guidelines.items():
                    report_lines.append(f"{key}: {value}")
            else:
                report_lines.append(str(guidelines))
            report_lines.append("")
        
        report_lines.append("=" * 80)
        report_lines.append("End of Report")
        report_lines.append("=" * 80)
        
        report_content = "\n".join(report_lines)
        
        return Response(
            content=report_content,
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename=questionnaire_{questionnaire_id}_summary.txt"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading summary report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download summary report: {str(e)}"
        )


# Export router
__all__ = ["router"]

