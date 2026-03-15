"""
Questionnaire Chat Service
Manages questionnaire questions during Live2D chat sessions
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from src.core.logging import get_logger
from src.database.models_questionnaire import (
    QuestionnaireAssignment,
    QuestionnaireBank,
    QuestionnaireQuestion,
    ConversationAnswer
)
from src.services.emotion_scoring_service import get_emotion_scoring_service

logger = get_logger(__name__)


class QuestionnaireChatService:
    """
    Service for managing questionnaire questions in chat sessions
    
    Features:
    - Check for active questionnaire assignments
    - Get next question to ask
    - Store user answers with emotion analysis
    - Track progress
    """
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.QuestionnaireChatService")
        self.emotion_service = None
    
    async def initialize(self):
        """Initialize dependencies"""
        if not self.emotion_service:
            self.emotion_service = await get_emotion_scoring_service()
    
    async def get_active_assignment(
        self,
        user_id: int,
        db: Session
    ) -> Optional[QuestionnaireAssignment]:
        """
        Get active questionnaire assignment for user
        
        Args:
            user_id: User ID
            db: Database session
            
        Returns:
            Active assignment or None
        """
        try:
            result = db.execute(
                select(QuestionnaireAssignment)
                .where(
                    and_(
                        QuestionnaireAssignment.user_id == user_id,
                        QuestionnaireAssignment.status == "active"
                    )
                )
                .order_by(QuestionnaireAssignment.priority.desc())
                .limit(1)
            )
            
            assignment = result.scalar_one_or_none()
            return assignment
            
        except Exception as e:
            self.logger.error(f"Error getting active assignment: {e}")
            return None
    
    async def get_next_question(
        self,
        assignment: QuestionnaireAssignment,
        db: Session
    ) -> Optional[Tuple[QuestionnaireQuestion, str]]:
        """
        Get next question to ask from assignment
        
        Args:
            assignment: Questionnaire assignment
            db: Database session
            
        Returns:
            Tuple of (question, formatted_question_text) or None
        """
        try:
            # Get questionnaire
            questionnaire = db.query(QuestionnaireBank).filter(
                QuestionnaireBank.id == assignment.questionnaire_id
            ).first()
            
            if not questionnaire:
                return None
            
            # Get all questions ordered by sequence
            questions = db.query(QuestionnaireQuestion).filter(
                QuestionnaireQuestion.questionnaire_id == questionnaire.id
            ).order_by(QuestionnaireQuestion.sequence_order).all()
            
            if not questions:
                return None
            
            # Get already answered questions
            answered_question_ids = set(
                db.query(ConversationAnswer.question_id)
                .filter(ConversationAnswer.assignment_id == assignment.id)
                .all()
            )
            answered_question_ids = {q[0] for q in answered_question_ids}
            
            # Find next unanswered question
            for question in questions:
                if question.id not in answered_question_ids:
                    # Format question text
                    formatted_text = self._format_question_for_chat(question)
                    return (question, formatted_text)
            
            # All questions answered
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting next question: {e}")
            return None
    
    def _format_question_for_chat(self, question: QuestionnaireQuestion) -> str:
        """
        Format question for natural conversation
        
        Args:
            question: Question to format
            
        Returns:
            Formatted question text
        """
        # Use English or Chinese based on availability
        question_text = question.question_text
        
        # Add natural conversation prefix
        prefixes = [
            "I'd like to ask you something: ",
            "Can I ask you: ",
            "Here's a question for you: ",
            "I'm curious: ",
            ""
        ]
        
        import random
        prefix = random.choice(prefixes)
        
        return f"{prefix}{question_text}"
    
    async def should_ask_question_now(
        self,
        assignment: QuestionnaireAssignment,
        messages_since_last_question: int
    ) -> bool:
        """
        Determine if we should ask a questionnaire question now
        
        Args:
            assignment: Active assignment
            messages_since_last_question: Number of messages since last question
            
        Returns:
            True if should ask question now
        """
        # Ask naturally based on settings
        if not assignment.ask_naturally:
            return True
        
        # Ask every N messages (configurable)
        questions_per_conversation = assignment.questions_per_conversation or 2
        
        # Simple logic: ask if we've had enough conversation
        return messages_since_last_question >= (10 // questions_per_conversation)
    
    async def store_answer(
        self,
        assignment: QuestionnaireAssignment,
        question: QuestionnaireQuestion,
        user_message: str,
        session_id: str,
        conversation_context: Optional[Dict[str, Any]],
        db: Session
    ) -> ConversationAnswer:
        """
        Store user answer with emotion analysis
        
        Args:
            assignment: Questionnaire assignment
            question: Question that was asked
            user_message: User's response
            session_id: Chat session ID
            conversation_context: Additional context
            db: Database session
            
        Returns:
            Created ConversationAnswer
        """
        try:
            await self.initialize()
            
            # Perform emotion analysis
            analysis = await self.emotion_service.analyze_response(
                user_message=user_message,
                question_text=question.question_text,
                question_category=question.category or "general",
                conversation_context=conversation_context
            )
            
            # Calculate numeric score if applicable
            extracted_value = self.emotion_service.calculate_question_score(
                analysis,
                question.question_type
            )
            
            # Create conversation answer
            answer = ConversationAnswer(
                assignment_id=assignment.id,
                question_id=question.id,
                session_id=session_id,
                question_asked=question.question_text,
                user_message=user_message,
                extracted_answer_text=user_message,
                extracted_answer_value=extracted_value,
                extraction_confidence=analysis.get("overall_wellbeing_score", 50) / 100,
                extraction_method="ai_emotion_analysis",
                extraction_notes=analysis.get("analysis_summary", ""),
                needs_clarification=False,
                validation_status="pending",
                asked_at=datetime.now(),
                answered_at=datetime.now(),
                conversation_context=conversation_context,
                # Emotion analysis fields
                emotion_analysis_result=analysis,
                dominant_emotion=analysis.get("dominant_emotion"),
                emotion_intensity=analysis.get("emotion_intensity"),
                anxiety_risk_score=analysis.get("anxiety_risk_score"),
                emotional_regulation_score=analysis.get("emotional_regulation_score"),
                overall_wellbeing_score=analysis.get("overall_wellbeing_score"),
                analysis_summary=analysis.get("analysis_summary")
            )
            
            db.add(answer)
            
            # Update assignment progress
            assignment.questions_asked += 1
            assignment.questions_answered += 1
            assignment.current_question_index += 1
            
            # Check if completed
            if assignment.questions_answered >= assignment.total_questions:
                assignment.status = "completed"
                assignment.completed_at = datetime.now()
            
            db.commit()
            db.refresh(answer)
            
            self.logger.info(
                f"Stored answer for question {question.id} with emotion: "
                f"{analysis.get('dominant_emotion')} (wellbeing: {analysis.get('overall_wellbeing_score')})"
            )
            
            return answer
            
        except Exception as e:
            self.logger.error(f"Error storing answer: {e}")
            db.rollback()
            raise
    
    async def get_assignment_progress(
        self,
        assignment: QuestionnaireAssignment,
        db: Session
    ) -> Dict[str, Any]:
        """
        Get progress information for assignment
        
        Args:
            assignment: Questionnaire assignment
            db: Database session
            
        Returns:
            Progress information dict
        """
        try:
            # Get answered questions count
            answered_count = db.query(ConversationAnswer).filter(
                ConversationAnswer.assignment_id == assignment.id
            ).count()
            
            # Calculate progress percentage
            progress_pct = 0
            if assignment.total_questions > 0:
                progress_pct = int((answered_count / assignment.total_questions) * 100)
            
            return {
                "assignment_id": assignment.id,
                "questionnaire_id": assignment.questionnaire_id,
                "status": assignment.status,
                "total_questions": assignment.total_questions,
                "questions_answered": answered_count,
                "questions_remaining": assignment.total_questions - answered_count,
                "progress_percentage": progress_pct,
                "started_at": assignment.started_at.isoformat() if assignment.started_at else None,
                "completed_at": assignment.completed_at.isoformat() if assignment.completed_at else None
            }
            
        except Exception as e:
            self.logger.error(f"Error getting assignment progress: {e}")
            return {}


# Singleton instance
_questionnaire_chat_service = None


async def get_questionnaire_chat_service() -> QuestionnaireChatService:
    """Get singleton questionnaire chat service instance"""
    global _questionnaire_chat_service
    if _questionnaire_chat_service is None:
        _questionnaire_chat_service = QuestionnaireChatService()
        await _questionnaire_chat_service.initialize()
    return _questionnaire_chat_service
