"""
Emotion Scoring Service
Analyzes user responses for emotion, tone, and mental health indicators
"""

from typing import Dict, Any, Optional
from decimal import Decimal
import re

from src.core.logging import get_logger
from src.ai.ai_service import get_ai_service

logger = get_logger(__name__)


class EmotionScoringService:
    """
    Service for analyzing user responses and scoring based on emotion/tone
    
    Analyzes:
    - Dominant emotion (happy, sad, anxious, angry, neutral, etc.)
    - Emotion intensity (0-100)
    - Anxiety risk score (0-100)
    - Emotional regulation score (0-100)
    - Overall wellbeing score (0-100)
    """
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.EmotionScoringService")
        self.ai_service = None
    
    async def initialize(self):
        """Initialize AI service"""
        if not self.ai_service:
            self.ai_service = await get_ai_service()
    
    async def analyze_response(
        self,
        user_message: str,
        question_text: str,
        question_category: str = "general",
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze user response for emotion and mental health indicators
        
        Args:
            user_message: User's response text
            question_text: The question that was asked
            question_category: Category of question (e.g., "anxiety", "mood", "social")
            conversation_context: Additional context from conversation
            
        Returns:
            Dict with emotion analysis results
        """
        try:
            await self.initialize()
            
            # Build analysis prompt
            prompt = self._build_analysis_prompt(
                user_message, 
                question_text, 
                question_category,
                conversation_context
            )
            
            # Call AI for analysis
            response = await self.ai_service.generate_response(
                prompt=prompt,
                temperature=0.3,  # Lower temperature for consistent analysis
                max_tokens=500
            )
            
            # Parse AI response
            analysis = self._parse_analysis_response(response)
            
            # Add metadata
            analysis["question_category"] = question_category
            analysis["user_message_length"] = len(user_message)
            analysis["analysis_method"] = "ai_emotion_analysis"
            
            self.logger.info(
                f"Emotion analysis completed: {analysis['dominant_emotion']} "
                f"(intensity: {analysis['emotion_intensity']}, "
                f"wellbeing: {analysis['overall_wellbeing_score']})"
            )
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing response: {e}")
            return self._get_fallback_analysis()
    
    def _build_analysis_prompt(
        self,
        user_message: str,
        question_text: str,
        question_category: str,
        conversation_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for AI emotion analysis"""
        
        context_info = ""
        if conversation_context:
            context_info = f"\n\nConversation Context:\n{conversation_context}"
        
        prompt = f"""You are a mental health assessment AI analyzing a user's response to a questionnaire question.

Question Category: {question_category}
Question Asked: "{question_text}"
User's Response: "{user_message}"{context_info}

Analyze the user's response and provide a detailed emotional and mental health assessment.

Provide your analysis in the following JSON format:
{{
    "dominant_emotion": "<emotion>",
    "emotion_intensity": <0-100>,
    "anxiety_risk_score": <0-100>,
    "emotional_regulation_score": <0-100>,
    "overall_wellbeing_score": <0-100>,
    "analysis_summary": "<brief summary>",
    "key_indicators": ["<indicator1>", "<indicator2>"],
    "concerns": ["<concern1>", "<concern2>"],
    "positive_signs": ["<sign1>", "<sign2>"]
}}

Emotion Categories: happy, sad, anxious, angry, fearful, neutral, mixed, excited, calm, frustrated, hopeless, content

Scoring Guidelines:
- emotion_intensity: 0 (no emotion) to 100 (very intense)
- anxiety_risk_score: 0 (no anxiety) to 100 (severe anxiety)
- emotional_regulation_score: 0 (poor regulation) to 100 (excellent regulation)
- overall_wellbeing_score: 0 (poor wellbeing) to 100 (excellent wellbeing)

Consider:
1. Word choice and language patterns
2. Sentence structure and coherence
3. Emotional tone and intensity
4. Signs of distress or wellbeing
5. Coping mechanisms mentioned
6. Social connection indicators
7. Cultural context (Hong Kong)

Respond ONLY with the JSON object, no additional text."""
        
        return prompt
    
    def _parse_analysis_response(self, ai_response: str) -> Dict[str, Any]:
        """Parse AI response into structured analysis"""
        try:
            import json
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
            if json_match:
                analysis_data = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in AI response")
            
            # Validate and convert to proper types
            result = {
                "dominant_emotion": str(analysis_data.get("dominant_emotion", "neutral")),
                "emotion_intensity": Decimal(str(min(100, max(0, float(analysis_data.get("emotion_intensity", 50)))))),
                "anxiety_risk_score": Decimal(str(min(100, max(0, float(analysis_data.get("anxiety_risk_score", 50)))))),
                "emotional_regulation_score": Decimal(str(min(100, max(0, float(analysis_data.get("emotional_regulation_score", 50)))))),
                "overall_wellbeing_score": Decimal(str(min(100, max(0, float(analysis_data.get("overall_wellbeing_score", 50)))))),
                "analysis_summary": str(analysis_data.get("analysis_summary", ""))[:500],
                "key_indicators": analysis_data.get("key_indicators", [])[:10],
                "concerns": analysis_data.get("concerns", [])[:10],
                "positive_signs": analysis_data.get("positive_signs", [])[:10]
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error parsing analysis response: {e}")
            return self._get_fallback_analysis()
    
    def _get_fallback_analysis(self) -> Dict[str, Any]:
        """Return fallback analysis if AI analysis fails"""
        return {
            "dominant_emotion": "neutral",
            "emotion_intensity": Decimal("50.00"),
            "anxiety_risk_score": Decimal("50.00"),
            "emotional_regulation_score": Decimal("50.00"),
            "overall_wellbeing_score": Decimal("50.00"),
            "analysis_summary": "Unable to complete detailed analysis",
            "key_indicators": [],
            "concerns": [],
            "positive_signs": []
        }
    
    def calculate_question_score(
        self,
        analysis: Dict[str, Any],
        question_type: str = "scale"
    ) -> Optional[int]:
        """
        Calculate a numeric score for the question based on emotion analysis
        
        Args:
            analysis: Emotion analysis result
            question_type: Type of question (scale, yes_no, short_answer)
            
        Returns:
            Numeric score (typically 1-5 for scale questions)
        """
        try:
            # For scale questions, derive score from wellbeing
            if question_type == "scale":
                wellbeing = float(analysis.get("overall_wellbeing_score", 50))
                # Map 0-100 wellbeing to 1-5 scale
                score = int((wellbeing / 100) * 4) + 1
                return max(1, min(5, score))
            
            # For yes/no questions
            elif question_type == "yes_no":
                wellbeing = float(analysis.get("overall_wellbeing_score", 50))
                return 1 if wellbeing >= 50 else 0
            
            # For short answer, return None (no numeric score)
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error calculating question score: {e}")
            return None


# Singleton instance
_emotion_scoring_service = None


async def get_emotion_scoring_service() -> EmotionScoringService:
    """Get singleton emotion scoring service instance"""
    global _emotion_scoring_service
    if _emotion_scoring_service is None:
        _emotion_scoring_service = EmotionScoringService()
        await _emotion_scoring_service.initialize()
    return _emotion_scoring_service
