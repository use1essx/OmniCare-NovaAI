"""
Social Support Skill Configuration

Provides guidance for social relationships, family issues,
friendships, and peer interactions.
"""

from .base_skill import SkillConfig
from src.core.prompt_loader import load_skill_prompt

SOCIAL_SUPPORT_SKILL = SkillConfig(
    name="social_support",
    display_name="Social & Family Support",
    description="Provides support for social relationships, family dynamics, and peer interactions",
    
    keywords_en=[
        # Relationships
        "friends", "friend", "friendship", "classmates", "peers",
        "relationship", "boyfriend", "girlfriend", "crush",
        
        # Family
        "family", "parents", "mom", "mum", "dad", "father", "mother",
        "siblings", "brother", "sister", "grandparents",
        "divorce", "separated", "fighting", "arguing",
        
        # Social issues
        "lonely", "alone", "no friends", "left out", "excluded",
        "bullying", "bullied", "teased", "made fun of",
        "fight", "argument", "conflict", "misunderstanding",
        
        # Social skills
        "shy", "nervous", "awkward", "don't know what to say",
        "making friends", "fit in", "popular"
    ],
    
    keywords_zh=[
        # Relationships
        "朋友", "友情", "同學", "同伴",
        "關係", "男朋友", "女朋友", "鍾意嘅人",
        
        # Family
        "家庭", "父母", "媽媽", "爸爸", "阿爸", "阿媽",
        "兄弟姐妹", "哥哥", "姐姐", "弟弟", "妹妹", "爺爺嫲嫲",
        "離婚", "分開", "嘈交", "吵架",
        
        # Social issues
        "孤獨", "冇朋友", "被排斥", "被冷落",
        "欺凌", "被蝦", "被取笑", "被笑",
        "打交", "吵架", "誤會",
        
        # Social skills
        "怕醜", "緊張", "尷尬", "唔知講咩",
        "識朋友", "融入", "受歡迎"
    ],
    
    priority=55,
    
    # Load prompts from files
    system_prompt_addition=load_skill_prompt("social_support", "system_prompt"),
    response_guidelines=load_skill_prompt("social_support", "response_guidelines"),
    
    available_functions=[
        "provide_social_tip",
        "record_family_concern",
        "suggest_communication_strategy"
    ],
    
    knowledge_categories=[
        "psychoeducation",
        "parent_guide",
        "family_support"
    ],
    
    emotion_hints={
        "lonely": "warm",
        "family_conflict": "understanding",
        "friend_problem": "supportive"
    },
    
    requires_safety_check=True
)

