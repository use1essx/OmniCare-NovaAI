"""
Questionnaire Repository
Data access layer for questionnaire management, assignments, and conversational answers
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models_questionnaire import (
    QuestionnaireBank,
    QuestionnaireQuestion,
    QuestionOption,
    QuestionnaireAssignment,
    ConversationAnswer,
    QuestionnaireResponse,
    QuestionAnswer
)
from src.database.models_comprehensive import User

logger = logging.getLogger(__name__)


class QuestionnaireRepository:
    """Repository for questionnaire CRUD operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def get_questionnaire_by_id(self, questionnaire_id: int) -> Optional[QuestionnaireBank]:
        """Get questionnaire with all questions and options"""
        if isinstance(self.db, AsyncSession):
            result = await self.db.execute(
                select(QuestionnaireBank)
                .options(
                    joinedload(QuestionnaireBank.questions).joinedload(QuestionnaireQuestion.options)
                )
                .where(QuestionnaireBank.id == questionnaire_id)
            )
            return result.scalar_one_or_none()
        else:
            return self.db.query(QuestionnaireBank).options(
                joinedload(QuestionnaireBank.questions).joinedload(QuestionnaireQuestion.options)
            ).filter(QuestionnaireBank.id == questionnaire_id).first()
    
    async def list_questionnaires(
        self,
        status: Optional[str] = None,
        language: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[QuestionnaireBank]:
        """List questionnaires with filtering"""
        query = select(QuestionnaireBank)
        
        if status:
            query = query.where(QuestionnaireBank.status == status)
        if language:
            query = query.where(QuestionnaireBank.language == language)
        
        query = query.order_by(desc(QuestionnaireBank.created_at)).limit(limit).offset(offset)
        
        if isinstance(self.db, AsyncSession):
            result = await self.db.execute(query)
            return result.scalars().all()
        else:
            return self.db.execute(query).scalars().all()
    
    async def update_questionnaire(
        self,
        questionnaire_id: int,
        update_data: Dict[str, Any]
    ) -> Optional[QuestionnaireBank]:
        """Update questionnaire metadata"""
        questionnaire = await self.get_questionnaire_by_id(questionnaire_id)
        if not questionnaire:
            return None
        
        for key, value in update_data.items():
            if hasattr(questionnaire, key):
                setattr(questionnaire, key, value)
        
        if isinstance(self.db, AsyncSession):
            await self.db.commit()
            await self.db.refresh(questionnaire)
        else:
            self.db.commit()
            self.db.refresh(questionnaire)
        
        return questionnaire
    
    async def update_question(
        self,
        question_id: int,
        update_data: Dict[str, Any]
    ) -> Optional[QuestionnaireQuestion]:
        """Update a specific question"""
        if isinstance(self.db, AsyncSession):
            result = await self.db.execute(
                select(QuestionnaireQuestion).where(QuestionnaireQuestion.id == question_id)
            )
            question = result.scalar_one_or_none()
        else:
            question = self.db.query(QuestionnaireQuestion).filter(
                QuestionnaireQuestion.id == question_id
            ).first()
        
        if not question:
            return None
        
        for key, value in update_data.items():
            if hasattr(question, key):
                setattr(question, key, value)
        
        if isinstance(self.db, AsyncSession):
            await self.db.commit()
            await self.db.refresh(question)
        else:
            self.db.commit()
            self.db.refresh(question)
        
        return question


class QuestionnaireAssignmentRepository:
    """Repository for questionnaire assignments and conversational answers"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_assignment(
        self,
        questionnaire_id: int,
        user_id: int,
        assigned_by: int,
        questions_per_conversation: int = 2,
        priority: int = 5,
        admin_notes: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> QuestionnaireAssignment:
        """Create a new questionnaire assignment"""
        
        # Get total questions count
        if isinstance(self.db, AsyncSession):
            result = await self.db.execute(
                select(func.count(QuestionnaireQuestion.id))
                .where(QuestionnaireQuestion.questionnaire_id == questionnaire_id)
            )
            total_questions = result.scalar()
        else:
            total_questions = self.db.query(func.count(QuestionnaireQuestion.id)).filter(
                QuestionnaireQuestion.questionnaire_id == questionnaire_id
            ).scalar()
        
        assignment = QuestionnaireAssignment(
            questionnaire_id=questionnaire_id,
            user_id=user_id,
            assigned_by=assigned_by,
            total_questions=total_questions,
            questions_per_conversation=questions_per_conversation,
            priority=priority,
            admin_notes=admin_notes,
            expires_at=expires_at,
            status='active'
        )
        
        self.db.add(assignment)
        
        if isinstance(self.db, AsyncSession):
            await self.db.commit()
            await self.db.refresh(assignment)
        else:
            self.db.commit()
            self.db.refresh(assignment)
        
        logger.info(f"Created assignment {assignment.id}: questionnaire {questionnaire_id} → user {user_id}")
        return assignment
    
    async def get_active_assignments_for_user(self, user_id: int) -> List[QuestionnaireAssignment]:
        """Get all active questionnaire assignments for a user"""
        query = select(QuestionnaireAssignment).options(
            joinedload(QuestionnaireAssignment.questionnaire).joinedload(QuestionnaireBank.questions)
        ).where(
            and_(
                QuestionnaireAssignment.user_id == user_id,
                QuestionnaireAssignment.status == 'active',
                or_(
                    QuestionnaireAssignment.expires_at.is_(None),
                    QuestionnaireAssignment.expires_at > datetime.utcnow()
                )
            )
        ).order_by(desc(QuestionnaireAssignment.priority))
        
        if isinstance(self.db, AsyncSession):
            result = await self.db.execute(query)
            return result.scalars().all()
        else:
            return self.db.execute(query).scalars().all()
    
    async def get_assignment_by_id(self, assignment_id: int) -> Optional[QuestionnaireAssignment]:
        """Get assignment with full details"""
        query = select(QuestionnaireAssignment).options(
            joinedload(QuestionnaireAssignment.questionnaire).joinedload(QuestionnaireBank.questions),
            joinedload(QuestionnaireAssignment.conversation_answers)
        ).where(QuestionnaireAssignment.id == assignment_id)
        
        if isinstance(self.db, AsyncSession):
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        else:
            return self.db.execute(query).scalar_one_or_none()
    
    async def get_next_questions_to_ask(
        self,
        assignment_id: int,
        count: int = 2
    ) -> List[QuestionnaireQuestion]:
        """Get the next N questions to ask for an assignment"""
        assignment = await self.get_assignment_by_id(assignment_id)
        if not assignment:
            return []
        
        # Get questions that haven't been asked yet
        all_questions = sorted(assignment.questionnaire.questions, key=lambda q: q.sequence_order)
        
        # Get already asked question IDs
        if isinstance(self.db, AsyncSession):
            result = await self.db.execute(
                select(ConversationAnswer.question_id)
                .where(ConversationAnswer.assignment_id == assignment_id)
            )
            asked_question_ids = set(result.scalars().all())
        else:
            asked_question_ids = set(
                self.db.query(ConversationAnswer.question_id)
                .filter(ConversationAnswer.assignment_id == assignment_id)
                .all()
            )
        
        # Filter out asked questions
        remaining_questions = [q for q in all_questions if q.id not in asked_question_ids]
        
        return remaining_questions[:count]
    
    async def record_conversation_answer(
        self,
        assignment_id: int,
        question_id: int,
        question_asked: str,
        user_message: str,
        extracted_answer_text: Optional[str] = None,
        extracted_answer_value: Optional[int] = None,
        extraction_confidence: Optional[float] = None,
        extraction_method: str = "ai_parse",
        extraction_notes: Optional[str] = None,
        conversation_context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        conversation_id: Optional[int] = None,
        message_id: Optional[int] = None
    ) -> ConversationAnswer:
        """Record an answer extracted from conversation"""
        
        answer = ConversationAnswer(
            assignment_id=assignment_id,
            question_id=question_id,
            question_asked=question_asked,
            user_message=user_message,
            extracted_answer_text=extracted_answer_text,
            extracted_answer_value=extracted_answer_value,
            extraction_confidence=extraction_confidence,
            extraction_method=extraction_method,
            extraction_notes=extraction_notes,
            conversation_context=conversation_context,
            session_id=session_id,
            conversation_id=conversation_id,
            message_id=message_id,
            needs_clarification=extraction_confidence < 0.6 if extraction_confidence else False,
            validation_status='pending'
        )
        
        self.db.add(answer)
        
        # Update assignment progress
        assignment = await self.get_assignment_by_id(assignment_id)
        if assignment:
            assignment.questions_answered += 1
            if assignment.started_at is None:
                assignment.started_at = datetime.utcnow()
            
            # Check if completed
            if assignment.questions_answered >= assignment.total_questions:
                assignment.status = 'completed'
                assignment.completed_at = datetime.utcnow()
        
        if isinstance(self.db, AsyncSession):
            await self.db.commit()
            await self.db.refresh(answer)
        else:
            self.db.commit()
            self.db.refresh(answer)
        
        logger.info(f"Recorded answer for assignment {assignment_id}, question {question_id}, confidence: {extraction_confidence}")
        return answer
    
    async def get_pending_answers_for_review(
        self,
        assignment_id: Optional[int] = None,
        limit: int = 50
    ) -> List[ConversationAnswer]:
        """Get answers that need admin review"""
        query = select(ConversationAnswer).options(
            joinedload(ConversationAnswer.question),
            joinedload(ConversationAnswer.assignment)
        ).where(
            ConversationAnswer.validation_status.in_(['pending', 'needs_review'])
        )
        
        if assignment_id:
            query = query.where(ConversationAnswer.assignment_id == assignment_id)
        
        query = query.order_by(desc(ConversationAnswer.answered_at)).limit(limit)
        
        if isinstance(self.db, AsyncSession):
            result = await self.db.execute(query)
            return result.scalars().all()
        else:
            return self.db.execute(query).scalars().all()
    
    async def validate_answer(
        self,
        answer_id: int,
        validated_by: int,
        validation_status: str,
        corrected_text: Optional[str] = None,
        corrected_value: Optional[int] = None
    ) -> Optional[ConversationAnswer]:
        """Admin validates/corrects an extracted answer"""
        if isinstance(self.db, AsyncSession):
            result = await self.db.execute(
                select(ConversationAnswer).where(ConversationAnswer.id == answer_id)
            )
            answer = result.scalar_one_or_none()
        else:
            answer = self.db.query(ConversationAnswer).filter(
                ConversationAnswer.id == answer_id
            ).first()
        
        if not answer:
            return None
        
        answer.validation_status = validation_status
        answer.validated_by = validated_by
        answer.validated_at = datetime.utcnow()
        
        if corrected_text is not None:
            answer.extracted_answer_text = corrected_text
        if corrected_value is not None:
            answer.extracted_answer_value = corrected_value
        
        if isinstance(self.db, AsyncSession):
            await self.db.commit()
            await self.db.refresh(answer)
        else:
            self.db.commit()
            self.db.refresh(answer)
        
        logger.info(f"Answer {answer_id} validated by user {validated_by}: {validation_status}")
        return answer
    
    async def list_assignments_for_admin(
        self,
        status: Optional[str] = None,
        user_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[QuestionnaireAssignment]:
        """List all assignments for admin dashboard"""
        query = select(QuestionnaireAssignment).options(
            joinedload(QuestionnaireAssignment.questionnaire),
            joinedload(QuestionnaireAssignment.conversation_answers)
        )
        
        if status:
            query = query.where(QuestionnaireAssignment.status == status)
        if user_id:
            query = query.where(QuestionnaireAssignment.user_id == user_id)
        
        query = query.order_by(desc(QuestionnaireAssignment.created_at)).limit(limit).offset(offset)
        
        if isinstance(self.db, AsyncSession):
            result = await self.db.execute(query)
            return result.scalars().all()
        else:
            return self.db.execute(query).scalars().all()
    
    async def update_assignment_status(
        self,
        assignment_id: int,
        status: str
    ) -> Optional[QuestionnaireAssignment]:
        """Update assignment status (pause, resume, cancel)"""
        assignment = await self.get_assignment_by_id(assignment_id)
        if not assignment:
            return None
        
        assignment.status = status
        
        if isinstance(self.db, AsyncSession):
            await self.db.commit()
            await self.db.refresh(assignment)
        else:
            self.db.commit()
            self.db.refresh(assignment)
        
        logger.info(f"Assignment {assignment_id} status updated to: {status}")
        return assignment










