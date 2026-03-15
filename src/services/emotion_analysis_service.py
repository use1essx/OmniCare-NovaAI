"""
Emotion Analysis Service
分析用戶對話的情緒、語氣和心理風險

Author: Healthcare AI Team
Date: 2025-12-23
Updated: 2025-12-27 - Integrated AI-powered psychological analysis
"""

import re
import logging
from typing import Dict, List, Optional
from datetime import datetime
import json

from src.ai.unified_ai_client import AIRequest, AIResponse
from src.ai.providers.nova_bedrock_client import get_nova_client

logger = logging.getLogger(__name__)



class EmotionAnalysisService:
    """
    情緒分析服務
    - 分析用戶回覆的情緒（快樂、悲傷、焦慮、憤怒）
    - 分析語言特徵（語調、情緒詞彙、句子結構）
    - 計算風險分數（焦慮風險、情緒調節能力）
    """
    
    # 情緒詞彙庫（擴展版）
    EMOTION_KEYWORDS = {
        "joy": {
            "en": ["happy", "glad", "excited", "joyful", "wonderful", "great", "amazing", 
                   "love", "like", "enjoy", "fun", "good", "nice", "awesome", "fantastic",
                   "delighted", "pleased", "cheerful", "yay", "hooray"],
            "zh": ["開心", "高興", "興奮", "快樂", "喜歡", "愛", "好", "棒", "太好了",
                   "哇", "耶", "讚", "爽", "歡樂", "愉快", "舒服", "滿足"]
        },
        "sadness": {
            "en": ["sad", "unhappy", "depressed", "down", "upset", "disappointed", 
                   "miserable", "gloomy", "lonely", "hurt", "heartbroken", "cry", 
                   "tears", "sorrow", "grief"],
            "zh": ["難過", "傷心", "沮喪", "失望", "不開心", "憂鬱", "孤獨", "寂寞",
                   "痛苦", "哭", "眼淚", "悲傷", "心痛", "委屈", "鬱悶"]
        },
        "anxiety": {
            "en": ["anxious", "worried", "nervous", "stressed", "scared", "afraid", 
                   "fear", "panic", "tense", "uneasy", "concerned", "troubled",
                   "frighten", "terrified", "anxious"],
            "zh": ["焦慮", "擔心", "緊張", "害怕", "恐懼", "不安", "驚慌", "煩惱",
                   "憂慮", "緊繃", "壓力", "惶恐", "驚恐", "擔憂", "焦灼"]
        },
        "anger": {
            "en": ["angry", "mad", "furious", "annoyed", "irritated", "upset", 
                   "frustrated", "rage", "hate", "dislike", "angry", "pissed",
                   "outraged", "indignant"],
            "zh": ["生氣", "憤怒", "煩", "討厭", "惱火", "火大", "不爽", "抓狂",
                   "氣死", "煩死", "恨", "厭惡", "暴躁", "煩躁"]
        },
        "neutral": {
            "en": ["okay", "fine", "normal", "alright", "so-so", "maybe", "perhaps"],
            "zh": ["還好", "普通", "一般", "平常", "尚可", "可以", "也許", "可能"]
        }
    }
    
    # 負面情緒強度詞（加重風險分數）
    INTENSITY_MODIFIERS = {
        "high": ["very", "extremely", "really", "so", "too", "super", "totally",
                 "非常", "特別", "超級", "太", "好", "真的", "真"],
        "medium": ["quite", "pretty", "fairly", "rather",
                   "有點", "稍微", "比較", "還"],
        "low": ["a bit", "a little", "somewhat", "slightly",
                "一點點", "些許", "微微"]
    }
    
    # 焦慮相關的生理/行為表現
    ANXIETY_INDICATORS = {
        "en": ["can't sleep", "tired", "exhausted", "headache", "stomach ache",
               "heart racing", "shaking", "sweating", "dizzy", "can't focus",
               "can't concentrate", "restless", "avoid", "escape"],
        "zh": ["睡不著", "失眠", "累", "疲倦", "頭痛", "肚子痛", "心跳快",
               "發抖", "冒汗", "頭暈", "無法專心", "坐立不安", "逃避", "躲"]
    }
    
    def __init__(self):
        """初始化情緒分析服務"""
        self.logger = logger
        try:
            self.nova_client = get_nova_client()
            self.logger.info("✅ Nova client initialized for emotion analysis")
        except Exception as e:
            self.logger.warning(f"⚠️ Nova client initialization failed: {e} - falling back to keyword matching")
            self.nova_client = None
        
    async def analyze_emotion(self, 
                             user_message: str, 
                             question_context: Optional[str] = None,
                             conversation_history: Optional[List[str]] = None) -> Dict:
        """
        分析用戶消息的情緒和風險（使用AI心理分析）
        
        Args:
            user_message: 用戶回覆的消息
            question_context: 問卷問題的上下文（可選）
            conversation_history: 對話歷史（可選，用於趨勢分析）
            
        Returns:
            Dict: {
                "emotions": {
                    "joy": float,      # 0-100
                    "sadness": float,
                    "anxiety": float,
                    "anger": float,
                    "neutral": float
                },
                "dominant_emotion": str,  # 主要情緒
                "emotion_intensity": float,  # 情緒強度 0-100
                "language_features": {
                    "message_length": int,
                    "exclamation_count": int,
                    "question_count": int,
                    "negative_words_count": int,
                    "positive_words_count": int,
                    "sentence_complexity": str  # "simple", "medium", "complex"
                },
                "risk_scores": {
                    "anxiety_risk": float,  # 0-100 (越高越危險)
                    "emotional_regulation": float,  # 0-100 (越高越好)
                    "overall_wellbeing": float  # 0-100 (越高越好)
                },
                "analysis_summary": str,  # 分析總結
                "timestamp": str
            }
        """
        try:
            self.logger.info(f"🧠 Analyzing emotion for message: {user_message[:50]}...")
            
            # Try AI-powered analysis first
            if self.nova_client:
                result = await self._ai_powered_analysis(user_message, question_context)
                if result:
                    self.logger.info(f"✅ AI analysis complete: {result['dominant_emotion']} "
                                   f"(anxiety_risk={result['risk_scores']['anxiety_risk']:.1f}%)")
                    return result
            
            # Fallback to keyword-based analysis
            self.logger.warning("⚠️ Falling back to keyword-based analysis")
            return await self._keyword_based_analysis(user_message, question_context, conversation_history)
            
        except Exception as e:
            self.logger.error(f"Error analyzing emotion: {e}")
            # 返回中性結果
            return {
                "emotions": {"neutral": 100.0},
                "dominant_emotion": "neutral",
                "emotion_intensity": 0.0,
                "language_features": {},
                "risk_scores": {
                    "anxiety_risk": 0.0,
                    "emotional_regulation": 50.0,
                    "overall_wellbeing": 50.0
                },
                "analysis_summary": "Analysis unavailable",
                "timestamp": datetime.now().isoformat()
            }
    
    async def _ai_powered_analysis(self, user_message: str, question_context: Optional[str] = None) -> Optional[Dict]:
        """
        使用AI模型進行深度心理分析
        """
        try:
            # SECURITY: Input validation
            if not user_message or len(user_message) > 10000:
                self.logger.warning("Invalid user message length")
                return None
            
            prompt = f"""# Task: Child Psychological Response Analysis

You are a child clinical psychologist analyzing a child's response to assess their emotional state and mental health risks.

## Context:
**Question**: {question_context or "General conversation"}
**Child's Response**: "{user_message}"

## Analysis Framework:

### 1. Anxiety Risk Score (0-100, higher = more risk)
Assess indicators:
- Expressions of worry, fear, or nervousness
- Avoidance behaviors mentioned
- Physical symptoms (insomnia, stomach aches, tension)
- Perfectionism or fear of failure
- Social anxiety signs
- Excessive concern about outcomes

**CRITICAL**: Even if the child doesn't use words like "anxious" or "worried", look for:
- "I can't do it" / "I'm a failure" → HIGH anxiety (70-90)
- "I can't sleep" / "insomnia" → HIGH anxiety (60-80)
- "I'm putting things off" / procrastination → MEDIUM-HIGH anxiety (50-70)
- "I dare not tell my family" / hiding feelings → HIGH anxiety (70-90)
- "I feel frustrated and depressed" → HIGH anxiety (60-80)

### 2. Emotional Regulation Score (0-100, higher = better ability)
Assess indicators:
- Ability to name and describe emotions clearly
- Coping strategies mentioned
- Balance between emotions
- Self-awareness and insight
- Ability to seek help

**Scoring Guide**:
- 80-100: Excellent emotional awareness and coping
- 60-79: Good regulation with some challenges
- 40-59: Fair regulation, needs support
- 20-39: Poor regulation, significant difficulties
- 0-19: Crisis level, immediate intervention needed

### 3. Overall Wellbeing Score (0-100, higher = better)
Holistic assessment:
- General mood and outlook
- Energy levels and engagement
- Social connections
- Self-esteem and self-worth
- Overall life satisfaction

**Scoring Guide**:
- 80-100: Thriving, positive mental health
- 60-79: Good wellbeing with minor concerns
- 40-59: Moderate concerns, needs monitoring
- 20-39: Significant distress, needs intervention
- 0-19: Crisis level, immediate help needed

### 4. Emotion Breakdown
Estimate percentage for each:
- Joy/Happiness (0-100%)
- Sadness (0-100%)
- Anxiety/Fear (0-100%)
- Anger/Frustration (0-100%)
- Neutral (0-100%)

Total should add up to approximately 100%.

## Output Format (JSON):
{{
  "emotions": {{
    "joy": 10.0,
    "sadness": 40.0,
    "anxiety": 35.0,
    "anger": 10.0,
    "neutral": 5.0
  }},
  "dominant_emotion": "sadness",
  "emotion_intensity": 75.0,
  "risk_scores": {{
    "anxiety_risk": 75.0,
    "emotional_regulation": 45.0,
    "overall_wellbeing": 25.0
  }},
  "analysis_summary": "Child shows significant signs of anxiety and low self-esteem. Mentions of being a 'failure' and hiding feelings from family are concerning. Insomnia indicates high stress. Needs immediate support and follow-up.",
  "key_concerns": ["Low self-worth", "Sleep disturbance", "Hiding feelings", "Procrastination"],
  "protective_factors": ["Energy despite insomnia", "Normal appetite"]
}}

## Important Guidelines:
1. **Be sensitive to implicit distress** - Children may not directly say "I'm anxious" but show it through behaviors
2. **Context matters** - "I'm fine" after describing problems = denial/minimization = HIGH RISK
3. **Self-deprecation is serious** - "I'm a failure" is a major red flag (70-90 anxiety risk)
4. **Physical symptoms count** - Insomnia, appetite changes, fatigue are anxiety indicators
5. **Hidden feelings are concerning** - "I dare not tell" suggests shame and isolation
6. **Score conservatively high for safety** - Better to overestimate risk than miss it

Now analyze the child's response and provide scores:"""

            # Use Nova client for analysis
            request = AIRequest(
                system_prompt="You are a child clinical psychologist analyzing emotional responses.",
                user_prompt=prompt,
                task_type="emotion_analysis",
                temperature=0.3,
                max_tokens=1500
            )
            
            response = await self.nova_client.make_request(request=request)
            
            if not response or not response.content:
                self.logger.error("Empty response from Nova client")
                return None
            
            # Extract JSON from response
            analysis = self._extract_json(response.content)
            if not analysis:
                self.logger.error("Failed to extract JSON from AI response")
                return None
            
            # Add language features
            analysis["language_features"] = self._analyze_language_features(user_message)
            analysis["timestamp"] = datetime.now().isoformat()
            
            return analysis
                
        except Exception as e:
            self.logger.error(f"AI analysis error: {e}")
            return None
    
    def _extract_json(self, text: str) -> Optional[Dict]:
        """從AI回應中提取JSON"""
        try:
            # Try to find JSON block
            if "```json" in text:
                match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
                if match:
                    return json.loads(match.group(1))
            
            # Try to find any JSON object
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            
            # Try parsing entire response
            return json.loads(text)
        except Exception as e:
            self.logger.error(f"JSON extraction error: {e}")
            return None
    
    async def _keyword_based_analysis(self, user_message: str, question_context: Optional[str],
                                     conversation_history: Optional[List[str]] = None) -> Dict:
        """
        原有的關鍵詞匹配分析（降級方案）
        """
        # 1. 情緒識別
        emotions = self._detect_emotions(user_message)
        dominant_emotion = max(emotions.items(), key=lambda x: x[1])[0]
        emotion_intensity = self._calculate_emotion_intensity(user_message, dominant_emotion)
        
        # 2. 語言特徵分析
        language_features = self._analyze_language_features(user_message)
        
        # 3. 焦慮風險評估
        anxiety_risk = self._calculate_anxiety_risk(
            user_message, 
            emotions, 
            language_features
        )
        
        # 4. 情緒調節能力評估
        emotional_regulation = self._calculate_emotional_regulation(
            emotions,
            language_features,
            conversation_history
        )
        
        # 5. 整體心理健康指標
        overall_wellbeing = self._calculate_overall_wellbeing(
            emotions,
            anxiety_risk,
            emotional_regulation
        )
        
        # 6. 生成分析總結
        analysis_summary = self._generate_summary(
            dominant_emotion,
            emotion_intensity,
            anxiety_risk,
            emotional_regulation
        )
        
        return {
            "emotions": emotions,
            "dominant_emotion": dominant_emotion,
            "emotion_intensity": round(emotion_intensity, 2),
            "language_features": language_features,
            "risk_scores": {
                "anxiety_risk": round(anxiety_risk, 2),
                "emotional_regulation": round(emotional_regulation, 2),
                "overall_wellbeing": round(overall_wellbeing, 2)
            },
            "analysis_summary": analysis_summary,
            "timestamp": datetime.now().isoformat()
        }

    
    def _detect_emotions(self, text: str) -> Dict[str, float]:
        """
        檢測文本中的各種情緒
        返回每種情緒的分數（0-100）
        """
        text_lower = text.lower()
        emotion_scores = {
            "joy": 0.0,
            "sadness": 0.0,
            "anxiety": 0.0,
            "anger": 0.0,
            "neutral": 50.0  # 默認中性
        }
        
        total_matches = 0
        
        for emotion, keywords in self.EMOTION_KEYWORDS.items():
            matches = 0
            # 檢查英文關鍵詞
            for keyword in keywords.get("en", []):
                if keyword.lower() in text_lower:
                    matches += 1
            # 檢查中文關鍵詞
            for keyword in keywords.get("zh", []):
                if keyword in text:
                    matches += 1
            
            if matches > 0:
                emotion_scores[emotion] = min(100.0, matches * 30)  # 每個匹配30分
                total_matches += matches
        
        # 如果沒有匹配到任何情緒，保持中性
        if total_matches == 0:
            emotion_scores["neutral"] = 100.0
        else:
            # 標準化分數
            total = sum(emotion_scores.values())
            if total > 0:
                for emotion in emotion_scores:
                    emotion_scores[emotion] = round((emotion_scores[emotion] / total) * 100, 2)
        
        return emotion_scores
    
    def _calculate_emotion_intensity(self, text: str, dominant_emotion: str) -> float:
        """
        計算情緒強度（0-100）
        考慮強度修飾詞、標點符號等
        """
        intensity = 50.0  # 基礎強度
        text_lower = text.lower()
        
        # 1. 檢查強度修飾詞
        for level, modifiers in self.INTENSITY_MODIFIERS.items():
            for modifier in modifiers:
                if modifier in text_lower or modifier in text:
                    if level == "high":
                        intensity += 20
                    elif level == "medium":
                        intensity += 10
                    elif level == "low":
                        intensity += 5
        
        # 2. 檢查標點符號
        exclamation_count = text.count("!") + text.count("！")
        intensity += min(exclamation_count * 10, 30)  # 每個感嘆號+10，最多+30
        
        # 3. 檢查重複字母或字符（如 "sooooo"）
        if re.search(r'(.)\1{2,}', text):  # 連續重複3次以上
            intensity += 15
        
        # 4. 全大寫（表示強烈情緒）
        if text.isupper() and len(text) > 3:
            intensity += 20
        
        # 限制在0-100範圍內
        return min(100.0, max(0.0, intensity))
    
    def _analyze_language_features(self, text: str) -> Dict:
        """
        分析語言特徵
        """
        features = {
            "message_length": len(text),
            "word_count": len(text.split()),
            "exclamation_count": text.count("!") + text.count("！"),
            "question_count": text.count("?") + text.count("？"),
            "negative_words_count": 0,
            "positive_words_count": 0,
            "sentence_count": len(re.split(r'[.!?。！？]', text)),
            "avg_word_length": 0
        }
        
        # 計算正面/負面詞彙
        text_lower = text.lower()
        for keyword in self.EMOTION_KEYWORDS["joy"]["en"] + self.EMOTION_KEYWORDS["joy"]["zh"]:
            if keyword in text_lower or keyword in text:
                features["positive_words_count"] += 1
        
        for emotion in ["sadness", "anxiety", "anger"]:
            for keyword in self.EMOTION_KEYWORDS[emotion]["en"] + self.EMOTION_KEYWORDS[emotion]["zh"]:
                if keyword in text_lower or keyword in text:
                    features["negative_words_count"] += 1
        
        # 計算平均詞長
        words = text.split()
        if words:
            features["avg_word_length"] = round(sum(len(w) for w in words) / len(words), 2)
        
        # 句子複雜度
        if features["word_count"] < 5:
            features["sentence_complexity"] = "simple"
        elif features["word_count"] < 15:
            features["sentence_complexity"] = "medium"
        else:
            features["sentence_complexity"] = "complex"
        
        return features
    
    def _calculate_anxiety_risk(self, text: str, emotions: Dict, language_features: Dict) -> float:
        """
        計算焦慮風險分數（0-100，越高越危險）
        """
        risk = 0.0
        text_lower = text.lower()
        
        # 1. 焦慮情緒分數（權重40%）
        risk += emotions.get("anxiety", 0) * 0.4
        
        # 2. 焦慮指標詞彙（權重30%）
        anxiety_indicator_count = 0
        for indicator in self.ANXIETY_INDICATORS["en"] + self.ANXIETY_INDICATORS["zh"]:
            if indicator in text_lower or indicator in text:
                anxiety_indicator_count += 1
        risk += min(30.0, anxiety_indicator_count * 10)
        
        # 3. 負面情緒累積（權重20%）
        negative_score = emotions.get("sadness", 0) + emotions.get("anger", 0)
        risk += (negative_score / 200) * 20  # 標準化到20分
        
        # 4. 語言特徵（權重10%）
        if language_features.get("negative_words_count", 0) > 2:
            risk += 10
        
        return min(100.0, risk)
    
    def _calculate_emotional_regulation(self, emotions: Dict, language_features: Dict, 
                                       conversation_history: Optional[List[str]] = None) -> float:
        """
        計算情緒調節能力（0-100，越高越好）
        """
        regulation = 50.0  # 基礎分數
        
        # 1. 情緒平衡（多種情緒混合表示較好的調節）
        non_zero_emotions = sum(1 for score in emotions.values() if score > 10)
        if non_zero_emotions > 1:
            regulation += 20
        
        # 2. 正面情緒比例
        positive_ratio = emotions.get("joy", 0) / 100
        regulation += positive_ratio * 20
        
        # 3. 句子複雜度（能表達複雜情感通常調節能力較好）
        if language_features.get("sentence_complexity") == "complex":
            regulation += 10
        
        # 4. 負面情緒極端程度（過於極端降低分數）
        max_negative = max(
            emotions.get("sadness", 0),
            emotions.get("anxiety", 0),
            emotions.get("anger", 0)
        )
        if max_negative > 80:
            regulation -= 20
        
        return min(100.0, max(0.0, regulation))
    
    def _calculate_overall_wellbeing(self, emotions: Dict, anxiety_risk: float, 
                                    emotional_regulation: float) -> float:
        """
        計算整體心理健康指標（0-100，越高越好）
        """
        # 正面情緒貢獻
        positive_score = emotions.get("joy", 0) * 0.3
        
        # 焦慮風險減分
        anxiety_penalty = anxiety_risk * 0.4
        
        # 情緒調節加分
        regulation_bonus = emotional_regulation * 0.3
        
        wellbeing = positive_score - anxiety_penalty + regulation_bonus
        
        return min(100.0, max(0.0, wellbeing))
    
    def _generate_summary(self, dominant_emotion: str, emotion_intensity: float,
                         anxiety_risk: float, emotional_regulation: float) -> str:
        """
        生成分析總結（中英雙語）
        """
        # 情緒描述
        emotion_desc = {
            "joy": "positive/joyful (正面/快樂)",
            "sadness": "sad/down (悲傷/低落)",
            "anxiety": "anxious/worried (焦慮/擔憂)",
            "anger": "angry/frustrated (憤怒/沮喪)",
            "neutral": "neutral/calm (中性/平靜)"
        }
        
        # 強度描述
        if emotion_intensity > 70:
            intensity_desc = "strong (強烈)"
        elif emotion_intensity > 40:
            intensity_desc = "moderate (中等)"
        else:
            intensity_desc = "mild (輕微)"
        
        # 風險評估
        if anxiety_risk > 70:
            risk_desc = "high risk - needs attention (高風險 - 需要關注)"
        elif anxiety_risk > 40:
            risk_desc = "moderate risk - monitor closely (中等風險 - 密切監測)"
        else:
            risk_desc = "low risk (低風險)"
        
        # 調節能力
        if emotional_regulation > 70:
            regulation_desc = "good (良好)"
        elif emotional_regulation > 40:
            regulation_desc = "fair (尚可)"
        else:
            regulation_desc = "needs support (需要支持)"
        
        summary = f"Emotion: {emotion_desc.get(dominant_emotion, 'unknown')} ({intensity_desc}); " \
                 f"Anxiety Risk: {risk_desc}; " \
                 f"Emotional Regulation: {regulation_desc}"
        
        return summary


# 全局實例（單例）
_emotion_service_instance = None

def get_emotion_analysis_service() -> EmotionAnalysisService:
    """獲取情緒分析服務實例（單例模式）"""
    global _emotion_service_instance
    if _emotion_service_instance is None:
        _emotion_service_instance = EmotionAnalysisService()
    return _emotion_service_instance

