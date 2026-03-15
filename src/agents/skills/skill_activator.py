"""
Skill Activator

Dynamically detects and activates relevant skills based on:
- AI-powered intelligent routing (primary method)
- User message keywords (fallback)
- Conversation history context
- Multimodal signals (emotion, movement)
- Crisis detection

Safety skill always takes priority when crisis keywords detected.
"""

import logging
from typing import Any, Dict, List, Optional, Set

from .base_skill import SkillConfig, SkillContext

logger = logging.getLogger(__name__)

# Feature flag for AI routing
USE_AI_ROUTING = True


class SkillActivator:
    """
    Detects and activates skills based on conversation context.
    
    Features:
    - AI-powered intelligent routing (when available)
    - Keyword-based detection fallback (EN + ZH)
    - Crisis keyword override (safety_crisis always activated)
    - Multimodal signal integration (emotion, movement)
    - Conversation history awareness
    - Multiple simultaneous skill activation
    """
    
    def __init__(self, skills: Optional[Dict[str, SkillConfig]] = None, ai_service=None):
        """
        Initialize skill activator.
        
        Args:
            skills: Dictionary of skill name -> SkillConfig
            ai_service: Optional AI service for intelligent routing
        """
        if skills is None:
            # Import default skills
            from . import ALL_SKILLS
            skills = ALL_SKILLS
        
        self.skills = skills
        self.ai_service = ai_service
        self._intelligent_router = None
        
        # Build crisis keyword set for fast lookup
        self._crisis_keywords: Set[str] = set()
        for skill in self.skills.values():
            self._crisis_keywords.update(kw.lower() for kw in skill.crisis_keywords)
    
    def set_ai_service(self, ai_service):
        """Set the AI service for intelligent routing"""
        self.ai_service = ai_service
        if self._intelligent_router:
            self._intelligent_router.ai_service = ai_service
    
    def _get_intelligent_router(self):
        """Get or create the intelligent router"""
        if self._intelligent_router is None:
            from .intelligent_router import IntelligentSkillRouter
            self._intelligent_router = IntelligentSkillRouter(self.ai_service)
        return self._intelligent_router
    
    async def detect_skills(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        multimodal: Optional[Dict[str, Any]] = None,
        previous_skills: Optional[List[str]] = None
    ) -> List[SkillContext]:
        """
        Detect which skills should be activated for this message.
        
        Uses AI-powered intelligent routing when available, with
        keyword-based detection as fallback.
        
        Args:
            message: User message text
            context: Conversation context (history, session info)
            multimodal: Multimodal data (emotion, movement)
            previous_skills: Skills active in previous turn
            
        Returns:
            List of SkillContext objects for activated skills
        """
        activated: List[SkillContext] = []
        
        # Step 1: Try AI-powered intelligent routing
        if USE_AI_ROUTING and self.ai_service:
            try:
                ai_result = await self._detect_skills_with_ai(message, multimodal)
                if ai_result:
                    activated = ai_result
                    logger.info(f"🤖 AI routing activated: {[s.skill_name for s in activated]}")
            except Exception as e:
                logger.warning(f"AI routing failed, falling back to keywords: {e}")
        
        # Step 2: Fallback to keyword-based detection if AI didn't activate
        if not activated:
            activated = self._detect_skills_by_keywords(message)
        
        # Step 3: Multimodal signal enhancement
        if multimodal:
            activated = self._enhance_from_multimodal(activated, multimodal, message)
        
        # Step 4: Context-based continuity
        if previous_skills and context:
            activated = self._check_context_continuity(
                activated, previous_skills, context
            )
        
        # Step 5: Sort by priority (highest first)
        activated.sort(
            key=lambda x: self.skills.get(x.skill_name, SkillConfig(
                name='default', display_name='Default', description=''
            )).priority,
            reverse=True
        )
        
        # Step 6: Default skill if none activated
        if not activated:
            activated.append(SkillContext(
                skill_name='wellness_coaching',
                activation_reason='default_fallback',
                confidence=0.5
            ))
        
        logger.info(
            f"Activated skills: {[s.skill_name for s in activated]} "
            f"for message: {message[:50]}..."
        )
        
        return activated
    
    async def _detect_skills_with_ai(
        self,
        message: str,
        multimodal: Optional[Dict[str, Any]] = None
    ) -> List[SkillContext]:
        """
        Use AI to intelligently determine which skills to activate.
        
        Args:
            message: User message
            multimodal: Optional multimodal context
            
        Returns:
            List of SkillContext from AI routing
        """
        router = self._get_intelligent_router()
        result = await router.route(message, multimodal=multimodal)
        
        activated = []
        for skill_decision in result.skills:
            # Validate skill exists
            if skill_decision.name in self.skills:
                activated.append(SkillContext(
                    skill_name=skill_decision.name,
                    activation_reason=f"ai_routing: {skill_decision.reason}",
                    confidence=skill_decision.confidence
                ))
        
        # Always ensure crisis is detected if AI says so
        if result.crisis_detected and not any(s.skill_name == 'safety_crisis' for s in activated):
            activated.insert(0, SkillContext(
                skill_name='safety_crisis',
                activation_reason='ai_crisis_detection',
                confidence=1.0
            ))
            logger.warning("🚨 AI detected crisis in message")
        
        return activated
    
    def _detect_skills_by_keywords(self, message: str) -> List[SkillContext]:
        """
        Fallback keyword-based skill detection.
        
        Args:
            message: User message
            
        Returns:
            List of activated skills
        """
        activated: List[SkillContext] = []
        
        # Check for crisis keywords first (HIGHEST PRIORITY)
        if self._detect_crisis(message):
            crisis_skill = self.skills.get('safety_crisis')
            if crisis_skill:
                activated.append(SkillContext(
                    skill_name='safety_crisis',
                    activation_reason='crisis_keyword_detected',
                    confidence=1.0
                ))
                logger.warning("Crisis keywords detected - safety_crisis activated")
        
        # Keyword-based detection for other skills
        for skill_name, skill_config in self.skills.items():
            if any(s.skill_name == skill_name for s in activated):
                continue
            
            if skill_config.matches_keyword(message):
                activated.append(SkillContext(
                    skill_name=skill_name,
                    activation_reason='keyword_match',
                    confidence=0.8
                ))
        
        return activated
    
    def _detect_crisis(self, message: str) -> bool:
        """
        Check if message contains crisis keywords.
        
        Args:
            message: User message
            
        Returns:
            True if crisis keywords found
        """
        message_lower = message.lower()
        
        for keyword in self._crisis_keywords:
            if keyword in message_lower or keyword in message:
                return True
        
        return False
    
    def _enhance_from_multimodal(
        self,
        activated: List[SkillContext],
        multimodal: Dict[str, Any],
        message: str
    ) -> List[SkillContext]:
        """
        Enhance skill activation based on multimodal signals.
        
        Args:
            activated: Currently activated skills
            multimodal: Multimodal context (emotion, movement)
            message: User message
            
        Returns:
            Enhanced skill list
        """
        emotion_data = multimodal.get('emotion')
        movement_data = multimodal.get('movement')
        
        # Check emotion signals
        if emotion_data:
            emotion = emotion_data.get('emotion', '')
            intensity = emotion_data.get('intensity', 0)
            
            # High-intensity negative emotions might need mental health skill
            if emotion in ['sad', 'anxious', 'fearful', 'distressed'] and intensity >= 4:
                if not any(s.skill_name == 'mental_health' for s in activated):
                    activated.append(SkillContext(
                        skill_name='mental_health',
                        activation_reason='emotion_signal',
                        confidence=0.7,
                        emotion_signal=f"{emotion}_{intensity}"
                    ))
            
            # Very distressed expression might indicate crisis
            if emotion == 'distressed' and intensity == 5:
                if not any(s.skill_name == 'safety_crisis' for s in activated):
                    activated.append(SkillContext(
                        skill_name='safety_crisis',
                        activation_reason='severe_distress_detected',
                        confidence=0.6,
                        emotion_signal=f"{emotion}_{intensity}"
                    ))
            
            # Update emotion signals in existing contexts
            for skill_ctx in activated:
                skill_ctx.emotion_signal = f"{emotion}_{intensity}"
        
        # Check movement signals
        if movement_data:
            energy = movement_data.get('energy_level', '')
            gesture = movement_data.get('gesture', '')
            
            # Very low energy + slouched might indicate depression
            if energy == 'very_low' and gesture == 'slouched':
                if not any(s.skill_name == 'mental_health' for s in activated):
                    activated.append(SkillContext(
                        skill_name='mental_health',
                        activation_reason='low_energy_posture',
                        confidence=0.6,
                        movement_signal=f"{energy}_{gesture}"
                    ))
            
            # Update movement signals in existing contexts
            for skill_ctx in activated:
                skill_ctx.movement_signal = f"{energy}_{gesture}"
        
        return activated
    
    def _check_context_continuity(
        self,
        activated: List[SkillContext],
        previous_skills: List[str],
        context: Dict[str, Any]
    ) -> List[SkillContext]:
        """
        Maintain skill continuity from previous turn if relevant.
        
        Args:
            activated: Currently activated skills
            previous_skills: Skills from previous turn
            context: Conversation context
            
        Returns:
            Enhanced skill list with continuity
        """
        # If we have activated skills, check if previous skills should continue
        current_skill_names = {s.skill_name for s in activated}
        
        for prev_skill in previous_skills:
            # Don't add duplicates
            if prev_skill in current_skill_names:
                continue
            
            # Continue safety_crisis if it was active (until explicitly resolved)
            if prev_skill == 'safety_crisis':
                activated.append(SkillContext(
                    skill_name='safety_crisis',
                    activation_reason='crisis_continuity',
                    confidence=0.9
                ))
            
            # Continue mental_health for a few turns to maintain rapport
            elif prev_skill == 'mental_health':
                # Only continue if no contradicting skill
                if 'wellness_coaching' not in current_skill_names:
                    activated.append(SkillContext(
                        skill_name='mental_health',
                        activation_reason='context_continuity',
                        confidence=0.6
                    ))
        
        return activated
    
    def get_skill_config(self, skill_name: str) -> Optional[SkillConfig]:
        """Get configuration for a specific skill"""
        return self.skills.get(skill_name)
    
    def get_combined_prompt_addition(
        self,
        active_skills: List[SkillContext]
    ) -> str:
        """
        Get combined prompt additions from all active skills.
        
        Args:
            active_skills: List of active skill contexts
            
        Returns:
            Combined prompt addition string
        """
        additions = []
        
        for skill_ctx in active_skills:
            config = self.skills.get(skill_ctx.skill_name)
            if config and config.system_prompt_addition:
                additions.append(f"[{config.display_name}]")
                additions.append(config.system_prompt_addition)
        
        return "\n\n".join(additions)
    
    def get_available_functions(
        self,
        active_skills: List[SkillContext]
    ) -> List[str]:
        """
        Get combined available functions from all active skills.
        
        Args:
            active_skills: List of active skill contexts
            
        Returns:
            List of function names
        """
        functions = set()
        
        for skill_ctx in active_skills:
            config = self.skills.get(skill_ctx.skill_name)
            if config:
                functions.update(config.available_functions)
        
        return list(functions)
    
    def get_knowledge_categories(
        self,
        active_skills: List[SkillContext]
    ) -> List[str]:
        """
        Get combined knowledge categories for RAG from active skills.
        
        Args:
            active_skills: List of active skill contexts
            
        Returns:
            List of category names
        """
        categories = set()
        
        for skill_ctx in active_skills:
            config = self.skills.get(skill_ctx.skill_name)
            if config:
                categories.update(config.knowledge_categories)
        
        return list(categories)


# Singleton
_activator_instance: Optional[SkillActivator] = None


def get_skill_activator(ai_service=None) -> SkillActivator:
    """
    Get or create skill activator singleton.
    
    Args:
        ai_service: Optional AI service for intelligent routing
        
    Returns:
        SkillActivator instance
    """
    global _activator_instance
    if _activator_instance is None:
        _activator_instance = SkillActivator(ai_service=ai_service)
    elif ai_service and not _activator_instance.ai_service:
        _activator_instance.set_ai_service(ai_service)
    return _activator_instance


def reset_skill_activator() -> None:
    """Reset the singleton (for testing)"""
    global _activator_instance
    _activator_instance = None

