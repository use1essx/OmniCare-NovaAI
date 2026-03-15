"""
Answer Extraction Service
Uses AI to extract structured answers from natural conversation
"""

import logging
import json
import re
from typing import Dict, Any, Optional, List

from src.ai.unified_ai_client import AIRequest
from src.ai.providers.nova_bedrock_client import get_nova_client

logger = logging.getLogger(__name__)


class AnswerExtractionService:
    """
    Service to extract questionnaire answers from natural conversation using AI.
    Analyzes user responses and maps them to structured questionnaire answers.
    """
    
    def __init__(self):
        """Initialize answer extraction service with Nova client"""
        try:
            self.nova_client = get_nova_client()
            logger.info("✅ Nova client initialized for answer extraction")
        except Exception as e:
            logger.warning(f"⚠️ Nova client initialization failed: {e} - falling back to pattern matching")
            self.nova_client = None
    
    async def extract_answer(
        self,
        question: Dict[str, Any],
        user_message: str,
        conversation_context: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Extract answer from user's conversational response.
        
        Args:
            question: Question dict with text, type, options
            user_message: User's natural language response
            conversation_context: Recent conversation messages for context
            
        Returns:
            {
                "text": extracted answer text,
                "value": extracted numeric value (for scale/rating),
                "confidence": 0.0-1.0 confidence score,
                "method": extraction method used,
                "notes": explanation of extraction
            }
        """
        
        question_type = question.get("question_type", "short_answer")
        question_text = question.get("question_text", "")
        
        # Use different extraction strategies based on question type
        if question_type in ["scale", "rating"]:
            return await self._extract_scale_answer(question, user_message, conversation_context)
        elif question_type == "yes_no":
            return await self._extract_yes_no_answer(question, user_message, conversation_context)
        elif question_type == "multiple_choice":
            return await self._extract_multiple_choice_answer(question, user_message, conversation_context)
        else:
            return await self._extract_text_answer(question, user_message, conversation_context)
    
    async def _extract_scale_answer(
        self,
        question: Dict[str, Any],
        user_message: str,
        conversation_context: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Extract numeric scale/rating answer"""
        
        # Try simple pattern matching first
        numbers = re.findall(r'\b([0-9]|10)\b', user_message)
        if numbers:
            value = int(numbers[0])
            return {
                "text": user_message,
                "value": value,
                "confidence": 0.85,
                "method": "pattern_match",
                "notes": f"Found numeric value {value} in response"
            }
        
        # Try keyword matching for qualitative responses
        qualitative_map = {
            "never": 1,
            "rarely": 2,
            "sometimes": 3,
            "often": 4,
            "always": 5,
            "not at all": 1,
            "a little": 2,
            "moderately": 3,
            "quite a bit": 4,
            "extremely": 5,
            "very bad": 1,
            "bad": 2,
            "okay": 3,
            "good": 4,
            "very good": 5,
            "excellent": 5
        }
        
        user_lower = user_message.lower()
        for keyword, value in qualitative_map.items():
            if keyword in user_lower:
                return {
                    "text": user_message,
                    "value": value,
                    "confidence": 0.75,
                    "method": "keyword_match",
                    "notes": f"Matched keyword '{keyword}' to value {value}"
                }
        
        # Fall back to AI extraction
        return await self._ai_extract_answer(question, user_message, conversation_context)
    
    async def _extract_yes_no_answer(
        self,
        question: Dict[str, Any],
        user_message: str,
        conversation_context: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Extract yes/no answer"""
        
        user_lower = user_message.lower()
        
        # Positive indicators
        yes_keywords = ["yes", "yeah", "yep", "sure", "definitely", "absolutely", "correct", "right", "agree", "true"]
        no_keywords = ["no", "nope", "nah", "not", "never", "disagree", "false", "incorrect", "wrong"]
        
        yes_count = sum(1 for kw in yes_keywords if kw in user_lower)
        no_count = sum(1 for kw in no_keywords if kw in user_lower)
        
        if yes_count > no_count:
            return {
                "text": "Yes",
                "value": 1,
                "confidence": 0.80,
                "method": "keyword_match",
                "notes": f"Detected affirmative response (yes keywords: {yes_count})"
            }
        elif no_count > yes_count:
            return {
                "text": "No",
                "value": 0,
                "confidence": 0.80,
                "method": "keyword_match",
                "notes": f"Detected negative response (no keywords: {no_count})"
            }
        
        # Ambiguous - use AI
        return await self._ai_extract_answer(question, user_message, conversation_context)
    
    async def _extract_multiple_choice_answer(
        self,
        question: Dict[str, Any],
        user_message: str,
        conversation_context: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Extract multiple choice answer"""
        
        options = question.get("options", [])
        if not options:
            return await self._extract_text_answer(question, user_message, conversation_context)
        
        # Try to match user response to one of the options
        user_lower = user_message.lower()
        best_match = None
        best_score = 0
        
        for option in options:
            option_text = option.get("option_text", "").lower()
            # Simple substring matching
            if option_text in user_lower or user_lower in option_text:
                match_score = len(option_text) / (len(user_lower) + 1)
                if match_score > best_score:
                    best_score = match_score
                    best_match = option
        
        if best_match and best_score > 0.3:
            return {
                "text": best_match.get("option_text"),
                "value": best_match.get("option_value"),
                "confidence": min(0.95, best_score + 0.5),
                "method": "option_match",
                "notes": f"Matched to option: {best_match.get('option_text')}"
            }
        
        # Fall back to AI
        return await self._ai_extract_answer(question, user_message, conversation_context)
    
    async def _extract_text_answer(
        self,
        question: Dict[str, Any],
        user_message: str,
        conversation_context: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Extract free-text answer"""
        
        # For short answer questions, the user's message IS the answer
        return {
            "text": user_message,
            "value": None,
            "confidence": 0.90,
            "method": "direct_text",
            "notes": "User's response captured as-is"
        }
    
    async def _ai_extract_answer(
        self,
        question: Dict[str, Any],
        user_message: str,
        conversation_context: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Use AI to extract answer when simple methods fail.
        Uses Nova for complex extraction.
        """
        
        # SECURITY: Input validation
        if not user_message or len(user_message) > 10000:
            logger.warning("Invalid user message length")
            return self._fallback_result(user_message)
        
        if not self.nova_client:
            logger.warning("Nova client not available, using fallback")
            return self._fallback_result(user_message)
        
        try:
            # Build context
            context_str = ""
            if conversation_context:
                context_str = "\n".join([
                    f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                    for msg in conversation_context[-5:]  # Last 5 messages
                ])
            
            # Build extraction prompt
            question_type = question.get("question_type", "short_answer")
            question_text = question.get("question_text", "")
            options_str = ""
            
            if question.get("options"):
                options_str = "\nAvailable options:\n" + "\n".join([
                    f"- {opt.get('option_text')} (value: {opt.get('option_value')})"
                    for opt in question["options"]
                ])
            
            prompt = f"""You are an expert at extracting structured answers from natural conversation.

Question Type: {question_type}
Question: {question_text}
{options_str}

Recent Conversation:
{context_str}

User's Response: "{user_message}"

Extract the answer from the user's response. Return a JSON object with:
- "text": The extracted answer as text
- "value": Numeric value if applicable (for scale/rating/multiple choice)
- "confidence": Your confidence (0.0-1.0)
- "notes": Brief explanation of your extraction

Be lenient and interpret natural language. If the answer is unclear, set confidence below 0.6.

Return ONLY the JSON object, no other text."""
            
            # Use Nova client for extraction
            request = AIRequest(
                system_prompt="You are a helpful assistant that extracts structured data from conversations. Always respond with valid JSON.",
                user_prompt=prompt,
                task_type="answer_extraction",
                temperature=0.3,
                max_tokens=500
            )
            
            response = await self.nova_client.make_request(request=request)
            
            if not response or not response.content:
                logger.error("Empty response from Nova client")
                return self._fallback_result(user_message)
            
            # Try to parse JSON from response
            try:
                # Extract JSON if wrapped in markdown
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response.content, re.DOTALL)
                if json_match:
                    ai_response = json_match.group(1)
                else:
                    ai_response = response.content
                
                extracted = json.loads(ai_response)
                extracted["method"] = "ai_parse"
                return extracted
            except json.JSONDecodeError:
                logger.warning(f"AI response not valid JSON: {response.content}")
                return self._fallback_result(user_message)
            
        except Exception as e:
            logger.error(f"AI extraction failed: {e}")
            return self._fallback_result(user_message)
    
    def _fallback_result(self, user_message: str) -> Dict[str, Any]:
        """Return fallback result when AI extraction fails"""
        return {
            "text": user_message,
            "value": None,
            "confidence": 0.40,
            "method": "fallback",
            "notes": "Could not extract structured answer, using raw response"
        }
    
    def should_ask_clarification(self, extraction_result: Dict[str, Any]) -> bool:
        """Determine if we should ask for clarification based on extraction confidence"""
        confidence = extraction_result.get("confidence", 0.0)
        return confidence < 0.60
    
    def generate_clarification_question(
        self,
        question: Dict[str, Any],
        extraction_result: Dict[str, Any]
    ) -> str:
        """Generate a natural clarification question"""
        
        question_text = question.get("question_text", "")
        question_type = question.get("question_type", "")
        
        if question_type in ["scale", "rating"]:
            return f"Just to clarify, on a scale from 1 to 5, how would you rate that?"
        elif question_type == "yes_no":
            return f"So, would that be a yes or no?"
        elif question_type == "multiple_choice":
            options = question.get("options", [])
            if options:
                options_text = ", ".join([opt.get("option_text") for opt in options[:3]])
                return f"Could you clarify? Would you say it's more like: {options_text}?"
        
        return "Could you tell me a bit more about that?"










