#!/usr/bin/env python3
"""
Answer Extraction Service
Extracts questionnaire answers from natural language user responses
"""

import logging
import re
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from src.database.connection import get_async_session_context
from src.database.models_questionnaire import ConversationAnswer, QuestionnaireQuestion
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)


class AnswerExtractor:
    """
    Extracts and validates questionnaire answers from natural language
    """
    
    def __init__(self):
        # Common answer patterns for Likert-scale questions
        self.likert_patterns = {
            0: [
                r'\bnot at all\b', r'\bnever\b', r'\bno\b', r'\bnone\b',
                r'\b完全沒有\b', r'\b從來沒有\b', r'\b冇\b', r'\b唔會\b'
            ],
            1: [
                r'\bseveral days\b', r'\bsometimes\b', r'\ba little\b', r'\brarely\b',
                r'\b幾日\b', r'\b有時\b', r'\b少少\b', r'\b偶爾\b'
            ],
            2: [
                r'\bmore than half\b', r'\boften\b', r'\bfrequently\b',
                r'\b超過一半\b', r'\b經常\b', r'\b好多時\b'
            ],
            3: [
                r'\bnearly every day\b', r'\balways\b', r'\bvery often\b', r'\ball the time\b',
                r'\b幾乎每日\b', r'\b成日\b', r'\b一直\b', r'\b日日\b'
            ]
        }
    
    async def extract_answer_from_message(
        self, 
        user_message: str, 
        question_id: int,
        assignment_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Extract answer from user's natural language response
        
        Args:
            user_message: User's response message
            question_id: ID of the question being answered
            assignment_id: ID of the questionnaire assignment
        
        Returns:
            Dictionary with extracted answer info, or None if no answer found
        """
        try:
            async with get_async_session_context() as session:
                # Get the question details
                question_query = select(QuestionnaireQuestion).where(
                    QuestionnaireQuestion.id == question_id
                )
                result = await session.execute(question_query)
                question = result.scalar_one_or_none()
                
                if not question:
                    logger.warning(f"Question {question_id} not found")
                    return None
                
                # Extract answer based on question type
                if question.question_type == 'likert':
                    answer_value, confidence = self._extract_likert_answer(user_message)
                elif question.question_type == 'yes_no':
                    answer_value, confidence = self._extract_yes_no_answer(user_message)
                elif question.question_type == 'multiple_choice':
                    answer_value, confidence = self._extract_multiple_choice_answer(user_message, question)
                else:
                    # Free text - just store the message
                    answer_value = None
                    confidence = 0.5
                
                # Determine if answer is clear enough
                needs_clarification = confidence < 0.6
                
                return {
                    'answer_value': answer_value,
                    'answer_text': user_message,
                    'confidence': confidence,
                    'needs_clarification': needs_clarification,
                    'extraction_method': 'pattern_matching'
                }
                
        except Exception as e:
            logger.error(f"Error extracting answer: {e}")
            return None
    
    def _extract_likert_answer(self, message: str) -> Tuple[Optional[int], float]:
        """
        Extract Likert scale answer (0-3) from message
        
        Returns:
            (answer_value, confidence)
        """
        message_lower = message.lower()
        
        logger.info(f"🔍 Extracting Likert answer from: '{message[:100]}...'")
        
        # Enhanced patterns with more flexible matching
        # Score 3 - Nearly every day / Always / Very often / Every day
        if any(pattern in message_lower for pattern in [
            'nearly every day', 'every day', 'everyday', 'always', 'all the time',
            'very often', 'constantly', 'daily', 'each day', 'all day',
            '幾乎每日', '每日', '成日', '一直', '日日'
        ]):
            logger.info(f"📊 Extracted Likert answer: 3 (nearly every day)")
            return (3, 0.9)
        
        # Score 2 - More than half / Often / Frequently
        if any(pattern in message_lower for pattern in [
            'more than half', 'often', 'frequently', 'most days', 'usually',
            'quite often', 'a lot', 'many times', 'regularly',
            '超過一半', '經常', '好多時', '通常'
        ]):
            logger.info(f"📊 Extracted Likert answer: 2 (often)")
            return (2, 0.9)
        
        # Score 1 - Several days / Sometimes / A little
        if any(pattern in message_lower for pattern in [
            'several days', 'sometimes', 'a little', 'rarely', 'occasionally',
            'once in a while', 'from time to time', 'now and then', 'a bit',
            '幾日', '有時', '少少', '偶爾', '間中'
        ]):
            logger.info(f"📊 Extracted Likert answer: 1 (sometimes)")
            return (1, 0.9)
        
        # Score 0 - Not at all / Never / No / Can still / Don't have
        if any(pattern in message_lower for pattern in [
            'not at all', 'never', 'no ', ' no', 'none', 'not really',
            "don't", "can't", 'cannot', 'able to', 'still can', 'can still',
            "don't have", "haven't", 'not', 'fine', 'okay',
            '完全沒有', '從來沒有', '冇', '唔會', '可以', '能夠'
        ]):
            logger.info(f"📊 Extracted Likert answer: 0 (not at all)")
            return (0, 0.8)
        
        # Try to extract numbers directly
        numbers = re.findall(r'\b([0-3])\b', message)
        if numbers:
            value = int(numbers[0])
            logger.info(f"📊 Extracted Likert answer from number: {value}")
            return (value, 0.8)
        
        # NEW: If message contains strong negative sentiment words, assume high score (3)
        # This handles responses like "I want to", "I feel worthless", "I have no appetite"
        negative_indicators = [
            'want to', 'feel', 'have', 'am', 'get', 'think',
            'worthless', 'hopeless', 'sad', 'depressed', 'anxious',
            'no appetite', 'little appetite', 'tired', 'exhausted'
        ]
        
        # Check if message is affirmative (contains these indicators)
        if any(indicator in message_lower for indicator in negative_indicators):
            # If it's a short affirmative response to a negative question, score it high
            if len(message.split()) < 15:  # Short response
                logger.info(f"📊 Extracted Likert answer: 2 (inferred from affirmative response)")
                return (2, 0.7)  # Default to "often" for affirmative responses
        
        # No clear answer found
        logger.warning(f"❌ Could not extract Likert answer from: {message[:50]}...")
        logger.warning(f"   Message (lowercase): {message_lower[:50]}...")
        return (None, 0.0)
    
    def _extract_yes_no_answer(self, message: str) -> Tuple[Optional[int], float]:
        """
        Extract yes/no answer from message
        
        Returns:
            (1 for yes, 0 for no, confidence)
        """
        message_lower = message.lower()
        
        # Yes patterns
        yes_patterns = [
            r'\byes\b', r'\byeah\b', r'\byep\b', r'\bsure\b', r'\bof course\b',
            r'\b係\b', r'\b是\b', r'\b有\b', r'\b會\b'
        ]
        
        # No patterns
        no_patterns = [
            r'\bno\b', r'\bnope\b', r'\bnot\b', r'\bnever\b',
            r'\b唔係\b', r'\b不是\b', r'\b冇\b', r'\b唔會\b'
        ]
        
        for pattern in yes_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return (1, 0.8)
        
        for pattern in no_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return (0, 0.8)
        
        return (None, 0.0)
    
    def _extract_multiple_choice_answer(
        self, 
        message: str, 
        question: QuestionnaireQuestion
    ) -> Tuple[Optional[int], float]:
        """
        Extract multiple choice answer from message
        
        Returns:
            (option_index, confidence)
        """
        # This would need to match against question options
        # For now, try to extract a number
        numbers = re.findall(r'\b([0-9])\b', message)
        if numbers:
            value = int(numbers[0])
            return (value, 0.6)
        
        return (None, 0.0)
    
    async def save_extracted_answer(
        self,
        assignment_id: int,
        question_id: int,
        user_message: str,
        extracted_data: Dict[str, Any]
    ) -> bool:
        """
        Save extracted answer to database
        
        Returns:
            True if saved successfully
        """
        try:
            async with get_async_session_context() as session:
                # Find the conversation answer record for this question
                query = select(ConversationAnswer).where(
                    and_(
                        ConversationAnswer.assignment_id == assignment_id,
                        ConversationAnswer.question_id == question_id,
                        ConversationAnswer.extracted_answer_value.is_(None)  # Not yet answered (check for NULL)
                    )
                ).order_by(ConversationAnswer.asked_at.desc())
                
                result = await session.execute(query)
                answer_record = result.scalar_one_or_none()
                
                if not answer_record:
                    logger.warning(f"No pending answer record found for question {question_id}")
                    return False
                
                # Update the record with extracted answer
                answer_record.user_message = user_message
                answer_record.extracted_answer_text = extracted_data.get('answer_text')
                answer_record.extracted_answer_value = extracted_data.get('answer_value')
                answer_record.extraction_confidence = extracted_data.get('confidence')
                answer_record.extraction_method = extracted_data.get('extraction_method')
                answer_record.needs_clarification = extracted_data.get('needs_clarification', False)
                answer_record.answered_at = datetime.utcnow()
                
                await session.commit()
                
                logger.info(f"✅ Saved answer for question {question_id}: value={extracted_data.get('answer_value')}, confidence={extracted_data.get('confidence')}")
                
                # Update assignment progress
                await self._update_assignment_progress(assignment_id, session)
                
                return True
                
        except Exception as e:
            logger.error(f"Error saving extracted answer: {e}")
            return False
    
    async def _update_assignment_progress(self, assignment_id: int, session):
        """Update the questions_answered counter in assignment"""
        try:
            from src.database.models_questionnaire import QuestionnaireAssignment
            
            # Count answered questions
            count_query = select(ConversationAnswer).where(
                and_(
                    ConversationAnswer.assignment_id == assignment_id,
                    ConversationAnswer.extracted_answer_value.isnot(None)  # Has answer (check for NOT NULL)
                )
            )
            result = await session.execute(count_query)
            answered_count = len(result.scalars().all())
            
            # Update assignment
            assignment_query = select(QuestionnaireAssignment).where(
                QuestionnaireAssignment.id == assignment_id
            )
            assignment_result = await session.execute(assignment_query)
            assignment = assignment_result.scalar_one_or_none()
            
            if assignment:
                assignment.questions_answered = answered_count
                
                # Mark as completed if all questions answered
                if answered_count >= assignment.total_questions:
                    assignment.status = 'completed'
                    assignment.completed_at = datetime.utcnow()
                    logger.info(f"🎉 Assignment {assignment_id} completed! {answered_count}/{assignment.total_questions} questions answered")
                else:
                    assignment.status = 'in_progress'
                
                await session.commit()
                logger.info(f"📊 Updated assignment {assignment_id} progress: {answered_count}/{assignment.total_questions}")
                
        except Exception as e:
            logger.error(f"Error updating assignment progress: {e}")


# Singleton instance
_answer_extractor = None

def get_answer_extractor() -> AnswerExtractor:
    """Get singleton instance of AnswerExtractor"""
    global _answer_extractor
    if _answer_extractor is None:
        _answer_extractor = AnswerExtractor()
    return _answer_extractor
