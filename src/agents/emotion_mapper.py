"""
Agent Emotion Mapper - Healthcare AI V2
=======================================

Maps healthcare AI agent responses to Live2D avatar emotions and expressions.
Provides intelligent emotion detection based on agent type, response content,
urgency level, and cultural context for Hong Kong healthcare scenarios.

Features:
- Agent-specific emotion mapping
- Sentiment analysis for dynamic emotion selection
- Urgency-based emotion intensity adjustment
- Cultural emotion adaptation (Hong Kong context)
- Traditional Chinese language emotion detection
- Healthcare-specific emotion categories
"""

from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass

from src.core.logging import get_logger


logger = get_logger(__name__)


# ============================================================================
# EMOTION DEFINITIONS
# ============================================================================

class EmotionCategory(str, Enum):
    """Emotion categories for healthcare context"""
    PROFESSIONAL = "professional"
    CARING = "caring"
    URGENT = "urgent"
    SUPPORTIVE = "supportive"
    ENCOURAGING = "encouraging"
    SERIOUS = "serious"
    GENTLE = "gentle"
    PLAYFUL = "playful"
    NEUTRAL = "neutral"


class EmotionIntensity(str, Enum):
    """Emotion intensity levels"""
    SUBTLE = "subtle"
    MODERATE = "moderate"
    STRONG = "strong"
    INTENSE = "intense"


@dataclass
class EmotionMapping:
    """Emotion mapping with metadata"""
    emotion_id: str
    display_name: str
    category: EmotionCategory
    intensity: EmotionIntensity
    agent_types: List[str]
    triggers: List[str]  # Keywords or phrases that trigger this emotion
    cultural_variants: Dict[str, str]  # Language-specific variants
    description: str


# ============================================================================
# PREDEFINED EMOTION MAPPINGS
# ============================================================================

class EmotionLibrary:
    """
    Library of predefined emotions for healthcare AI agents
    """
    
    # Illness Monitor Agent (慧心助手) Emotions
    ILLNESS_MONITOR_EMOTIONS = [
        EmotionMapping(
            emotion_id="professional_caring",
            display_name="Professional Caring",
            category=EmotionCategory.PROFESSIONAL,
            intensity=EmotionIntensity.MODERATE,
            agent_types=["illness_monitor"],
            triggers=["symptom", "pain", "medication", "treatment", "診斷", "症狀", "藥物"],
            cultural_variants={"zh-HK": "專業關懷", "en": "Professional Caring"},
            description="Warm but professional medical consultation demeanor"
        ),
        EmotionMapping(
            emotion_id="concerned_medical",
            display_name="Medical Concern",
            category=EmotionCategory.SERIOUS,
            intensity=EmotionIntensity.STRONG,
            agent_types=["illness_monitor"],
            triggers=["severe", "serious", "worsening", "emergency", "嚴重", "惡化", "緊急"],
            cultural_variants={"zh-HK": "醫療關注", "en": "Medical Concern"},
            description="Heightened concern for serious medical conditions"
        ),
        EmotionMapping(
            emotion_id="reassuring_medical",
            display_name="Medical Reassurance",
            category=EmotionCategory.CARING,
            intensity=EmotionIntensity.MODERATE,
            agent_types=["illness_monitor"],
            triggers=["normal", "common", "treatable", "recovery", "正常", "常見", "可治療"],
            cultural_variants={"zh-HK": "醫療安慰", "en": "Medical Reassurance"},
            description="Reassuring tone for manageable health conditions"
        ),
        EmotionMapping(
            emotion_id="explaining_medical",
            display_name="Medical Explanation",
            category=EmotionCategory.PROFESSIONAL,
            intensity=EmotionIntensity.SUBTLE,
            agent_types=["illness_monitor"],
            triggers=["because", "means", "caused by", "explanation", "因為", "意思", "解釋"],
            cultural_variants={"zh-HK": "醫療解釋", "en": "Medical Explanation"},
            description="Clear, educational explanation of medical concepts"
        )
    ]
    
    # Mental Health Agent (小星星) Emotions  
    MENTAL_HEALTH_EMOTIONS = [
        EmotionMapping(
            emotion_id="gentle_supportive",
            display_name="Gentle Support",
            category=EmotionCategory.SUPPORTIVE,
            intensity=EmotionIntensity.MODERATE,
            agent_types=["mental_health"],
            triggers=["sad", "depressed", "anxious", "worried", "傷心", "抑鬱", "焦慮", "擔心"],
            cultural_variants={"zh-HK": "溫柔支持", "en": "Gentle Support"},
            description="Soft, understanding support for emotional difficulties"
        ),
        EmotionMapping(
            emotion_id="encouraging_youthful",
            display_name="Encouraging",
            category=EmotionCategory.ENCOURAGING,
            intensity=EmotionIntensity.STRONG,
            agent_types=["mental_health"],
            triggers=["can do", "possible", "strength", "better", "可以做到", "有可能", "力量"],
            cultural_variants={"zh-HK": "鼓勵青春", "en": "Encouraging"},
            description="Youthful, energetic encouragement"
        ),
        EmotionMapping(
            emotion_id="listening_attentive",
            display_name="Attentive Listening",
            category=EmotionCategory.GENTLE,
            intensity=EmotionIntensity.SUBTLE,
            agent_types=["mental_health"],
            triggers=["tell me", "how do you feel", "what happened", "講俾我聽", "你覺得點"],
            cultural_variants={"zh-HK": "專心聆聽", "en": "Attentive Listening"},
            description="Focused, empathetic listening posture"
        ),
        EmotionMapping(
            emotion_id="comforting_warm",
            display_name="Warm Comfort",
            category=EmotionCategory.CARING,
            intensity=EmotionIntensity.STRONG,
            agent_types=["mental_health"],
            triggers=["crying", "hurt", "alone", "scared", "喊", "受傷", "孤單", "驚"],
            cultural_variants={"zh-HK": "溫暖安慰", "en": "Warm Comfort"},
            description="Warm, nurturing comfort for distress"
        ),
        EmotionMapping(
            emotion_id="playful_cheerful",
            display_name="Playful Cheer",
            category=EmotionCategory.PLAYFUL,
            intensity=EmotionIntensity.MODERATE,
            agent_types=["mental_health"],
            triggers=["better", "good", "happy", "fun", "好啲", "開心", "好玩"],
            cultural_variants={"zh-HK": "頑皮開朗", "en": "Playful Cheer"},
            description="Light-hearted, cheerful VTuber-style expression"
        )
    ]
    
    # Safety Guardian Agent Emotions
    SAFETY_GUARDIAN_EMOTIONS = [
        EmotionMapping(
            emotion_id="alert_focused",
            display_name="Alert Focus",
            category=EmotionCategory.URGENT,
            intensity=EmotionIntensity.STRONG,
            agent_types=["safety_guardian"],
            triggers=["emergency", "urgent", "immediate", "now", "緊急", "即刻", "而家"],
            cultural_variants={"zh-HK": "警覺專注", "en": "Alert Focus"},
            description="Heightened alertness for emergency situations"
        ),
        EmotionMapping(
            emotion_id="commanding_authoritative",
            display_name="Authoritative Command",
            category=EmotionCategory.SERIOUS,
            intensity=EmotionIntensity.INTENSE,
            agent_types=["safety_guardian"],
            triggers=["call 999", "go to hospital", "stop", "don't", "叫999", "去醫院", "停"],
            cultural_variants={"zh-HK": "權威指令", "en": "Authoritative Command"},
            description="Clear, authoritative emergency instruction"
        ),
        EmotionMapping(
            emotion_id="instructional_clear",
            display_name="Clear Instruction",
            category=EmotionCategory.PROFESSIONAL,
            intensity=EmotionIntensity.STRONG,
            agent_types=["safety_guardian"],
            triggers=["step", "first", "then", "procedure", "步驟", "首先", "然後", "程序"],
            cultural_variants={"zh-HK": "清晰指導", "en": "Clear Instruction"},
            description="Clear, step-by-step emergency guidance"
        ),
        EmotionMapping(
            emotion_id="reassuring_authority",
            display_name="Reassuring Authority",
            category=EmotionCategory.CARING,
            intensity=EmotionIntensity.MODERATE,
            agent_types=["safety_guardian"],
            triggers=["help is coming", "you're safe", "stay calm", "援助嚟緊", "你安全", "保持冷靜"],
            cultural_variants={"zh-HK": "權威安撫", "en": "Reassuring Authority"},
            description="Calm, authoritative reassurance during crisis"
        )
    ]
    
    # Wellness Coach Agent Emotions
    WELLNESS_COACH_EMOTIONS = [
        EmotionMapping(
            emotion_id="energetic_positive",
            display_name="Energetic Positive",
            category=EmotionCategory.ENCOURAGING,
            intensity=EmotionIntensity.STRONG,
            agent_types=["wellness_coach"],
            triggers=["exercise", "healthy", "improve", "goal", "運動", "健康", "改善", "目標"],
            cultural_variants={"zh-HK": "活力正面", "en": "Energetic Positive"},
            description="High-energy motivation for health improvement"
        ),
        EmotionMapping(
            emotion_id="motivating_supportive",
            display_name="Motivating Support",
            category=EmotionCategory.ENCOURAGING,
            intensity=EmotionIntensity.MODERATE,
            agent_types=["wellness_coach"],
            triggers=["progress", "achievement", "success", "proud", "進步", "成就", "成功", "驕傲"],
            cultural_variants={"zh-HK": "激勵支持", "en": "Motivating Support"},
            description="Supportive motivation for wellness achievements"
        ),
        EmotionMapping(
            emotion_id="celebratory_joyful",
            display_name="Celebratory Joy",
            category=EmotionCategory.PLAYFUL,
            intensity=EmotionIntensity.STRONG,
            agent_types=["wellness_coach"],
            triggers=["great job", "excellent", "amazing", "congratulations", "做得好", "好叻", "恭喜"],
            cultural_variants={"zh-HK": "慶祝喜悅", "en": "Celebratory Joy"},
            description="Joyful celebration of wellness milestones"
        ),
        EmotionMapping(
            emotion_id="demonstrating_helpful",
            display_name="Helpful Demonstration",
            category=EmotionCategory.PROFESSIONAL,
            intensity=EmotionIntensity.MODERATE,
            agent_types=["wellness_coach"],
            triggers=["show you", "like this", "demonstration", "example", "示範", "好似咁", "例子"],
            cultural_variants={"zh-HK": "有用示範", "en": "Helpful Demonstration"},
            description="Clear, helpful demonstration of wellness practices"
        )
    ]


# ============================================================================
# EMOTION MAPPER CLASS
# ============================================================================

class EmotionMapper:
    """
    Maps agent responses to appropriate Live2D avatar emotions
    
    Uses intelligent analysis of:
    - Agent type and personality
    - Response content and sentiment
    - Urgency level and context
    - Cultural and language factors
    """
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.EmotionMapper")
        
        # Load emotion library
        self.emotion_library = self._build_emotion_library()
        
        # Sentiment keywords for dynamic analysis
        self.positive_keywords = {
            "en": ["good", "great", "excellent", "wonderful", "happy", "success", "better", "improvement"],
            "zh-HK": ["好", "好好", "好叻", "開心", "成功", "進步", "改善", "優秀"]
        }
        
        self.negative_keywords = {
            "en": ["bad", "terrible", "serious", "severe", "emergency", "danger", "crisis", "urgent"],
            "zh-HK": ["唔好", "嚴重", "緊急", "危險", "危機", "急", "糟糕", "麻煩"]
        }
        
        self.neutral_keywords = {
            "en": ["normal", "common", "typical", "regular", "standard", "usual"],
            "zh-HK": ["正常", "常見", "一般", "普通", "標準", "平時"]
        }
        
        # Cache for frequently used mappings
        self.mapping_cache: Dict[str, str] = {}
        
    def _build_emotion_library(self) -> Dict[str, EmotionMapping]:
        """Build comprehensive emotion library"""
        library = {}
        
        # Add all predefined emotions
        all_emotions = (
            EmotionLibrary.ILLNESS_MONITOR_EMOTIONS +
            EmotionLibrary.MENTAL_HEALTH_EMOTIONS +
            EmotionLibrary.SAFETY_GUARDIAN_EMOTIONS +
            EmotionLibrary.WELLNESS_COACH_EMOTIONS
        )
        
        for emotion in all_emotions:
            library[emotion.emotion_id] = emotion
        
        self.logger.info(f"Loaded {len(library)} emotions into library")
        return library
    
    def map_agent_to_emotion(
        self,
        agent_type: str,
        response: str,
        urgency: str = "low",
        confidence: float = 1.0,
        language: str = "en",
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Map agent response to appropriate emotion
        
        Args:
            agent_type: Type of agent (e.g., "illness_monitor")
            response: Agent response text
            urgency: Urgency level ("low", "medium", "high", "emergency")
            confidence: Agent confidence score (0.0 - 1.0)
            language: Response language ("en", "zh-HK")
            context: Additional context information
            
        Returns:
            Emotion ID for Live2D avatar
        """
        try:
            # Create cache key
            cache_key = f"{agent_type}:{urgency}:{hash(response[:100])}:{language}"
            if cache_key in self.mapping_cache:
                return self.mapping_cache[cache_key]
            
            # Get candidate emotions for agent type
            candidate_emotions = self._get_agent_emotions(agent_type)
            
            if not candidate_emotions:
                # Fallback to neutral if no agent-specific emotions
                return "neutral"
            
            # Score emotions based on multiple factors
            emotion_scores = {}
            
            for emotion in candidate_emotions:
                score = self._score_emotion(emotion, response, urgency, confidence, language, context)
                emotion_scores[emotion.emotion_id] = score
            
            # Select best emotion
            best_emotion = max(emotion_scores.items(), key=lambda x: x[1])
            selected_emotion = best_emotion[0]
            
            # Cache result
            self.mapping_cache[cache_key] = selected_emotion
            
            self.logger.debug(
                f"Mapped {agent_type} response to emotion '{selected_emotion}' "
                f"(score: {best_emotion[1]:.2f}, urgency: {urgency})"
            )
            
            return selected_emotion
            
        except Exception as e:
            self.logger.error(f"Error mapping emotion: {e}")
            return self._get_fallback_emotion(agent_type, urgency)
    
    def _get_agent_emotions(self, agent_type: str) -> List[EmotionMapping]:
        """Get emotions available for specific agent type"""
        return [
            emotion for emotion in self.emotion_library.values()
            if agent_type in emotion.agent_types
        ]
    
    def _score_emotion(
        self,
        emotion: EmotionMapping,
        response: str,
        urgency: str,
        confidence: float,
        language: str,
        context: Optional[Dict[str, Any]]
    ) -> float:
        """
        Score emotion based on multiple factors
        
        Args:
            emotion: Emotion to score
            response: Agent response text
            urgency: Urgency level
            confidence: Agent confidence
            language: Response language
            context: Additional context
            
        Returns:
            Emotion score (0.0 - 1.0)
        """
        score = 0.0
        
        # 1. Trigger keyword matching (30% weight)
        trigger_score = self._calculate_trigger_score(emotion, response, language)
        score += trigger_score * 0.30
        
        # 2. Urgency alignment (25% weight)
        urgency_score = self._calculate_urgency_score(emotion, urgency)
        score += urgency_score * 0.25
        
        # 3. Sentiment analysis (20% weight)
        sentiment_score = self._calculate_sentiment_score(emotion, response, language)
        score += sentiment_score * 0.20
        
        # 4. Confidence adjustment (15% weight)
        confidence_score = self._calculate_confidence_score(emotion, confidence)
        score += confidence_score * 0.15
        
        # 5. Cultural context (10% weight)
        cultural_score = self._calculate_cultural_score(emotion, language, context)
        score += cultural_score * 0.10
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _calculate_trigger_score(self, emotion: EmotionMapping, response: str, language: str) -> float:
        """Calculate score based on trigger keyword matching"""
        if not emotion.triggers:
            return 0.3  # Base score if no triggers defined
        
        response_lower = response.lower()
        matching_triggers = 0
        
        for trigger in emotion.triggers:
            if trigger.lower() in response_lower:
                matching_triggers += 1
        
        # Higher score for more trigger matches
        if matching_triggers == 0:
            return 0.0
        elif matching_triggers <= 2:
            return 0.5
        else:
            return 1.0
    
    def _calculate_urgency_score(self, emotion: EmotionMapping, urgency: str) -> float:
        """Calculate score based on urgency alignment"""
        urgency_emotion_map = {
            "emergency": [EmotionCategory.URGENT, EmotionCategory.SERIOUS],
            "high": [EmotionCategory.URGENT, EmotionCategory.SERIOUS, EmotionCategory.PROFESSIONAL],
            "medium": [EmotionCategory.PROFESSIONAL, EmotionCategory.CARING, EmotionCategory.SUPPORTIVE],
            "low": [EmotionCategory.GENTLE, EmotionCategory.ENCOURAGING, EmotionCategory.PLAYFUL, EmotionCategory.NEUTRAL]
        }
        
        expected_categories = urgency_emotion_map.get(urgency, [EmotionCategory.NEUTRAL])
        
        if emotion.category in expected_categories:
            return 1.0
        else:
            # Partial score for related categories
            if urgency == "emergency" and emotion.category in [EmotionCategory.PROFESSIONAL, EmotionCategory.CARING]:
                return 0.3
            elif urgency == "high" and emotion.category in [EmotionCategory.CARING, EmotionCategory.SUPPORTIVE]:
                return 0.5
            else:
                return 0.1
    
    def _calculate_sentiment_score(self, emotion: EmotionMapping, response: str, language: str) -> float:
        """Calculate score based on sentiment analysis"""
        response_lower = response.lower()
        
        # Count sentiment keywords
        positive_count = sum(
            1 for keyword in self.positive_keywords.get(language, [])
            if keyword in response_lower
        )
        
        negative_count = sum(
            1 for keyword in self.negative_keywords.get(language, [])
            if keyword in response_lower
        )
        
        neutral_count = sum(
            1 for keyword in self.neutral_keywords.get(language, [])
            if keyword in response_lower
        )
        
        # Determine dominant sentiment
        if positive_count > negative_count and positive_count > neutral_count:
            sentiment = "positive"
        elif negative_count > positive_count and negative_count > neutral_count:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        
        # Score based on emotion-sentiment alignment
        sentiment_emotion_map = {
            "positive": [EmotionCategory.ENCOURAGING, EmotionCategory.PLAYFUL, EmotionCategory.CARING],
            "negative": [EmotionCategory.URGENT, EmotionCategory.SERIOUS, EmotionCategory.SUPPORTIVE],
            "neutral": [EmotionCategory.PROFESSIONAL, EmotionCategory.GENTLE, EmotionCategory.NEUTRAL]
        }
        
        expected_categories = sentiment_emotion_map.get(sentiment, [EmotionCategory.NEUTRAL])
        
        if emotion.category in expected_categories:
            return 1.0
        else:
            return 0.3
    
    def _calculate_confidence_score(self, emotion: EmotionMapping, confidence: float) -> float:
        """Calculate score based on agent confidence"""
        # High confidence favors more assertive emotions
        # Low confidence favors more cautious emotions
        
        assertive_categories = [EmotionCategory.PROFESSIONAL, EmotionCategory.URGENT, EmotionCategory.ENCOURAGING]
        cautious_categories = [EmotionCategory.GENTLE, EmotionCategory.SUPPORTIVE, EmotionCategory.NEUTRAL]
        
        if confidence >= 0.8:
            return 1.0 if emotion.category in assertive_categories else 0.5
        elif confidence >= 0.6:
            return 0.8  # Balanced score for medium confidence
        else:
            return 1.0 if emotion.category in cautious_categories else 0.3
    
    def _calculate_cultural_score(self, emotion: EmotionMapping, language: str, context: Optional[Dict[str, Any]]) -> float:
        """Calculate score based on cultural context"""
        # Hong Kong cultural preferences
        if language == "zh-HK":
            # Prefer more formal, respectful emotions for Traditional Chinese
            formal_categories = [EmotionCategory.PROFESSIONAL, EmotionCategory.CARING, EmotionCategory.GENTLE]
            if emotion.category in formal_categories:
                return 1.0
            else:
                return 0.7
        
        # English preferences
        elif language == "en":
            # More open to playful and encouraging emotions
            return 1.0
        
        return 0.8  # Default score
    
    def _get_fallback_emotion(self, agent_type: str, urgency: str) -> str:
        """Get fallback emotion when mapping fails"""
        fallback_map = {
            "illness_monitor": {
                "emergency": "concerned_medical",
                "high": "professional_caring",
                "medium": "professional_caring",
                "low": "reassuring_medical"
            },
            "mental_health": {
                "emergency": "gentle_supportive",
                "high": "gentle_supportive",
                "medium": "encouraging_youthful",
                "low": "playful_cheerful"
            },
            "safety_guardian": {
                "emergency": "commanding_authoritative",
                "high": "alert_focused",
                "medium": "instructional_clear",
                "low": "reassuring_authority"
            },
            "wellness_coach": {
                "emergency": "motivating_supportive",
                "high": "energetic_positive",
                "medium": "motivating_supportive",
                "low": "celebratory_joyful"
            }
        }
        
        agent_fallbacks = fallback_map.get(agent_type, {})
        return agent_fallbacks.get(urgency, "professional_caring")
    
    def get_emotion_details(self, emotion_id: str) -> Optional[EmotionMapping]:
        """Get detailed information about an emotion"""
        return self.emotion_library.get(emotion_id)
    
    def get_available_emotions(self, agent_type: Optional[str] = None) -> List[EmotionMapping]:
        """Get list of available emotions, optionally filtered by agent type"""
        if agent_type:
            return self._get_agent_emotions(agent_type)
        else:
            return list(self.emotion_library.values())
    
    def get_emotion_for_urgency(self, agent_type: str, urgency: str) -> str:
        """Get recommended emotion for specific agent type and urgency level"""
        return self._get_fallback_emotion(agent_type, urgency)
    
    def clear_cache(self):
        """Clear emotion mapping cache"""
        self.mapping_cache.clear()
        self.logger.info("Emotion mapping cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cache_size": len(self.mapping_cache),
            "total_emotions": len(self.emotion_library),
            "cache_keys": list(self.mapping_cache.keys())[-10:]  # Last 10 keys
        }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_emotion_display_name(emotion_id: str, language: str = "en") -> str:
    """
    Get display name for emotion in specified language
    
    Args:
        emotion_id: Emotion identifier
        language: Language code ("en", "zh-HK")
        
    Returns:
        Display name in specified language
    """
    emotion_mapper = EmotionMapper()
    emotion = emotion_mapper.get_emotion_details(emotion_id)
    
    if not emotion:
        return emotion_id
    
    return emotion.cultural_variants.get(language, emotion.display_name)


def analyze_response_sentiment(response: str, language: str = "en") -> Tuple[str, float]:
    """
    Analyze sentiment of response text
    
    Args:
        response: Response text to analyze
        language: Language of response
        
    Returns:
        Tuple of (sentiment, confidence)
    """
    emotion_mapper = EmotionMapper()
    
    response_lower = response.lower()
    
    # Count sentiment indicators
    positive_count = sum(
        1 for keyword in emotion_mapper.positive_keywords.get(language, [])
        if keyword in response_lower
    )
    
    negative_count = sum(
        1 for keyword in emotion_mapper.negative_keywords.get(language, [])
        if keyword in response_lower
    )
    
    neutral_count = sum(
        1 for keyword in emotion_mapper.neutral_keywords.get(language, [])
        if keyword in response_lower
    )
    
    total_count = positive_count + negative_count + neutral_count
    
    if total_count == 0:
        return "neutral", 0.5
    
    # Determine sentiment and confidence
    if positive_count > negative_count and positive_count > neutral_count:
        sentiment = "positive"
        confidence = positive_count / total_count
    elif negative_count > positive_count and negative_count > neutral_count:
        sentiment = "negative"
        confidence = negative_count / total_count
    else:
        sentiment = "neutral"
        confidence = max(neutral_count / total_count, 0.6)
    
    return sentiment, min(confidence, 1.0)


# ============================================================================
# GLOBAL EMOTION MAPPER INSTANCE
# ============================================================================

# Global instance for use across the application
emotion_mapper = EmotionMapper()
