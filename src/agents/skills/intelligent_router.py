"""
Intelligent Skill Router

Uses AI to intelligently determine which skill should handle a message,
rather than relying only on keyword matching.

This provides more accurate skill selection based on:
- Understanding message context and intent
- Recognizing emotional undertones
- Handling ambiguous or complex messages
- Supporting bilingual (EN/ZH) understanding
"""

import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from src.core.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


@dataclass
class SkillDecision:
    """Result of AI skill routing decision"""
    name: str
    confidence: float
    reason: str


@dataclass  
class RoutingResult:
    """Complete routing result from AI"""
    skills: List[SkillDecision]
    primary_skill: str
    crisis_detected: bool
    analysis: str
    raw_response: Optional[str] = None


class IntelligentSkillRouter:
    """
    AI-powered skill router that uses LLM to intelligently
    determine the best skill(s) for handling a message.
    
    Features:
    - Context-aware routing (understands nuance)
    - Bilingual support (EN + ZH-HK)
    - Crisis detection with high sensitivity
    - Multi-skill activation when appropriate
    - Fallback to keyword matching if AI fails
    """
    
    def __init__(self, ai_service=None):
        """
        Initialize the intelligent router.
        
        Args:
            ai_service: AI service for making LLM calls
        """
        self.ai_service = ai_service
        self._router_prompt = None
        self._load_prompt()
    
    def _load_prompt(self):
        """Load the skill router prompt from file"""
        self._router_prompt = load_prompt(
            "system/skill_router",
            default=self._get_fallback_prompt()
        )
    
    def _get_fallback_prompt(self) -> str:
        """Fallback prompt if file not found"""
        return """Analyze this message and determine which skill to use.
Skills: safety_crisis, mental_health, physical_health, social_support, sleep_support, wellness_coaching
Respond with JSON: {"primary_skill": "skill_name", "confidence": 0.8, "crisis_detected": false}"""
    
    async def route(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        multimodal: Optional[Dict[str, Any]] = None
    ) -> RoutingResult:
        """
        Use AI to determine the best skill(s) for this message.
        
        Args:
            message: User message to analyze
            context: Optional conversation context
            multimodal: Optional multimodal signals (emotion, movement)
            
        Returns:
            RoutingResult with skill decisions
        """
        if not self.ai_service:
            logger.warning("No AI service - falling back to default routing")
            return self._fallback_routing(message)
        
        try:
            # Build the routing prompt
            full_prompt = f"{self._router_prompt}\n\nUser message: \"{message}\""
            
            # Add multimodal context if available
            if multimodal:
                emotion = multimodal.get('emotion', {})
                movement = multimodal.get('movement', {})
                if emotion or movement:
                    full_prompt += "\n\nMultimodal context:"
                    if emotion:
                        full_prompt += f"\n- Detected emotion: {emotion.get('emotion', 'unknown')} (intensity: {emotion.get('intensity', 0)}/5)"
                    if movement:
                        full_prompt += f"\n- Energy level: {movement.get('energy_level', 'unknown')}"
            
            # Call AI for routing decision using process_request
            from src.ai.ai_service import AIRequest
            
            request = AIRequest(
                user_input=full_prompt,
                system_prompt="You are a skill router. Analyze the message and return JSON only.",
                agent_type="router",
                content_type="routing"
            )
            
            response = await self.ai_service.process_request(request)
            
            if response and response.content:
                return self._parse_routing_response(response.content, message)
            else:
                return self._fallback_routing(message)
            
        except Exception as e:
            logger.error(f"AI routing failed: {e}, falling back to keyword routing")
            return self._fallback_routing(message)
    
    def _parse_routing_response(self, response: str, message: str) -> RoutingResult:
        """
        Parse the AI's JSON response.
        
        Args:
            response: Raw AI response
            message: Original message (for fallback)
            
        Returns:
            Parsed RoutingResult
        """
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            
            data = json.loads(json_str.strip())
            
            # Parse skills
            skills = []
            for skill_data in data.get("skills", []):
                skills.append(SkillDecision(
                    name=skill_data.get("name", "wellness_coaching"),
                    confidence=float(skill_data.get("confidence", 0.5)),
                    reason=skill_data.get("reason", "")
                ))
            
            # If no skills parsed, use primary_skill
            if not skills and data.get("primary_skill"):
                skills.append(SkillDecision(
                    name=data["primary_skill"],
                    confidence=float(data.get("confidence", 0.8)),
                    reason=data.get("analysis", "AI routing decision")
                ))
            
            return RoutingResult(
                skills=skills if skills else [SkillDecision("wellness_coaching", 0.5, "default")],
                primary_skill=data.get("primary_skill", skills[0].name if skills else "wellness_coaching"),
                crisis_detected=data.get("crisis_detected", False),
                analysis=data.get("analysis", ""),
                raw_response=response
            )
            
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(f"Failed to parse AI routing response: {e}")
            logger.debug(f"Raw response: {response}")
            return self._fallback_routing(message)
    
    def _fallback_routing(self, message: str) -> RoutingResult:
        """
        Fallback keyword-based routing when AI is unavailable.
        
        Args:
            message: User message
            
        Returns:
            Basic routing result
        """
        message_lower = message.lower()
        
        # Crisis keywords (highest priority)
        crisis_keywords = ["suicide", "kill myself", "want to die", "自殺", "想死", "唔想活", "end my life", "hurt myself"]
        for kw in crisis_keywords:
            if kw in message_lower or kw in message:
                return RoutingResult(
                    skills=[SkillDecision("safety_crisis", 1.0, "Crisis keyword detected")],
                    primary_skill="safety_crisis",
                    crisis_detected=True,
                    analysis="Crisis keyword detected in message"
                )
        
        # Mental health keywords
        mental_keywords = ["sad", "depressed", "anxious", "stressed", "lonely", "傷心", "難過", "焦慮", "壓力"]
        for kw in mental_keywords:
            if kw in message_lower or kw in message:
                return RoutingResult(
                    skills=[SkillDecision("mental_health", 0.8, "Emotional content detected")],
                    primary_skill="mental_health",
                    crisis_detected=False,
                    analysis="Mental health related content"
                )
        
        # Physical health keywords
        physical_keywords = ["sick", "pain", "hurt", "fever", "doctor", "病", "痛", "發燒", "醫生"]
        for kw in physical_keywords:
            if kw in message_lower or kw in message:
                return RoutingResult(
                    skills=[SkillDecision("physical_health", 0.8, "Physical symptom mentioned")],
                    primary_skill="physical_health",
                    crisis_detected=False,
                    analysis="Physical health related content"
                )
        
        # Sleep keywords
        sleep_keywords = ["sleep", "tired", "insomnia", "nightmare", "瞓", "攰", "失眠"]
        for kw in sleep_keywords:
            if kw in message_lower or kw in message:
                return RoutingResult(
                    skills=[SkillDecision("sleep_support", 0.8, "Sleep issue mentioned")],
                    primary_skill="sleep_support",
                    crisis_detected=False,
                    analysis="Sleep related content"
                )
        
        # Social keywords
        social_keywords = ["friend", "family", "bully", "lonely", "朋友", "家人", "欺凌"]
        for kw in social_keywords:
            if kw in message_lower or kw in message:
                return RoutingResult(
                    skills=[SkillDecision("social_support", 0.8, "Social issue mentioned")],
                    primary_skill="social_support",
                    crisis_detected=False,
                    analysis="Social/relationship related content"
                )
        
        # Default to wellness coaching
        return RoutingResult(
            skills=[SkillDecision("wellness_coaching", 0.5, "General conversation")],
            primary_skill="wellness_coaching",
            crisis_detected=False,
            analysis="General wellness conversation"
        )


# Singleton instance
_router_instance: Optional[IntelligentSkillRouter] = None


def get_intelligent_router(ai_service=None) -> IntelligentSkillRouter:
    """Get or create the intelligent router singleton"""
    global _router_instance
    if _router_instance is None:
        _router_instance = IntelligentSkillRouter(ai_service)
    elif ai_service and not _router_instance.ai_service:
        _router_instance.ai_service = ai_service
    return _router_instance


def reset_intelligent_router():
    """Reset the singleton (for testing)"""
    global _router_instance
    _router_instance = None

