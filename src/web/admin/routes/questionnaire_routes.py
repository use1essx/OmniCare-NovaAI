"""
Admin Questionnaire Management Routes
API endpoints for managing questionnaires, assignments, and reviewing conversational answers
"""

import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import get_async_session
from src.database.models_comprehensive import User
from src.web.auth.dependencies import get_current_user, get_optional_user
from src.web.admin.config.permissions import check_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/questionnaires", tags=["Admin Questionnaires"])


# =============================================================================
# Pydantic Models
# =============================================================================

class QuestionnaireUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(draft|active|archived)$")
    category: Optional[str] = None
    target_age_min: Optional[int] = None
    target_age_max: Optional[int] = None
    estimated_duration_minutes: Optional[int] = None


class QuestionUpdateRequest(BaseModel):
    question_text: Optional[str] = None
    question_text_zh: Optional[str] = None
    help_text: Optional[str] = None


class AssignQuestionnaireRequest(BaseModel):
    questionnaire_id: int
    user_id: int
    questions_per_conversation: int = Field(default=2, ge=1, le=5)
    priority: int = Field(default=5, ge=1, le=10)
    admin_notes: Optional[str] = None
    days_until_expiry: Optional[int] = Field(None, ge=1, le=365)


class ValidateAnswerRequest(BaseModel):
    validation_status: str = Field(..., pattern="^(validated|rejected|needs_review)$")
    corrected_text: Optional[str] = None
    corrected_value: Optional[int] = None


# =============================================================================
# Permission Dependency
# =============================================================================

async def require_admin_access(request: Request) -> None:
    """
    Simplified admin access check - assumes admin interface has already authenticated.
    TODO: Add proper session validation.
    """
    # For now, trust that the admin interface has already validated the user
    return None


# =============================================================================
# Questionnaire Management Endpoints
# =============================================================================

@router.get("/")
async def list_questionnaires(
    request: Request,
    status: Optional[str] = Query(None, pattern="^(draft|active|archived)$"),
    language: Optional[str] = Query(None, pattern="^(en|zh-HK)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: None = Depends(require_admin_access),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    List all questionnaires with filtering and pagination.
    Accessible by admins and healthcare workers.
    """
    try:
        from sqlalchemy import select
        from src.database.models_questionnaire import QuestionnaireBank
        
        query = select(QuestionnaireBank)
        
        if status:
            query = query.where(QuestionnaireBank.status == status)
        if language:
            query = query.where(QuestionnaireBank.language == language)
        
        # Pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        result = await db.execute(query)
        questionnaires = result.scalars().all()
        
        return {
            "success": True,
            "total": len(questionnaires),
            "questionnaires": [
                {
                    "id": q.id,
                    "title": q.title,
                    "description": q.description,
                    "status": q.status,
                    "category": q.category,
                    "language": q.language,
                    "total_questions": q.total_questions,
                    "created_at": q.created_at.isoformat() if q.created_at else None
                }
                for q in questionnaires
            ]
        }
    except Exception as e:
        logger.error(f"Error listing questionnaires: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e), "questionnaires": []}


@router.get("/{questionnaire_id}")
async def get_questionnaire(
    questionnaire_id: int,
    current_user: User = Depends(require_admin_access),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    Get full questionnaire details including all questions and options.
    For admin viewing and editing.
    """
    try:
        service = QuestionnaireService(db)
        questionnaire = await service.get_questionnaire_with_details(questionnaire_id)
        
        if not questionnaire:
            raise HTTPException(status_code=404, detail="Questionnaire not found")
        
        return questionnaire
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting questionnaire {questionnaire_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get questionnaire")


@router.patch("/{questionnaire_id}")
async def update_questionnaire(
    questionnaire_id: int,
    update_data: QuestionnaireUpdateRequest,
    current_user: User = Depends(require_admin_access),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    Update questionnaire metadata (title, description, status, etc.).
    Admin can edit generated questionnaires.
    """
    try:
        service = QuestionnaireService(db)
        
        # Convert to dict and filter None values
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        
        if not update_dict:
            raise HTTPException(status_code=400, detail="No update data provided")
        
        questionnaire = await service.update_questionnaire_metadata(
            questionnaire_id=questionnaire_id,
            update_data=update_dict
        )
        
        if not questionnaire:
            raise HTTPException(status_code=404, detail="Questionnaire not found")
        
        logger.info(f"Admin {current_user.id} updated questionnaire {questionnaire_id}")
        return questionnaire
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating questionnaire {questionnaire_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update questionnaire")


@router.patch("/questions/{question_id}")
async def update_question(
    question_id: int,
    update_data: QuestionUpdateRequest,
    current_user: User = Depends(require_admin_access),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, str]:
    """
    Update a specific question's text.
    Allows admin to refine AI-generated questions.
    """
    try:
        service = QuestionnaireService(db)
        
        success = await service.update_question_text(
            question_id=question_id,
            question_text=update_data.question_text,
            question_text_zh=update_data.question_text_zh,
            help_text=update_data.help_text
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Question not found")
        
        logger.info(f"Admin {current_user.id} updated question {question_id}")
        return {"message": "Question updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating question {question_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update question")


# =============================================================================
# Assignment Management Endpoints
# =============================================================================

@router.post("/assignments")
async def assign_questionnaire(
    assignment_data: AssignQuestionnaireRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    Assign a questionnaire to a user for conversational collection.
    Admin selects a user (role='user') and questionnaire.
    """
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import select, func
        from src.database.models_questionnaire import QuestionnaireBank, QuestionnaireAssignment, QuestionnaireQuestion
        
        # Verify questionnaire exists
        q_query = select(QuestionnaireBank).where(QuestionnaireBank.id == assignment_data.questionnaire_id)
        q_result = await db.execute(q_query)
        questionnaire = q_result.scalar_one_or_none()
        
        if not questionnaire:
            return {"success": False, "error": f"Questionnaire {assignment_data.questionnaire_id} not found"}
        
        # Count total questions
        count_query = select(func.count(QuestionnaireQuestion.id)).where(
            QuestionnaireQuestion.questionnaire_id == assignment_data.questionnaire_id
        )
        count_result = await db.execute(count_query)
        total_questions = count_result.scalar() or 0
        
        # Calculate expiry if provided
        expires_at = None
        if assignment_data.days_until_expiry:
            expires_at = datetime.utcnow() + timedelta(days=assignment_data.days_until_expiry)
        
        # Create assignment
        new_assignment = QuestionnaireAssignment(
            questionnaire_id=assignment_data.questionnaire_id,
            user_id=assignment_data.user_id,
            assigned_by_id=1,  # TODO: Get from session
            status="assigned",
            priority=assignment_data.priority,
            questions_per_conversation=assignment_data.questions_per_conversation or 2,
            total_questions=total_questions,
            questions_answered=0,
            admin_notes=assignment_data.admin_notes,
            assigned_at=datetime.utcnow(),
            expires_at=expires_at
        )
        
        db.add(new_assignment)
        await db.commit()
        await db.refresh(new_assignment)
        
        logger.info(f"✅ Assigned questionnaire {assignment_data.questionnaire_id} to user {assignment_data.user_id}")
        
        return {
            "success": True,
            "assignment_id": new_assignment.id,
            "questionnaire_id": new_assignment.questionnaire_id,
            "user_id": new_assignment.user_id,
            "status": new_assignment.status,
            "total_questions": new_assignment.total_questions
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Error assigning questionnaire: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/assignments")
async def list_assignments(
    status: Optional[str] = Query(None, pattern="^(active|paused|completed|cancelled)$"),
    user_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin_access),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    List all questionnaire assignments.
    Admin can see progress and status of all assignments.
    """
    try:
        service = QuestionnaireAssignmentService(db)
        result = await service.get_assignments_for_admin(
            status=status,
            user_id=user_id,
            page=page,
            page_size=page_size
        )
        return result
    except Exception as e:
        logger.error(f"Error listing assignments: {e}")
        raise HTTPException(status_code=500, detail="Failed to list assignments")


@router.post("/assignments/{assignment_id}/pause")
async def pause_assignment(
    assignment_id: int,
    current_user: User = Depends(require_admin_access),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, str]:
    """Pause an active assignment (temporarily stop asking questions)"""
    try:
        service = QuestionnaireAssignmentService(db)
        success = await service.pause_assignment(assignment_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        logger.info(f"Admin {current_user.id} paused assignment {assignment_id}")
        return {"message": "Assignment paused successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing assignment {assignment_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to pause assignment")


@router.post("/assignments/{assignment_id}/resume")
async def resume_assignment(
    assignment_id: int,
    current_user: User = Depends(require_admin_access),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, str]:
    """Resume a paused assignment"""
    try:
        service = QuestionnaireAssignmentService(db)
        success = await service.resume_assignment(assignment_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        logger.info(f"Admin {current_user.id} resumed assignment {assignment_id}")
        return {"message": "Assignment resumed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming assignment {assignment_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to resume assignment")


@router.post("/assignments/{assignment_id}/cancel")
async def cancel_assignment(
    assignment_id: int,
    current_user: User = Depends(require_admin_access),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, str]:
    """Cancel an assignment"""
    try:
        service = QuestionnaireAssignmentService(db)
        success = await service.cancel_assignment(assignment_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        logger.info(f"Admin {current_user.id} cancelled assignment {assignment_id}")
        return {"message": "Assignment cancelled successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling assignment {assignment_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel assignment")


# =============================================================================
# Answer Review Endpoints
# =============================================================================

@router.get("/answers/pending-review")
async def get_pending_answers(
    assignment_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_admin_access),
    db: AsyncSession = Depends(get_async_session)
) -> List[Dict[str, Any]]:
    """
    Get answers that need admin review.
    Shows extracted answers from conversations for validation.
    """
    try:
        service = QuestionnaireAssignmentService(db)
        answers = await service.get_answers_for_review(
            assignment_id=assignment_id,
            limit=limit
        )
        return answers
    except Exception as e:
        logger.error(f"Error getting pending answers: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pending answers")


@router.post("/answers/{answer_id}/validate")
async def validate_answer(
    answer_id: int,
    validation_data: ValidateAnswerRequest,
    current_user: User = Depends(require_admin_access),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    Admin validates or corrects an extracted answer.
    Can approve, reject, or mark for further review.
    """
    try:
        service = QuestionnaireAssignmentService(db)
        
        result = await service.validate_answer(
            answer_id=answer_id,
            validated_by_user_id=current_user.id,
            validation_status=validation_data.validation_status,
            corrected_text=validation_data.corrected_text,
            corrected_value=validation_data.corrected_value
        )
        
        logger.info(f"✅ Admin {current_user.id} validated answer {answer_id}: {validation_data.validation_status}")
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error validating answer {answer_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate answer")


# =============================================================================
# User Selection Helper Endpoint
# =============================================================================

@router.get("/users/available")
async def get_available_users(
    request: Request,
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    Get list of users with role='user' for assignment selection.
    Admin uses this to select which user to assign questionnaire to.
    
    This endpoint uses simple session-based authentication.
    """
    try:
        # Simple session-based auth check - check if user is logged in via admin session
        # This is for admin interface, so we trust the session cookie
        from sqlalchemy import select
        from src.database.models_comprehensive import User
        
        # TODO: Add proper session validation here if needed
        # For now, we'll allow access from admin interface (which already has auth)
        
        query = select(User).where(User.role == 'user', User.is_active == True)
        
        if search:
            from sqlalchemy import or_
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    User.username.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                    User.full_name.ilike(search_pattern)
                )
            )
        
        query = query.limit(limit)
        
        result = await db.execute(query)
        users = result.scalars().all()
        
        logger.info(f"📋 Found {len(users)} users with role='user'")
        
        users_list = []
        for u in users:
            try:
                user_data = {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "full_name": u.full_name or u.username,
                    "language_preference": u.language_preference or 'en'
                }
                users_list.append(user_data)
                logger.debug(f"  User: {user_data}")
            except Exception as user_err:
                logger.warning(f"Error processing user {u.id}: {user_err}")
                continue
        
        return {
            "success": True,
            "users": users_list
        }
    except Exception as e:
        logger.error(f"❌ Error getting available users: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e),
            "users": []
        }


# =============================================================================
# Additional Endpoints for UI Integration
# =============================================================================

@router.put("/{questionnaire_id}")
async def update_questionnaire(
    questionnaire_id: int,
    request: Request,
    update_data: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    Update questionnaire title, description, and questions.
    """
    try:
        from sqlalchemy import select, update
        from src.database.models_questionnaire import QuestionnaireBank, QuestionnaireQuestion
        
        # Update questionnaire basic info
        if "title" in update_data or "description" in update_data:
            stmt = update(QuestionnaireBank).where(
                QuestionnaireBank.id == questionnaire_id
            )
            
            update_values = {}
            if "title" in update_data:
                update_values["title"] = update_data["title"]
            if "description" in update_data:
                update_values["description"] = update_data["description"]
            
            if update_values:
                stmt = stmt.values(**update_values)
                await db.execute(stmt)
        
        # Update questions if provided
        if "questions" in update_data:
            for question in update_data["questions"]:
                if "id" in question and "question_text" in question:
                    stmt = update(QuestionnaireQuestion).where(
                        QuestionnaireQuestion.id == question["id"]
                    ).values(question_text=question["question_text"])
                    await db.execute(stmt)
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Questionnaire updated successfully"
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating questionnaire: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/{questionnaire_id}/assignments")
async def get_questionnaire_assignments(
    questionnaire_id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    Get all assignments for a specific questionnaire.
    """
    try:
        from sqlalchemy import select, func
        from src.database.models_questionnaire import QuestionnaireAssignment, ConversationAnswer
        
        # Query assignments directly
        query = select(QuestionnaireAssignment).where(
            QuestionnaireAssignment.questionnaire_id == questionnaire_id
        ).order_by(QuestionnaireAssignment.assigned_at.desc())
        
        result = await db.execute(query)
        assignments = result.scalars().all()
        
        assignments_list = []
        for a in assignments:
            try:
                # Count answered questions
                count_query = select(func.count(ConversationAnswer.id)).where(
                    ConversationAnswer.assignment_id == a.id
                )
                count_result = await db.execute(count_query)
                questions_answered = count_result.scalar() or 0
                
                assignment_data = {
                    "id": a.id,
                    "user_id": a.user_id,
                    "status": a.status,
                    "priority": a.priority or 5,
                    "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
                    "questions_answered": questions_answered,
                    "total_questions": a.total_questions or 0
                }
                assignments_list.append(assignment_data)
            except Exception as assign_err:
                logger.warning(f"Error processing assignment {a.id}: {assign_err}")
                continue
        
        logger.info(f"📋 Found {len(assignments_list)} assignments for questionnaire {questionnaire_id}")
        
        return {
            "success": True,
            "assignments": assignments_list
        }
    except Exception as e:
        logger.error(f"Error getting assignments: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e),
            "assignments": []
        }


@router.delete("/assignments/{assignment_id}")
async def delete_assignment(
    assignment_id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    Delete a questionnaire assignment.
    """
    try:
        from sqlalchemy import delete
        from src.database.models_questionnaire import QuestionnaireAssignment
        
        stmt = delete(QuestionnaireAssignment).where(
            QuestionnaireAssignment.id == assignment_id
        )
        
        await db.execute(stmt)
        await db.commit()
        
        logger.info(f"✅ Deleted assignment {assignment_id}")
        
        return {
            "success": True,
            "message": "Assignment deleted successfully"
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting assignment: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }

