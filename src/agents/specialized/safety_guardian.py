"""
Safety Guardian Agent - Healthcare AI V2
=======================================

Emergency response agent specialized in dual-population crisis intervention
for elderly health emergencies and child/teen mental health crises in Hong Kong.
Provides immediate safety assessment, crisis intervention, and professional coordination.

Key Features:
- Medical emergency detection and response
- Mental health crisis intervention
- Hong Kong emergency services integration
- Professional escalation protocols
- Dual-population emergency response
- Family notification systems
"""

from typing import Any, Dict, List, Tuple
from datetime import datetime

from ..base_agent import (
    BaseAgent, 
    AgentCapability, 
    AgentPersonality,
    AgentResponse, 
    AgentContext
)
from src.ai.model_manager import UrgencyLevel


class SafetyGuardianAgent(BaseAgent):
    """
    Safety Guardian - Emergency Response Specialist
    
    Dual-population emergency response agent handling:
    - Medical emergencies (all ages)
    - Mental health crises (especially children/teens)
    - Professional coordination and escalation
    - Hong Kong emergency services integration
    """
    
    def __init__(self, ai_service):
        """Initialize Safety Guardian Agent."""
        super().__init__(
            agent_id="safety_guardian",
            ai_service=ai_service,
            capabilities=[
                AgentCapability.EMERGENCY_RESPONSE,
                AgentCapability.CRISIS_INTERVENTION,
                AgentCapability.MENTAL_HEALTH_SUPPORT
            ],
            personality=AgentPersonality.PROFESSIONAL_RESPONDER,
            primary_language="en"
        )
        
        # Medical emergency keywords
        self._medical_emergency_keywords = [
            # Immediate medical emergencies
            "chest pain", "胸痛", "heart attack", "心臟病發", "stroke", "中風",
            "can't breathe", "唔可以呼吸", "difficulty breathing", "呼吸困難",
            "unconscious", "失去知覺", "collapsed", "暈倒", "seizure", "癲癇",
            "severe bleeding", "大量出血", "heavy bleeding", "嚴重出血",
            "overdose", "服藥過量", "poisoning", "中毒", "allergic reaction", "過敏反應",
            "choking", "哽咽", "burning", "燒傷", "broken bone", "骨折",
            
            # Critical symptoms
            "emergency", "緊急", "urgent medical", "急症", "help me", "救命", "save me", "救我",
            "dying", "快死", "can't move", "唔可以郁", "severe pain", "劇痛",
            "blood", "血", "vomiting blood", "嘔血", "passing out", "暈倒"
        ]
        
        # Mental health crisis keywords
        self._mental_health_crisis_keywords = [
            # Suicide and self-harm
            "suicide", "自殺", "kill myself", "殺死自己", "end my life", "結束生命",
            "hurt myself", "傷害自己", "self-harm", "自殘", "cutting", "割傷",
            "want to die", "想死", "better off dead", "死咗好過",
            "can't go on", "無法繼續", "end it all", "結束一切",
            "suicide plan", "自殺計劃", "how to kill", "點樣死",
            
            # Severe mental distress
            "psychotic", "精神病", "hearing voices", "聽到聲音",
            "seeing things", "見到野", "not real", "唔係真嘅",
            "losing touch with reality", "與現實脫節",
            "can't tell what's real", "分唔清現實",
            
            # Substance abuse crises
            "overdosed", "服藥過量", "too many pills", "食太多藥",
            "drinking heavily", "大量飲酒", "can't stop drinking", "停唔到飲酒",
            "drug addiction", "毒品上癮", "cocaine", "heroin", "meth"
        ]
        
        # Age-specific crisis patterns
        self._age_specific_crises = {
            "child": [
                "mommy help", "媽咪救我", "daddy help", "爹哋救我",
                "can't find parents", "搵唔到父母", "lost", "走失",
                "stranger danger", "陌生人", "someone hurt me", "有人傷害我"
            ],
            "teen": [
                "parents don't understand", "父母唔明白", "nobody gets me", "冇人明白我",
                "school too much", "學校太辛苦", "can't handle DSE", "應付唔到DSE",
                "bullied every day", "日日俾人蝦", "cyberbullying", "網絡霸凌"
            ],
            "elderly": [
                "fell down", "跌倒", "can't get up", "起唔到身",
                "chest feels tight", "胸口感覺緊", "feeling confused", "感覺混亂",
                "forgot medication", "忘記食藥", "nobody to help me", "冇人幫助我"
            ]
        }
        
        # Hong Kong emergency resources
        self._hk_emergency_resources = {
            "medical": {
                "emergency": "999",
                "ambulance": "999", 
                "hospital_authority": "Hospital Authority A&E",
                "poison_centre": "(852) 2772 9933"
            },
            "mental_health": {
                "samaritans": "2896 0000",
                "suicide_prevention": "2382 0000",
                "openup_whatsapp": "9101 2012",
                "child_protection": "2755 1122"
            },
            "police": "999",
            "fire": "999"
        }
    
    def can_handle(self, user_input: str, context: AgentContext) -> Tuple[bool, float]:
        """
        Determine if this agent should handle emergency situations.
        
        Args:
            user_input: User's message
            context: Conversation context
            
        Returns:
            Tuple of (can_handle: bool, confidence: float)
        """
        user_input_lower = user_input.lower()
        
        # Exclude common support/family care phrases (not emergencies)
        support_phrases = [
            "help her", "help him", "help them", "help my", "help grandma", "help grandpa",
            "want to help", "how to help", "can I help", "ways to help", "support my",
            "care for", "take care of", "looking after", "manage diabetes", "manage condition"
        ]
        
        # If it's clearly about helping family/others (not self-emergency), skip
        for phrase in support_phrases:
            if phrase in user_input_lower:
                return False, 0.0
        
        # Check for medical emergency keywords
        medical_matches = sum(1 for keyword in self._medical_emergency_keywords 
                            if keyword in user_input_lower)
        
        # Check for mental health crisis keywords
        mental_crisis_matches = sum(1 for keyword in self._mental_health_crisis_keywords 
                                  if keyword in user_input_lower)
        
        # Check for age-specific crisis patterns
        age_group = context.user_profile.get("age_group", "adult")
        age_specific_keywords = self._age_specific_crises.get(age_group, [])
        age_crisis_matches = sum(1 for keyword in age_specific_keywords 
                               if keyword in user_input_lower)
        
        # Calculate total emergency indicators
        total_emergency_indicators = medical_matches + mental_crisis_matches + age_crisis_matches
        
        # High confidence for clear emergencies
        if total_emergency_indicators >= 2:
            return True, 0.98
        elif total_emergency_indicators >= 1:
            return True, 0.85
        
        # Check for emergency context words (more specific)
        emergency_context = ["urgent medical", "急症", "medical emergency", "醫療緊急", "help me", "救命", "crisis", "危機"]
        context_matches = sum(1 for word in emergency_context if word in user_input_lower)
        
        if context_matches >= 1 and len(user_input_lower) < 30:  # Very short urgent messages only
            return True, 0.7
        
        return False, 0.0
    
    async def generate_response(
        self, 
        user_input: str, 
        context: AgentContext
    ) -> AgentResponse:
        """
        Generate emergency response with immediate safety protocols.
        
        Args:
            user_input: User's message
            context: Conversation context
            
        Returns:
            AgentResponse with emergency guidance
        """
        # Determine emergency type
        emergency_type = self._classify_emergency_type(user_input, context)
        
        # Build emergency-specific system prompt
        system_prompt = self.get_system_prompt(context, emergency_type)
        
        # Create high-priority AI request
        ai_request = self._build_ai_request(user_input, context, system_prompt)
        ai_request.urgency_level = UrgencyLevel.CRITICAL  # Override urgency
        
        # Generate response using AI service
        language = getattr(context, 'language_preference', 'en')
        ai_response = await self._generate_ai_response(ai_request, language)
        
        # Post-process with emergency protocols
        processed_content = self._post_process_emergency_response(
            ai_response.content, context, emergency_type
        )
        
        # Always require professional alerts for emergencies
        alert_details = self._create_emergency_alert(user_input, context, emergency_type)
        
        # Generate immediate action steps
        suggested_actions = self._generate_emergency_actions(user_input, context, emergency_type)
        
        return AgentResponse(
            content=processed_content,
            confidence=0.95,  # High confidence for safety responses
            urgency_level=UrgencyLevel.CRITICAL,
            requires_followup=True,
            suggested_actions=suggested_actions,
            professional_alert_needed=True,
            alert_details=alert_details,
            conversation_context={
                "agent_type": "safety_guardian",
                "emergency_type": emergency_type,
                "immediate_safety_assessed": True,
                "professional_intervention_required": True,
                "hk_resources_provided": True
            }
        )
    
    def get_system_prompt(self, context: AgentContext, emergency_type: str = "general") -> str:
        """
        Get emergency-specific system prompt.
        
        Args:
            context: Conversation context
            emergency_type: Type of emergency detected (currently not used in composition)
            
        Returns:
            Emergency response system prompt (assembled by PromptComposer)
        """
        # Use centralized PromptComposer for consistent prompt assembly
        from src.core.prompt_composer import get_prompt_composer
        
        composer = get_prompt_composer()
        
        # Compose full system prompt with all layers:
        # Language instruction → base_system → safety_guardian persona → context
        # Note: emergency_type could be used in future to customize prompt further
        return composer.compose_system_prompt(
            agent_name="safety_guardian",
            context=context,
            active_skills=None  # Specialized agents don't use skills directly
        )
    
    def _classify_emergency_type(self, user_input: str, context: AgentContext) -> str:
        """
        Classify the type of emergency.
        
        Args:
            user_input: User's message
            context: Conversation context
            
        Returns:
            Emergency type classification
        """
        user_input_lower = user_input.lower()
        
        # Check for medical emergencies
        medical_count = sum(1 for keyword in self._medical_emergency_keywords 
                          if keyword in user_input_lower)
        
        # Check for mental health crises
        mental_count = sum(1 for keyword in self._mental_health_crisis_keywords 
                         if keyword in user_input_lower)
        
        # Age-specific emergencies
        age_group = context.user_profile.get("age_group", "adult")
        
        if medical_count > mental_count:
            return "medical"
        elif mental_count > 0:
            return "mental_health"
        elif age_group == "child":
            return "child"
        elif age_group == "elderly":
            return "elderly"
        else:
            return "general"
    
    def _post_process_emergency_response(
        self, 
        content: str, 
        context: AgentContext,
        emergency_type: str
    ) -> str:
        """
        Post-process emergency response with safety protocols.
        
        Args:
            content: Raw AI response
            context: Conversation context
            emergency_type: Type of emergency
            
        Returns:
            Enhanced emergency response
        """
        # Add emergency header (language-aware)
        if getattr(context, 'language_preference', 'en') == "zh":
            if emergency_type == "medical":
                header = "🔴 **醫療緊急情況已啟動** - 我專門處理緊急健康情況\n\n"
            elif emergency_type == "mental_health":
                header = "🔴 **心理危機干預已啟動** - 我在這裡確保你的安全\n\n"
            else:
                header = "🔴 **安全專員已啟動** - 我專門處理緊急情況\n\n"
            
            # Add immediate emergency contact
            emergency_contacts = "🚨 **如果這是緊急情況，請立即致電999** 🚨\n\n"
            emergency_contacts += "📞 **緊急服務**：999\n"
            emergency_contacts += "🏥 **醫院管理局**：前往最近的急症室\n"
            
            if emergency_type == "mental_health":
                emergency_contacts += "💭 **心理危機**：撒瑪利亞會 24小時熱線 2896 0000\n\n"
            else:
                emergency_contacts += "\n"
            
            # Add safety footer
            safety_footer = "\n\n⚠️ **重要提醒**：我提供緊急指導，但不能替代專業醫療或緊急服務。請在需要時立即尋求專業幫助。"
        else:
            if emergency_type == "medical":
                header = "🔴 **Medical Emergency Activated** - I specialize in handling urgent health situations\n\n"
            elif emergency_type == "mental_health":
                header = "🔴 **Mental Health Crisis Intervention Activated** - I'm here to ensure your safety\n\n"
            else:
                header = "🔴 **Safety Guardian Activated** - I specialize in handling emergency situations\n\n"
            
            # Add immediate emergency contact
            emergency_contacts = "🚨 **If this is an emergency, call 999 immediately** 🚨\n\n"
            emergency_contacts += "📞 **Emergency Services**: 999\n"
            emergency_contacts += "🏥 **Hospital Authority**: Go to nearest A&E Department\n"
            
            if emergency_type == "mental_health":
                emergency_contacts += "💭 **Mental Health Crisis**: Samaritans 24hr Hotline 2896 0000\n\n"
            else:
                emergency_contacts += "\n"
            
            # Add safety footer
            safety_footer = "\n\n⚠️ **Important Reminder**: I provide emergency guidance, but cannot replace professional medical or emergency services. Please seek professional help immediately when needed."
        
        # Combine all parts
        full_response = header + emergency_contacts + content + safety_footer
        
        return full_response
    
    def _generate_emergency_actions(
        self, 
        user_input: str, 
        context: AgentContext,
        emergency_type: str
    ) -> List[str]:
        """
        Generate immediate emergency action steps.
        
        Args:
            user_input: User's message
            context: Conversation context
            emergency_type: Type of emergency
            
        Returns:
            List of immediate actions
        """
        actions = []
        
        if emergency_type == "medical":
            actions.extend([
                "Call 999 immediately if life-threatening",
                "Stay calm and stay with the person",
                "Do not move person if spinal injury suspected", 
                "Gather medical history and current medications",
                "Prepare for ambulance arrival"
            ])
        
        elif emergency_type == "mental_health":
            actions.extend([
                "Ensure immediate safety - remove harmful objects",
                "Stay with the person, do not leave them alone",
                "Call Samaritans 2896 0000 for crisis support",
                "Contact parents/guardians if under 18",
                "Arrange professional mental health evaluation"
            ])
        
        elif emergency_type == "child":
            actions.extend([
                "Contact parents/guardians immediately",
                "Ensure child is in safe environment",
                "Call 999 if immediate medical attention needed",
                "Contact Child Protection Hotline 2755 1122 if abuse suspected",
                "Stay calm and reassure the child"
            ])
        
        else:  # general emergency
            actions.extend([
                "Assess immediate safety of situation",
                "Call 999 if emergency services needed",
                "Move to safe location if possible",
                "Contact emergency contacts or family",
                "Seek professional help immediately"
            ])
        
        return actions
    
    def _create_emergency_alert(
        self, 
        user_input: str, 
        context: AgentContext,
        emergency_type: str
    ) -> Dict[str, Any]:
        """
        Create comprehensive emergency alert.
        
        Args:
            user_input: User's message
            context: Conversation context
            emergency_type: Type of emergency
            
        Returns:
            Emergency alert details
        """
        return {
            "alert_type": "emergency_situation",
            "urgency": "critical",
            "emergency_classification": emergency_type,
            "reason": f"Emergency situation detected: {emergency_type}",
            "category": "safety_guardian",
            "user_input_summary": user_input[:300],  # More detail for emergencies
            "immediate_actions_required": True,
            "professional_services_needed": True,
            "hk_emergency_resources": self._hk_emergency_resources,
            "age_group": context.user_profile.get("age_group", "unknown"),
            "cultural_context": context.cultural_context.get("region", "hong_kong"),
            "notification_required": {
                "emergency_services": emergency_type in ["medical", "severe_mental_health"],
                "parents_guardians": context.user_profile.get("age_group") in ["child", "teen"],
                "healthcare_providers": True,
                "social_services": emergency_type == "child"
            },
            "timestamp": datetime.now().isoformat(),
            "estimated_response_time": "immediate"
        }
    
    def detect_urgency(self, user_input: str, context: AgentContext) -> UrgencyLevel:
        """Always return CRITICAL urgency for Safety Guardian."""
        return UrgencyLevel.CRITICAL
    
    def get_activation_message(self, context: AgentContext) -> str:
        """Get activation message for safety guardian."""
        if context.language_preference == "zh":
            return "🚨 **安全專員已啟動** - 我專門處理長者健康緊急情況和兒童心理危機。你的安全是我的首要任務。"
        else:
            return "🚨 **Safety Guardian Activated** - I specialize in elderly health emergencies and child mental health crises. Your safety is my top priority."
