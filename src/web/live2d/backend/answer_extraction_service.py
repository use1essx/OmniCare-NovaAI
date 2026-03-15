#!/usr/bin/env python3
"""
Answer Extraction Service for Questionnaire Integration
Uses AI to extract structured answers from natural language user responses
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import get_async_session_context
from src.database.models_questionnaire import (
    ConversationAnswer,
    QuestionnaireQuestion,
    QuestionnaireAssignment
)
from src.services.emotion_analysis_service import get_emotion_analysis_service
from src.ai.unified_ai_client import AIRequest
from src.ai.providers.nova_bedrock_client import get_nova_client

logger = logging.getLogger(__name__)


class AnswerExtractionService:
    """
    Service for extracting structured answers from conversational responses
    """
    
    def __init__(self):
        """Initialize answer extraction service with Nova client"""
        try:
            self.nova_client = get_nova_client()
            logger.info("✅ Nova client initialized for answer extraction")
        except Exception as e:
            logger.warning(f"⚠️ Nova client initialization failed: {e} - falling back to pattern matching")
            self.nova_client = None
    
    async def extract_answer_from_response(
        self,
        user_response: str,
        question_text: str,
        question_type: str,
        conversation_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract structured answer from user's natural language response
        
        Args:
            user_response: User's natural language response
            question_text: The original questionnaire question
            question_type: Type of question (scale, yes_no, multiple_choice, short_answer, rating)
            conversation_context: Previous conversation messages for context
        
        Returns:
            Dictionary with extracted answer and metadata
        """
        try:
            # Build extraction prompt based on question type
            system_prompt = self._build_extraction_prompt(question_type)
            user_prompt = self._build_user_prompt(question_text, user_response, conversation_context)
            
            # Call AI to extract answer
            extraction_result = await self._call_ai_extraction(system_prompt, user_prompt)
            
            return extraction_result
            
        except Exception as e:
            logger.error(f"Error extracting answer: {e}")
            return {
                'success': False,
                'error': str(e),
                'extracted_text': None,
                'extracted_value': None,
                'confidence': 0.0
            }
    
    def _build_extraction_prompt(self, question_type: str) -> str:
        """Build system prompt based on question type"""
        base_prompt = """You are an AI assistant specialized in extracting structured answers from natural language responses to questionnaire questions.

Your task is to analyze the user's response and extract the relevant answer in a structured format.

Important guidelines:
1. Be lenient and understanding - users may phrase answers in various ways
2. Consider context from previous messages
3. If the user's response is ambiguous or unclear, use your best judgment
4. Provide a confidence score (0.0-1.0) for your extraction
5. For cultural context: This is for Hong Kong healthcare setting

"""
        
        type_specific = {
            'scale': """
Question Type: SCALE (e.g., 1-5, 1-10)
- Extract the numeric value the user indicates
- Look for numbers, keywords like "high", "low", "medium", "very", etc.
- Map descriptive words to scale values (e.g., "very high" = near max, "low" = near min)
""",
            'yes_no': """
Question Type: YES/NO
- Extract boolean answer
- Look for affirmative (yes, yeah, sure, definitely, ok) or negative (no, nope, not really, don't think so) responses
- Consider partial agreements (maybe = uncertain, leaning yes if more positive context)
""",
            'multiple_choice': """
Question Type: MULTIPLE CHOICE
- Extract which option the user selected
- Match keywords from the user's response to the available options
- Be flexible with phrasing
""",
            'short_answer': """
Question Type: SHORT ANSWER (open-ended text)
- Extract the user's full answer as text
- Clean up and summarize if needed
- Preserve key information
""",
            'rating': """
Question Type: RATING
- Extract numeric rating value
- Similar to scale, but typically out of 5 or 10
- Map descriptive words to ratings
"""
        }
        
        return base_prompt + type_specific.get(question_type, type_specific['short_answer']) + """

Return your response in this EXACT JSON format (no extra text):
{
    "extracted_text": "The extracted answer as text",
    "extracted_value": <numeric value if applicable, otherwise null>,
    "confidence": <float between 0.0 and 1.0>,
    "reasoning": "Brief explanation of how you extracted the answer"
}
"""
    
    def _build_user_prompt(
        self,
        question_text: str,
        user_response: str,
        conversation_context: Optional[str] = None
    ) -> str:
        """Build user prompt with question and response"""
        prompt = f"""Question asked: "{question_text}"

User's response: "{user_response}"
"""
        
        if conversation_context:
            prompt = f"""Previous conversation context:
{conversation_context}

""" + prompt
        
        prompt += """
Extract the structured answer from the user's response.
Return ONLY the JSON object, no other text."""
        
        return prompt
    
    async def _call_ai_extraction(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Call AI API to extract answer using Nova"""
        # SECURITY: Input validation
        if not user_prompt or len(user_prompt) > 10000:
            logger.warning("Invalid user prompt length")
            return {
                'success': False,
                'error': 'Invalid input length',
                'extracted_text': None,
                'extracted_value': None,
                'confidence': 0.0
            }
        
        if not self.nova_client:
            logger.warning("Nova client not available for answer extraction")
            return {
                'success': False,
                'error': 'Nova client not configured',
                'extracted_text': None,
                'extracted_value': None,
                'confidence': 0.0
            }
        
        try:
            # Use Nova client for extraction
            request = AIRequest(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                task_type="answer_extraction",
                temperature=0.3,
                max_tokens=500
            )
            
            response = await self.nova_client.make_request(request=request)
            
            if not response or not response.content:
                logger.error("Empty response from Nova client")
                return {
                    'success': False,
                    'error': 'Empty AI response',
                    'extracted_text': None,
                    'extracted_value': None,
                    'confidence': 0.0
                }
            
            content = response.content
            
            # Parse JSON response
            try:
                # Try to find JSON block
                import re
                if "```json" in content:
                    match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                    if match:
                        content = match.group(1)
                
                result = json.loads(content)
                return {
                    'success': True,
                    'extracted_text': result.get('extracted_text'),
                    'extracted_value': result.get('extracted_value'),
                    'confidence': float(result.get('confidence', 0.8)),
                    'reasoning': result.get('reasoning', '')
                }
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse AI response as JSON: {content}")
                return {
                    'success': True,
                    'extracted_text': content,
                    'extracted_value': None,
                    'confidence': 0.5,
                    'reasoning': 'Fallback: could not parse structured response'
                }
                        
        except Exception as e:
            logger.error(f"Error calling AI extraction API: {e}")
            return {
                'success': False,
                'error': str(e),
                'extracted_text': None,
                'extracted_value': None,
                'confidence': 0.0
            }
    
    async def save_extracted_answer(
        self,
        answer_record_id: int,
        user_response_text: str,
        extracted_text: Optional[str],
        extracted_value: Optional[int],
        confidence: float,
        extraction_method: str = 'ai',
        question_context: Optional[str] = None,
        conversation_history: Optional[list] = None
    ) -> bool:
        """
        Save the extracted answer to database WITH EMOTION ANALYSIS
        
        Args:
            answer_record_id: ID of the ConversationAnswer record
            user_response_text: User's original response
            extracted_text: Extracted text answer
            extracted_value: Extracted numeric value (if applicable)
            confidence: Confidence score of extraction
            extraction_method: Method used for extraction (ai, keyword, manual)
            question_context: The question text for context
            conversation_history: Previous conversation messages
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            async with get_async_session_context() as session:
                # Get the answer record
                query = select(ConversationAnswer).where(
                    ConversationAnswer.id == answer_record_id
                )
                result = await session.execute(query)
                answer_record = result.scalar_one_or_none()
                
                if not answer_record:
                    logger.error(f"Answer record {answer_record_id} not found")
                    return False
                
                # 🆕 EMOTION ANALYSIS - Analyze user's emotional state from response
                emotion_service = get_emotion_analysis_service()
                emotion_analysis = await emotion_service.analyze_emotion(
                    user_message=user_response_text,
                    question_context=question_context,
                    conversation_history=conversation_history
                )
                
                logger.info(f"🧠 Emotion Analysis: {emotion_analysis['dominant_emotion']} "
                           f"({emotion_analysis['emotion_intensity']}%), "
                           f"Anxiety Risk: {emotion_analysis['risk_scores']['anxiety_risk']}%")
                
                # Update with extracted answer (optional - can skip if you don't need text)
                answer_record.user_response_text = user_response_text
                answer_record.extracted_answer_text = extracted_text or ""
                answer_record.extracted_answer_value = extracted_value
                answer_record.extraction_confidence = confidence
                answer_record.extraction_method = extraction_method
                answer_record.answered_at = datetime.utcnow()
                
                # 🆕 Save emotion analysis results
                answer_record.emotion_analysis_result = emotion_analysis
                answer_record.dominant_emotion = emotion_analysis['dominant_emotion']
                answer_record.emotion_intensity = emotion_analysis['emotion_intensity']
                answer_record.anxiety_risk_score = emotion_analysis['risk_scores']['anxiety_risk']
                answer_record.emotional_regulation_score = emotion_analysis['risk_scores']['emotional_regulation']
                answer_record.overall_wellbeing_score = emotion_analysis['risk_scores']['overall_wellbeing']
                answer_record.analysis_summary = emotion_analysis['analysis_summary']
                
                # Mark for review if:
                # 1. Low extraction confidence
                # 2. High anxiety risk
                # 3. Low emotional regulation
                if (confidence < 0.7 or 
                    emotion_analysis['risk_scores']['anxiety_risk'] > 70 or
                    emotion_analysis['risk_scores']['emotional_regulation'] < 30):
                    answer_record.needs_review = True
                    logger.warning(f"⚠️ Answer marked for review: "
                                 f"confidence={confidence}, "
                                 f"anxiety_risk={emotion_analysis['risk_scores']['anxiety_risk']}")
                
                await session.commit()
                
                # Update assignment progress
                await self._update_assignment_progress(answer_record.assignment_id, session)
                
                logger.info(f"✅ Saved extracted answer with emotion analysis for question {answer_record.question_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving extracted answer: {e}")
            return False
    
    async def _update_assignment_progress(self, assignment_id: int, session: AsyncSession):
        """Update assignment progress when an answer is saved"""
        try:
            # Get assignment
            assignment_query = select(QuestionnaireAssignment).where(
                QuestionnaireAssignment.id == assignment_id
            )
            result = await session.execute(assignment_query)
            assignment = result.scalar_one_or_none()
            
            if assignment:
                # Count answered questions
                from sqlalchemy import func
                count_query = select(func.count(ConversationAnswer.id)).where(
                    ConversationAnswer.assignment_id == assignment_id,
                    ConversationAnswer.answered_at.isnot(None)
                )
                count_result = await session.execute(count_query)
                questions_answered = count_result.scalar() or 0
                
                # Update assignment
                assignment.questions_answered = questions_answered
                if assignment.status == 'assigned':
                    assignment.status = 'in_progress'
                    assignment.started_at = datetime.utcnow()
                
                # Check if completed
                if questions_answered >= assignment.total_questions:
                    assignment.status = 'completed'
                    assignment.completed_at = datetime.utcnow()
                    logger.info(f"🎉 Assignment {assignment_id} completed!")
                
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error updating assignment progress: {e}")


# Singleton instance
_answer_extraction_service = None

def get_answer_extraction_service() -> AnswerExtractionService:
    """Get singleton instance of AnswerExtractionService"""
    global _answer_extraction_service
    if _answer_extraction_service is None:
        _answer_extraction_service = AnswerExtractionService()
    return _answer_extraction_service









