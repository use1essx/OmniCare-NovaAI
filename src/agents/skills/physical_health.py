"""
Physical Health Skill Configuration

Provides guidance on physical health concerns, 
HK healthcare facilities, and medical information.
"""

from .base_skill import SkillConfig
from src.core.prompt_loader import load_skill_prompt

PHYSICAL_HEALTH_SKILL = SkillConfig(
    name="physical_health",
    display_name="Physical Health Guidance",
    description="Provides physical health guidance and Hong Kong healthcare facility information",
    
    keywords_en=[
        # Symptoms
        "sick", "ill", "pain", "hurt", "ache", "fever", "headache", "stomachache",
        "tired", "fatigue", "dizzy", "nausea", "vomiting", "cough", "cold",
        "sore throat", "injury", "wound", "bleeding",
        
        # Body parts
        "head", "stomach", "chest", "back", "leg", "arm", "eye", "ear",
        
        # Medical
        "doctor", "hospital", "clinic", "medicine", "medication", "treatment",
        "checkup", "appointment", "emergency", "ambulance",
        
        # Lifestyle
        "exercise", "nutrition", "diet", "weight", "sleep problem", "insomnia"
    ],
    
    keywords_zh=[
        # Symptoms
        "病", "唔舒服", "痛", "發燒", "頭痛", "肚痛", "肚屙",
        "攰", "疲倦", "暈", "嘔", "咳", "傷風", "感冒",
        "喉嚨痛", "受傷", "流血",
        
        # Body parts
        "頭", "肚", "胸口", "背", "腳", "手", "眼", "耳",
        
        # Medical
        "醫生", "醫院", "診所", "藥", "治療", "檢查", "急症", "救護車",
        
        # Lifestyle
        "運動", "營養", "飲食", "體重", "瞓唔著", "失眠"
    ],
    
    priority=60,
    
    # Load prompts from files
    system_prompt_addition=load_skill_prompt("physical_health", "system_prompt"),
    response_guidelines=load_skill_prompt("physical_health", "response_guidelines"),
    
    available_functions=[
        "find_nearby_facility",
        "provide_health_info",
        "record_symptom",
        "emergency_guidance"
    ],
    
    knowledge_categories=[
        "hk_facilities",
        "medication",
        "professional_guidelines"
    ],
    
    emotion_hints={
        "sick": "caring",
        "pain": "concerned",
        "worried_health": "reassuring"
    },
    
    requires_safety_check=True
)

