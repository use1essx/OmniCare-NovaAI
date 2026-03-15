"""
Agent Orchestrator - Healthcare AI V2
====================================

Intelligent agent routing and orchestration system based on patterns from the
reference system. Implements smart agent detection, intent analysis, urgency
assessment, and emergency override mechanisms.

Key Features:
- Intent analysis and agent selection
- Confidence scoring for agent routing
- Emergency override mechanisms
- Multi-agent collaboration
- Conversation flow management
- Professional alert coordination
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio
import logging

from .base_agent import BaseAgent, AgentContext, AgentResponse, AgentCapability
from .specialized.illness_monitor import IllnessMonitorAgent
from .specialized.mental_health import MentalHealthAgent
from .specialized.safety_guardian import SafetyGuardianAgent
from .specialized.wellness_coach import WellnessCoachAgent
from .specialized.smartkidpath_screener import SmartKidPathScreenerAgent
from src.ai.ai_service import HealthcareAIService


class AgentSelectionStrategy(Enum):
    """Agent selection strategies."""
    CONFIDENCE_BASED = "confidence_based"
    URGENCY_OVERRIDE = "urgency_override"
    MULTI_AGENT = "multi_agent"
    MANUAL_SELECTION = "manual_selection"
    AI_ROUTING = "ai_routing"  # Intelligent AI-powered routing


@dataclass
class AgentScore:
    """Agent scoring for selection."""
    agent_id: str
    confidence: float
    reasons: List[str]
    capabilities_match: List[AgentCapability]
    urgency_factor: float


@dataclass
class OrchestrationResult:
    """Result of agent orchestration."""
    selected_agent: str
    selection_strategy: AgentSelectionStrategy
    confidence: float
    alternative_agents: List[str]
    reasons: List[str]
    emergency_override: bool
    multi_agent_needed: bool


class AgentOrchestrator:
    """
    Intelligent agent routing and orchestration system.
    
    Uses AI-powered intelligent routing to select the best agent
    based on message understanding, not just keywords.
    
    Features:
    - AI-powered intelligent routing (primary)
    - Keyword-based fallback
    - Emergency override for crisis detection
    - Multi-agent collaboration support
    """
    
    # Feature flag for AI routing
    USE_AI_ROUTING = True
    
    def __init__(self, ai_service: HealthcareAIService):
        """
        Initialize Agent Orchestrator.
        
        Args:
            ai_service: AI service for agent initialization
        """
        self.ai_service = ai_service
        self.logger = logging.getLogger("agent.orchestrator")
        
        # Initialize intelligent router
        self._intelligent_router = None
        
        # Initialize all agents
        self.agents: Dict[str, BaseAgent] = {
            # "illness_monitor": IllnessMonitorAgent(ai_service),  # Disabled for teen/kid focus
            "mental_health": MentalHealthAgent(ai_service),
            "safety_guardian": SafetyGuardianAgent(ai_service),
            "wellness_coach": WellnessCoachAgent(ai_service),
            "smartkidpath_screener": SmartKidPathScreenerAgent(ai_service)
        }
        
        # Map skill names to agent names (for AI routing compatibility)
        self.skill_to_agent_map = {
            "safety_crisis": "safety_guardian",
            "mental_health": "mental_health",
            "physical_health": "wellness_coach",  # Remapped from illness_monitor
            "wellness_coaching": "wellness_coach",
            "sleep_support": "mental_health",  # Mental health handles sleep
            "social_support": "mental_health",  # Mental health handles social
            "motor_screening": "smartkidpath_screener",
        }
        
        # Agent priority for emergency situations
        self.emergency_priority = [
            "safety_guardian",
            # "illness_monitor",  # Disabled
            "mental_health",
            "wellness_coach",
            "smartkidpath_screener"
        ]
        
        # Configuration
        self.confidence_threshold = 0.6
        self.emergency_confidence_threshold = 0.4  # Lower threshold for emergencies
        self.multi_agent_threshold = 0.8  # When multiple agents score high
        
    async def route_request(
        self, 
        user_input: str, 
        context: AgentContext,
        preferred_agent: Optional[str] = None
    ) -> Tuple[BaseAgent, OrchestrationResult]:
        """
        Route user request to the most appropriate agent.
        
        Uses AI-powered intelligent routing when available,
        falling back to keyword-based detection.
        
        Args:
            user_input: User's message
            context: Conversation context
            preferred_agent: Manually specified agent preference
            
        Returns:
            Tuple of (selected_agent, orchestration_result)
        """
        self.logger.info(f"Routing request: {user_input[:100]}...")
        
        # Manual selection takes priority
        if preferred_agent and preferred_agent in self.agents:
            self.logger.info(f"Manual agent selection: {preferred_agent}")
            return self.agents[preferred_agent], OrchestrationResult(
                selected_agent=preferred_agent,
                selection_strategy=AgentSelectionStrategy.MANUAL_SELECTION,
                confidence=1.0,
                alternative_agents=[],
                reasons=[f"Manually selected {preferred_agent}"],
                emergency_override=False,
                multi_agent_needed=False
            )
        
        # Try AI-powered intelligent routing first
        if self.USE_AI_ROUTING:
            try:
                ai_result = await self._route_with_ai(user_input, context)
                if ai_result:
                    self.logger.info(f"🤖 AI routing selected: {ai_result.selected_agent} (confidence: {ai_result.confidence:.2f})")
                    return self.agents[ai_result.selected_agent], ai_result
            except Exception as e:
                self.logger.warning(f"AI routing failed, falling back to keyword routing: {e}")
        
        # Fallback: Evaluate all agents with keyword matching
        agent_scores = await self._evaluate_agents(user_input, context)
        
        # Check for emergency situations first
        emergency_result = self._check_emergency_override(agent_scores, user_input, context)
        if emergency_result:
            self.logger.warning(f"Emergency override activated: {emergency_result.selected_agent}")
            return self.agents[emergency_result.selected_agent], emergency_result
        
        # Standard agent selection
        orchestration_result = self._select_best_agent(agent_scores, user_input, context)
        selected_agent = self.agents[orchestration_result.selected_agent]
        
        self.logger.info(
            f"Selected agent: {orchestration_result.selected_agent} "
            f"(confidence: {orchestration_result.confidence:.2f})"
        )
        
        return selected_agent, orchestration_result
    
    async def _route_with_ai(
        self,
        user_input: str,
        context: AgentContext
    ) -> Optional[OrchestrationResult]:
        """
        Use AI to intelligently route the request.
        
        Args:
            user_input: User's message
            context: Conversation context
            
        Returns:
            OrchestrationResult if successful, None otherwise
        """
        from .skills.intelligent_router import IntelligentSkillRouter
        
        # Get or create intelligent router
        if self._intelligent_router is None:
            self._intelligent_router = IntelligentSkillRouter(self.ai_service)
        
        # Route with AI
        routing_result = await self._intelligent_router.route(user_input)
        
        if not routing_result.skills:
            return None
        
        # Map skill to agent
        primary_skill = routing_result.primary_skill
        agent_name = self.skill_to_agent_map.get(primary_skill, "wellness_coach")
        
        # Make sure agent exists
        if agent_name not in self.agents:
            agent_name = "wellness_coach"
        
        return OrchestrationResult(
            selected_agent=agent_name,
            selection_strategy=AgentSelectionStrategy.AI_ROUTING,
            confidence=routing_result.skills[0].confidence,
            alternative_agents=[
                self.skill_to_agent_map.get(s.name, s.name) 
                for s in routing_result.skills[1:3]
            ],
            reasons=[f"AI analysis: {routing_result.analysis}"] + [
                f"{s.name}: {s.reason}" for s in routing_result.skills
            ],
            emergency_override=routing_result.crisis_detected,
            multi_agent_needed=len(routing_result.skills) > 1
        )
    
    async def _evaluate_agents(
        self, 
        user_input: str, 
        context: AgentContext
    ) -> List[AgentScore]:
        """
        Evaluate all agents for their ability to handle the request.
        
        Args:
            user_input: User's message
            context: Conversation context
            
        Returns:
            List of agent scores sorted by confidence
        """
        scores = []
        
        # Evaluate each agent in parallel
        evaluation_tasks = []
        for agent_id, agent in self.agents.items():
            task = self._evaluate_single_agent(agent_id, agent, user_input, context)
            evaluation_tasks.append(task)
        
        agent_evaluations = await asyncio.gather(*evaluation_tasks)
        
        # Process results
        for agent_id, evaluation in zip(self.agents.keys(), agent_evaluations):
            can_handle, confidence, reasons, capabilities = evaluation
            
            if can_handle:
                # Apply urgency factor
                urgency_factor = self._calculate_urgency_factor(user_input, context)
                
                scores.append(AgentScore(
                    agent_id=agent_id,
                    confidence=confidence,
                    reasons=reasons,
                    capabilities_match=capabilities,
                    urgency_factor=urgency_factor
                ))
        
        # Sort by confidence (descending)
        scores.sort(key=lambda x: x.confidence, reverse=True)
        
        return scores
    
    async def _evaluate_single_agent(
        self, 
        agent_id: str, 
        agent: BaseAgent, 
        user_input: str, 
        context: AgentContext
    ) -> Tuple[bool, float, List[str], List[AgentCapability]]:
        """
        Evaluate a single agent's capability to handle the request.
        
        Args:
            agent_id: Agent identifier
            agent: Agent instance
            user_input: User's message
            context: Conversation context
            
        Returns:
            Tuple of (can_handle, confidence, reasons, capabilities)
        """
        try:
            can_handle, confidence = agent.can_handle(user_input, context)
            
            if can_handle:
                # Analyze reasons based on agent type and input
                reasons = self._analyze_selection_reasons(agent, user_input, context)
                
                # Get matching capabilities
                capabilities = self._get_matching_capabilities(agent, user_input, context)
                
                return True, confidence, reasons, capabilities
            else:
                return False, 0.0, ["Cannot handle this type of request"], []
                
        except Exception as e:
            self.logger.error(f"Error evaluating agent {agent_id}: {e}")
            return False, 0.0, [f"Evaluation error: {str(e)}"], []
    
    def _analyze_selection_reasons(
        self, 
        agent: BaseAgent, 
        user_input: str, 
        context: AgentContext
    ) -> List[str]:
        """
        Analyze reasons why an agent is suitable for the request.
        
        Args:
            agent: Agent instance
            user_input: User's message
            context: Conversation context
            
        Returns:
            List of reasons for selection
        """
        reasons = []
        user_input_lower = user_input.lower()
        
        # Agent-specific reason analysis
        if agent.agent_id == "illness_monitor":
            if any(word in user_input_lower for word in ["pain", "痛", "sick", "病", "medication", "藥"]):
                reasons.append("Physical health symptoms or medication concerns detected")
            if context.user_profile.get("age_group") == "elderly":
                reasons.append("Elderly user profile matches illness monitoring specialization")
        
        elif agent.agent_id == "mental_health":
            if any(word in user_input_lower for word in ["stress", "壓力", "anxiety", "焦慮", "sad", "傷心"]):
                reasons.append("Mental health or emotional concerns identified")
            if context.user_profile.get("age_group") in ["child", "teen"]:
                reasons.append("Child/teen profile matches mental health specialization")
        
        elif agent.agent_id == "safety_guardian":
            if any(word in user_input_lower for word in ["emergency", "緊急", "救命", "urgent", "急"]):
                reasons.append("Emergency or crisis keywords detected")
        
        elif agent.agent_id == "wellness_coach":
            if any(word in user_input_lower for word in ["healthy", "健康", "improve", "改善", "prevent", "預防"]):
                reasons.append("Health improvement or prevention focus identified")

        elif agent.agent_id == "smartkidpath_screener":
            movement_terms = ["walk", "gait", "balance", "clumsy", "toe walk", "toe-walk", "toe walking", "run", "stumble", "trip"]
            child_terms = ["child", "kid", "son", "daughter", "p1", "p2", "p3", "k2", "k3"]
            if any(term in user_input_lower for term in movement_terms):
                reasons.append("Movement/gait screening keywords detected")
            if any(term in user_input_lower for term in child_terms) or context.user_profile.get("age_group") == "child":
                reasons.append("Child-focused screening context identified")
        
        # Add capability-based reasons
        for capability in agent.capabilities:
            if self._input_matches_capability(user_input, capability):
                reasons.append(f"Matches {capability.value} capability")
        
        return reasons
    
    def _get_matching_capabilities(
        self, 
        agent: BaseAgent, 
        user_input: str, 
        context: AgentContext
    ) -> List[AgentCapability]:
        """
        Get agent capabilities that match the user input.
        
        Args:
            agent: Agent instance
            user_input: User's message
            context: Conversation context
            
        Returns:
            List of matching capabilities
        """
        matching_capabilities = []
        
        for capability in agent.capabilities:
            if self._input_matches_capability(user_input, capability):
                matching_capabilities.append(capability)
        
        return matching_capabilities
    
    def _input_matches_capability(self, user_input: str, capability: AgentCapability) -> bool:
        """
        Check if user input matches a specific capability.
        
        Args:
            user_input: User's message
            capability: Agent capability to check
            
        Returns:
            True if input matches capability
        """
        user_input_lower = user_input.lower()
        
        capability_keywords = {
            AgentCapability.ILLNESS_MONITORING: ["illness", "病", "symptom", "症狀", "health", "健康"],
            AgentCapability.MENTAL_HEALTH_SUPPORT: ["mental", "心理", "emotion", "情緒", "stress", "壓力"],
            AgentCapability.EMERGENCY_RESPONSE: ["emergency", "緊急", "crisis", "危機", "urgent", "急"],
            AgentCapability.WELLNESS_COACHING: ["wellness", "保健", "healthy", "健康", "improve", "改善"],
            AgentCapability.MEDICATION_GUIDANCE: ["medication", "藥物", "drug", "藥", "prescription", "處方"],
            AgentCapability.CHRONIC_DISEASE_MANAGEMENT: ["diabetes", "糖尿病", "hypertension", "高血壓", "chronic", "慢性"],
            AgentCapability.CRISIS_INTERVENTION: ["suicide", "自殺", "crisis", "危機", "self-harm", "自傷"],
            AgentCapability.EDUCATIONAL_SUPPORT: ["learn", "學習", "understand", "了解", "explain", "解釋"]
        }
        
        keywords = capability_keywords.get(capability, [])
        return any(keyword in user_input_lower for keyword in keywords)
    
    def _calculate_urgency_factor(self, user_input: str, context: AgentContext) -> float:
        """
        Calculate urgency factor to boost agent confidence for urgent situations.
        
        Args:
            user_input: User's message
            context: Conversation context
            
        Returns:
            Urgency factor (0.0 - 1.0)
        """
        user_input_lower = user_input.lower()
        
        # Critical urgency indicators
        critical_indicators = [
            "emergency", "緊急", "urgent", "急", "help", "救命",
            "can't breathe", "唔可以呼吸", "chest pain", "胸痛",
            "suicide", "自殺", "dying", "快死"
        ]
        
        if any(indicator in user_input_lower for indicator in critical_indicators):
            return 1.0
        
        # High urgency indicators
        high_indicators = [
            "severe", "嚴重", "very worried", "好擔心", "crisis", "危機",
            "can't sleep", "瞓唔到", "pain", "痛"
        ]
        
        if any(indicator in user_input_lower for indicator in high_indicators):
            return 0.7
        
        # Medium urgency indicators
        medium_indicators = [
            "worried", "擔心", "concerned", "關心", "uncomfortable", "唔舒服"
        ]
        
        if any(indicator in user_input_lower for indicator in medium_indicators):
            return 0.4
        
        return 0.0
    
    def _check_emergency_override(
        self, 
        agent_scores: List[AgentScore], 
        user_input: str, 
        context: AgentContext
    ) -> Optional[OrchestrationResult]:
        """
        Check if emergency override should activate Safety Guardian.
        
        Args:
            agent_scores: Current agent scores
            user_input: User's message
            context: Conversation context
            
        Returns:
            Emergency orchestration result if override needed
        """
        # Check for critical emergency keywords
        critical_keywords = [
            "emergency", "緊急", "suicide", "自殺", "救命",
            "can't breathe", "唔可以呼吸", "chest pain", "胸痛",
            "overdose", "服藥過量", "dying", "快死"
        ]
        
        user_input_lower = user_input.lower()
        emergency_detected = any(keyword in user_input_lower for keyword in critical_keywords)
        
        if emergency_detected:
            # Check if safety guardian already scored highest
            if agent_scores and agent_scores[0].agent_id == "safety_guardian":
                # Safety guardian already selected normally
                return None
            
            # Emergency override to safety guardian
            return OrchestrationResult(
                selected_agent="safety_guardian",
                selection_strategy=AgentSelectionStrategy.URGENCY_OVERRIDE,
                confidence=0.95,
                alternative_agents=[score.agent_id for score in agent_scores[:2]],
                reasons=["Emergency keywords detected - safety override activated"],
                emergency_override=True,
                multi_agent_needed=False
            )
        
        return None
    
    def _select_best_agent(
        self, 
        agent_scores: List[AgentScore], 
        user_input: str, 
        context: AgentContext
    ) -> OrchestrationResult:
        """
        Select the best agent based on scores and context.
        
        Args:
            agent_scores: Agent scores
            user_input: User's message
            context: Conversation context
            
        Returns:
            Orchestration result
        """
        if not agent_scores:
            # Fallback to wellness coach for general health questions
            return OrchestrationResult(
                selected_agent="wellness_coach",
                selection_strategy=AgentSelectionStrategy.CONFIDENCE_BASED,
                confidence=0.5,
                alternative_agents=[],
                reasons=["No agents matched - using wellness coach as fallback"],
                emergency_override=False,
                multi_agent_needed=False
            )
        
        # Check for multi-agent scenario
        if len(agent_scores) >= 2 and agent_scores[1].confidence >= self.multi_agent_threshold:
            # Multiple agents score high - use primary but note alternatives
            multi_agent_needed = True
            alternative_agents = [score.agent_id for score in agent_scores[1:3]]
        else:
            multi_agent_needed = False
            alternative_agents = [score.agent_id for score in agent_scores[1:2]]
        
        best_score = agent_scores[0]
        
        # Apply confidence threshold
        if best_score.confidence < self.confidence_threshold:
            # Low confidence - might need human handoff
            self.logger.warning(f"Low confidence selection: {best_score.confidence:.2f}")
        
        return OrchestrationResult(
            selected_agent=best_score.agent_id,
            selection_strategy=AgentSelectionStrategy.CONFIDENCE_BASED,
            confidence=best_score.confidence,
            alternative_agents=alternative_agents,
            reasons=best_score.reasons,
            emergency_override=False,
            multi_agent_needed=multi_agent_needed
        )
    
    async def handle_multi_agent_scenario(
        self, 
        user_input: str, 
        context: AgentContext,
        primary_agent_id: str,
        secondary_agent_ids: List[str]
    ) -> Dict[str, AgentResponse]:
        """
        Handle scenarios where multiple agents should provide input.
        
        Args:
            user_input: User's message
            context: Conversation context
            primary_agent_id: Primary agent ID
            secondary_agent_ids: Secondary agent IDs
            
        Returns:
            Dict of agent responses
        """
        responses = {}
        
        # Get primary response
        primary_agent = self.agents[primary_agent_id]
        responses[primary_agent_id] = await primary_agent.generate_response(user_input, context)
        
        # Get secondary responses
        for agent_id in secondary_agent_ids:
            try:
                agent = self.agents[agent_id]
                response = await agent.generate_response(user_input, context)
                responses[agent_id] = response
            except Exception as e:
                self.logger.error(f"Error getting response from {agent_id}: {e}")
        
        return responses
    
    def get_agent_capabilities(self) -> Dict[str, List[AgentCapability]]:
        """
        Get capabilities of all agents.
        
        Returns:
            Dict mapping agent IDs to their capabilities
        """
        return {
            agent_id: agent.capabilities 
            for agent_id, agent in self.agents.items()
        }
    
    def get_agent_by_id(self, agent_id: str) -> Optional[BaseAgent]:
        """
        Get agent by ID.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Agent instance or None
        """
        return self.agents.get(agent_id)
    
    def get_available_agents(self) -> List[str]:
        """
        Get list of available agent IDs.
        
        Returns:
            List of agent IDs
        """
        return list(self.agents.keys())
