"""
Function Calling Tool Definitions for Healthcare AI V2

These tools enable the AI to:
1. Record important information during conversations with children
2. Provide intelligent analysis for social workers
3. Proactively take actions based on conversation context
4. Administer structured questionnaires during conversations
"""

from typing import List, Dict, Any
from src.tools.questionnaire_tool import QUESTIONNAIRE_TOOLS


# =============================================================================
# CHILD CHAT TOOLS - For AI conversations with children
# =============================================================================

CHILD_CHAT_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "record_concern",
            "description": "當兒童提到重要問題時，自動記錄到數據庫供社工查看。Record important concerns mentioned by the child for social worker review.",
            "parameters": {
                "type": "object",
                "properties": {
                    "concern_type": {
                        "type": "string",
                        "enum": ["bullying", "family", "school", "emotion", "behavior", "health", "safety", "other"],
                        "description": "問題類型 Type of concern"
                    },
                    "severity": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "description": "嚴重程度 1-5 (1=輕微, 5=嚴重) Severity level"
                    },
                    "summary": {
                        "type": "string",
                        "description": "問題摘要（簡短描述）Brief summary of the concern"
                    },
                    "child_message": {
                        "type": "string",
                        "description": "兒童的原話 Original message from child"
                    },
                    "needs_urgent_attention": {
                        "type": "boolean",
                        "description": "是否需要立即關注 Whether this needs immediate attention"
                    }
                },
                "required": ["concern_type", "severity", "summary", "child_message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "log_emotion",
            "description": "記錄兒童的情緒狀態變化。Track the child's emotional state changes over time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "emotion": {
                        "type": "string",
                        "enum": ["happy", "sad", "angry", "anxious", "scared", "confused", "excited", "calm", "frustrated", "lonely"],
                        "description": "情緒類型 Emotion type"
                    },
                    "intensity": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "description": "情緒強度 1-5 Emotion intensity"
                    },
                    "trigger": {
                        "type": "string",
                        "description": "觸發因素（如果有提到）Trigger or cause if mentioned"
                    },
                    "context": {
                        "type": "string",
                        "description": "情境描述 Context description"
                    }
                },
                "required": ["emotion", "intensity"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_coping_activity",
            "description": "推薦適合兒童的情緒調節活動。Suggest age-appropriate coping activities for the child.",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_emotion": {
                        "type": "string",
                        "description": "當前情緒 Current emotion state"
                    },
                    "child_age": {
                        "type": "integer",
                        "minimum": 6,
                        "maximum": 17,
                        "description": "兒童年齡 Child's age"
                    },
                    "activity_type": {
                        "type": "string",
                        "enum": ["breathing", "drawing", "writing", "physical", "game", "music", "meditation", "talking"],
                        "description": "活動類型 Activity type"
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 30,
                        "description": "建議時長（分鐘）Suggested duration in minutes"
                    }
                },
                "required": ["current_emotion", "activity_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "alert_social_worker",
            "description": "當檢測到嚴重問題時，立即通知社工。Immediately alert social worker when serious issues are detected.",
            "parameters": {
                "type": "object",
                "properties": {
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "優先級 Priority level"
                    },
                    "reason": {
                        "type": "string",
                        "description": "通知原因 Reason for alert"
                    },
                    "child_message": {
                        "type": "string",
                        "description": "兒童的相關訊息 Related child message"
                    },
                    "recommended_action": {
                        "type": "string",
                        "description": "建議採取的行動 Recommended action"
                    },
                    "detected_risk_factors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "檢測到的風險因素 Detected risk factors"
                    }
                },
                "required": ["priority", "reason", "child_message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "provide_resource",
            "description": "提供心理健康資源（熱線、文章、視頻等）。Provide mental health resources like hotlines, articles, videos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource_type": {
                        "type": "string",
                        "enum": ["hotline", "article", "video", "exercise", "contact", "website"],
                        "description": "資源類型 Resource type"
                    },
                    "topic": {
                        "type": "string",
                        "description": "主題 Topic or issue"
                    },
                    "age_appropriate": {
                        "type": "boolean",
                        "description": "是否適合年齡 Whether age-appropriate"
                    },
                    "language": {
                        "type": "string",
                        "enum": ["en", "zh-TW", "both"],
                        "description": "語言 Language"
                    }
                },
                "required": ["resource_type", "topic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "track_behavior_pattern",
            "description": "追蹤行為模式（如：持續的情緒低落、睡眠問題）。Track behavioral patterns over time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern_type": {
                        "type": "string",
                        "enum": ["sleep", "appetite", "social_withdrawal", "mood_changes", "attention", "aggression", "self_harm"],
                        "description": "行為模式類型 Pattern type"
                    },
                    "frequency": {
                        "type": "string",
                        "enum": ["rare", "occasional", "frequent", "daily", "constant"],
                        "description": "頻率 Frequency"
                    },
                    "duration": {
                        "type": "string",
                        "description": "持續時間（例如：\"2週\"、\"1個月\"）Duration (e.g., '2 weeks', '1 month')"
                    },
                    "severity_trend": {
                        "type": "string",
                        "enum": ["improving", "stable", "worsening"],
                        "description": "趨勢 Trend"
                    },
                    "notes": {
                        "type": "string",
                        "description": "備註 Additional notes"
                    }
                },
                "required": ["pattern_type", "frequency"]
            }
        }
    }
] + QUESTIONNAIRE_TOOLS  # Add questionnaire tools to child chat tools


# =============================================================================
# SOCIAL WORKER TOOLS - For professional analysis and decision support
# =============================================================================

SOCIAL_WORKER_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "analyze_child_progress",
            "description": "分析兒童在一段時間內的進展。Analyze child's progress over a specified time period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "child_id": {
                        "type": "string",
                        "description": "兒童ID Child ID"
                    },
                    "time_range": {
                        "type": "string",
                        "enum": ["week", "month", "3months", "6months", "year"],
                        "description": "時間範圍 Time range"
                    },
                    "metrics": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["emotion", "behavior", "social", "academic", "family", "physical_health"]
                        },
                        "description": "分析指標 Metrics to analyze"
                    },
                    "include_visualization": {
                        "type": "boolean",
                        "description": "是否包含圖表 Include charts/graphs"
                    }
                },
                "required": ["child_id", "time_range"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_risk_patterns",
            "description": "檢測潛在風險模式（如：持續情緒低落、自傷傾向）。Detect potential risk patterns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "child_id": {
                        "type": "string",
                        "description": "兒童ID Child ID"
                    },
                    "risk_types": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["self_harm", "depression", "anxiety", "aggression", "withdrawal", "substance", "eating_disorder"]
                        },
                        "description": "風險類型 Risk types to check"
                    },
                    "lookback_days": {
                        "type": "integer",
                        "minimum": 7,
                        "maximum": 365,
                        "description": "回溯天數 Days to look back"
                    },
                    "sensitivity": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "檢測敏感度 Detection sensitivity"
                    }
                },
                "required": ["child_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_questionnaire_responses",
            "description": "比較不同時期的問卷回答，追蹤變化。Compare questionnaire responses across time periods.",
            "parameters": {
                "type": "object",
                "properties": {
                    "child_id": {
                        "type": "string",
                        "description": "兒童ID Child ID"
                    },
                    "questionnaire_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "問卷ID列表 List of questionnaire IDs to compare"
                    },
                    "focus_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "關注領域 Areas to focus on"
                    }
                },
                "required": ["child_id", "questionnaire_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_similar_cases",
            "description": "搜索數據庫中類似的案例，學習最佳實踐。Search for similar cases to learn best practices.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symptoms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "症狀列表 List of symptoms"
                    },
                    "age_range": {
                        "type": "object",
                        "properties": {
                            "min": {"type": "integer", "minimum": 6, "maximum": 17},
                            "max": {"type": "integer", "minimum": 6, "maximum": 17}
                        },
                        "description": "年齡範圍 Age range"
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["mild", "moderate", "severe"],
                        "description": "嚴重程度 Severity level"
                    },
                    "include_outcomes": {
                        "type": "boolean",
                        "description": "包含治療結果 Include treatment outcomes"
                    },
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "description": "最大結果數 Maximum number of results"
                    }
                },
                "required": ["symptoms"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_intervention",
            "description": "基於AI分析推薦干預措施。Recommend interventions based on AI analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "child_profile": {
                        "type": "object",
                        "description": "兒童檔案（年齡、症狀等）Child profile including age, symptoms, etc."
                    },
                    "goals": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "治療目標 Treatment goals"
                    },
                    "intervention_types": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["therapy", "medication", "family_support", "school_support", "skills_training", "crisis_intervention"]
                        },
                        "description": "干預類型 Types of interventions to consider"
                    },
                    "consider_resources": {
                        "type": "boolean",
                        "description": "考慮可用資源 Consider available resources"
                    }
                },
                "required": ["child_profile", "goals"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_professional_report",
            "description": "生成專業評估報告。Generate professional assessment report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "child_id": {
                        "type": "string",
                        "description": "兒童ID Child ID"
                    },
                    "report_type": {
                        "type": "string",
                        "enum": ["initial", "progress", "final", "referral", "crisis"],
                        "description": "報告類型 Report type"
                    },
                    "include_chart_data": {
                        "type": "boolean",
                        "description": "包含圖表數據 Include chart data"
                    },
                    "include_recommendations": {
                        "type": "boolean",
                        "description": "包含建議 Include recommendations"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["pdf", "docx", "json"],
                        "description": "輸出格式 Output format"
                    },
                    "language": {
                        "type": "string",
                        "enum": ["en", "zh-TW", "both"],
                        "description": "語言 Language"
                    }
                },
                "required": ["child_id", "report_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_safety_plan",
            "description": "創建安全計劃（用於高風險情況）。Create a safety plan for high-risk situations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "child_id": {
                        "type": "string",
                        "description": "兒童ID Child ID"
                    },
                    "risk_factors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "風險因素 Risk factors"
                    },
                    "warning_signs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "警示信號 Warning signs"
                    },
                    "coping_strategies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "應對策略 Coping strategies"
                    },
                    "emergency_contacts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "relationship": {"type": "string"},
                                "phone": {"type": "string"}
                            }
                        },
                        "description": "緊急聯絡人 Emergency contacts"
                    }
                },
                "required": ["child_id", "risk_factors"]
            }
        }
    }
]


# =============================================================================
# COMBINED TOOLS
# =============================================================================

ALL_TOOLS = CHILD_CHAT_TOOLS + SOCIAL_WORKER_TOOLS


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_tools_by_context(context: str) -> List[Dict[str, Any]]:
    """
    獲取特定情境的工具
    Get tools for a specific context
    
    Args:
        context: "child_chat", "social_worker", or "all"
    
    Returns:
        List of tool definitions
    """
    if context == "child_chat":
        return CHILD_CHAT_TOOLS
    elif context == "social_worker":
        return SOCIAL_WORKER_TOOLS
    elif context == "all":
        return ALL_TOOLS
    else:
        raise ValueError(f"Unknown context: {context}")


def get_tool_by_name(tool_name: str) -> Dict[str, Any]:
    """
    根據名稱獲取工具定義
    Get tool definition by name
    
    Args:
        tool_name: Name of the tool
    
    Returns:
        Tool definition dict or None if not found
    """
    for tool in ALL_TOOLS:
        if tool["function"]["name"] == tool_name:
            return tool
    return None


def list_all_tool_names() -> List[str]:
    """
    列出所有可用工具的名稱
    List names of all available tools
    """
    return [tool["function"]["name"] for tool in ALL_TOOLS]


def get_tools_for_agent(agent_type: str) -> List[Dict[str, Any]]:
    """
    根據代理類型獲取相應的工具
    Get tools appropriate for the agent type
    
    Args:
        agent_type: Type of agent (e.g., "mental_health", "illness_monitor", "social_worker")
    
    Returns:
        List of tool definitions appropriate for this agent
    """
    # Mental health and child-facing agents use child chat tools
    if agent_type in ["mental_health", "小星星", "wellness_coach"]:
        return CHILD_CHAT_TOOLS
    
    # Social worker and admin agents use social worker tools
    elif agent_type in ["social_worker", "admin", "super_admin"]:
        return SOCIAL_WORKER_TOOLS
    
    # Default to child chat tools for safety (most common use case)
    else:
        return CHILD_CHAT_TOOLS

