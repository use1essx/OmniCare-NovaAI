"""
Safety Crisis Skill Configuration

HIGHEST PRIORITY skill for handling crisis situations,
self-harm, suicidal ideation, and abuse detection.
"""

from .base_skill import SkillConfig
from src.core.prompt_loader import load_skill_prompt

SAFETY_CRISIS_SKILL = SkillConfig(
    name="safety_crisis",
    display_name="Safety & Crisis Intervention",
    description="Handles crisis situations including self-harm, suicidal ideation, and abuse detection",
    
    keywords_en=[
        # Self-harm / Suicide
        "suicide", "kill myself", "end my life", "want to die", "better off dead",
        "hurt myself", "self-harm", "cutting", "overdose", "jump", "hang",
        "no point living", "can't go on", "end it", "give up on life",
        
        # Severe distress
        "hopeless", "worthless", "nobody cares", "hate myself", "burden",
        "everyone hate me", "world better without me", "no future",
        
        # Abuse
        "hit me", "beat me", "touch me", "abuse", "molest", "force me",
        "scared of", "hurt by", "threatened", "violence"
    ],
    
    keywords_zh=[
        # Self-harm / Suicide
        "自殺", "想死", "殺死自己", "唔想活", "死咗好過",
        "自殘", "割自己", "跳樓", "吊頸", "食藥",
        "冇意義", "唔想繼續", "放棄", "結束生命",
        
        # Severe distress
        "絕望", "冇用", "冇人關心", "憎恨自己", "累贅",
        "人人都憎我", "世界冇我會更好", "冇將來",
        
        # Abuse
        "打我", "虐待", "非禮", "侵犯", "威脅", "暴力",
        "驚佢", "傷害我"
    ],
    
    crisis_keywords=[
        # EN - Immediate danger
        "suicide", "kill myself", "want to die", "end my life", "hurt myself",
        "self-harm", "cutting", "overdose", "jump off", "hang myself",
        "don't want to live", "not want to live", "live anymore", "no point living",
        "end it all", "wish i was dead", "better off dead",
        
        # ZH - Immediate danger  
        "自殺", "想死", "殺死自己", "唔想活", "自殘", "割自己",
        "唔想再活", "死咗好", "活唔落去", "唔想做人"
    ],
    
    # HIGHEST priority - always override other skills
    priority=100,
    
    # Load prompts from files
    system_prompt_addition=load_skill_prompt("safety_crisis", "system_prompt"),
    response_guidelines=load_skill_prompt("safety_crisis", "response_guidelines"),
    
    available_functions=[
        "alert_social_worker",
        "create_safety_plan",
        "log_crisis_event",
        "escalate_to_emergency",
        "record_risk_level"
    ],
    
    knowledge_categories=[
        "crisis_protocol",
        "professional_guidelines"
    ],
    
    emotion_hints={
        "crisis": "calm_supportive",
        "distress": "steady_caring",
        "fear": "protective"
    },
    
    requires_safety_check=True
)

