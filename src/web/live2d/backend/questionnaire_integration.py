#!/usr/bin/env python3
"""
Questionnaire Integration for Live2D Chat
Handles the logic for naturally injecting questionnaire questions into conversations
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import get_async_session_context
from src.database.models_questionnaire import (
    QuestionnaireAssignment,
    QuestionnaireQuestion,
    QuestionnaireBank,
    ConversationAnswer
)

logger = logging.getLogger(__name__)


class QuestionnaireIntegration:
    """
    Manages questionnaire question injection into Live2D conversations
    """
    
    def __init__(self):
        self.questions_per_conversation = 1  # How many questions to ask per conversation
        self.min_messages_before_question = 2  # Minimum messages before asking first question
    
    async def check_active_assignment(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Check if user has an active questionnaire assignment
        
        Returns:
            Dictionary with assignment info if active, None otherwise
        """
        try:
            async with get_async_session_context() as session:
                # Query for active assignments
                query = select(QuestionnaireAssignment).where(
                    and_(
                        QuestionnaireAssignment.user_id == user_id,
                        QuestionnaireAssignment.status.in_(['assigned', 'in_progress', 'active'])
                    )
                ).order_by(QuestionnaireAssignment.priority.desc())
                
                result = await session.execute(query)
                assignment = result.scalar_one_or_none()
                
                if assignment:
                    logger.info(f"📝 Found active questionnaire assignment {assignment.id} for user {user_id}")
                    return {
                        'assignment_id': assignment.id,
                        'questionnaire_id': assignment.questionnaire_id,
                        'priority': assignment.priority,
                        'status': assignment.status,
                        'total_questions': assignment.total_questions or 0,
                        'questions_answered': assignment.questions_answered or 0
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Error checking active assignment: {e}")
            return None
    
    async def get_next_question(self, assignment_id: int, questionnaire_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the next unanswered question from the questionnaire
        
        Returns:
            Dictionary with question info if available, None if all questions answered
        """
        try:
            async with get_async_session_context() as session:
                # Get all questions for this questionnaire
                questions_query = select(QuestionnaireQuestion).where(
                    QuestionnaireQuestion.questionnaire_id == questionnaire_id
                ).order_by(QuestionnaireQuestion.sequence_order)
                
                questions_result = await session.execute(questions_query)
                all_questions = questions_result.scalars().all()
                
                if not all_questions:
                    logger.warning(f"No questions found for questionnaire {questionnaire_id}")
                    return None
                
                # Get already answered question IDs
                answered_query = select(ConversationAnswer.question_id).where(
                    ConversationAnswer.assignment_id == assignment_id
                )
                
                answered_result = await session.execute(answered_query)
                answered_question_ids = {row[0] for row in answered_result.all()}
                
                # Find first unanswered question
                for question in all_questions:
                    if question.id not in answered_question_ids:
                        logger.info(f"📋 Next question: {question.id} - {question.question_text[:50]}...")
                        return {
                            'question_id': question.id,
                            'question_text': question.question_text,  # English version
                            'question_text_zh': question.question_text_zh,  # Chinese version
                            'question_type': question.question_type,
                            'sequence_order': question.sequence_order
                        }
                
                # All questions answered
                logger.info(f"✅ All questions answered for assignment {assignment_id}")
                # Update assignment status to completed
                await self._mark_assignment_completed(assignment_id, session)
                return None
                
        except Exception as e:
            logger.error(f"Error getting next question: {e}")
            return None
    
    async def _mark_assignment_completed(self, assignment_id: int, session: AsyncSession):
        """Mark assignment as completed"""
        try:
            assignment_query = select(QuestionnaireAssignment).where(
                QuestionnaireAssignment.id == assignment_id
            )
            result = await session.execute(assignment_query)
            assignment = result.scalar_one_or_none()
            
            if assignment:
                assignment.status = 'completed'
                assignment.completed_at = datetime.utcnow()
                await session.commit()
                logger.info(f"✅ Assignment {assignment_id} marked as completed")
                
        except Exception as e:
            logger.error(f"Error marking assignment completed: {e}")
            await session.rollback()
    
    async def should_ask_question(self, message_count: int, assignment_info: Dict[str, Any]) -> bool:
        """
        Decide if a question should be asked in this conversation turn
        
        Args:
            message_count: Number of messages in current conversation
            assignment_info: Info about the active assignment
        
        Returns:
            True if a question should be asked, False otherwise
        """
        # Check if there are unanswered questions
        answered = assignment_info.get('questions_answered', 0)
        total = assignment_info.get('total_questions', 0)
        
        logger.info(f"📊 Questionnaire progress: {answered}/{total} questions answered, message_count={message_count}")
        
        if answered >= total:
            logger.info(f"✅ All questions answered, not asking more")
            return False
        
        # Space out questions more naturally:
        # - First question at message 3+ (let conversation develop a bit)
        # - Subsequent questions every 3 messages
        # This creates a natural conversational rhythm while completing questionnaires faster
        
        if answered == 0:
            # First question: ask at message 3 or later
            should_ask = message_count >= 3
        else:
            # Subsequent questions: ask every 3 messages after the first
            # Calculate expected message count for next question
            # First question at 3, then 3 + 3 = 6, then 6 + 3 = 9, etc.
            messages_between_questions = 3
            expected_message = 3 + (answered * messages_between_questions)
            # Ask at expected message or later
            should_ask = message_count >= expected_message
        
        logger.info(f"{'✅ Asking question' if should_ask else '⏸️ Not asking yet'} (message {message_count}, answered={answered})")
        
        return should_ask
    
    async def get_recently_asked_question(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Check if there's a recently asked question waiting for an answer
        
        Returns:
            Dictionary with question info if found, None otherwise
        """
        try:
            async with get_async_session_context() as session:
                # Query for unanswered questions asked in the last hour
                from datetime import timedelta
                one_hour_ago = datetime.utcnow() - timedelta(hours=1)
                
                query = select(ConversationAnswer, QuestionnaireQuestion).join(
                    QuestionnaireQuestion,
                    ConversationAnswer.question_id == QuestionnaireQuestion.id
                ).where(
                    and_(
                        ConversationAnswer.user_id == user_id,
                        ConversationAnswer.answered_at.is_(None),
                        ConversationAnswer.asked_at >= one_hour_ago
                    )
                ).order_by(ConversationAnswer.asked_at.desc())
                
                result = await session.execute(query)
                row = result.first()
                
                if row:
                    answer_record, question = row
                    logger.info(f"📋 Found recently asked question {question.id} waiting for answer")
                    return {
                        'answer_record_id': answer_record.id,
                        'question_id': question.id,
                        'question_text': answer_record.question_text_asked,
                        'question_type': question.question_type,
                        'assignment_id': answer_record.assignment_id
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Error checking recently asked question: {e}")
            return None
    
    async def record_question_asked(
        self, 
        assignment_id: int, 
        question_id: int,
        user_id: int,
        question_text: str
    ) -> int:
        """
        Record that a question was asked to the user
        
        Returns:
            The created ConversationAnswer ID
        """
        try:
            async with get_async_session_context() as session:
                answer_record = ConversationAnswer(
                    assignment_id=assignment_id,
                    question_id=question_id,
                    question_asked=question_text,
                    # user_message will be NULL until user responds
                    asked_at=datetime.utcnow(),
                    answered_at=None  # Explicitly set to None (will be filled when answered)
                )
                
                session.add(answer_record)
                await session.commit()
                await session.refresh(answer_record)
                
                logger.info(f"📝 Recorded question {question_id} asked (answer_record_id={answer_record.id})")
                return answer_record.id
                
        except Exception as e:
            logger.error(f"Error recording question asked: {e}")
            return None
    
    async def format_question_naturally(
        self, 
        question_text: str, 
        language: str = "en",
        question_text_zh: Optional[str] = None
    ) -> str:
        """
        Format the questionnaire question to sound natural in conversation
        
        Args:
            question_text: The English question text from questionnaire
            language: User's language preference
            question_text_zh: The Chinese question text (if available)
        
        Returns:
            Naturally formatted question in the appropriate language
        """
        # Select the appropriate question text based on language
        if language.startswith("zh") or language == "zh-HK":
            # Use Traditional Chinese (Hong Kong) version if available, fallback to English
            selected_text = question_text_zh if question_text_zh else question_text
        else:
            # Use English version
            selected_text = question_text
        
        # Return question directly without awkward lead-ins
        # The AI's response will provide context, and the question will follow naturally
        return selected_text


# Singleton instance
_questionnaire_integration = None

def get_questionnaire_integration() -> QuestionnaireIntegration:
    """Get singleton instance of QuestionnaireIntegration"""
    global _questionnaire_integration
    if _questionnaire_integration is None:
        _questionnaire_integration = QuestionnaireIntegration()
    return _questionnaire_integration

