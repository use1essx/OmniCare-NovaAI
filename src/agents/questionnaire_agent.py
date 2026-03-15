"""
Questionnaire Agent
Integrates questionnaire questions naturally into Live2D conversations
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
import os
import json

from src.services.questionnaire_service import QuestionnaireAssignmentService
from src.services.answer_extraction_service import AnswerExtractionService

logger = logging.getLogger(__name__)


class QuestionnaireAgent:
    """
    Agent that injects questionnaire questions naturally into conversations.
    Monitors active assignments and asks questions at appropriate times.
    """
    
    def __init__(self, db_session, ai_service=None):
        self.db = db_session
        self.assignment_service = QuestionnaireAssignmentService(db_session)
        self.extraction_service = AnswerExtractionService()
        # AI service for question naturalization
        self.ai_service = ai_service
    
    async def check_for_questions(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Check if there are questionnaire questions to ask this user.
        Returns question data if available, None otherwise.
        """
        try:
            result = await self.assignment_service.get_next_questions_for_conversation(user_id)
            
            if not result:
                return None
            
            assignment_id, questions = result
            
            if not questions:
                return None
            
            # Return the first question to ask
            question = questions[0]
            
            return {
                "assignment_id": assignment_id,
                "question_id": question.id,
                "question_text": question.question_text,
                "question_text_zh": question.question_text_zh,
                "question_type": question.question_type,
                "category": question.category,
                "help_text": question.help_text,
                "options": [
                    {
                        "id": opt.id,
                        "option_text": opt.option_text,
                        "option_text_zh": opt.option_text_zh,
                        "option_value": opt.option_value
                    }
                    for opt in sorted(question.options, key=lambda x: x.sequence_order)
                ] if question.options else []
            }
        except Exception as e:
            logger.error(f"Error checking for questions: {e}")
            return None
    
    async def naturalize_question(
        self,
        question_data: Dict[str, Any],
        conversation_context: List[Dict[str, str]],
        language: str = "en"
    ) -> str:
        """
        Transform a formal questionnaire question into natural conversation.
        Uses AI to make it feel organic and contextual.
        
        Args:
            question_data: The question to ask
            conversation_context: Recent conversation messages
            language: User's language preference
            
        Returns:
            Naturalized question text
        """
        
        question_text = question_data.get("question_text_zh") if language.startswith("zh") else question_data.get("question_text")
        question_type = question_data.get("question_type")
        
        # Build conversation context string
        context_str = ""
        if conversation_context:
            context_str = "\n".join([
                f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                for msg in conversation_context[-5:]  # Last 5 messages
            ])
        
        # Options string if applicable
        options_str = ""
        if question_data.get("options"):
            options = question_data["options"]
            if language.startswith("zh"):
                options_str = "\n可選項: " + ", ".join([opt.get("option_text_zh", opt.get("option_text")) for opt in options])
            else:
                options_str = "\nOptions: " + ", ".join([opt.get("option_text") for opt in options])
        
        try:
            # Use AI service for naturalization
            if not self.ai_service:
                logger.warning("AI service not available, returning original question")
                return question_text
            
            if language.startswith("zh"):
                prompt = f"""你是一個友善的AI助手，正在與用戶進行自然對話。你需要在對話中自然地問一個問卷問題。

最近的對話:
{context_str}

需要問的問題: {question_text}
{options_str}

請將這個問題自然地融入對話中，讓它聽起來不突兀。保持友善、輕鬆的語氣。不要直接說"我有個問題要問你"，而是自然地過渡到這個話題。

只返回自然化的問題文本，不要加其他說明。"""
            else:
                prompt = f"""You are a friendly AI assistant having a natural conversation with a user. You need to naturally ask a questionnaire question during the conversation.

Recent conversation:
{context_str}

Question to ask: {question_text}
{options_str}

Rephrase this question to fit naturally into the conversation flow. Make it sound organic and contextual, not like a formal survey. Keep a friendly, casual tone. Don't say "I have a question for you" - just transition naturally to the topic.

Return only the naturalized question text, no other explanation."""
            
            # Use AI service chat_completion
            response = await self.ai_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that makes questionnaire questions sound natural in conversation."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            if response.get('success'):
                naturalized = response['content'].strip()
                
                # Remove quotes if AI wrapped it
                naturalized = naturalized.strip('"').strip("'")
                
                logger.info(f"✨ Naturalized question: {naturalized[:100]}...")
                return naturalized
            else:
                logger.error(f"AI service returned error: {response.get('error_message')}")
                return question_text
        
        except Exception as e:
            logger.error(f"Failed to naturalize question: {e}")
        
        # Fallback: return original question
        return question_text
    
    async def process_user_response(
        self,
        assignment_id: int,
        question_data: Dict[str, Any],
        user_message: str,
        conversation_context: List[Dict[str, str]],
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process user's response to a questionnaire question.
        Extracts the answer and stores it.
        
        Returns:
            {
                "answer_recorded": bool,
                "needs_clarification": bool,
                "clarification_question": str or None,
                "extraction_confidence": float
            }
        """
        
        try:
            # Extract answer using AI
            extraction_result = await self.extraction_service.extract_answer(
                question=question_data,
                user_message=user_message,
                conversation_context=conversation_context
            )
            
            logger.info(f"📊 Extracted answer: {extraction_result}")
            
            # Check if we need clarification
            needs_clarification = self.extraction_service.should_ask_clarification(extraction_result)
            
            if needs_clarification:
                clarification_q = self.extraction_service.generate_clarification_question(
                    question_data,
                    extraction_result
                )
                
                return {
                    "answer_recorded": False,
                    "needs_clarification": True,
                    "clarification_question": clarification_q,
                    "extraction_confidence": extraction_result.get("confidence", 0.0)
                }
            
            # Record the answer
            await self.assignment_service.record_answer_from_conversation(
                assignment_id=assignment_id,
                question_id=question_data["question_id"],
                question_asked=question_data.get("naturalized_text", question_data["question_text"]),
                user_message=user_message,
                extracted_answer=extraction_result,
                conversation_context=conversation_context,
                session_id=session_id
            )
            
            logger.info(f"✅ Recorded answer for assignment {assignment_id}, question {question_data['question_id']}")
            
            return {
                "answer_recorded": True,
                "needs_clarification": False,
                "clarification_question": None,
                "extraction_confidence": extraction_result.get("confidence", 0.0)
            }
        
        except Exception as e:
            logger.error(f"Error processing user response: {e}")
            return {
                "answer_recorded": False,
                "needs_clarification": False,
                "clarification_question": None,
                "extraction_confidence": 0.0,
                "error": str(e)
            }
    
    async def should_inject_question(
        self,
        user_id: int,
        conversation_length: int,
        last_question_turn: Optional[int] = None
    ) -> bool:
        """
        Determine if now is a good time to inject a questionnaire question.
        
        Args:
            user_id: User ID
            conversation_length: Number of turns in current conversation
            last_question_turn: Turn number when last question was asked
            
        Returns:
            True if we should ask a question now
        """
        
        # Don't ask questions too early
        if conversation_length < 3:
            return False
        
        # Don't ask questions too frequently
        if last_question_turn and (conversation_length - last_question_turn) < 4:
            return False
        
        # Check if there are questions to ask
        question_data = await self.check_for_questions(user_id)
        if not question_data:
            return False
        
        # Ask every 5-7 turns
        if last_question_turn is None:
            return conversation_length >= 5
        else:
            return (conversation_length - last_question_turn) >= 5
    
    def generate_acknowledgment(
        self,
        extraction_confidence: float,
        language: str = "en"
    ) -> str:
        """Generate a natural acknowledgment after receiving an answer"""
        
        if language.startswith("zh"):
            if extraction_confidence > 0.8:
                return "明白了，謝謝你的分享。"
            elif extraction_confidence > 0.6:
                return "好的，我了解了。"
            else:
                return "謝謝你告訴我。"
        else:
            if extraction_confidence > 0.8:
                return "Got it, thanks for sharing that."
            elif extraction_confidence > 0.6:
                return "Okay, I understand."
            else:
                return "Thank you for telling me."










