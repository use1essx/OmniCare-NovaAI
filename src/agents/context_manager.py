"""
Conversation Context Manager - Healthcare AI V2
==============================================

Comprehensive context management system for conversation history, user profiles,
cultural adaptation, and language handling across healthcare AI agent interactions.

Key Features:
- Conversation history management
- User profile and preferences tracking
- Cultural context adaptation (Hong Kong specific)
- Language detection and handling
- Health pattern recognition
- Agent transition management
- Professional alert coordination
"""

from typing import Any, Dict, Optional
from datetime import datetime, timedelta
import logging
import re

from .base_agent import AgentContext
from .conversation_models import ConversationState, LanguagePreference, HealthPattern, UserProfile, ConversationMemory
from .db_session_manager import DatabaseSessionManager


class ConversationContextManager:
    """
    Comprehensive context management for healthcare AI conversations.
    
    Manages conversation history, user profiles, cultural adaptation,
    and cross-agent continuity for healthcare AI interactions.
    """
    
    def __init__(self):
        """Initialize Context Manager."""
        self.logger = logging.getLogger("agents.context_manager")
        
        # Database session manager for persistent storage
        self.db_session_manager = DatabaseSessionManager()
        
        # In-memory storage for user profiles (could be moved to DB later)
        self.user_profiles: Dict[str, UserProfile] = {}
        
        # Legacy in-memory storage (kept for fallback)
        self.conversation_memories: Dict[str, ConversationMemory] = {}
        
        # Configuration
        self.max_conversation_history = 50  # messages per session
        self.session_timeout = timedelta(hours=24)  # session expires after 24h
        self.health_pattern_window = timedelta(days=30)  # track patterns for 30 days
        
        # Hong Kong cultural patterns
        self.hk_cultural_indicators = {
            "formal_address": ["您", "please", "sir", "madam", "先生", "小姐", "太太"],
            "family_respect": ["父母", "parents", "elder", "長輩", "family", "家人"],
            "work_culture": ["overtime", "加班", "工作", "work", "boss", "老闆"],
            "housing": ["flat", "樓", "公屋", "居屋", "私樓", "subdivided", "劏房"],
            "healthcare": ["公立醫院", "私家醫生", "中醫", "tcm", "clinic", "診所"]
        }
        
        # Language detection patterns
        self.language_patterns = {
            "traditional_chinese": re.compile(r'[\u4e00-\u9fff]+'),
            "cantonese_specific": re.compile(r'[嘅|唔|咗|啦|呀|喇|咋|咩|呢|嚟|係]'),
            "english": re.compile(r'[a-zA-Z]+'),
            "mixed_language": re.compile(r'[\u4e00-\u9fff].*[a-zA-Z]|[a-zA-Z].*[\u4e00-\u9fff]')
        }
    
    def create_context(
        self, 
        user_id: str, 
        session_id: str,
        user_input: str,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> AgentContext:
        """
        Create comprehensive agent context from conversation state.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            user_input: Current user input
            additional_context: Additional context information
            
        Returns:
            AgentContext for agent processing
        """
        # Get or create user profile
        user_profile = self.get_or_create_user_profile(user_id, user_input)
        
        # Get or create conversation memory
        conversation_memory = self.get_or_create_conversation_memory(user_id, session_id)
        
        # Update conversation memory with current input
        self.update_conversation_history(conversation_memory, user_input, "user")
        
        # Extract cultural context
        cultural_context = self.extract_cultural_context(user_input, user_profile)
        
        # Resolve language preference:
        # Priority: request language > user profile > auto-detect
        language_pref = user_profile.language_preference.value
        if additional_context:
            # If language is specified in request, use it
            request_lang = additional_context.get("language")
            if request_lang and request_lang in ["en", "zh-HK"]:
                language_pref = request_lang
            elif request_lang == "auto":
                # Auto-detect from user input
                from src.core.language_manager import get_language_manager
                lm = get_language_manager()
                language_pref = lm.detect_language(user_input)
        
        # Create agent context
        context = AgentContext(
            user_id=user_id,
            session_id=session_id,
            conversation_history=conversation_memory.conversation_history[-10:],  # Last 10 exchanges
            user_profile=user_profile.__dict__,
            cultural_context=cultural_context,
            language_preference=language_pref,
            timestamp=datetime.now()
        )
        
        # Add additional context if provided
        if additional_context:
            for key, value in additional_context.items():
                if key != "language":  # Already handled above
                    setattr(context, key, value)
            context.organization_id = additional_context.get("organization_id")
            context.visibility = additional_context.get("visibility")
        
        return context
    
    def get_or_create_user_profile(self, user_id: str, user_input: str = "") -> UserProfile:
        """
        Get existing user profile or create new one.
        
        Args:
            user_id: User identifier
            user_input: Current user input for profile enrichment
            
        Returns:
            User profile
        """
        if user_id not in self.user_profiles:
            # Create new profile
            profile = UserProfile(user_id=user_id)
            
            # Initialize with basic detection from first input
            if user_input:
                profile_updates = self.detect_user_profile_from_input(user_input)
                self.update_user_profile(profile, profile_updates)
            
            self.user_profiles[user_id] = profile
            self.logger.info(f"Created new user profile for {user_id}")
        else:
            # Update existing profile if we have new input
            profile = self.user_profiles[user_id]
            if user_input:
                profile_updates = self.detect_user_profile_from_input(user_input)
                if profile_updates:
                    self.update_user_profile(profile, profile_updates)
        
        return self.user_profiles[user_id]
    
    def is_authenticated_user(self, user_id: str) -> bool:
        """Check if user is authenticated (not anonymous)."""
        return not user_id.startswith("anonymous_") and not user_id.startswith("ws_anonymous_")
    
    def get_session_key(self, user_id: str, session_id: str) -> str:
        """Generate session key for storage."""
        return f"{user_id}:{session_id}"
    
    def get_or_create_conversation_memory(
        self, 
        user_id: str, 
        session_id: str
    ) -> ConversationMemory:
        """
        Get existing conversation memory or create new session.
        Uses database storage for persistence.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            
        Returns:
            Conversation memory
        """
        return self.db_session_manager.get_or_create_conversation_memory(user_id, session_id)
    
    def detect_user_profile_from_input(self, user_input: str) -> Dict[str, Any]:
        """
        Detect user profile information from input text.
        
        Args:
            user_input: User's message
            
        Returns:
            Dict of detected profile information
        """
        profile_updates = {}
        input_lower = user_input.lower()
        
        # Age group detection
        age_indicators = {
            "child": [
                "小學", "primary school", "elementary", "小朋友", "kid", "child",
                "功課", "homework", "老師", "teacher", "同學", "classmate",
                "爸爸媽媽", "mommy", "daddy", "父母", "parents"
            ],
            "teen": [
                "中學", "secondary school", "high school", "中四", "中五", "中六",
                "DSE", "考試", "exam", "升學", "university", "大學",
                "青少年", "teenager", "teen", "朋友", "boyfriend", "girlfriend"
            ],
            "elderly": [
                "退休", "retired", "養老", "pension", "老人", "elderly", "長者", "senior",
                "孫", "grandchild", "獨居", "living alone", "老伴", "spouse passed",
                "關節", "arthritis", "血壓", "blood pressure", "糖尿病", "diabetes"
            ]
        }
        
        for age_group, keywords in age_indicators.items():
            if any(keyword in input_lower for keyword in keywords):
                profile_updates["age_group"] = age_group
                break
        
        # Specific age extraction
        age_patterns = [
            r'我今年(\d+)歲',
            r'i am (\d+)',
            r'(\d+) year old',
            r'age (\d+)',
        ]
        
        for pattern in age_patterns:
            match = re.search(pattern, input_lower)
            if match:
                age = int(match.group(1))
                profile_updates["detected_age"] = age
                # Override age group with specific age
                if age <= 12:
                    profile_updates["age_group"] = "child"
                elif age <= 19:
                    profile_updates["age_group"] = "teen"
                elif age >= 65:
                    profile_updates["age_group"] = "elderly"
                else:
                    profile_updates["age_group"] = "adult"
                break
        
        # Living situation detection
        living_indicators = {
            "alone": ["獨居", "living alone", "by myself", "一個人", "沒有人陪", "lonely"],
            "family": ["家人", "family", "父母", "parents", "兄弟姐妹", "siblings", "丈夫", "wife", "husband"],
            "care_facility": ["護老院", "care home", "nursing home", "老人院", "安老院"]
        }
        
        for situation, keywords in living_indicators.items():
            if any(keyword in input_lower for keyword in keywords):
                profile_updates["living_situation"] = situation
                break
        
        # Health conditions detection
        health_conditions = [
            "高血壓", "hypertension", "blood pressure",
            "糖尿病", "diabetes", 
            "心臟病", "heart disease", "heart condition",
            "關節炎", "arthritis",
            "抑鬱", "depression",
            "焦慮", "anxiety",
            "自閉症", "autism",
            "過度活躍", "adhd"
        ]
        
        mentioned_conditions = [condition for condition in health_conditions 
                              if condition in input_lower]
        
        if mentioned_conditions:
            profile_updates["health_conditions"] = mentioned_conditions
        
        # Language preference detection
        has_chinese = self.language_patterns["traditional_chinese"].search(user_input)
        has_english = self.language_patterns["english"].search(user_input)
        is_mixed = self.language_patterns["mixed_language"].search(user_input)
        
        if is_mixed or (has_chinese and has_english):
            profile_updates["language_preference"] = LanguagePreference.AUTO
        elif has_chinese and not has_english:
            profile_updates["language_preference"] = LanguagePreference.TRADITIONAL_CHINESE
        elif has_english and not has_chinese:
            profile_updates["language_preference"] = LanguagePreference.ENGLISH
        
        # Communication style detection
        if any(word in input_lower for word in ["please", "thank you", "謝謝", "麻煩", "請問", "您"]):
            profile_updates["communication_style"] = "formal"
        elif any(word in input_lower for word in ["hey", "hi", "咩話", "點解", "好嬲", "super"]):
            profile_updates["communication_style"] = "casual"
        
        return profile_updates
    
    def update_user_profile(self, profile: UserProfile, updates: Dict[str, Any]) -> None:
        """
        Update user profile with new information.
        
        Args:
            profile: User profile to update
            updates: Updates to apply
        """
        for key, value in updates.items():
            if key == "health_conditions":
                # Append to existing list, avoid duplicates
                existing = getattr(profile, key, [])
                for condition in value:
                    if condition not in existing:
                        existing.append(condition)
                setattr(profile, key, existing)
            elif key == "vulnerability_indicators":
                # Append to existing list, avoid duplicates
                existing = getattr(profile, key, [])
                for indicator in value:
                    if indicator not in existing:
                        existing.append(indicator)
                setattr(profile, key, existing)
            else:
                # Direct update
                setattr(profile, key, value)
        
        profile.updated_at = datetime.now()
    
    def extract_cultural_context(self, user_input: str, profile: UserProfile) -> Dict[str, Any]:
        """
        Extract cultural context from input and profile.
        
        Args:
            user_input: User's message
            profile: User profile
            
        Returns:
            Cultural context dict
        """
        context = {
            "region": profile.cultural_context,
            "language_mixing": False,
            "formality_level": "neutral",
            "family_orientation": False,
            "work_stress_context": False,
            "traditional_medicine_interest": False
        }
        
        input_lower = user_input.lower()
        
        # Check for language mixing
        context["language_mixing"] = bool(self.language_patterns["mixed_language"].search(user_input))
        
        # Detect formality level
        formal_indicators = [ind for category in ["formal_address", "family_respect"] 
                           for ind in self.hk_cultural_indicators[category]]
        if any(indicator in input_lower for indicator in formal_indicators):
            context["formality_level"] = "high"
        
        # Family orientation
        family_indicators = self.hk_cultural_indicators["family_respect"]
        context["family_orientation"] = any(indicator in input_lower for indicator in family_indicators)
        
        # Work stress context
        work_indicators = self.hk_cultural_indicators["work_culture"]
        context["work_stress_context"] = any(indicator in input_lower for indicator in work_indicators)
        
        # Traditional medicine interest
        tcm_indicators = ["中醫", "tcm", "traditional", "herbal", "草藥", "針灸", "acupuncture"]
        context["traditional_medicine_interest"] = any(indicator in input_lower for indicator in tcm_indicators)
        
        return context
    
    def update_conversation_history(
        self, 
        memory: ConversationMemory, 
        content: str, 
        role: str,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update conversation history with new message.
        
        Args:
            memory: Conversation memory
            content: Message content
            role: Message role ("user", "assistant", "system")
            agent_id: Agent that generated the message (if assistant)
            metadata: Additional message metadata
        """
        # Update database first
        self.db_session_manager.update_conversation_history(
            memory.user_id, 
            memory.session_id, 
            content, 
            role, 
            agent_id, 
            metadata
        )
        
        # Also update in-memory for immediate access
        message = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content[:1000],  # Limit message length
            "agent_id": agent_id,
            "metadata": metadata or {}
        }
        
        memory.conversation_history.append(message)
        memory.last_activity = datetime.now()
        
        # Trim history if too long
        if len(memory.conversation_history) > self.max_conversation_history:
            memory.conversation_history = memory.conversation_history[-self.max_conversation_history:]
        
        # Extract and track health topics
        if role == "user":
            self.extract_and_track_health_topics(memory, content)
    
    def extract_and_track_health_topics(self, memory: ConversationMemory, user_input: str) -> None:
        """
        Extract and track health topics from user input.
        
        Args:
            memory: Conversation memory
            user_input: User's message
        """
        input_lower = user_input.lower()
        
        # Health topic categories
        health_topics = {
            "physical_symptoms": ["pain", "痛", "headache", "頭痛", "fever", "發燒", "tired", "攰"],
            "mental_health": ["stress", "壓力", "anxiety", "焦慮", "sad", "傷心", "depressed", "抑鬱"],
            "medications": ["medication", "藥物", "pills", "藥丸", "dose", "劑量"],
            "chronic_conditions": ["diabetes", "糖尿病", "hypertension", "高血壓", "arthritis", "關節炎"],
            "lifestyle": ["exercise", "運動", "diet", "飲食", "sleep", "睡眠"],
            "preventive_care": ["checkup", "檢查", "screening", "篩檢", "vaccination", "疫苗"]
        }
        
        # Track mentioned topics
        for topic, keywords in health_topics.items():
            if any(keyword in input_lower for keyword in keywords):
                if topic not in memory.health_topics_discussed:
                    memory.health_topics_discussed.append(topic)
        
        # Keep only recent topics
        memory.health_topics_discussed = memory.health_topics_discussed[-20:]
    
    def track_agent_transition(
        self, 
        memory: ConversationMemory, 
        from_agent: Optional[str], 
        to_agent: str,
        reason: str
    ) -> None:
        """
        Track agent transitions for continuity.
        
        Args:
            memory: Conversation memory
            from_agent: Previous agent ID
            to_agent: New agent ID
            reason: Reason for transition
        """
        transition = {
            "timestamp": datetime.now().isoformat(),
            "from_agent": from_agent,
            "to_agent": to_agent,
            "reason": reason
        }
        
        memory.agent_handoffs.append(transition)
        memory.active_agent = to_agent
        
        # Update agent history
        if to_agent not in memory.agent_history:
            memory.agent_history.append(to_agent)
    
    def record_professional_alert(
        self, 
        memory: ConversationMemory, 
        alert_details: Dict[str, Any]
    ) -> None:
        """
        Record professional alert for tracking.
        
        Args:
            memory: Conversation memory
            alert_details: Alert information
        """
        alert_details["timestamp"] = datetime.now().isoformat()
        alert_details["session_id"] = memory.session_id
        
        memory.alerts_generated.append(alert_details)
        
        # Mark as escalated if high urgency
        if alert_details.get("urgency") in ["critical", "high"]:
            memory.conversation_state = ConversationState.ESCALATED
    
    def update_health_pattern(
        self, 
        memory: ConversationMemory, 
        pattern_type: str,
        description: str,
        agent_context: str
    ) -> None:
        """
        Update or create health pattern tracking.
        
        Args:
            memory: Conversation memory
            pattern_type: Type of pattern
            description: Pattern description
            agent_context: Agent that detected pattern
        """
        pattern_key = f"{pattern_type}:{description}"
        
        if pattern_key in memory.health_patterns:
            # Update existing pattern
            pattern = memory.health_patterns[pattern_key]
            pattern.last_mentioned = datetime.now()
            pattern.frequency += 1
        else:
            # Create new pattern
            pattern = HealthPattern(
                pattern_type=pattern_type,
                description=description,
                first_mentioned=datetime.now(),
                last_mentioned=datetime.now(),
                frequency=1,
                severity_trend="unknown",
                agent_context=agent_context
            )
            memory.health_patterns[pattern_key] = pattern
    
    def get_conversation_summary(self, memory: ConversationMemory) -> Dict[str, Any]:
        """
        Generate conversation summary for handoffs or analysis.
        
        Args:
            memory: Conversation memory
            
        Returns:
            Conversation summary
        """
        return {
            "session_id": memory.session_id,
            "user_id": memory.user_id,
            "duration": (datetime.now() - memory.started_at).total_seconds(),
            "state": memory.conversation_state.value,
            "active_agent": memory.active_agent,
            "agents_used": memory.agent_history,
            "health_topics": memory.health_topics_discussed,
            "alerts_count": len(memory.alerts_generated),
            "escalated": memory.conversation_state == ConversationState.ESCALATED,
            "message_count": len(memory.conversation_history),
            "health_patterns_count": len(memory.health_patterns)
        }
    
    def clear_temporary_session(self, user_id: str, session_id: str) -> bool:
        """
        Clear a temporary session (for anonymous users).
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            
        Returns:
            True if session was cleared, False if not found
        """
        return self.db_session_manager.clear_temporary_session(user_id, session_id)
    
    def clear_all_temporary_sessions(self) -> int:
        """
        Clear all temporary sessions (useful for cleanup).
        
        Returns:
            Number of sessions cleared
        """
        count = len(self.temporary_sessions)
        self.temporary_sessions.clear()
        self.logger.info(f"Cleared {count} temporary sessions")
        return count
    
    def get_session_info(self, user_id: str, session_id: str) -> Dict[str, Any]:
        """
        Get information about a session.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            
        Returns:
            Session information dictionary
        """
        return self.db_session_manager.get_session_info(user_id, session_id)
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired conversation sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        return self.db_session_manager.cleanup_expired_sessions()
