"""
Sleep Support Skill Configuration

Provides guidance for sleep issues, bedtime routines,
and sleep hygiene for children and adolescents.
"""

from .base_skill import SkillConfig
from src.core.prompt_loader import load_skill_prompt

SLEEP_SUPPORT_SKILL = SkillConfig(
    name="sleep_support",
    display_name="Sleep Support",
    description="Provides sleep guidance, bedtime routines, and sleep hygiene tips",
    
    keywords_en=[
        # Sleep problems
        "sleep", "sleeping", "can't sleep", "insomnia", "awake", "tired",
        "nightmare", "bad dream", "night terror", "scared at night",
        "wake up", "waking up", "restless", "tossing",
        
        # Bedtime
        "bedtime", "bed", "night", "evening", "late", "stay up",
        "oversleep", "sleep late", "can't wake up",
        
        # Quality
        "sleep quality", "deep sleep", "rest", "exhausted", "drowsy"
    ],
    
    keywords_zh=[
        # Sleep problems
        "瞓覺", "訓覺", "瞓唔著", "失眠", "眼瞓", "攰",
        "發惡夢", "夜驚", "夜晚驚",
        "瞓醒", "紮醒", "輾轉反側",
        
        # Bedtime
        "訓教時間", "上床", "夜晚", "遲", "熬夜",
        "賴床", "瞓過龍", "起唔到身",
        
        # Quality
        "睡眠質素", "休息", "好攰", "眼訓"
    ],
    
    priority=45,
    
    # Load prompts from files
    system_prompt_addition=load_skill_prompt("sleep_support", "system_prompt"),
    response_guidelines=load_skill_prompt("sleep_support", "response_guidelines"),
    
    available_functions=[
        "suggest_bedtime_routine",
        "provide_relaxation_technique",
        "track_sleep_pattern"
    ],
    
    knowledge_categories=[
        "psychoeducation",
        "coping_strategies"
    ],
    
    emotion_hints={
        "tired": "soothing",
        "scared_night": "calming",
        "restless": "peaceful"
    },
    
    requires_safety_check=False
)

