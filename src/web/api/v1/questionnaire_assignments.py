"""
Questionnaire Assignment API
Allows admins to assign questionnaires to users for Live2D chat sessions
"""

from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from src.database.connection import get_sync_db
from src.database.models_comprehensive import User
from src.database.models_questionnaire import (
    QuestionnaireAssignment,
    QuestionnaireBank,
    QuestionnaireQuestion,
    ConversationAnswer
)
from src.web.auth.dependencies import get_current_user
from src.core.logging import get_logger
from src.services.questionnaire_chat_service import get_questionnaire_chat_service

logger = get_logger(__name__)
router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class AssignQuestionnaireRequest(BaseModel):
    """Request to assign questionnaire to user"""
    questionnaire_id: int = Field(..., description="ID of questionnaire to assign")
    user_id: int = Field(..., description="ID of user to assign to")
    questions_per_conversation: int = Field(default=2, ge=1, le=10, description="Questions to ask per conversation")
    ask_naturally: bool = Field(default=True, description="Ask questions naturally during conversation")
    priority: int = Field(default=5, ge=1, le=10, description="Priority (1-10, higher = more important)")
    expires_in_days: Optional[int] = Field(default=30, ge=1, le=365, description="Days until assignment expires")
    admin_notes: Optional[str] = Field(default=None, max_length=1000)


class AssignmentResponse(BaseModel):
    """Response for assignment operations"""
    success: bool
    assignment_id: Optional[int] = None
    message: str
    assignment: Optional[dict] = None


class AssignmentProgressResponse(BaseModel):
    """Response for assignment progress"""
    assignment_id: int
    questionnaire_id: int
    questionnaire_title: str
    user_id: int
    status: str
    total_questions: int
    questions_answered: int
    questions_remaining: int
    progress_percentage: int
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    answers: Optional[List[dict]] = None


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/assign", response_model=AssignmentResponse)
async def assign_questionnaire(
    request: AssignQuestionnaireRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """
    Assign a questionnaire to a user for Live2D chat sessions
    
    Only admins and caregivers can assign questionnaires.
    SECURITY: Organization isolation enforced - can only assign to users in same organization.
    """
    try:
        # Check permissions
        if not current_user.is_admin and current_user.role not in ["doctor", "nurse", "social_worker"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins and healthcare staff can assign questionnaires"
            )
        
        # SECURITY: Verify user exists and belongs to same organization
        target_user = db.query(User).filter(User.id == request.user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {request.user_id} not found"
            )
        
        # SECURITY: Organization isolation - can only assign to users in same org
        if not current_user.is_super_admin:
            if target_user.organization_id != current_user.organization_id:
                # Return 404 instead of 403 to avoid revealing user existence
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User {request.user_id} not found"
                )
        
        # Verify questionnaire exists
        questionnaire = db.query(QuestionnaireBank).filter(
            QuestionnaireBank.id == request.questionnaire_id
        ).first()
        
        if not questionnaire:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Questionnaire {request.questionnaire_id} not found"
            )
        
        # Check if user already has an active assignment for this questionnaire
        existing = db.query(QuestionnaireAssignment).filter(
            and_(
                QuestionnaireAssignment.user_id == request.user_id,
                QuestionnaireAssignment.questionnaire_id == request.questionnaire_id,
                QuestionnaireAssignment.status == "active"
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has an active assignment for this questionnaire"
            )
        
        # Calculate expiration date
        expires_at = None
        if request.expires_in_days:
            expires_at = datetime.now() + timedelta(days=request.expires_in_days)
        
        # Create assignment
        assignment = QuestionnaireAssignment(
            questionnaire_id=request.questionnaire_id,
            user_id=request.user_id,
            assigned_by=current_user.id,
            status="active",
            total_questions=questionnaire.total_questions,
            questions_asked=0,
            questions_answered=0,
            current_question_index=0,
            assigned_at=datetime.now(),
            expires_at=expires_at,
            questions_per_conversation=request.questions_per_conversation,
            ask_naturally=request.ask_naturally,
            priority=request.priority,
            admin_notes=request.admin_notes
        )
        
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        
        logger.info(
            f"Questionnaire {questionnaire.id} assigned to user {request.user_id} "
            f"by {current_user.username} (assignment ID: {assignment.id})"
        )
        
        return AssignmentResponse(
            success=True,
            assignment_id=assignment.id,
            message=f"Questionnaire '{questionnaire.title}' assigned successfully",
            assignment={
                "id": assignment.id,
                "questionnaire_title": questionnaire.title,
                "user_id": request.user_id,
                "total_questions": questionnaire.total_questions,
                "expires_at": expires_at.isoformat() if expires_at else None
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning questionnaire: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign questionnaire: {str(e)}"
        )


@router.get("/user/{user_id}", response_model=List[AssignmentProgressResponse])
async def get_user_assignments(
    user_id: int,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """
    Get all questionnaire assignments for a user
    
    SECURITY: Organization isolation enforced - can only view users in same organization.
    
    Args:
        user_id: User ID
        status_filter: Filter by status (active, completed, paused, cancelled)
    """
    try:
        # SECURITY: Verify target user exists and check organization isolation
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # SECURITY: Check permissions - users can view their own, admins can view their org
        if current_user.id != user_id:
            if not current_user.is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own assignments"
                )
            
            # SECURITY: Organization isolation - admins can only view users in their org
            if not current_user.is_super_admin:
                if target_user.organization_id != current_user.organization_id:
                    # Return 404 instead of 403 to avoid revealing user existence
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found"
                    )
        
        # Build query
        query = db.query(QuestionnaireAssignment).filter(
            QuestionnaireAssignment.user_id == user_id
        )
        
        if status_filter:
            query = query.filter(QuestionnaireAssignment.status == status_filter)
        
        assignments = query.order_by(
            QuestionnaireAssignment.priority.desc(),
            QuestionnaireAssignment.assigned_at.desc()
        ).all()
        
        # Build response
        result = []
        for assignment in assignments:
            questionnaire = db.query(QuestionnaireBank).filter(
                QuestionnaireBank.id == assignment.questionnaire_id
            ).first()
            
            if not questionnaire:
                continue
            
            # Get progress
            answered_count = db.query(ConversationAnswer).filter(
                ConversationAnswer.assignment_id == assignment.id
            ).count()
            
            progress_pct = 0
            if assignment.total_questions > 0:
                progress_pct = int((answered_count / assignment.total_questions) * 100)
            
            result.append(AssignmentProgressResponse(
                assignment_id=assignment.id,
                questionnaire_id=questionnaire.id,
                questionnaire_title=questionnaire.title,
                user_id=user_id,
                status=assignment.status,
                total_questions=assignment.total_questions,
                questions_answered=answered_count,
                questions_remaining=assignment.total_questions - answered_count,
                progress_percentage=progress_pct,
                started_at=assignment.started_at.isoformat() if assignment.started_at else None,
                completed_at=assignment.completed_at.isoformat() if assignment.completed_at else None
            ))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user assignments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/assignment/{assignment_id}/progress", response_model=AssignmentProgressResponse)
async def get_assignment_progress(
    assignment_id: int,
    include_answers: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """
    Get detailed progress for a specific assignment
    
    SECURITY: Organization isolation enforced - can only view assignments in same organization.
    
    Args:
        assignment_id: Assignment ID
        include_answers: Include all answers in response
    """
    try:
        # Get assignment
        assignment = db.query(QuestionnaireAssignment).filter(
            QuestionnaireAssignment.id == assignment_id
        ).first()
        
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assignment {assignment_id} not found"
            )
        
        # SECURITY: Get target user and verify organization isolation
        target_user = db.query(User).filter(User.id == assignment.user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment user not found"
            )
        
        # SECURITY: Check permissions - users can view their own, admins can view their org
        if current_user.id != assignment.user_id:
            if not current_user.is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own assignments"
                )
            
            # SECURITY: Organization isolation - admins can only view assignments in their org
            if not current_user.is_super_admin:
                if target_user.organization_id != current_user.organization_id:
                    # Return 404 instead of 403 to avoid revealing assignment existence
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Assignment {assignment_id} not found"
                    )
        
        # Get questionnaire
        questionnaire = db.query(QuestionnaireBank).filter(
            QuestionnaireBank.id == assignment.questionnaire_id
        ).first()
        
        if not questionnaire:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questionnaire not found"
            )
        
        # Get answers
        answers = db.query(ConversationAnswer).filter(
            ConversationAnswer.assignment_id == assignment_id
        ).order_by(ConversationAnswer.answered_at).all()
        
        answered_count = len(answers)
        progress_pct = 0
        if assignment.total_questions > 0:
            progress_pct = int((answered_count / assignment.total_questions) * 100)
        
        # Build response
        response = AssignmentProgressResponse(
            assignment_id=assignment.id,
            questionnaire_id=questionnaire.id,
            questionnaire_title=questionnaire.title,
            user_id=assignment.user_id,
            status=assignment.status,
            total_questions=assignment.total_questions,
            questions_answered=answered_count,
            questions_remaining=assignment.total_questions - answered_count,
            progress_percentage=progress_pct,
            started_at=assignment.started_at.isoformat() if assignment.started_at else None,
            completed_at=assignment.completed_at.isoformat() if assignment.completed_at else None
        )
        
        # Include answers if requested
        if include_answers:
            response.answers = [
                {
                    "question_id": answer.question_id,
                    "question_text": answer.question_asked,
                    "user_message": answer.user_message,
                    "dominant_emotion": answer.dominant_emotion,
                    "emotion_intensity": float(answer.emotion_intensity) if answer.emotion_intensity else None,
                    "anxiety_risk_score": float(answer.anxiety_risk_score) if answer.anxiety_risk_score else None,
                    "overall_wellbeing_score": float(answer.overall_wellbeing_score) if answer.overall_wellbeing_score else None,
                    "analysis_summary": answer.analysis_summary,
                    "answered_at": answer.answered_at.isoformat()
                }
                for answer in answers
            ]
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting assignment progress: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/assignment/{assignment_id}/status")
async def update_assignment_status(
    assignment_id: int,
    new_status: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """
    Update assignment status (pause, resume, cancel)
    
    Args:
        assignment_id: Assignment ID
        new_status: New status (active, paused, cancelled)
    """
    try:
        # Validate status
        valid_statuses = ["active", "paused", "cancelled"]
        if new_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        # Get assignment
        assignment = db.query(QuestionnaireAssignment).filter(
            QuestionnaireAssignment.id == assignment_id
        ).first()
        
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assignment {assignment_id} not found"
            )
        
        # Check permissions
        if not current_user.is_admin and current_user.id != assignment.assigned_by:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins or the assigner can update assignment status"
            )
        
        # Update status
        old_status = assignment.status
        assignment.status = new_status
        
        db.commit()
        
        logger.info(
            f"Assignment {assignment_id} status updated from {old_status} to {new_status} "
            f"by {current_user.username}"
        )
        
        return {
            "success": True,
            "message": f"Assignment status updated to {new_status}",
            "assignment_id": assignment_id,
            "old_status": old_status,
            "new_status": new_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating assignment status: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/assignment/{assignment_id}")
async def delete_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """
    Delete a questionnaire assignment
    
    Only admins or the assigner can delete assignments.
    """
    try:
        # Get assignment
        assignment = db.query(QuestionnaireAssignment).filter(
            QuestionnaireAssignment.id == assignment_id
        ).first()
        
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assignment {assignment_id} not found"
            )
        
        # Check permissions
        if not current_user.is_admin and current_user.id != assignment.assigned_by:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins or the assigner can delete assignments"
            )
        
        # Delete assignment (cascade will delete answers)
        db.delete(assignment)
        db.commit()
        
        logger.info(f"Assignment {assignment_id} deleted by {current_user.username}")
        
        return {
            "success": True,
            "message": "Assignment deleted successfully",
            "assignment_id": assignment_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting assignment: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
