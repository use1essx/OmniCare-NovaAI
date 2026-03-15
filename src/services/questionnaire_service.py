"""
Questionnaire Service
Business logic for questionnaire management, assignments, and answer extraction
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import json

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.repositories.questionnaire_repository import (
    QuestionnaireRepository,
    QuestionnaireAssignmentRepository
)
from src.database.models_questionnaire import (
    QuestionnaireBank,
    QuestionnaireQuestion,
    QuestionnaireAssignment,
    ConversationAnswer
)
from src.database.models_comprehensive import User

logger = logging.getLogger(__name__)


class QuestionnaireService:
    """Service for questionnaire management operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repo = QuestionnaireRepository(db)
    
    async def get_questionnaire_with_details(self, questionnaire_id: int) -> Optional[Dict[str, Any]]:
        """Get questionnaire with all details formatted for admin UI"""
        questionnaire = await self.repo.get_questionnaire_by_id(questionnaire_id)
        if not questionnaire:
            return None
        
        return {
            "id": questionnaire.id,
            "title": questionnaire.title,
            "description": questionnaire.description,
            "status": questionnaire.status,
            "language": questionnaire.language,
            "category": questionnaire.category,
            "total_questions": questionnaire.total_questions,
            "estimated_duration_minutes": questionnaire.estimated_duration_minutes,
            "source": questionnaire.source,
            "target_age_min": questionnaire.target_age_min,
            "target_age_max": questionnaire.target_age_max,
            "created_at": questionnaire.created_at.isoformat() if questionnaire.created_at else None,
            "questions": [
                {
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
                        for opt in sorted(q.options, key=lambda x: x.sequence_order)
                    ] if q.options else []
                }
                for q in sorted(questionnaire.questions, key=lambda x: x.sequence_order)
            ]
        }
    
    async def list_questionnaires_for_admin(
        self,
        status: Optional[str] = None,
        language: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """List questionnaires with pagination"""
        offset = (page - 1) * page_size
        questionnaires = await self.repo.list_questionnaires(
            status=status,
            language=language,
            limit=page_size,
            offset=offset
        )
        
        return {
            "questionnaires": [
                {
                    "id": q.id,
                    "title": q.title,
                    "description": q.description,
                    "status": q.status,
                    "language": q.language,
                    "category": q.category,
                    "total_questions": q.total_questions,
                    "source": q.source,
                    "created_at": q.created_at.isoformat() if q.created_at else None
                }
                for q in questionnaires
            ],
            "page": page,
            "page_size": page_size,
            "total": len(questionnaires)
        }
    
    async def update_questionnaire_metadata(
        self,
        questionnaire_id: int,
        update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update questionnaire metadata (title, description, status, etc.)"""
        
        # Validate allowed fields
        allowed_fields = {
            'title', 'description', 'status', 'category', 
            'target_age_min', 'target_age_max', 'estimated_duration_minutes'
        }
        filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}
        
        questionnaire = await self.repo.update_questionnaire(questionnaire_id, filtered_data)
        if not questionnaire:
            return None
        
        logger.info(f"Updated questionnaire {questionnaire_id}: {filtered_data}")
        return await self.get_questionnaire_with_details(questionnaire_id)
    
    async def update_question_text(
        self,
        question_id: int,
        question_text: Optional[str] = None,
        question_text_zh: Optional[str] = None,
        help_text: Optional[str] = None
    ) -> bool:
        """Update question text (for admin editing)"""
        update_data = {}
        if question_text is not None:
            update_data['question_text'] = question_text
        if question_text_zh is not None:
            update_data['question_text_zh'] = question_text_zh
        if help_text is not None:
            update_data['help_text'] = help_text
        
        question = await self.repo.update_question(question_id, update_data)
        if question:
            logger.info(f"Updated question {question_id}")
            return True
        return False


class QuestionnaireAssignmentService:
    """Service for questionnaire assignments and conversational collection"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repo = QuestionnaireAssignmentRepository(db)
        self.questionnaire_repo = QuestionnaireRepository(db)
    
    async def assign_questionnaire_to_user(
        self,
        questionnaire_id: int,
        user_id: int,
        assigned_by_user_id: int,
        questions_per_conversation: int = 2,
        priority: int = 5,
        admin_notes: Optional[str] = None,
        days_until_expiry: Optional[int] = None
    ) -> Dict[str, Any]:
        """Admin assigns a questionnaire to a user for conversational collection"""
        
        # Validate questionnaire exists
        questionnaire = await self.questionnaire_repo.get_questionnaire_by_id(questionnaire_id)
        if not questionnaire:
            raise ValueError(f"Questionnaire {questionnaire_id} not found")
        
        # Validate user exists (would need UserRepository)
        # For now, assume valid
        
        # Calculate expiry
        expires_at = None
        if days_until_expiry:
            expires_at = datetime.utcnow() + timedelta(days=days_until_expiry)
        
        assignment = await self.repo.create_assignment(
            questionnaire_id=questionnaire_id,
            user_id=user_id,
            assigned_by=assigned_by_user_id,
            questions_per_conversation=questions_per_conversation,
            priority=priority,
            admin_notes=admin_notes,
            expires_at=expires_at
        )
        
        logger.info(f"✅ Assigned questionnaire {questionnaire_id} to user {user_id} by admin {assigned_by_user_id}")
        
        return {
            "assignment_id": assignment.id,
            "questionnaire_id": assignment.questionnaire_id,
            "user_id": assignment.user_id,
            "status": assignment.status,
            "total_questions": assignment.total_questions,
            "questions_per_conversation": assignment.questions_per_conversation,
            "priority": assignment.priority,
            "assigned_at": assignment.assigned_at.isoformat(),
            "expires_at": assignment.expires_at.isoformat() if assignment.expires_at else None
        }
    
    async def get_active_questionnaires_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all active questionnaire assignments for a user (for chat integration)"""
        assignments = await self.repo.get_active_assignments_for_user(user_id)
        
        return [
            {
                "assignment_id": a.id,
                "questionnaire_id": a.questionnaire_id,
                "questionnaire_title": a.questionnaire.title,
                "total_questions": a.total_questions,
                "questions_answered": a.questions_answered,
                "progress_percentage": int((a.questions_answered / a.total_questions) * 100) if a.total_questions > 0 else 0,
                "priority": a.priority,
                "questions_per_conversation": a.questions_per_conversation
            }
            for a in assignments
        ]
    
    async def get_next_questions_for_conversation(
        self,
        user_id: int
    ) -> Optional[Tuple[int, List[QuestionnaireQuestion]]]:
        """
        Get the next questions to ask in conversation.
        Returns (assignment_id, questions) or None if no active assignments.
        """
        assignments = await self.repo.get_active_assignments_for_user(user_id)
        
        if not assignments:
            return None
        
        # Get highest priority assignment
        assignment = assignments[0]
        
        questions = await self.repo.get_next_questions_to_ask(
            assignment.id,
            count=assignment.questions_per_conversation
        )
        
        if not questions:
            # No more questions - mark as completed
            await self.repo.update_assignment_status(assignment.id, 'completed')
            return None
        
        return (assignment.id, questions)
    
    async def record_answer_from_conversation(
        self,
        assignment_id: int,
        question_id: int,
        question_asked: str,
        user_message: str,
        extracted_answer: Dict[str, Any],
        conversation_context: Optional[List[Dict]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record an answer extracted from natural conversation"""
        
        answer = await self.repo.record_conversation_answer(
            assignment_id=assignment_id,
            question_id=question_id,
            question_asked=question_asked,
            user_message=user_message,
            extracted_answer_text=extracted_answer.get('text'),
            extracted_answer_value=extracted_answer.get('value'),
            extraction_confidence=extracted_answer.get('confidence'),
            extraction_method=extracted_answer.get('method', 'ai_parse'),
            extraction_notes=extracted_answer.get('notes'),
            conversation_context={'messages': conversation_context} if conversation_context else None,
            session_id=session_id
        )
        
        return {
            "answer_id": answer.id,
            "assignment_id": answer.assignment_id,
            "question_id": answer.question_id,
            "extracted_answer_text": answer.extracted_answer_text,
            "extraction_confidence": float(answer.extraction_confidence) if answer.extraction_confidence else None,
            "needs_clarification": answer.needs_clarification,
            "validation_status": answer.validation_status
        }
    
    async def get_assignments_for_admin(
        self,
        status: Optional[str] = None,
        user_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """List all assignments for admin dashboard"""
        offset = (page - 1) * page_size
        assignments = await self.repo.list_assignments_for_admin(
            status=status,
            user_id=user_id,
            limit=page_size,
            offset=offset
        )
        
        return {
            "assignments": [
                {
                    "id": a.id,
                    "questionnaire_id": a.questionnaire_id,
                    "questionnaire_title": a.questionnaire.title,
                    "user_id": a.user_id,
                    "status": a.status,
                    "total_questions": a.total_questions,
                    "questions_answered": a.questions_answered,
                    "progress_percentage": int((a.questions_answered / a.total_questions) * 100) if a.total_questions > 0 else 0,
                    "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
                    "started_at": a.started_at.isoformat() if a.started_at else None,
                    "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                    "admin_notes": a.admin_notes
                }
                for a in assignments
            ],
            "page": page,
            "page_size": page_size
        }
    
    async def get_answers_for_review(
        self,
        assignment_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get answers that need admin review"""
        answers = await self.repo.get_pending_answers_for_review(
            assignment_id=assignment_id,
            limit=limit
        )
        
        return [
            {
                "id": ans.id,
                "assignment_id": ans.assignment_id,
                "question_id": ans.question_id,
                "question_text": ans.question.question_text,
                "question_asked": ans.question_asked,
                "user_message": ans.user_message,
                "extracted_answer_text": ans.extracted_answer_text,
                "extracted_answer_value": ans.extracted_answer_value,
                "extraction_confidence": float(ans.extraction_confidence) if ans.extraction_confidence else None,
                "extraction_notes": ans.extraction_notes,
                "needs_clarification": ans.needs_clarification,
                "validation_status": ans.validation_status,
                "answered_at": ans.answered_at.isoformat() if ans.answered_at else None,
                "conversation_context": ans.conversation_context
            }
            for ans in answers
        ]
    
    async def validate_answer(
        self,
        answer_id: int,
        validated_by_user_id: int,
        validation_status: str,
        corrected_text: Optional[str] = None,
        corrected_value: Optional[int] = None
    ) -> Dict[str, Any]:
        """Admin validates or corrects an extracted answer"""
        
        answer = await self.repo.validate_answer(
            answer_id=answer_id,
            validated_by=validated_by_user_id,
            validation_status=validation_status,
            corrected_text=corrected_text,
            corrected_value=corrected_value
        )
        
        if not answer:
            raise ValueError(f"Answer {answer_id} not found")
        
        logger.info(f"✅ Answer {answer_id} validated by admin {validated_by_user_id}: {validation_status}")
        
        return {
            "answer_id": answer.id,
            "validation_status": answer.validation_status,
            "validated_at": answer.validated_at.isoformat() if answer.validated_at else None,
            "extracted_answer_text": answer.extracted_answer_text,
            "extracted_answer_value": answer.extracted_answer_value
        }
    
    async def pause_assignment(self, assignment_id: int) -> bool:
        """Pause an active assignment"""
        assignment = await self.repo.update_assignment_status(assignment_id, 'paused')
        return assignment is not None
    
    async def resume_assignment(self, assignment_id: int) -> bool:
        """Resume a paused assignment"""
        assignment = await self.repo.update_assignment_status(assignment_id, 'active')
        return assignment is not None
    
    async def cancel_assignment(self, assignment_id: int) -> bool:
        """Cancel an assignment"""
        assignment = await self.repo.update_assignment_status(assignment_id, 'cancelled')
        return assignment is not None
    
    async def get_assignments_by_questionnaire(self, questionnaire_id: int) -> List[QuestionnaireAssignment]:
        """Get all assignments for a specific questionnaire"""
        from sqlalchemy import select
        from src.database.models_questionnaire import QuestionnaireAssignment
        
        query = select(QuestionnaireAssignment).where(
            QuestionnaireAssignment.questionnaire_id == questionnaire_id
        ).order_by(QuestionnaireAssignment.assigned_at.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def count_answered_questions(self, assignment_id: int) -> int:
        """Count how many questions have been answered for an assignment"""
        from sqlalchemy import select, func
        from src.database.models_questionnaire import ConversationAnswer
        
        query = select(func.count(ConversationAnswer.id)).where(
            ConversationAnswer.assignment_id == assignment_id
        )
        
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def count_total_questions(self, questionnaire_id: int) -> int:
        """Count total questions in a questionnaire"""
        from sqlalchemy import select, func
        from src.database.models_questionnaire import QuestionnaireQuestion
        
        query = select(func.count(QuestionnaireQuestion.id)).where(
            QuestionnaireQuestion.questionnaire_id == questionnaire_id
        )
        
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def delete_assignment(self, assignment_id: int) -> bool:
        """Delete an assignment"""
        from sqlalchemy import delete
        from src.database.models_questionnaire import QuestionnaireAssignment
        
        query = delete(QuestionnaireAssignment).where(
            QuestionnaireAssignment.id == assignment_id
        )
        
        await self.db.execute(query)
        await self.db.commit()
        return True

