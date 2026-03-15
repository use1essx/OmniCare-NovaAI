"""
Wellness Coaching Skill Configuration

Provides general wellness guidance, positive reinforcement,
and healthy lifestyle encouragement.
"""

from .base_skill import SkillConfig
from src.core.prompt_loader import load_skill_prompt

WELLNESS_COACHING_SKILL = SkillConfig(
    name="wellness_coaching",
    display_name="Wellness Coaching",
    description="Provides wellness guidance, positive reinforcement, and healthy lifestyle tips",
    
    keywords_en=[
        # Wellness
        "healthy", "health", "wellness", "wellbeing", "lifestyle",
        "habits", "routine", "balance", "self-care", "relax", "relaxation",
        
        # Activities
        "exercise", "workout", "sports", "hobby", "hobbies", "activity",
        "outdoors", "nature", "walk", "meditation", "yoga",
        
        # Goals
        "improve", "better", "goal", "motivation", "energy", "positive",
        "happy", "happiness", "joy", "gratitude", "mindful", "mindfulness",
        
        # General chat
        "bored", "nothing to do", "suggest", "recommend", "fun",
        "what should I do", "any ideas"
    ],
    
    keywords_zh=[
        # Wellness
        "健康", "養生", "生活方式", "習慣", "日常", "平衡",
        "自我照顧", "放鬆", "休息",
        
        # Activities
        "運動", "做gym", "行山", "興趣", "活動", "戶外", "大自然",
        "冥想", "瑜珈",
        
        # Goals
        "改善", "進步", "目標", "動力", "精力", "正面",
        "開心", "快樂", "感恩", "正念",
        
        # General chat
        "悶", "冇嘢做", "建議", "推薦", "好玩"
    ],
    
    priority=40,
    
    # Load prompts from files
    system_prompt_addition=load_skill_prompt("wellness_coaching", "system_prompt"),
    response_guidelines=load_skill_prompt("wellness_coaching", "response_guidelines"),
    
    available_functions=[
        "suggest_activity",
        "track_wellness_goal",
        "provide_tip"
    ],
    
    knowledge_categories=[
        "coping_strategies",
        "parent_guide"
    ],
    
    emotion_hints={
        "bored": "energetic",
        "seeking": "enthusiastic",
        "happy": "joyful"
    },
    
    requires_safety_check=False
)

