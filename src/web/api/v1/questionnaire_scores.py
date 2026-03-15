"""
Questionnaire Scoring API Endpoints
Provides endpoints for viewing and analyzing questionnaire scores
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from src.database.connection import get_async_db
from src.database.models_questionnaire import (
    QuestionnaireAssignment,
    ConversationAnswer,
    QuestionnaireBank,
    QuestionnaireQuestion,
    ScoringRule
)
from src.database.models_comprehensive import User
from src.web.auth.dependencies import get_current_user, require_role
from src.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["questionnaire-scores"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class QuestionAnswerDetail(BaseModel):
    """Individual question and answer"""
    question_id: int
    question_text: str
    user_answer_text: str
    answer_value: Optional[int]
    confidence: Optional[float]
    
    class Config:
        from_attributes = True


class UserScoreDetail(BaseModel):
    """User's score for a questionnaire"""
    user_id: int
    username: str
    assignment_id: int
    status: str
    total_score: int
    max_possible_score: int
    percentage: float
    questions_answered: int
    total_questions: int
    completed_at: Optional[datetime]
    answers: List[QuestionAnswerDetail]
    
    class Config:
        from_attributes = True


class QuestionnaireScoresResponse(BaseModel):
    """Response containing all user scores for a questionnaire"""
    questionnaire_id: int
    questionnaire_title: str
    user_scores: List[UserScoreDetail]
    total_users: int


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get(
    "/{questionnaire_id}/users",
    summary="Get all user scores for a questionnaire",
    description="Get scores for all users who have completed or are completing this questionnaire"
)
async def get_questionnaire_user_scores(
    questionnaire_id: int,
    current_user: User = Depends(get_current_user),  # Changed from require_role("admin")
    db: AsyncSession = Depends(get_async_db)
):
    """Get all user scores for a questionnaire"""
    
    logger.info(f"📊 Getting scores for questionnaire {questionnaire_id}, user: {current_user.username}")
    
    try:
        # Get questionnaire info
        questionnaire_query = select(QuestionnaireBank).where(
            QuestionnaireBank.id == questionnaire_id
        )
        questionnaire_result = await db.execute(questionnaire_query)
        questionnaire = questionnaire_result.scalar_one_or_none()
        
        if not questionnaire:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Questionnaire {questionnaire_id} not found"
            )
        
        # Get all assignments for this questionnaire
        # Prioritize completed assignments with answers, then by most recent
        assignments_query = select(QuestionnaireAssignment, User).join(
            User, QuestionnaireAssignment.user_id == User.id
        ).where(
            QuestionnaireAssignment.questionnaire_id == questionnaire_id
        ).order_by(
            # First: completed assignments
            QuestionnaireAssignment.status == 'completed',
            # Then: assignments with answers
            QuestionnaireAssignment.questions_answered.desc(),
            # Finally: most recent
            QuestionnaireAssignment.created_at.desc()
        )
        
        assignments_result = await db.execute(assignments_query)
        assignments_with_users = assignments_result.all()
        
        user_scores = []
        
        for assignment, user in assignments_with_users:
            # Get all answers for this assignment
            answers_query = select(ConversationAnswer, QuestionnaireQuestion).join(
                QuestionnaireQuestion,
                ConversationAnswer.question_id == QuestionnaireQuestion.id
            ).where(
                ConversationAnswer.assignment_id == assignment.id
            ).order_by(QuestionnaireQuestion.sequence_order)
            
            answers_result = await db.execute(answers_query)
            answers_with_questions = answers_result.all()
            
            # Calculate total score and aggregate emotion analysis scores
            total_score = 0
            max_possible_score = 0
            answer_details = []
            
            # Emotion analysis aggregation
            anxiety_scores = []
            emotional_regulation_scores = []
            wellbeing_scores = []
            high_risk_count = 0
            
            for answer, question in answers_with_questions:
                # Add to score if answer has a value
                if answer.extracted_answer_value is not None:
                    total_score += answer.extracted_answer_value
                
                # Max score depends on question type (assuming Likert 0-3)
                max_possible_score += 3
                
                # Collect emotion analysis scores if available
                if answer.anxiety_risk_score is not None:
                    anxiety_scores.append(float(answer.anxiety_risk_score))
                    if float(answer.anxiety_risk_score) >= 70:
                        high_risk_count += 1
                
                if answer.emotional_regulation_score is not None:
                    emotional_regulation_scores.append(float(answer.emotional_regulation_score))
                
                if answer.overall_wellbeing_score is not None:
                    wellbeing_scores.append(float(answer.overall_wellbeing_score))
                
                answer_details.append(QuestionAnswerDetail(
                    question_id=question.id,
                    question_text=question.question_text,
                    user_answer_text=answer.user_message or "(not answered)",
                    answer_value=answer.extracted_answer_value,
                    confidence=float(answer.extraction_confidence) if answer.extraction_confidence else None
                ))
            
            # Calculate percentage
            percentage = (total_score / max_possible_score * 100) if max_possible_score > 0 else 0
            
            # Calculate average emotion analysis scores from actual data
            avg_anxiety_risk = sum(anxiety_scores) / len(anxiety_scores) if anxiety_scores else 0
            avg_emotional_regulation = sum(emotional_regulation_scores) / len(emotional_regulation_scores) if emotional_regulation_scores else 0
            avg_overall_wellbeing = sum(wellbeing_scores) / len(wellbeing_scores) if wellbeing_scores else 0
            
            # Determine risk level based on anxiety and wellbeing
            if avg_anxiety_risk >= 70 or avg_overall_wellbeing < 30:
                risk_level = "high"
            elif avg_anxiety_risk >= 40 or avg_overall_wellbeing < 60:
                risk_level = "medium"
            else:
                risk_level = "low"
            
            user_scores.append({
                "user_id": user.id,
                "username": user.username,
                "assignment_id": assignment.id,
                "status": assignment.status,
                "total_score": total_score,
                "max_possible_score": max_possible_score,
                "percentage": round(percentage, 1),
                "questions_answered": assignment.questions_answered or 0,
                "total_questions": assignment.total_questions or 0,
                "response_count": len([a for a in answer_details if a.answer_value is not None]),
                "completed_at": assignment.completed_at.isoformat() if assignment.completed_at else None,
                "answers": [
                    {
                        "question_id": detail.question_id,
                        "question_text": detail.question_text,
                        "user_answer_text": detail.user_answer_text,
                        "answer_value": detail.answer_value,
                        "confidence": detail.confidence
                    }
                    for detail in answer_details
                ],
                "avg_anxiety_risk": round(avg_anxiety_risk, 1) if avg_anxiety_risk else None,
                "avg_emotional_regulation": round(avg_emotional_regulation, 1) if avg_emotional_regulation else None,
                "avg_overall_wellbeing": round(avg_overall_wellbeing, 1) if avg_overall_wellbeing else None,
                "risk_level": risk_level,
                "high_risk_responses": high_risk_count
            })
        
        # Return in format expected by frontend
        result = {
            "success": True,
            "questionnaire_id": questionnaire_id,
            "questionnaire_title": questionnaire.title,
            "scores": user_scores,
            "user_scores": user_scores,
            "total_users": len(user_scores)
        }
        
        logger.info(f"📊 Returning {len(user_scores)} user scores for questionnaire {questionnaire_id}")
        
        return JSONResponse(content=result)
        
    except HTTPException as he:
        logger.error(f"HTTP exception in get_questionnaire_user_scores: {he.detail}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting questionnaire scores: {e}", exc_info=True)
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception args: {e.args}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving questionnaire scores: {str(e)}"
        )


@router.get(
    "/{questionnaire_id}/users/{user_id}",
    response_model=UserScoreDetail,
    summary="Get specific user's score for a questionnaire",
    description="Get detailed score information for a specific user"
)
async def get_user_questionnaire_score(
    questionnaire_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> UserScoreDetail:
    """Get a specific user's score for a questionnaire"""
    
    # Check permissions - admin or the user themselves
    if current_user.role not in ["admin", "super_admin"] and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user's scores"
        )
    
    try:
        # Get assignment
        assignment_query = select(QuestionnaireAssignment, User).join(
            User, QuestionnaireAssignment.user_id == User.id
        ).where(
            and_(
                QuestionnaireAssignment.questionnaire_id == questionnaire_id,
                QuestionnaireAssignment.user_id == user_id
            )
        ).order_by(QuestionnaireAssignment.created_at.desc())
        
        assignment_result = await db.execute(assignment_query)
        result = assignment_result.first()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No assignment found for this user and questionnaire"
            )
        
        assignment, user = result
        
        # Get all answers
        answers_query = select(ConversationAnswer, QuestionnaireQuestion).join(
            QuestionnaireQuestion,
            ConversationAnswer.question_id == QuestionnaireQuestion.id
        ).where(
            ConversationAnswer.assignment_id == assignment.id
        ).order_by(QuestionnaireQuestion.sequence_order)
        
        answers_result = await db.execute(answers_query)
        answers_with_questions = answers_result.all()
        
        # Calculate score
        total_score = 0
        max_possible_score = 0
        answer_details = []
        
        for answer, question in answers_with_questions:
            if answer.extracted_answer_value is not None:
                total_score += answer.extracted_answer_value
            
            max_possible_score += 3
            
            answer_details.append(QuestionAnswerDetail(
                question_id=question.id,
                question_text=question.question_text,
                user_answer_text=answer.user_message or "(not answered)",
                answer_value=answer.extracted_answer_value,
                confidence=float(answer.extraction_confidence) if answer.extraction_confidence else None
            ))
        
        percentage = (total_score / max_possible_score * 100) if max_possible_score > 0 else 0
        
        return UserScoreDetail(
            user_id=user.id,
            username=user.username,
            assignment_id=assignment.id,
            status=assignment.status,
            total_score=total_score,
            max_possible_score=max_possible_score,
            percentage=round(percentage, 1),
            questions_answered=assignment.questions_answered or 0,
            total_questions=assignment.total_questions or 0,
            completed_at=assignment.completed_at,
            answers=answer_details
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user questionnaire score: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user score"
        )
