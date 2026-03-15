"""
Mental Health Skill Configuration

Provides emotional support, anxiety/depression screening,
and general mental wellbeing guidance.
"""

from .base_skill import SkillConfig
from src.core.prompt_loader import load_skill_prompt

MENTAL_HEALTH_SKILL = SkillConfig(
    name="mental_health",
    display_name="Mental Health Support",
    description="Provides emotional support, anxiety/depression awareness, and mental wellbeing guidance",
    
    keywords_en=[
        # Emotions
        "sad", "sadness", "unhappy", "depressed", "depression", "anxious", "anxiety",
        "worried", "worry", "stressed", "stress", "overwhelmed", "scared", "fear",
        "lonely", "alone", "hopeless", "helpless", "nervous", "panic", "crying",
        "upset", "angry", "frustrated", "confused", "lost", "empty",
        
        # Mental health terms
        "mental health", "emotional", "feelings", "mood", "therapy", "counseling",
        "psychologist", "psychiatrist", "breakdown", "burnout",
        
        # Youth specific
        "exam stress", "school pressure", "bullying", "bullied", "friends problem",
        "family problems", "parents fighting", "nobody understands"
    ],
    
    keywords_zh=[
        # Emotions
        "傷心", "難過", "不開心", "抑鬱", "焦慮", "擔心", "壓力", "害怕",
        "孤獨", "寂寞", "絕望", "無助", "緊張", "恐慌", "哭", "喊",
        "嬲", "憤怒", "沮喪", "迷失", "空虛",
        
        # Mental health
        "心理健康", "情緒", "感受", "心情", "輔導", "心理醫生",
        
        # Youth specific
        "考試壓力", "學業壓力", "欺凌", "被欺負", "朋友問題",
        "家庭問題", "父母吵架", "冇人明白"
    ],
    
    priority=70,
    
    # Load prompts from files
    system_prompt_addition=load_skill_prompt("mental_health", "system_prompt"),
    response_guidelines=load_skill_prompt("mental_health", "response_guidelines"),
    
    available_functions=[
        "record_concern",
        "track_mood",
        "suggest_coping_strategy",
        "schedule_follow_up"
    ],
    
    knowledge_categories=[
        "psychoeducation",
        "coping_strategies",
        "child_mental_health",
        "adolescent_mental_health"
    ],
    
    emotion_hints={
        "sad": "concerned",
        "anxious": "supportive",
        "angry": "calm",
        "lonely": "warm"
    },
    
    requires_safety_check=True
)

