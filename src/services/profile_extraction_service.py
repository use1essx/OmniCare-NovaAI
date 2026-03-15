"""
Profile Extraction Service - Healthcare AI V2
=============================================

AI-assisted profile building through natural conversation.
Extracts user profile data from chat messages and helps fill incomplete profiles.

Features:
- Detect incomplete profile fields
- Extract profile data from conversation
- Generate natural questions to gather missing info
- Update health profile in database
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

from src.core.logging import get_logger
from src.database.health_profile_models import (
    HealthProfile, 
    AgeGroupEnum, 
    GenderEnum, 
    SchoolLevelEnum
)

logger = get_logger(__name__)


@dataclass
class ProfileCompleteness:
    """Profile completeness assessment"""
    is_complete: bool
    completion_percentage: float
    missing_fields: List[str]
    priority_fields: List[str]  # Fields to ask about first
    next_question_topic: Optional[str]


@dataclass
class ExtractedProfileData:
    """Data extracted from conversation"""
    field_name: str
    value: Any
    confidence: float
    source_text: str
    is_correction: bool = False  # True if user is correcting previous info


class ProfileExtractionService:
    """
    Service for AI-assisted profile building through conversation.
    
    Analyzes chat messages to extract profile information and
    generates natural questions to gather missing data.
    """
    
    # Priority order for gathering profile info (most important first)
    PRIORITY_FIELDS = [
        "nickname",           # What to call them
        "age",                # Age group affects communication style
        "school_level",       # School context
        "current_mood",       # Current emotional state
        "hobbies",            # Interests for rapport building
        "stress_sources",     # Key mental health info
        "coping_strategies",  # How they handle stress
    ]
    
    # Fields that can be extracted from conversation
    EXTRACTABLE_FIELDS = {
        "nickname": ["name", "call me", "叫我", "我叫", "都叫我", "其實叫", "唔係", "actually"],
        "age": ["years old", "歲", "year old", "age"],
        "school_level": ["p1", "p2", "p3", "p4", "p5", "p6", "s1", "s2", "s3", "s4", "s5", "s6", 
                        "primary", "secondary", "小學", "中學", "大學", "university",
                        "小一", "小二", "小三", "小四", "小五", "小六",
                        "中一", "中二", "中三", "中四", "中五", "中六", "讀緊"],
        "current_mood": ["feeling", "feel", "mood", "覺得", "心情", "開心", "唔開心", "sad", "happy", 
                        "stressed", "anxious", "worried", "擔心", "焦慮", "壓力", "攰", "嬲"],
        "hobbies": ["like to", "enjoy", "hobby", "興趣", "鍾意", "喜歡", "play", "玩", "學", "打機", "打波", "睇"],
        "stress_sources": ["stress", "pressure", "worried about", "壓力", "擔心", "煩惱", 
                          "exam", "考試", "homework", "功課", "做唔完", "辛苦", "煩", "問題"],
        "favorite_subjects": ["favorite subject", "like", "好鍾意", "最鍾意", "math", "數學", 
                             "english", "英文", "chinese", "中文", "science", "科學"],
        "challenging_subjects": ["hard", "difficult", "struggle", "難", "唔識", "唔明", "don't understand"],
        "sleep_hours_weekday": ["sleep", "瞓", "hours", "小時", "bedtime", "瞓覺"],
        "physical_activity_level": ["exercise", "sport", "運動", "active", "play", "玩"],
        "friend_circle_size": ["friends", "朋友", "alone", "孤獨", "lonely"],
        "relationship_with_parents": ["parents", "父母", "mom", "dad", "媽媽", "爸爸", "family", "家人"],
        "dream_career": ["want to be", "dream", "future", "將來", "夢想", "想做"],
    }
    
    # Question templates for gathering missing info (Traditional Chinese - Cantonese)
    QUESTION_TEMPLATES = {
        "nickname": "我可以點樣稱呼你呀？",
        "age": "你今年幾歲呀？",
        "school_level": "你而家讀緊邊級呀？",
        "current_mood": "你今日心情點呀？",
        "hobbies": "你平時鍾意做啲咩呀？有咩興趣？",
        "stress_sources": "最近有冇咩嘢令你覺得有壓力或者煩惱？",
        "favorite_subjects": "你最鍾意邊科呀？",
        "challenging_subjects": "有冇邊科你覺得比較難？",
        "sleep_hours_weekday": "你平時幾點瞓覺呀？瞓得夠唔夠？",
        "physical_activity_level": "你平時有冇做運動呀？",
        "friend_circle_size": "你喺學校有冇好朋友呀？",
        "dream_career": "你將來想做咩呀？有冇諗過？",
        "coping_strategies": "當你唔開心嘅時候，你通常會點做呀？",
    }
    
    # Correction patterns - when user wants to fix previous info
    CORRECTION_PATTERNS = [
        r"唔係",           # "not" / "no"
        r"錯咗",           # "wrong"
        r"其實",           # "actually"
        r"應該係",         # "should be"
        r"唔啱",           # "incorrect"
        r"搞錯",           # "made a mistake"
        r"改返",           # "change back"
        r"改做",           # "change to"
        r"唔好叫我",       # "don't call me"
        r"actually",
        r"sorry",
        r"i meant",
        r"not.*but",
        r"correction",
    ]
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.ProfileExtractionService")
    
    def assess_profile_completeness(self, profile: Optional[HealthProfile]) -> ProfileCompleteness:
        """
        Assess how complete a user's profile is.
        
        Args:
            profile: User's health profile (may be None)
            
        Returns:
            ProfileCompleteness assessment
        """
        if not profile:
            return ProfileCompleteness(
                is_complete=False,
                completion_percentage=0.0,
                missing_fields=self.PRIORITY_FIELDS.copy(),
                priority_fields=self.PRIORITY_FIELDS[:3],
                next_question_topic="nickname"
            )
        
        # Check which priority fields are filled
        filled_fields = []
        missing_fields = []
        
        for field in self.PRIORITY_FIELDS:
            value = getattr(profile, field, None)
            if value is not None and value != "" and value != []:
                filled_fields.append(field)
            else:
                missing_fields.append(field)
        
        # Calculate completion percentage
        total_fields = len(self.PRIORITY_FIELDS)
        completion_percentage = (len(filled_fields) / total_fields) * 100 if total_fields > 0 else 0
        
        # Determine next question topic
        next_topic = missing_fields[0] if missing_fields else None
        
        return ProfileCompleteness(
            is_complete=len(missing_fields) == 0,
            completion_percentage=completion_percentage,
            missing_fields=missing_fields,
            priority_fields=missing_fields[:3],
            next_question_topic=next_topic
        )
    
    def extract_profile_data_from_message(
        self, 
        message: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> List[ExtractedProfileData]:
        """
        Extract profile data from a user message.
        
        Args:
            message: User's chat message
            context: Optional conversation context
            
        Returns:
            List of extracted profile data
        """
        extracted = []
        message_lower = message.lower()
        
        # Check if this is a correction
        is_correction = self._is_correction_message(message)
        
        # Try to extract each field type
        for field_name, keywords in self.EXTRACTABLE_FIELDS.items():
            if any(kw in message_lower for kw in keywords):
                value, confidence = self._extract_field_value(field_name, message)
                if value is not None:
                    # Boost confidence for corrections (user is being explicit)
                    if is_correction:
                        confidence = min(confidence + 0.1, 1.0)
                    
                    extracted.append(ExtractedProfileData(
                        field_name=field_name,
                        value=value,
                        confidence=confidence,
                        source_text=message[:100],
                        is_correction=is_correction
                    ))
        
        return extracted
    
    def _is_correction_message(self, message: str) -> bool:
        """
        Check if the message is correcting previous information.
        
        Args:
            message: User's message
            
        Returns:
            True if this is a correction
        """
        message_lower = message.lower()
        for pattern in self.CORRECTION_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE) or pattern in message:
                return True
        return False
        
        return extracted
    
    def _extract_field_value(self, field_name: str, message: str) -> Tuple[Optional[Any], float]:
        """
        Extract specific field value from message.
        
        Args:
            field_name: Name of the field to extract
            message: User's message
            
        Returns:
            Tuple of (extracted_value, confidence)
        """
        message_lower = message.lower()
        
        if field_name == "nickname":
            # Extract name patterns - be more specific to avoid false positives
            # Exclude common non-name patterns
            non_name_words = [
                "the", "a", "an", "男仔", "女仔", "學生", "人", 
                "雙魚座", "白羊座", "金牛座", "雙子座", "巨蟹座", "獅子座",
                "處女座", "天秤座", "天蠍座", "射手座", "山羊座", "水瓶座",
                "中一", "中二", "中三", "中四", "中五", "中六",
                "小一", "小二", "小三", "小四", "小五", "小六",
            ]
            
            # Correction patterns first (higher priority)
            correction_patterns = [
                r"唔係[,，\s]*我?其實叫\s*([^\s，,。！？啦呀嘅先]+)",   # "唔係，我其實叫阿強"
                r"唔係[,，\s]*其實我?叫\s*([^\s，,。！？啦呀嘅先]+)",   # "唔係，其實我叫阿強"
                r"唔係[,，\s]*我其實叫([^\s，,。！？啦呀嘅先]+)",       # "唔係，我其實叫阿強" (no space)
                r"唔係[,，\s]*叫我\s*([^\s，,。！？啦呀嘅先]+)",   # "唔係, 叫我小明" - extract name after 叫我
                r"唔係[,，\s]*叫\s*([^\s，,。！？啦呀嘅先]+)",     # "唔係, 叫阿強"
                r"其實[我]?叫\s*([^\s，,。！？啦呀嘅]+)",          # "其實叫阿明" or "其實我叫阿明"
                r"其實我叫([^\s，,。！？啦呀嘅]+)",                # "其實我叫阿明" (no space)
                r"應該係\s*([^\s，,。！？啦呀嘅]+)",               # "應該係阿明"
                r"錯咗[,，\s]*[我]?叫\s*([^\s，,。！？啦呀嘅]+)",  # "錯咗, 我叫阿明"
                r"改做\s*([^\s，,。！？啦呀嘅]+)",                 # "改做阿明"
                r"actually[,\s]*call me\s+(\w+)",
                r"sorry[,\s]*my name is\s+(\w+)",
                r"i meant\s+(\w+)",
            ]
            
            for pattern in correction_patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    if len(name) <= 10 and name not in non_name_words:
                        return name, 0.9  # Higher confidence for corrections
            
            # Standard patterns
            patterns = [
                r"叫我\s*([^\s，,。！？啦呀嘅]+)",
                r"我叫\s*([^\s，,。！？啦呀嘅]+)",
                r"都叫我\s*([^\s，,。！？啦呀嘅]+)",
                r"call me\s+(\w+)",
                r"my name is\s+(\w+)",
                r"i'm\s+(\w+)",
                r"i am\s+(\w+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    # Filter out common non-name words and zodiac signs
                    if len(name) <= 10 and name not in non_name_words and not any(nw in name for nw in non_name_words):
                        return name, 0.8
            # Skip "我係" pattern as it's too broad (我係男仔, 我係雙魚座, etc.)
        
        elif field_name == "age":
            # Extract age
            patterns = [
                r"(\d{1,2})\s*歲",
                r"(\d{1,2})\s*years?\s*old",
                r"i'm\s*(\d{1,2})",
                r"我\s*(\d{1,2})\s*歲",
            ]
            for pattern in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    age = int(match.group(1))
                    if 5 <= age <= 25:  # Reasonable age range
                        return age, 0.9
        
        elif field_name == "school_level":
            # Extract school level - check for Chinese grade names
            level_map = {
                "p1": SchoolLevelEnum.P1, "小一": SchoolLevelEnum.P1,
                "p2": SchoolLevelEnum.P2, "小二": SchoolLevelEnum.P2,
                "p3": SchoolLevelEnum.P3, "小三": SchoolLevelEnum.P3,
                "p4": SchoolLevelEnum.P4, "小四": SchoolLevelEnum.P4,
                "p5": SchoolLevelEnum.P5, "小五": SchoolLevelEnum.P5,
                "p6": SchoolLevelEnum.P6, "小六": SchoolLevelEnum.P6,
                "s1": SchoolLevelEnum.S1, "中一": SchoolLevelEnum.S1,
                "s2": SchoolLevelEnum.S2, "中二": SchoolLevelEnum.S2,
                "s3": SchoolLevelEnum.S3, "中三": SchoolLevelEnum.S3,
                "s4": SchoolLevelEnum.S4, "中四": SchoolLevelEnum.S4,
                "s5": SchoolLevelEnum.S5, "中五": SchoolLevelEnum.S5,
                "s6": SchoolLevelEnum.S6, "中六": SchoolLevelEnum.S6,
            }
            # Check message for school level keywords
            for key, value in level_map.items():
                if key in message_lower or key in message:
                    return value.value, 0.9
        
        elif field_name == "current_mood":
            # Extract mood - IMPORTANT: Check negation first!
            # Cantonese negation: 唔 (m4) means "not"
            
            # Check for negated happy (唔開心 = not happy = sad)
            if "唔開心" in message or "唔happy" in message_lower or "not happy" in message_lower:
                return "sad", 0.85
            
            # Check for negated okay (唔ok = not okay)
            if "唔ok" in message_lower or "唔好" in message:
                return "sad", 0.7
            
            # Now check positive moods (only if not negated)
            mood_keywords = {
                "happy": ["happy", "開心", "good", "great", "高興"],
                "okay": ["okay", "ok", "fine", "普通", "一般", "都ok"],
                "sad": ["sad", "傷心", "unhappy", "down", "唔開心", "難過"],
                "stressed": ["stressed", "壓力大", "有壓力", "好大壓力", "壓力"],
                "anxious": ["anxious", "焦慮", "worried", "擔心", "緊張", "驚"],
                "tired": ["tired", "攰", "累", "exhausted", "好攰"],
                "angry": ["angry", "嬲", "mad", "frustrated", "好嬲"],
            }
            
            # Check stressed/anxious/tired/angry first (more specific)
            for mood in ["stressed", "anxious", "tired", "angry", "sad"]:
                keywords = mood_keywords[mood]
                if any(kw in message_lower or kw in message for kw in keywords):
                    return mood, 0.7
            
            # Then check happy/okay (less specific)
            for mood in ["happy", "okay"]:
                keywords = mood_keywords[mood]
                if any(kw in message_lower or kw in message for kw in keywords):
                    return mood, 0.7
        
        elif field_name == "hobbies":
            # Extract hobbies - map Chinese to English standardized values
            hobby_map = {
                "gaming": ["gaming", "打機", "game", "遊戲", "玩game"],
                "reading": ["reading", "睇書", "看書", "閱讀"],
                "basketball": ["basketball", "籃球", "打籃球", "打波"],
                "football": ["football", "足球", "踢波"],
                "sports": ["sports", "運動", "做運動"],
                "music": ["music", "音樂", "聽歌", "聽音樂"],
                "singing": ["singing", "唱歌", "唱k"],
                "piano": ["piano", "鋼琴", "彈琴", "學琴", "練琴"],
                "drawing": ["drawing", "畫畫", "畫圖", "繪畫"],
                "art": ["art", "藝術", "美術"],
                "cooking": ["cooking", "煮嘢食", "煮飯", "烹飪"],
                "youtube": ["youtube", "睇youtube", "睇yt"],
                "anime": ["anime", "動漫", "睇動漫", "睇卡通"],
                "manga": ["manga", "漫畫", "睇漫畫"],
                "lego": ["lego", "砌lego", "砌積木"],
            }
            found_hobbies = []
            for hobby_name, keywords in hobby_map.items():
                if any(kw in message_lower or kw in message for kw in keywords):
                    found_hobbies.append(hobby_name)
            if found_hobbies:
                return found_hobbies, 0.7
        
        elif field_name == "stress_sources":
            # Extract stress sources - ONLY when context indicates stress/problem
            # Check for stress indicators in the message
            stress_indicators = ["壓力", "煩", "擔心", "問題", "難", "辛苦", "做唔完", "唔夠", "stress", "worried", "problem", "difficult"]
            has_stress_context = any(ind in message_lower or ind in message for ind in stress_indicators)
            
            # Only extract stress sources if there's a stress context
            if not has_stress_context:
                return None, 0.0
            
            stress_keywords = {
                "exam": ["exam", "考試", "test", "測驗", "dse"],
                "homework": ["homework", "功課", "assignment", "做唔完"],
                "school": ["school", "學校", "返學"],
                "parents": ["parents", "父母", "mom", "dad", "媽媽", "爸爸", "屋企人"],
                "friends": ["friends", "朋友", "friendship", "同學"],
                "future": ["future", "將來", "career", "前途"],
                "grades": ["grades", "成績", "marks", "分數"],
            }
            found_sources = []
            for source, keywords in stress_keywords.items():
                if any(kw in message_lower or kw in message for kw in keywords):
                    found_sources.append(source)
            if found_sources:
                return found_sources, 0.7
        
        return None, 0.0
    
    def get_profile_question(self, topic: str, language: str = "zh-HK") -> Optional[str]:
        """
        Get a natural question to ask about a profile topic.
        
        Args:
            topic: Profile field to ask about
            language: Language preference
            
        Returns:
            Question string or None
        """
        return self.QUESTION_TEMPLATES.get(topic)
    
    def build_profile_context_for_ai(
        self, 
        profile: Optional[HealthProfile],
        completeness: ProfileCompleteness
    ) -> str:
        """
        Build context string for AI about user's profile status.
        
        Args:
            profile: User's health profile
            completeness: Profile completeness assessment
            
        Returns:
            Context string for AI prompt
        """
        lines = ["### User Profile Status"]
        
        if not profile:
            lines.append("- Profile: Not yet created")
            lines.append("- Status: New user, profile is empty")
            lines.append(f"- Next topic to ask: {completeness.next_question_topic}")
        else:
            lines.append(f"- Profile completion: {completeness.completion_percentage:.0f}%")
            
            # Add known info
            if profile.nickname:
                lines.append(f"- Nickname: {profile.nickname}")
            if profile.age:
                lines.append(f"- Age: {profile.age}")
            if profile.school_level:
                lines.append(f"- School level: {profile.school_level.value if hasattr(profile.school_level, 'value') else profile.school_level}")
            if profile.current_mood:
                lines.append(f"- Current mood: {profile.current_mood}")
            if profile.hobbies:
                lines.append(f"- Hobbies: {', '.join(profile.hobbies) if isinstance(profile.hobbies, list) else profile.hobbies}")
            if profile.stress_sources:
                lines.append(f"- Stress sources: {', '.join(profile.stress_sources) if isinstance(profile.stress_sources, list) else profile.stress_sources}")
        
        # Add guidance for AI
        if not completeness.is_complete:
            lines.append("")
            lines.append("### Profile Building Guidance")
            lines.append("The user's profile is incomplete. While chatting naturally:")
            lines.append(f"- Missing fields: {', '.join(completeness.priority_fields[:3])}")
            if completeness.next_question_topic:
                question = self.get_profile_question(completeness.next_question_topic)
                if question:
                    lines.append(f"- Suggested question: {question}")
            lines.append("- Weave questions naturally into conversation, don't interrogate")
            lines.append("- Focus on building rapport first, then gather info")
        
        return "\n".join(lines)


    def analyze_chat_for_improvements(
        self,
        messages: List[Dict[str, Any]],
        extractions: List[List[ExtractedProfileData]]
    ) -> Dict[str, Any]:
        """
        Analyze chat history to find missed extractions and suggest keyword improvements.
        
        Args:
            messages: List of {"user": message, "description": desc, "expected_field": field}
            extractions: List of extraction results for each message
            
        Returns:
            Analysis report with suggestions
        """
        analysis = {
            "missed_extractions": [],
            "false_positives": [],
            "suggested_keywords": {},
            "pattern_suggestions": [],
            "summary": {}
        }
        
        # Common patterns that might indicate profile info
        potential_patterns = {
            "nickname": [
                r"我(係|叫|名)(.+)",
                r"(.+)呀我",
                r"人哋叫我(.+)",
                r"朋友叫我(.+)",
            ],
            "age": [
                r"(\d+)歲",
                r"今年(\d+)",
                r"(\d+)\s*years",
            ],
            "school_level": [
                r"(中|小)[一二三四五六]",
                r"(p|s)[1-6]",
                r"讀緊(.+)",
                r"year\s*(\d+)",
            ],
            "current_mood": [
                r"(開心|唔開心|sad|happy|stressed|攰|嬲|焦慮|擔心)",
                r"心情(.+)",
                r"覺得(.+)",
                r"feel(ing)?\s+(\w+)",
            ],
            "hobbies": [
                r"鍾意(.+)",
                r"喜歡(.+)",
                r"興趣(.+)",
                r"like\s+(.+)",
                r"enjoy\s+(.+)",
            ],
            "stress_sources": [
                r"壓力(.+)",
                r"擔心(.+)",
                r"煩(.+)",
                r"stressed\s+about\s+(.+)",
            ],
        }
        
        # Analyze each message
        for i, (msg_data, extracted) in enumerate(zip(messages, extractions)):
            message = msg_data.get("user", "")
            description = msg_data.get("description", "")
            expected_field = msg_data.get("expected_field")
            
            message_lower = message.lower()
            
            # Check for missed extractions based on description
            if "告知" in description or "更正" in description:
                # This message should have extracted something
                if not extracted:
                    # Find what field was expected
                    field_hints = {
                        "暱稱": "nickname",
                        "年齡": "age", 
                        "年級": "school_level",
                        "心情": "current_mood",
                        "興趣": "hobbies",
                        "壓力": "stress_sources",
                    }
                    
                    expected = None
                    for hint, field in field_hints.items():
                        if hint in description:
                            expected = field
                            break
                    
                    if expected:
                        analysis["missed_extractions"].append({
                            "message": message,
                            "description": description,
                            "expected_field": expected,
                            "index": i
                        })
                        
                        # Suggest new keywords based on the message
                        words = re.findall(r'[\u4e00-\u9fff]+|\w+', message)
                        for word in words:
                            if len(word) >= 2 and word not in self.EXTRACTABLE_FIELDS.get(expected, []):
                                if expected not in analysis["suggested_keywords"]:
                                    analysis["suggested_keywords"][expected] = set()
                                analysis["suggested_keywords"][expected].add(word)
            
            # Check for false positives (noise that was extracted)
            elif "噪音" in description and extracted:
                for ext in extracted:
                    analysis["false_positives"].append({
                        "message": message,
                        "description": description,
                        "extracted_field": ext.field_name,
                        "extracted_value": ext.value,
                        "index": i
                    })
            
            # Look for patterns that might be useful
            for field, patterns in potential_patterns.items():
                for pattern in patterns:
                    match = re.search(pattern, message, re.IGNORECASE)
                    if match and not any(e.field_name == field for e in extracted):
                        # Found a pattern match but no extraction
                        if "告知" in description or field in description.lower():
                            analysis["pattern_suggestions"].append({
                                "field": field,
                                "pattern": pattern,
                                "message": message,
                                "match": match.group(0)
                            })
        
        # Convert sets to lists for JSON serialization
        for field in analysis["suggested_keywords"]:
            analysis["suggested_keywords"][field] = list(analysis["suggested_keywords"][field])
        
        # Generate summary
        analysis["summary"] = {
            "total_messages": len(messages),
            "missed_count": len(analysis["missed_extractions"]),
            "false_positive_count": len(analysis["false_positives"]),
            "fields_needing_improvement": list(analysis["suggested_keywords"].keys()),
            "pattern_matches_missed": len(analysis["pattern_suggestions"])
        }
        
        return analysis
    
    def generate_improvement_report(self, analysis: Dict[str, Any]) -> str:
        """
        Generate a human-readable improvement report in Traditional Chinese.
        
        Args:
            analysis: Analysis results from analyze_chat_for_improvements
            
        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 70)
        lines.append("# OmniCare 提取功能改進建議報告")
        lines.append("=" * 70)
        lines.append("")
        
        # Summary
        summary = analysis.get("summary", {})
        lines.append("## 摘要")
        lines.append("-" * 50)
        lines.append(f"總訊息數: {summary.get('total_messages', 0)}")
        lines.append(f"漏提取數: {summary.get('missed_count', 0)}")
        lines.append(f"誤提取數: {summary.get('false_positive_count', 0)}")
        lines.append(f"需改進欄位: {', '.join(summary.get('fields_needing_improvement', []))}")
        lines.append("")
        
        # Missed extractions
        missed = analysis.get("missed_extractions", [])
        if missed:
            lines.append("## 漏提取的訊息")
            lines.append("-" * 50)
            for item in missed:
                lines.append(f"• 訊息: {item['message']}")
                lines.append(f"  描述: {item['description']}")
                lines.append(f"  預期欄位: {item['expected_field']}")
                lines.append("")
        
        # False positives
        false_pos = analysis.get("false_positives", [])
        if false_pos:
            lines.append("## 誤提取的訊息（噪音被提取）")
            lines.append("-" * 50)
            for item in false_pos:
                lines.append(f"• 訊息: {item['message']}")
                lines.append(f"  描述: {item['description']}")
                lines.append(f"  誤提取: {item['extracted_field']} = {item['extracted_value']}")
                lines.append("")
        
        # Suggested keywords
        suggestions = analysis.get("suggested_keywords", {})
        if suggestions:
            lines.append("## 建議新增關鍵字")
            lines.append("-" * 50)
            for field, keywords in suggestions.items():
                lines.append(f"### {field}")
                lines.append(f"建議新增: {', '.join(keywords)}")
                lines.append("")
        
        # Pattern suggestions
        patterns = analysis.get("pattern_suggestions", [])
        if patterns:
            lines.append("## 建議新增正則表達式")
            lines.append("-" * 50)
            seen_patterns = set()
            for item in patterns:
                key = (item['field'], item['pattern'])
                if key not in seen_patterns:
                    seen_patterns.add(key)
                    lines.append(f"• 欄位: {item['field']}")
                    lines.append(f"  模式: {item['pattern']}")
                    lines.append(f"  範例: {item['message']} → {item['match']}")
                    lines.append("")
        
        # Recommendations
        lines.append("## 改進建議")
        lines.append("-" * 50)
        if missed:
            lines.append("1. 在 EXTRACTABLE_FIELDS 中新增建議的關鍵字")
        if false_pos:
            lines.append("2. 加強噪音過濾邏輯，避免誤提取")
        if patterns:
            lines.append("3. 考慮新增正則表達式模式以提高提取準確度")
        lines.append("4. 定期運行 QA 測試以監控提取品質")
        lines.append("")
        
        return "\n".join(lines)


# Singleton instance
_profile_extraction_service: Optional[ProfileExtractionService] = None


def get_profile_extraction_service() -> ProfileExtractionService:
    """Get singleton ProfileExtractionService instance."""
    global _profile_extraction_service
    if _profile_extraction_service is None:
        _profile_extraction_service = ProfileExtractionService()
    return _profile_extraction_service
