"""
OmniCare Screener Agent
===========================

Early screening agent for caregivers/social workers/teachers focusing on
3–9 y/o motor and socio-emotional observations (non-diagnostic).
"""

from typing import List, Tuple

from ..base_agent import (
    BaseAgent,
    AgentCapability,
    AgentPersonality,
    AgentResponse,
    AgentContext,
)
from src.ai.model_manager import UrgencyLevel


class SmartKidPathScreenerAgent(BaseAgent):
    """Adult-facing early screening agent for young children."""

    def __init__(self, ai_service):
        super().__init__(
            agent_id="smartkidpath_screener",
            ai_service=ai_service,
            capabilities=[
                AgentCapability.EDUCATIONAL_SUPPORT,
                AgentCapability.WELLNESS_COACHING,
            ],
            personality=AgentPersonality.PROFESSIONAL_RESPONDER,
            primary_language="en",
        )
        self._movement_keywords = [
            "walk",
            "walking",
            "run",
            "running",
            "gait",
            "balance",
            "clumsy",
            "clumsiness",
            "toe walk",
            "toe-walk",
            "toe walking",
            "stumble",
            "fall",
            "falls",
            "trip",
            "coordination",
            "movement",
            "motor",
            "posture",
            "stand",
            "jump",
            "hop",
            "uneven",
            "limp",
            "drag",
            "stiff",
        ]
        self._child_terms = [
            "child",
            "kid",
            "son",
            "daughter",
            "boy",
            "girl",
            "k2",
            "k3",
            "p1",
            "p2",
            "p3",
            "3 year",
            "4 year",
            "5 year",
            "6 year",
            "7 year",
            "8 year",
            "9 year",
        ]
        self._urgent_indicators = ["pain", "hurt", "injury", "sudden", "cannot walk", "weakness"]

    def can_handle(self, user_input: str, context: AgentContext) -> Tuple[bool, float]:
        """
        Determine if this agent should handle the request.
        
        Triggered by movement/gait/balance questions about a young child.
        """
        text = user_input.lower()
        movement_hits = sum(1 for kw in self._movement_keywords if kw in text)
        child_hits = sum(1 for kw in self._child_terms if kw in text)

        # If user profile explicitly flags a child subject, boost confidence
        profile_age = (context.user_profile or {}).get("age_group")
        subject_child = profile_age == "child"
        total_hits = movement_hits + child_hits + (1 if subject_child else 0)

        # Don't handle if no relevant keywords found
        if total_hits == 0:
            return False, 0.0

        confidence = 0.4 + 0.15 * total_hits
        if "screen" in text or "check" in text or "video" in text:
            confidence += 0.1
        return True, min(confidence, 0.95)

    async def generate_response(self, user_input: str, context: AgentContext) -> AgentResponse:
        """
        Generate a structured OmniCare screening reply.
        """
        system_prompt = self.get_system_prompt(context)
        ai_request = self._build_ai_request(user_input, context, system_prompt)
        language = getattr(context, 'language_preference', 'en')
        ai_response = await self._generate_ai_response(ai_request, language)

        content = self._post_process_response(
            ai_response.content,
            context,
            user_input=user_input,
        )

        urgency = self.detect_urgency(user_input, context)
        red_flag = self._detect_red_flags(user_input)

        return AgentResponse(
            content=content,
            confidence=ai_response.confidence_score or 0.78,
            urgency_level=urgency,
            requires_followup=True,
            suggested_actions=self._generate_suggested_actions(red_flag),
            professional_alert_needed=red_flag and urgency in [UrgencyLevel.HIGH, UrgencyLevel.CRITICAL],
            alert_details={"reason": "movement_red_flag"} if red_flag else None,
            conversation_context={
                "agent_type": "smartkidpath_screener",
                "movement_terms": self._extract_movement_terms(user_input),
            },
        )

    def get_system_prompt(self, context: AgentContext) -> str:
        """Compose system prompt using PromptComposer with motor_screening skill."""
        from src.core.prompt_composer import get_prompt_composer

        composer = get_prompt_composer()
        return composer.compose_system_prompt(
            agent_name="smartkidpath_screener",
            context=context,
            active_skills=["motor_screening"],
        )

    def _post_process_response(self, content: str, context: AgentContext, user_input: str) -> str:
        """Apply light cultural adaptation and keep structure intact."""
        content = self.adapt_to_culture(content, context)
        return content

    def _detect_red_flags(self, user_input: str) -> bool:
        """Identify mentions that should trigger in-person care reminders."""
        text = user_input.lower()
        return any(flag in text for flag in self._urgent_indicators)

    def _generate_suggested_actions(self, red_flag: bool) -> List[str]:
        """High-level suggested actions for dashboards."""
        actions = [
            "Log key movement observations for this session",
            "Share summary with caregivers/social worker",
        ]
        if red_flag:
            actions.append("Encourage in-person review with paediatrician/therapy team promptly")
        else:
            actions.append("Plan follow-up check-in after new footage or observations")
        return actions

    def _extract_movement_terms(self, user_input: str) -> List[str]:
        """Capture movement-related keywords for context logging."""
        text = user_input.lower()
        return [kw for kw in self._movement_keywords if kw in text][:5]
