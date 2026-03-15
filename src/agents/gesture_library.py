"""
Hong Kong Cultural Gesture Library - Healthcare AI V2
=====================================================

Comprehensive library of culturally appropriate gestures for Live2D avatars
in Hong Kong healthcare context. Includes Cantonese-specific expressions,
traditional Chinese cultural elements, and modern Hong Kong social gestures.

Features:
- Hong Kong specific cultural gestures
- Cantonese language expression mapping
- Healthcare context-appropriate movements
- Agent personality-specific gesture sets
- Traditional and modern HK cultural fusion
- Accessibility and inclusivity considerations
"""

import random
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass

from src.core.logging import get_logger


logger = get_logger(__name__)


# ============================================================================
# GESTURE DEFINITIONS
# ============================================================================

class GestureCategory(str, Enum):
    """Gesture categories for organization"""
    GREETING = "greeting"
    MEDICAL_CONSULTATION = "medical_consultation"
    EMOTIONAL_SUPPORT = "emotional_support"
    EMERGENCY_RESPONSE = "emergency_response"
    CULTURAL_EXPRESSION = "cultural_expression"
    TEACHING_DEMONSTRATION = "teaching_demonstration"
    ENCOURAGEMENT = "encouragement"
    RESPECTFUL_INTERACTION = "respectful_interaction"


class GestureIntensity(str, Enum):
    """Gesture intensity levels"""
    SUBTLE = "subtle"          # Small, gentle movements
    MODERATE = "moderate"      # Normal, clear gestures
    EXPRESSIVE = "expressive"  # Large, animated movements
    DRAMATIC = "dramatic"      # Very animated, attention-grabbing


class CulturalContext(str, Enum):
    """Cultural context for gesture appropriateness"""
    TRADITIONAL = "traditional"    # Traditional Chinese culture
    MODERN_HK = "modern_hk"       # Modern Hong Kong culture
    YOUTH_CULTURE = "youth_culture" # Young people/teen culture
    ELDERLY_RESPECT = "elderly_respect" # Elderly interaction
    PROFESSIONAL = "professional"  # Professional healthcare setting
    CASUAL = "casual"             # Casual, friendly interaction


@dataclass
class GestureMapping:
    """Cultural gesture mapping with metadata"""
    gesture_id: str
    display_name: str
    category: GestureCategory
    intensity: GestureIntensity
    cultural_context: List[CulturalContext]
    agent_types: List[str]
    trigger_contexts: List[str]  # When to use this gesture
    cantonese_expressions: List[str]  # Related Cantonese expressions
    traditional_meaning: str  # Traditional cultural meaning
    modern_adaptation: str    # Modern Hong Kong adaptation
    description: str
    accessibility_notes: str  # Notes for users with different abilities
    animation_notes: str     # Technical notes for Live2D animation


# ============================================================================
# HONG KONG CULTURAL GESTURE LIBRARY
# ============================================================================

class HKGestureLibrary:
    """
    Comprehensive library of Hong Kong cultural gestures
    """
    
    # Traditional Chinese Cultural Gestures
    TRADITIONAL_GESTURES = [
        GestureMapping(
            gesture_id="respectful_bow",
            display_name="尊敬鞠躬",
            category=GestureCategory.RESPECTFUL_INTERACTION,
            intensity=GestureIntensity.SUBTLE,
            cultural_context=[CulturalContext.TRADITIONAL, CulturalContext.ELDERLY_RESPECT, CulturalContext.PROFESSIONAL],
            agent_types=["illness_monitor", "safety_guardian"],
            trigger_contexts=["elderly_patient", "formal_consultation", "serious_diagnosis", "showing_respect"],
            cantonese_expressions=["請多指教", "唔該晒", "多謝您"],
            traditional_meaning="Shows deep respect and humility in formal interactions",
            modern_adaptation="Adapted as gentle head nod in professional healthcare settings",
            description="Gentle bow from waist showing respect for patients and elders",
            accessibility_notes="Can be adapted as head nod for users with mobility limitations",
            animation_notes="15-20 degree forward lean, hold 1-2 seconds, gentle return"
        ),
        
        GestureMapping(
            gesture_id="tea_offering_gesture",
            display_name="奉茶手勢",
            category=GestureCategory.CULTURAL_EXPRESSION,
            intensity=GestureIntensity.MODERATE,
            cultural_context=[CulturalContext.TRADITIONAL, CulturalContext.MODERN_HK],
            agent_types=["illness_monitor", "mental_health", "wellness_coach"],
            trigger_contexts=["offering_help", "hospitality", "comfort", "traditional_medicine"],
            cantonese_expressions=["飲茶", "請飲", "慢慢飲"],
            traditional_meaning="Hospitality and care through offering refreshment",
            modern_adaptation="Gesture of offering support and comfort in healthcare",
            description="Gentle two-handed offering gesture, palms up, welcoming",
            accessibility_notes="Single-handed version available for those with limited mobility",
            animation_notes="Both hands extend forward, palms up, gentle upward motion"
        ),
        
        GestureMapping(
            gesture_id="traditional_greeting",
            display_name="傳統問候",
            category=GestureCategory.GREETING,
            intensity=GestureIntensity.MODERATE,
            cultural_context=[CulturalContext.TRADITIONAL, CulturalContext.PROFESSIONAL],
            agent_types=["illness_monitor", "safety_guardian"],
            trigger_contexts=["first_meeting", "formal_greeting", "respect_showing"],
            cantonese_expressions=["您好", "早晨", "請坐"],
            traditional_meaning="Respectful greeting acknowledging the other person's dignity",
            modern_adaptation="Professional medical greeting with cultural warmth",
            description="Hands together in prayer position with slight bow",
            accessibility_notes="Can be modified to single hand gesture",
            animation_notes="Palms together at chest level, gentle bow, 2-second hold"
        )
    ]
    
    # Modern Hong Kong Cultural Gestures
    MODERN_HK_GESTURES = [
        GestureMapping(
            gesture_id="cha_chaan_teng_point",
            display_name="茶餐廳指路",
            category=GestureCategory.TEACHING_DEMONSTRATION,
            intensity=GestureIntensity.MODERATE,
            cultural_context=[CulturalContext.MODERN_HK, CulturalContext.CASUAL],
            agent_types=["wellness_coach", "mental_health"],
            trigger_contexts=["giving_directions", "explaining_locations", "casual_conversation"],
            cantonese_expressions=["行呢邊", "轉左", "直行"],
            traditional_meaning="Helpful direction-giving in community settings",
            modern_adaptation="Friendly, helpful guidance in healthcare navigation",
            description="Casual pointing with open hand, friendly and approachable",
            accessibility_notes="Voice description accompanies visual gesture",
            animation_notes="Open palm pointing, relaxed wrist, warm expression"
        ),
        
        GestureMapping(
            gesture_id="dim_sum_sharing",
            display_name="點心分享",
            category=GestureCategory.CULTURAL_EXPRESSION,
            intensity=GestureIntensity.MODERATE,
            cultural_context=[CulturalContext.MODERN_HK, CulturalContext.CASUAL],
            agent_types=["mental_health", "wellness_coach"],
            trigger_contexts=["sharing_wisdom", "community_support", "family_discussion"],
            cantonese_expressions=["一齊食", "分享下", "試下啦"],
            traditional_meaning="Community bonding through shared meals",
            modern_adaptation="Sharing knowledge and support in healthcare context",
            description="Inviting gesture towards shared space, encouraging participation",
            accessibility_notes="Accompanied by verbal invitation for inclusive participation",
            animation_notes="Sweeping arm motion towards center, open and inviting"
        ),
        
        GestureMapping(
            gesture_id="mtr_directions",
            display_name="港鐵指路",
            category=GestureCategory.TEACHING_DEMONSTRATION,
            intensity=GestureIntensity.MODERATE,
            cultural_context=[CulturalContext.MODERN_HK, CulturalContext.PROFESSIONAL],
            agent_types=["illness_monitor", "safety_guardian"],
            trigger_contexts=["hospital_directions", "clinic_navigation", "transport_guidance"],
            cantonese_expressions=["搭呢條線", "出口A", "轉車"],
            traditional_meaning="Practical navigation help within Hong Kong infrastructure",
            modern_adaptation="Healthcare facility navigation and transport guidance",
            description="Clear directional gestures mimicking MTR signage style",
            accessibility_notes="Clear verbal directions with landmark references",
            animation_notes="Sharp, clear pointing motions with definitive pauses"
        ),
        
        GestureMapping(
            gesture_id="local_recommendation",
            display_name="本地推薦",
            category=GestureCategory.CULTURAL_EXPRESSION,
            intensity=GestureIntensity.EXPRESSIVE,
            cultural_context=[CulturalContext.MODERN_HK, CulturalContext.CASUAL],
            agent_types=["wellness_coach", "mental_health"],
            trigger_contexts=["recommending_services", "local_knowledge", "community_resources"],
            cantonese_expressions=["呢間好好", "試下啦", "真係推薦"],
            traditional_meaning="Sharing local knowledge and community recommendations",
            modern_adaptation="Recommending healthcare services and wellness resources",
            description="Enthusiastic pointing with confident expression, authentic recommendation",
            accessibility_notes="Detailed verbal explanation of recommendations",
            animation_notes="Confident pointing with positive facial expression"
        )
    ]
    
    # Cantonese Language-Specific Gestures
    CANTONESE_EXPRESSION_GESTURES = [
        GestureMapping(
            gesture_id="cantonese_emphasis",
            display_name="廣東話強調",
            category=GestureCategory.CULTURAL_EXPRESSION,
            intensity=GestureIntensity.EXPRESSIVE,
            cultural_context=[CulturalContext.MODERN_HK, CulturalContext.YOUTH_CULTURE],
            agent_types=["mental_health", "wellness_coach"],
            trigger_contexts=["emphasizing_point", "emotional_expression", "cantonese_conversation"],
            cantonese_expressions=["真係㗎", "好重要㗎", "係咁㗎啦"],
            traditional_meaning="Emotional emphasis in Cantonese conversation patterns",
            modern_adaptation="Expressive communication in healthcare discussions",
            description="Animated hand gestures accompanying Cantonese speech patterns",
            accessibility_notes="Gesture matches vocal emphasis patterns",
            animation_notes="Rhythmic hand movements matching speech cadence"
        ),
        
        GestureMapping(
            gesture_id="aiya_expression",
            display_name="哎呀表達",
            category=GestureCategory.EMOTIONAL_SUPPORT,
            intensity=GestureIntensity.MODERATE,
            cultural_context=[CulturalContext.MODERN_HK, CulturalContext.CASUAL],
            agent_types=["mental_health", "illness_monitor"],
            trigger_contexts=["sympathy", "understanding_concern", "mild_disappointment"],
            cantonese_expressions=["哎呀", "唉", "咁樣啊"],
            traditional_meaning="Expressing sympathy and understanding",
            modern_adaptation="Empathetic response in healthcare conversations",
            description="Hand to forehead or gentle head shake showing understanding",
            accessibility_notes="Accompanied by empathetic vocal tone",
            animation_notes="Gentle head movement with concerned expression"
        ),
        
        GestureMapping(
            gesture_id="wah_amazement",
            display_name="嘩驚嘆",
            category=GestureCategory.ENCOURAGEMENT,
            intensity=GestureIntensity.EXPRESSIVE,
            cultural_context=[CulturalContext.MODERN_HK, CulturalContext.YOUTH_CULTURE],
            agent_types=["mental_health", "wellness_coach"],
            trigger_contexts=["amazement", "positive_surprise", "celebration"],
            cantonese_expressions=["嘩", "好勁啊", "好叻"],
            traditional_meaning="Expressing amazement and admiration",
            modern_adaptation="Celebrating patient progress and achievements",
            description="Wide eyes with open mouth, hands slightly raised in amazement",
            accessibility_notes="Enthusiastic vocal expression accompanies gesture",
            animation_notes="Eyes widen, slight mouth opening, hands raise slightly"
        )
    ]
    
    # Medical and Healthcare-Specific Gestures
    MEDICAL_GESTURES = [
        GestureMapping(
            gesture_id="medical_consultation",
            display_name="醫療諮詢",
            category=GestureCategory.MEDICAL_CONSULTATION,
            intensity=GestureIntensity.MODERATE,
            cultural_context=[CulturalContext.PROFESSIONAL, CulturalContext.TRADITIONAL],
            agent_types=["illness_monitor", "safety_guardian"],
            trigger_contexts=["explaining_symptoms", "medical_advice", "professional_consultation"],
            cantonese_expressions=["點樣呀", "邊度痛", "覺得點"],
            traditional_meaning="Professional medical inquiry with cultural sensitivity",
            modern_adaptation="Modern healthcare consultation with traditional respect",
            description="Professional pointing to body areas with gentle, caring expression",
            accessibility_notes="Clear verbal description of areas being discussed",
            animation_notes="Gentle pointing with medical diagram reference"
        ),
        
        GestureMapping(
            gesture_id="reassuring_medical",
            display_name="醫療安撫",
            category=GestureCategory.EMOTIONAL_SUPPORT,
            intensity=GestureIntensity.SUBTLE,
            cultural_context=[CulturalContext.PROFESSIONAL, CulturalContext.ELDERLY_RESPECT],
            agent_types=["illness_monitor", "mental_health"],
            trigger_contexts=["reassurance", "comfort", "anxiety_relief"],
            cantonese_expressions=["唔洗驚", "會好返嘅", "慢慢嚟"],
            traditional_meaning="Calming presence in times of health concern",
            modern_adaptation="Professional reassurance with cultural warmth",
            description="Open palms facing down, gentle lowering motion, calming presence",
            accessibility_notes="Calm, steady voice accompanies soothing gesture",
            animation_notes="Slow, gentle downward palm movement, peaceful expression"
        ),
        
        GestureMapping(
            gesture_id="concern_expression",
            display_name="關心表達",
            category=GestureCategory.EMOTIONAL_SUPPORT,
            intensity=GestureIntensity.SUBTLE,
            cultural_context=[CulturalContext.PROFESSIONAL, CulturalContext.MODERN_HK],
            agent_types=["illness_monitor", "mental_health", "safety_guardian"],
            trigger_contexts=["showing_concern", "empathy", "serious_discussion"],
            cantonese_expressions=["我好擔心", "要小心啲", "注意下"],
            traditional_meaning="Expressing genuine care and concern for others' wellbeing",
            modern_adaptation="Professional healthcare concern with personal touch",
            description="Slight forward lean, furrowed brow, hands clasped in concern",
            accessibility_notes="Concerned tone of voice conveys caring",
            animation_notes="Subtle forward lean, gentle facial expression change"
        ),
    ]
    
    # Emergency and Safety Gestures
    EMERGENCY_GESTURES = [
        GestureMapping(
            gesture_id="emergency_stance",
            display_name="緊急姿態",
            category=GestureCategory.EMERGENCY_RESPONSE,
            intensity=GestureIntensity.DRAMATIC,
            cultural_context=[CulturalContext.PROFESSIONAL],
            agent_types=["safety_guardian"],
            trigger_contexts=["emergency_situation", "urgent_action", "crisis_response"],
            cantonese_expressions=["緊急", "快啲", "救命"],
            traditional_meaning="Immediate action required for safety",
            modern_adaptation="Emergency healthcare response with clear authority",
            description="Alert posture, raised hand for attention, urgent but controlled",
            accessibility_notes="Clear, loud voice commands accompany urgent gestures",
            animation_notes="Straight posture, raised hand, alert facial expression"
        ),
        
        GestureMapping(
            gesture_id="stop_gesture",
            display_name="停止手勢",
            category=GestureCategory.EMERGENCY_RESPONSE,
            intensity=GestureIntensity.DRAMATIC,
            cultural_context=[CulturalContext.PROFESSIONAL],
            agent_types=["safety_guardian", "illness_monitor"],
            trigger_contexts=["stop_action", "prevent_harm", "safety_warning"],
            cantonese_expressions=["停", "唔好", "危險"],
            traditional_meaning="Clear signal to prevent dangerous action",
            modern_adaptation="Healthcare safety intervention with clear authority",
            description="Firm palm facing forward, strong stance, clear eye contact",
            accessibility_notes="Strong verbal 'stop' command accompanies gesture",
            animation_notes="Firm palm forward, steady arm, serious expression"
        ),
        
        GestureMapping(
            gesture_id="urgent_pointing",
            display_name="急切指示",
            category=GestureCategory.EMERGENCY_RESPONSE,
            intensity=GestureIntensity.EXPRESSIVE,
            cultural_context=[CulturalContext.PROFESSIONAL],
            agent_types=["safety_guardian"],
            trigger_contexts=["emergency_directions", "urgent_guidance", "immediate_action"],
            cantonese_expressions=["去嗰邊", "快啲走", "跟住我"],
            traditional_meaning="Clear direction in times of urgent need",
            modern_adaptation="Emergency healthcare navigation and guidance",
            description="Sharp, definitive pointing with urgent but controlled energy",
            accessibility_notes="Clear verbal directions with landmark references",
            animation_notes="Quick, decisive pointing motion with confident posture"
        )
    ]
    
    # Youth and Mental Health Gestures
    YOUTH_SUPPORT_GESTURES = [
        GestureMapping(
            gesture_id="encouraging_smile",
            display_name="鼓勵微笑",
            category=GestureCategory.ENCOURAGEMENT,
            intensity=GestureIntensity.MODERATE,
            cultural_context=[CulturalContext.YOUTH_CULTURE, CulturalContext.MODERN_HK],
            agent_types=["mental_health", "wellness_coach"],
            trigger_contexts=["encouragement", "positive_reinforcement", "youth_interaction"],
            cantonese_expressions=["好叻", "加油", "得㗎"],
            traditional_meaning="Positive reinforcement and encouragement",
            modern_adaptation="Youth-friendly mental health support",
            description="Bright smile with thumbs up or gentle clapping motion",
            accessibility_notes="Enthusiastic vocal encouragement",
            animation_notes="Bright facial expression with positive hand gesture"
        ),
        
        GestureMapping(
            gesture_id="listening_pose",
            display_name="聆聽姿態",
            category=GestureCategory.EMOTIONAL_SUPPORT,
            intensity=GestureIntensity.SUBTLE,
            cultural_context=[CulturalContext.YOUTH_CULTURE, CulturalContext.PROFESSIONAL],
            agent_types=["mental_health"],
            trigger_contexts=["active_listening", "emotional_support", "confidential_discussion"],
            cantonese_expressions=["講俾我聽", "我明白", "慢慢講"],
            traditional_meaning="Respectful attention and active listening",
            modern_adaptation="Youth-friendly counseling approach",
            description="Slight forward lean, hands relaxed, full attention focused",
            accessibility_notes="Patient silence and encouraging vocal cues",
            animation_notes="Gentle forward lean, relaxed posture, attentive eyes"
        ),
        
        GestureMapping(
            gesture_id="heart_hands",
            display_name="愛心手勢",
            category=GestureCategory.EMOTIONAL_SUPPORT,
            intensity=GestureIntensity.MODERATE,
            cultural_context=[CulturalContext.YOUTH_CULTURE, CulturalContext.MODERN_HK],
            agent_types=["mental_health"],
            trigger_contexts=["expressing_care", "emotional_connection", "support"],
            cantonese_expressions=["錫錫", "愛你", "關心你"],
            traditional_meaning="Expressing love and care",
            modern_adaptation="Modern way to show care and emotional support",
            description="Hands forming heart shape, warm expression, caring gesture",
            accessibility_notes="Warm, caring vocal tone",
            animation_notes="Hands form heart shape above head, gentle smile"
        ),
    ]


# ============================================================================
# GESTURE LIBRARY CLASS
# ============================================================================

class GestureLibrary:
    """
    Main gesture library for Live2D avatar cultural expressions
    
    Manages:
    - Cultural gesture selection
    - Context-appropriate gesture mapping
    - Agent personality gesture matching
    - Accessibility considerations
    - Dynamic gesture recommendation
    """
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.GestureLibrary")
        
        # Build comprehensive gesture library
        self.gesture_library = self._build_gesture_library()
        
        # Gesture selection cache
        self.selection_cache: Dict[str, str] = {}
        
        # Gesture usage statistics
        self.usage_stats: Dict[str, int] = {}
        
        self.logger.info(f"Loaded {len(self.gesture_library)} cultural gestures")
    
    def _build_gesture_library(self) -> Dict[str, GestureMapping]:
        """Build comprehensive gesture library"""
        library = {}
        
        # Add all predefined gestures
        all_gestures = (
            HKGestureLibrary.TRADITIONAL_GESTURES +
            HKGestureLibrary.MODERN_HK_GESTURES +
            HKGestureLibrary.CANTONESE_EXPRESSION_GESTURES +
            HKGestureLibrary.MEDICAL_GESTURES +
            HKGestureLibrary.EMERGENCY_GESTURES +
            HKGestureLibrary.YOUTH_SUPPORT_GESTURES
        )
        
        for gesture in all_gestures:
            library[gesture.gesture_id] = gesture
        
        return library
    
    def get_cultural_gesture(
        self,
        agent_type: str,
        context: str,
        language: str = "en",
        urgency: str = "low",
        user_age_group: Optional[str] = None,
        cultural_preference: str = "modern_hk"
    ) -> str:
        """
        Get culturally appropriate gesture for context
        
        Args:
            agent_type: Type of agent requesting gesture
            context: Context or trigger for gesture
            language: Language of interaction ("en", "zh-HK")
            urgency: Urgency level of situation
            user_age_group: Age group of user ("child", "teen", "adult", "elderly")
            cultural_preference: Cultural context preference
            
        Returns:
            Gesture ID for Live2D animation
        """
        try:
            # Create cache key
            cache_key = f"{agent_type}:{urgency}:{hash(context[:50])}:{language}:{cultural_preference}"
            if cache_key in self.selection_cache:
                gesture_id = self.selection_cache[cache_key]
                self._track_usage(gesture_id)
                return gesture_id
            
            # Get candidate gestures
            candidates = self._get_candidate_gestures(
                agent_type, context, urgency, user_age_group, cultural_preference
            )
            
            if not candidates:
                gesture_id = self._get_fallback_gesture(agent_type, urgency)
            else:
                # Score and select best gesture
                gesture_id = self._select_best_gesture(candidates, context, language, urgency)
            
            # Cache result
            self.selection_cache[cache_key] = gesture_id
            self._track_usage(gesture_id)
            
            self.logger.debug(f"Selected gesture '{gesture_id}' for {agent_type} in {cultural_preference} context")
            return gesture_id
            
        except Exception as e:
            self.logger.error(f"Error selecting cultural gesture: {e}")
            return self._get_fallback_gesture(agent_type, urgency)
    
    def _get_candidate_gestures(
        self,
        agent_type: str,
        context: str,
        urgency: str,
        user_age_group: Optional[str],
        cultural_preference: str
    ) -> List[GestureMapping]:
        """Get candidate gestures based on criteria"""
        candidates = []
        context_lower = context.lower()
        
        for gesture in self.gesture_library.values():
            # Check agent type compatibility
            if agent_type not in gesture.agent_types:
                continue
            
            # Check cultural context compatibility
            cultural_contexts = [ctx.value for ctx in gesture.cultural_context]
            if cultural_preference not in cultural_contexts:
                continue
            
            # Check trigger context matching
            context_matches = any(
                trigger in context_lower for trigger in gesture.trigger_contexts
            )
            
            # Check urgency appropriateness
            urgency_appropriate = self._is_urgency_appropriate(gesture, urgency)
            
            # Check age group appropriateness
            age_appropriate = self._is_age_appropriate(gesture, user_age_group)
            
            if context_matches and urgency_appropriate and age_appropriate:
                candidates.append(gesture)
        
        return candidates
    
    def _is_urgency_appropriate(self, gesture: GestureMapping, urgency: str) -> bool:
        """Check if gesture intensity matches urgency level"""
        urgency_intensity_map = {
            "emergency": [GestureIntensity.DRAMATIC, GestureIntensity.EXPRESSIVE],
            "high": [GestureIntensity.EXPRESSIVE, GestureIntensity.MODERATE],
            "medium": [GestureIntensity.MODERATE, GestureIntensity.SUBTLE],
            "low": [GestureIntensity.SUBTLE, GestureIntensity.MODERATE]
        }
        
        appropriate_intensities = urgency_intensity_map.get(urgency, [GestureIntensity.MODERATE])
        return gesture.intensity in appropriate_intensities
    
    def _is_age_appropriate(self, gesture: GestureMapping, user_age_group: Optional[str]) -> bool:
        """Check if gesture is appropriate for user age group"""
        if not user_age_group:
            return True
        
        age_cultural_map = {
            "child": [CulturalContext.YOUTH_CULTURE, CulturalContext.CASUAL],
            "teen": [CulturalContext.YOUTH_CULTURE, CulturalContext.MODERN_HK],
            "adult": [CulturalContext.MODERN_HK, CulturalContext.PROFESSIONAL],
            "elderly": [CulturalContext.TRADITIONAL, CulturalContext.ELDERLY_RESPECT, CulturalContext.PROFESSIONAL]
        }
        
        appropriate_contexts = age_cultural_map.get(user_age_group, [CulturalContext.MODERN_HK])
        return any(ctx in gesture.cultural_context for ctx in appropriate_contexts)
    
    def _select_best_gesture(
        self,
        candidates: List[GestureMapping],
        context: str,
        language: str,
        urgency: str
    ) -> str:
        """Select best gesture from candidates"""
        if len(candidates) == 1:
            return candidates[0].gesture_id
        
        # Score candidates
        scores = {}
        context_lower = context.lower()
        
        for gesture in candidates:
            score = 0.0
            
            # Context trigger matching (40% weight)
            trigger_matches = sum(
                1 for trigger in gesture.trigger_contexts
                if trigger in context_lower
            )
            score += (trigger_matches / max(len(gesture.trigger_contexts), 1)) * 0.4
            
            # Cantonese expression matching for zh-HK (30% weight)
            if language == "zh-HK":
                cantonese_matches = sum(
                    1 for expr in gesture.cantonese_expressions
                    if any(word in context_lower for word in expr.split())
                )
                score += (cantonese_matches / max(len(gesture.cantonese_expressions), 1)) * 0.3
            else:
                score += 0.2  # Default score for non-Cantonese
            
            # Usage diversity (20% weight) - prefer less frequently used gestures
            usage_count = self.usage_stats.get(gesture.gesture_id, 0)
            max_usage = max(self.usage_stats.values()) if self.usage_stats else 1
            diversity_score = 1.0 - (usage_count / max(max_usage, 1))
            score += diversity_score * 0.2
            
            # Random factor for variety (10% weight)
            score += random.uniform(0, 0.1)
            
            scores[gesture.gesture_id] = score
        
        # Select highest scoring gesture
        best_gesture = max(scores.items(), key=lambda x: x[1])
        return best_gesture[0]
    
    def _get_fallback_gesture(self, agent_type: str, urgency: str) -> str:
        """Get fallback gesture when no candidates found"""
        fallback_map = {
            "illness_monitor": {
                "emergency": "concern_expression",
                "high": "medical_consultation",
                "medium": "reassuring_medical",
                "low": "traditional_greeting"
            },
            "mental_health": {
                "emergency": "encouraging_smile",
                "high": "listening_pose",
                "medium": "heart_hands",
                "low": "encouraging_smile"
            },
            "safety_guardian": {
                "emergency": "emergency_stance",
                "high": "urgent_pointing",
                "medium": "stop_gesture",
                "low": "respectful_bow"
            },
            "wellness_coach": {
                "emergency": "encouraging_smile",
                "high": "local_recommendation",
                "medium": "dim_sum_sharing",
                "low": "tea_offering_gesture"
            }
        }
        
        agent_fallbacks = fallback_map.get(agent_type, {})
        return agent_fallbacks.get(urgency, "traditional_greeting")
    
    def _track_usage(self, gesture_id: str):
        """Track gesture usage for diversity scoring"""
        self.usage_stats[gesture_id] = self.usage_stats.get(gesture_id, 0) + 1
    
    def get_gesture_details(self, gesture_id: str) -> Optional[GestureMapping]:
        """Get detailed information about a gesture"""
        return self.gesture_library.get(gesture_id)
    
    def get_gestures_by_category(self, category: GestureCategory) -> List[GestureMapping]:
        """Get all gestures in a specific category"""
        return [
            gesture for gesture in self.gesture_library.values()
            if gesture.category == category
        ]
    
    def get_gestures_by_agent(self, agent_type: str) -> List[GestureMapping]:
        """Get all gestures available for a specific agent"""
        return [
            gesture for gesture in self.gesture_library.values()
            if agent_type in gesture.agent_types
        ]
    
    def get_cantonese_expressions(self, gesture_id: str) -> List[str]:
        """Get Cantonese expressions associated with a gesture"""
        gesture = self.get_gesture_details(gesture_id)
        return gesture.cantonese_expressions if gesture else []
    
    def search_gestures_by_cantonese(self, cantonese_text: str) -> List[str]:
        """Search gestures by Cantonese expression"""
        results = []
        text_lower = cantonese_text.lower()
        
        for gesture in self.gesture_library.values():
            for expression in gesture.cantonese_expressions:
                if any(word in text_lower for word in expression):
                    results.append(gesture.gesture_id)
                    break
        
        return results
    
    def get_accessibility_notes(self, gesture_id: str) -> str:
        """Get accessibility notes for a gesture"""
        gesture = self.get_gesture_details(gesture_id)
        return gesture.accessibility_notes if gesture else ""
    
    def get_animation_notes(self, gesture_id: str) -> str:
        """Get animation notes for Live2D implementation"""
        gesture = self.get_gesture_details(gesture_id)
        return gesture.animation_notes if gesture else ""
    
    def clear_cache(self):
        """Clear gesture selection cache"""
        self.selection_cache.clear()
        self.logger.info("Gesture selection cache cleared")
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        """Get gesture usage statistics"""
        total_uses = sum(self.usage_stats.values())
        
        return {
            "total_gestures": len(self.gesture_library),
            "total_uses": total_uses,
            "most_used": max(self.usage_stats.items(), key=lambda x: x[1]) if self.usage_stats else None,
            "least_used": min(self.usage_stats.items(), key=lambda x: x[1]) if self.usage_stats else None,
            "cache_size": len(self.selection_cache),
            "usage_distribution": dict(sorted(self.usage_stats.items(), key=lambda x: x[1], reverse=True)[:10])
        }
    
    def get_cultural_gesture_recommendations(
        self,
        user_profile: Dict[str, Any],
        conversation_context: List[Dict[str, Any]]
    ) -> List[Tuple[str, str, float]]:
        """
        Get personalized gesture recommendations
        
        Args:
            user_profile: User information and preferences
            conversation_context: Recent conversation history
            
        Returns:
            List of tuples: (gesture_id, reason, relevance_score)
        """
        recommendations = []
        
        # Analyze user preferences
        age_group = user_profile.get("age_group", "adult")
        user_profile.get("language", "en")
        cultural_background = user_profile.get("cultural_background", "modern_hk")
        
        # Analyze conversation context
        recent_topics = []
        if conversation_context:
            for item in conversation_context[-3:]:  # Last 3 exchanges
                recent_topics.extend(item.get("topics", []))
        
        # Generate recommendations based on patterns
        for gesture in self.gesture_library.values():
            relevance_score = 0.0
            reasons = []
            
            # Age appropriateness
            if self._is_age_appropriate(gesture, age_group):
                relevance_score += 0.3
                reasons.append(f"Age-appropriate for {age_group}")
            
            # Cultural matching
            if any(ctx.value == cultural_background for ctx in gesture.cultural_context):
                relevance_score += 0.3
                reasons.append(f"Matches {cultural_background} culture")
            
            # Topic relevance
            topic_matches = sum(
                1 for topic in recent_topics
                if any(trigger in topic.lower() for trigger in gesture.trigger_contexts)
            )
            if topic_matches > 0:
                relevance_score += 0.4
                reasons.append("Relevant to recent topics")
            
            if relevance_score > 0.5:  # Only include high-relevance recommendations
                recommendations.append((
                    gesture.gesture_id,
                    "; ".join(reasons),
                    relevance_score
                ))
        
        # Sort by relevance score
        recommendations.sort(key=lambda x: x[2], reverse=True)
        
        return recommendations[:5]  # Top 5 recommendations


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_gesture_display_name(gesture_id: str, language: str = "en") -> str:
    """
    Get display name for gesture
    
    Args:
        gesture_id: Gesture identifier
        language: Language for display name
        
    Returns:
        Display name
    """
    gesture_library = GestureLibrary()
    gesture = gesture_library.get_gesture_details(gesture_id)
    
    if not gesture:
        return gesture_id
    
    return gesture.display_name


def find_gestures_for_cantonese_phrase(phrase: str) -> List[str]:
    """
    Find appropriate gestures for Cantonese phrase
    
    Args:
        phrase: Cantonese phrase or expression
        
    Returns:
        List of gesture IDs
    """
    gesture_library = GestureLibrary()
    return gesture_library.search_gestures_by_cantonese(phrase)


# ============================================================================
# GLOBAL GESTURE LIBRARY INSTANCE
# ============================================================================

# Global instance for use across the application
gesture_library = GestureLibrary()
