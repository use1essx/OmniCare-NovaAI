"""
Mental Health Agent (小星星) - Healthcare AI V2
===========================================

VTuber-style AI companion specialized in comprehensive mental health support
for vulnerable children and teenagers in Hong Kong. Provides engaging,
culturally-sensitive emotional support and crisis intervention.

Key Features:
- Child/teen mental health screening and support
- VTuber personality for engagement
- Crisis detection and intervention
- Parent/guardian alert system
- Hong Kong educational system awareness
- Cultural family dynamics understanding
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from ..base_agent import (
    BaseAgent, 
    AgentCapability, 
    AgentPersonality,
    AgentResponse, 
    AgentContext
)


class MentalHealthAgent(BaseAgent):
    """
    小星星 (Little Star) - VTuber-style mental health companion
    
    Specialized mental health support agent with focus on:
    - Child and teenager emotional wellbeing
    - Crisis intervention and suicide prevention
    - School stress and academic pressure
    - Family dynamics and cultural sensitivity
    - Engaging VTuber personality for connection
    """
    
    def __init__(self, ai_service):
        """Initialize Mental Health Agent."""
        super().__init__(
            agent_id="mental_health",
            ai_service=ai_service,
            capabilities=[
                AgentCapability.MENTAL_HEALTH_SUPPORT,
                AgentCapability.CRISIS_INTERVENTION,
                AgentCapability.EDUCATIONAL_SUPPORT
            ],
            personality=AgentPersonality.VTUBER_FRIEND,
            primary_language="zh"
        )
        
        # Mental health keywords for detection
        self._mental_health_keywords = [
            # Mental health conditions
            "stress", "壓力", "anxiety", "焦慮", "depression", "抑鬱", "mental", "心理",
            "mood", "心情", "emotion", "情緒", "feeling", "感覺", "overwhelmed", "不知所措",
            "sad", "傷心", "angry", "憤怒", "frustrated", "沮喪", "lonely", "孤獨",
            "worried", "擔心", "nervous", "緊張", "panic", "恐慌", "fear", "害怕",
            
            # Specific conditions
            "autism", "自閉症", "adhd", "過度活躍", "attention", "專注", "hyperactive", "多動",
            "social anxiety", "社交焦慮", "school anxiety", "學校焦慮", "exam stress", "考試壓力",
            
            # Youth-specific contexts
            "school", "學校", "exam", "考試", "study", "讀書", "homework", "功課",
            "friends", "朋友", "classmates", "同學", "teacher", "老師", "parents", "父母",
            "family", "家庭", "siblings", "兄弟姐妹", "bullying", "欺凌", "bully", "霸凌",
            
            # Age indicators
            "child", "小朋友", "kid", "兒童", "teenager", "青少年", "teen", "少年",
            "student", "學生", "youth", "青年", "young", "年輕", "DSE", "會考"
        ]
        
        # Crisis keywords requiring immediate attention
        self._crisis_keywords = [
            # Suicide/self-harm
            "suicide", "自殺", "kill myself", "殺死自己", "hurt myself", "傷害自己",
            "die", "死", "end it all", "結束一切", "can't go on", "無法繼續",
            "self-harm", "自殘", "cutting", "割傷", "want to die", "想死",
            "better off dead", "死咗好過", "not worth living", "唔值得生存",
            
            # Severe distress
            "can't take it", "受唔住", "hopeless", "絕望", "worthless", "冇用",
            "nobody cares", "冇人關心", "hate myself", "憎恨自己"
        ]
        
        # Age-specific communication adaptations
        self._age_adaptations = {
            "child": {
                "style": "playful_simple",
                "concerns": ["family", "school_basic", "friends", "activities"],
                "language": ["simple", "encouraging", "fun_emojis"]
            },
            "teen": {
                "style": "understanding_relatable", 
                "concerns": ["academic_pressure", "peer_relationships", "identity", "future"],
                "language": ["internet_slang", "validation", "non_judgmental"]
            }
        }
        
        # Hong Kong specific context
        self._hk_context = {
            "education": ["DSE", "HKDSE", "JUPAS", "tuition", "補習", "名校", "elite_school"],
            "family": ["filial_piety", "孝順", "face", "面子", "generation_gap", "代溝"],
            "living": ["small_flat", "唐樓", "public_housing", "居屋", "privacy", "私隱"],
            "culture": ["collectivist", "hierarchy", "respect_elders", "尊重長輩"]
        }
    
    def can_handle(self, user_input: str, context: AgentContext) -> Tuple[bool, float]:
        """
        Determine if this agent can handle mental health requests.
        
        Args:
            user_input: User's message
            context: Conversation context
            
        Returns:
            Tuple of (can_handle: bool, confidence: float)
        """
        user_input_lower = user_input.lower()
        
        # Check for crisis keywords first - high priority
        crisis_matches = sum(1 for keyword in self._crisis_keywords 
                           if keyword in user_input_lower)
        
        if crisis_matches > 0:
            return False, 0.0  # Defer to Safety Guardian for crisis situations
        
        # Check for mental health keywords
        mh_keyword_matches = sum(1 for keyword in self._mental_health_keywords 
                               if keyword in user_input_lower)
        
        # Check for age indicators (prefer younger demographics)
        age_indicators = ["child", "kid", "teen", "student", "school", "exam", "homework"]
        age_matches = sum(1 for indicator in age_indicators 
                         if indicator in user_input_lower)
        
        # Check user profile age
        age_group = context.user_profile.get("age_group", "adult")
        age_boost = 0.3 if age_group in ["child", "teen"] else 0.0
        
        # Calculate confidence
        total_matches = mh_keyword_matches + (age_matches * 1.5)  # Weight age indicators
        base_confidence = min(0.9, 0.4 + (total_matches * 0.15))
        final_confidence = min(0.95, base_confidence + age_boost)
        
        if total_matches >= 2 or (mh_keyword_matches >= 1 and age_group in ["child", "teen"]):
            return True, final_confidence
        
        # Check for school/family stress patterns
        stress_contexts = [
            "school stress", "學校壓力", "exam anxiety", "考試焦慮",
            "friend problems", "朋友問題", "family issues", "家庭問題",
            "can't concentrate", "唔能夠專心", "too much pressure", "太大壓力"
        ]
        
        stress_matches = sum(1 for context_phrase in stress_contexts 
                           if context_phrase in user_input_lower)
        
        if stress_matches > 0:
            return True, 0.8
        
        return False, 0.0
    
    async def generate_response(
        self, 
        user_input: str, 
        context: AgentContext
    ) -> AgentResponse:
        """
        Generate mental health support response.
        
        Args:
            user_input: User's message
            context: Conversation context
            
        Returns:
            AgentResponse with mental health support
        """
        # Build system prompt
        system_prompt = self.get_system_prompt(context)
        
        # Create AI request
        ai_request = self._build_ai_request(user_input, context, system_prompt)
        
        # Generate response using AI service
        language = getattr(context, 'language_preference', 'en')
        ai_response = await self._generate_ai_response(ai_request, language)
        
        # Post-process response with VTuber style
        processed_content = self._post_process_response(ai_response.content, context)
        
        # Detect urgency and crisis potential
        urgency = self.detect_urgency(user_input, context)
        needs_alert, alert_details = self.should_alert_professional(
            user_input, context, processed_content
        )
        
        # Generate suggested actions
        suggested_actions = self._generate_suggested_actions(user_input, context)
        
        return AgentResponse(
            content=processed_content,
            confidence=ai_response.confidence_score,
            urgency_level=urgency,
            requires_followup=True,  # Mental health always benefits from follow-up
            suggested_actions=suggested_actions,
            professional_alert_needed=needs_alert,
            alert_details=alert_details,
            conversation_context={
                "agent_type": "mental_health",
                "mental_health_topics": self._extract_mental_health_topics(user_input),
                "age_group": context.user_profile.get("age_group", "unknown"),
                "crisis_indicators": self._detect_crisis_indicators(user_input),
                "school_context": self._detect_school_context(user_input),
                "family_context": self._detect_family_context(user_input)
            }
        )
    
    def get_system_prompt(self, context: AgentContext) -> str:
        """
        Get the system prompt for mental health support.
        
        Args:
            context: Conversation context
            
        Returns:
            Customized system prompt (assembled by PromptComposer)
        """
        # Use centralized PromptComposer for consistent prompt assembly
        from src.core.prompt_composer import get_prompt_composer
        
        composer = get_prompt_composer()
        
        # Compose full system prompt with all layers:
        # Language instruction → base_system → mental_health persona → context
        return composer.compose_system_prompt(
            agent_name="mental_health",
            context=context,
            active_skills=None  # Specialized agents don't use skills directly
        )
    
    def _post_process_response(self, content: str, context: AgentContext) -> str:
        """
        Post-process the AI response with VTuber enhancements.
        
        Args:
            content: Raw AI response
            context: Conversation context
            
        Returns:
            VTuber-enhanced response
        """
        # Add cultural adaptation
        content = self.adapt_to_culture(content, context)
        
        # Add VTuber elements if not already present
        if not any(emoji in content for emoji in ["✨", "💙", "🌟", "😊"]):
            content = "✨ " + content
        
        # Add crisis resources for mental health content
        crisis_indicators = ["sad", "傷心", "hopeless", "絕望", "overwhelmed", "不知所措"]
        if any(indicator in content.lower() for indicator in crisis_indicators):
            if context.language_preference == "zh":
                content += "\n\n💙 **記住，你並不孤單！**\n🆘 如有危機：撒瑪利亞會 24小時熱線 2896 0000"
            else:
                content += "\n\n💙 **Remember, you're not alone!**\n🆘 Crisis support: Samaritans Hong Kong 24/7 hotline 2896 0000"
        
        return content
    
    def _generate_suggested_actions(
        self, 
        user_input: str, 
        context: AgentContext
    ) -> List[str]:
        """
        Generate mental health specific suggested actions.
        
        Args:
            user_input: User's message
            context: Conversation context
            
        Returns:
            List of suggested actions
        """
        actions = []
        user_input_lower = user_input.lower()
        age_group = context.user_profile.get("age_group", "teen")
        
        # School stress actions
        if any(word in user_input_lower for word in ["school", "學校", "exam", "考試", "study", "讀書"]):
            if age_group == "child":
                actions.extend([
                    "Talk to parents about school worries",
                    "Ask teacher for help with difficult subjects",
                    "Take breaks during homework time"
                ])
            else:  # teen
                actions.extend([
                    "Use study techniques like Pomodoro method",
                    "Connect with school counselor for support",
                    "Consider discussing study pressure with parents"
                ])
        
        # Social anxiety actions
        if any(word in user_input_lower for word in ["friends", "朋友", "social", "社交", "shy", "害羞"]):
            actions.extend([
                "Practice small social interactions",
                "Join clubs or activities with shared interests",
                "Use online platforms to build confidence first"
            ])
        
        # Family issues actions  
        if any(word in user_input_lower for word in ["family", "家庭", "parents", "父母", "argue", "爭吵"]):
            actions.extend([
                "Find calm moments to express feelings",
                "Ask for family meeting to discuss concerns",
                "Talk to trusted adult about family stress"
            ])
        
        # General mental health actions
        actions.extend([
            "Practice daily mindfulness or deep breathing",
            "Maintain regular sleep and exercise routine",
            "Keep a feelings journal to track patterns",
            "Connect with supportive friends or family",
            "Consider speaking with school counselor"
        ])
        
        return actions[:5]  # Limit to top 5 actions
    
    def _extract_mental_health_topics(self, user_input: str) -> List[str]:
        """Extract mental health topics from user input."""
        topics = []
        user_input_lower = user_input.lower()
        
        topic_mapping = {
            "anxiety": ["anxiety", "焦慮", "nervous", "緊張", "worried", "擔心"],
            "depression": ["sad", "傷心", "depression", "抑鬱", "hopeless", "絕望"],
            "stress": ["stress", "壓力", "overwhelmed", "不知所措", "pressure", "壓迫"],
            "school_issues": ["school", "學校", "exam", "考試", "grades", "成績"],
            "social_issues": ["friends", "朋友", "bullying", "欺凌", "lonely", "孤獨"],
            "family_issues": ["family", "家庭", "parents", "父母", "siblings", "兄弟姐妹"],
            "identity": ["confused", "混亂", "who am i", "我係邊個", "identity", "身份"],
            "attention": ["focus", "專注", "adhd", "過度活躍", "concentrate", "集中"]
        }
        
        for topic, keywords in topic_mapping.items():
            if any(keyword in user_input_lower for keyword in keywords):
                topics.append(topic)
        
        return topics
    
    def _detect_crisis_indicators(self, user_input: str) -> List[str]:
        """Detect crisis indicators in user input."""
        indicators = []
        user_input_lower = user_input.lower()
        
        crisis_patterns = {
            "self_harm": ["hurt myself", "傷害自己", "cutting", "割傷", "self-harm", "自殘"],
            "suicidal_ideation": ["suicide", "自殺", "kill myself", "want to die", "想死"],
            "hopelessness": ["hopeless", "絕望", "worthless", "冇用", "no point", "冇意思"],
            "isolation": ["nobody cares", "冇人關心", "all alone", "完全孤獨", "no friends", "冇朋友"],
            "substance_use": ["drinking", "飲酒", "drugs", "毒品", "pills", "藥丸"],
            "eating_issues": ["not eating", "唔食野", "binge", "暴食", "purge", "嘔吐"]
        }
        
        for indicator, keywords in crisis_patterns.items():
            if any(keyword in user_input_lower for keyword in keywords):
                indicators.append(indicator)
        
        return indicators
    
    def _detect_school_context(self, user_input: str) -> Dict[str, Any]:
        """Detect school-related context."""
        context = {}
        user_input_lower = user_input.lower()
        
        # Academic pressure
        if any(term in user_input_lower for term in ["dse", "exam", "test", "grades", "成績"]):
            context["academic_pressure"] = True
        
        # School relationships
        if any(term in user_input_lower for term in ["teacher", "老師", "classmates", "同學"]):
            context["school_relationships"] = True
            
        # Bullying
        if any(term in user_input_lower for term in ["bullying", "欺凌", "bully", "霸凌"]):
            context["bullying_concern"] = True
            
        return context
    
    def _detect_family_context(self, user_input: str) -> Dict[str, Any]:
        """Detect family-related context."""
        context = {}
        user_input_lower = user_input.lower()
        
        # Family conflict
        if any(term in user_input_lower for term in ["fight", "爭吵", "argue", "嘈交", "angry parents", "嬲父母"]):
            context["family_conflict"] = True
        
        # Cultural pressure
        if any(term in user_input_lower for term in ["expectations", "期望", "disappointed", "失望", "face", "面子"]):
            context["cultural_pressure"] = True
            
        return context
    
    def should_alert_professional(
        self, 
        user_input: str, 
        context: AgentContext,
        response: str
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Determine if professional alert is needed for mental health concerns.
        
        Args:
            user_input: User's message
            context: Conversation context
            response: Generated response
            
        Returns:
            Tuple of (needs_alert: bool, alert_details: Optional[Dict])
        """
        # Crisis indicators requiring immediate parent/professional alert
        crisis_indicators = self._detect_crisis_indicators(user_input)
        
        if crisis_indicators:
            urgency = "critical" if any(ind in ["self_harm", "suicidal_ideation"] 
                                     for ind in crisis_indicators) else "high"
            
            return True, {
                "alert_type": "mental_health_crisis",
                "urgency": urgency,
                "reason": f"Crisis indicators detected: {', '.join(crisis_indicators)}",
                "category": "mental_health",
                "user_input_summary": user_input[:200],
                "crisis_indicators": crisis_indicators,
                "recommended_action": "Immediate mental health professional intervention",
                "parent_notification": True,
                "age_group": context.user_profile.get("age_group", "unknown"),
                "timestamp": datetime.now().isoformat()
            }
        
        # Persistent mental health concerns
        persistent_concerns = [
            "weeks of sadness", "幾個星期傷心", "can't function", "做唔到野",
            "stopped eating", "唔食野", "not sleeping", "瞓唔到",
            "failing grades", "成績差", "lost all friends", "冇晒朋友"
        ]
        
        if any(concern in user_input.lower() for concern in persistent_concerns):
            return True, {
                "alert_type": "persistent_mental_health_concern",
                "urgency": "medium",
                "reason": "Persistent mental health symptoms affecting functioning",
                "category": "mental_health_monitoring",
                "user_input_summary": user_input[:200],
                "recommended_action": "Mental health professional consultation",
                "parent_notification": context.user_profile.get("age_group") in ["child", "teen"],
                "timestamp": datetime.now().isoformat()
            }
        
        return super().should_alert_professional(user_input, context, response)
    
    def get_activation_message(self, context: AgentContext) -> str:
        """Get activation message for mental health agent."""
        age_group = context.user_profile.get("age_group", "teen")
        
        if age_group == "child":
            if context.language_preference == "zh":
                return "🌟 Hello小朋友！我係小星星！✨ 我係你嘅好朋友，想同我傾計心事嗎？💙"
            else:
                return "🌟 Hi there! I'm Little Star! ✨ I'm your friendly companion here to listen and support you! 💙"
        else:  # teen or adult
            if context.language_preference == "zh":
                return "🌟 Hey！我係小星星！✨ 我知道做香港teen好tough，想傾計嗎？I'm here for you! 💙"
            else:
                return "🌟 Hey! I'm Little Star! ✨ I know being a teen in HK is tough. Want to chat? I'm here to listen! 💙"
