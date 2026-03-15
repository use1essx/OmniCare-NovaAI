"""
Function Calling Tool Handlers for Healthcare AI V2

These handlers execute the actual tool calls and interact with the database,
external services, and other system components.
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.database.connection import get_sync_db
from src.database.models_comprehensive import (
    AuditLog
)
from src.services.notification import get_notification_service
from src.tools.questionnaire_tool import QUESTIONNAIRE_HANDLERS


logger = get_logger(__name__)


class ToolHandler:
    """處理所有 Function Calling 工具調用 Handles all function calling tool executions"""
    
    def __init__(self, db_session: Optional[Session] = None):
        """
        初始化工具處理器
        
        Args:
            db_session: Optional database session, will create one if not provided
        """
        self.db = db_session
        self._owns_session = db_session is None
        
        if self._owns_session:
            self.db = next(get_sync_db())
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._owns_session and self.db:
            self.db.close()
    
    # =========================================================================
    # CHILD CHAT TOOLS HANDLERS
    # =========================================================================
    
    def handle_record_concern(
        self,
        concern_type: str,
        severity: int,
        summary: str,
        child_message: str,
        needs_urgent_attention: bool = False,
        user_id: Optional[int] = None,
        conversation_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        記錄兒童提到的重要問題
        Record important concerns mentioned by the child
        """
        try:
            # Create audit log entry for the concern
            audit_entry = AuditLog(
                user_id=user_id,
                event_type="record_concern",
                event_category="function_calling",
                event_description=f"AI recorded concern: {concern_type} (severity: {severity})",
                target_type="concern",
                target_id=str(user_id) if user_id else "anonymous",
                target_details={
                    "concern_type": concern_type,
                    "severity": severity,
                    "summary": summary,
                    "child_message": child_message,
                    "needs_urgent_attention": needs_urgent_attention,
                    "conversation_id": conversation_id,
                    "timestamp": datetime.utcnow().isoformat()
                },
                result="success",
                severity_level="warning" if severity >= 4 else "info"
            )
            
            self.db.add(audit_entry)
            self.db.commit()
            
            logger.info(
                f"Recorded concern: type={concern_type}, severity={severity}, urgent={needs_urgent_attention}",
                extra={
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "concern_type": concern_type,
                    "severity": severity
                }
            )
            
            result = {
                "success": True,
                "concern_id": audit_entry.id,
                "message": "問題已記錄 Concern recorded successfully",
                "needs_review": needs_urgent_attention or severity >= 4,
                "recommended_action": self._get_recommended_action(concern_type, severity)
            }
            
            # If urgent, trigger alert AND send email notification
            if needs_urgent_attention or severity >= 4:
                self._trigger_urgent_alert(audit_entry.id, concern_type, severity, summary)
                
                # Send email notification to social workers
                self._send_email_notification(
                    alert_type="concern_recorded",
                    severity="critical" if severity >= 4 else "warning",
                    details={
                        "concern_id": audit_entry.id,
                        "concern_type": concern_type,
                        "severity": f"{severity}/5",
                        "summary": summary,
                        "child_message": child_message,
                        "needs_urgent_attention": needs_urgent_attention,
                        "recommended_action": result["recommended_action"]
                    }
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Error recording concern: {e}")
            self.db.rollback()
            return {
                "success": False,
                "error": str(e),
                "message": "記錄問題時發生錯誤 Error recording concern"
            }
    
    def handle_log_emotion(
        self,
        emotion: str,
        intensity: int,
        trigger: Optional[str] = None,
        context: Optional[str] = None,
        user_id: Optional[int] = None,
        conversation_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        記錄兒童的情緒狀態
        Log child's emotional state
        """
        try:
            audit_entry = AuditLog(
                user_id=user_id,
                event_type="log_emotion",
                event_category="function_calling",
                event_description=f"AI logged emotion: {emotion} (intensity: {intensity})",
                target_type="emotion",
                target_id=str(user_id) if user_id else "anonymous",
                target_details={
                    "emotion": emotion,
                    "intensity": intensity,
                    "trigger": trigger,
                    "context": context,
                    "conversation_id": conversation_id,
                    "timestamp": datetime.utcnow().isoformat()
                },
                result="success",
                severity_level="info"
            )
            
            self.db.add(audit_entry)
            self.db.commit()
            
            logger.info(
                f"Logged emotion: {emotion} (intensity: {intensity})",
                extra={
                    "user_id": user_id,
                    "emotion": emotion,
                    "intensity": intensity
                }
            )
            
            # Analyze emotion pattern
            pattern_analysis = self._analyze_emotion_pattern(user_id, emotion)
            
            return {
                "success": True,
                "emotion_log_id": audit_entry.id,
                "message": "情緒已記錄 Emotion logged successfully",
                "pattern_detected": pattern_analysis.get("pattern_detected", False),
                "trend": pattern_analysis.get("trend", "stable"),
                "suggestions": self._get_emotion_support_suggestions(emotion, intensity)
            }
            
        except Exception as e:
            logger.error(f"Error logging emotion: {e}")
            self.db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def handle_suggest_coping_activity(
        self,
        current_emotion: str,
        activity_type: str,
        child_age: Optional[int] = None,
        duration_minutes: Optional[int] = 10
    ) -> Dict[str, Any]:
        """
        推薦情緒調節活動
        Suggest coping activities
        """
        try:
            activities = {
                "breathing": {
                    "name": "深呼吸練習 Deep Breathing",
                    "description": "慢慢吸氣，數到4，然後慢慢呼氣。重複5次。Breathe in slowly for 4 counts, then breathe out. Repeat 5 times.",
                    "duration": 5,
                    "age_range": [6, 17]
                },
                "drawing": {
                    "name": "情緒繪畫 Emotion Drawing",
                    "description": "用顏色和形狀畫出你的感受。Use colors and shapes to draw how you feel.",
                    "duration": 15,
                    "age_range": [6, 14]
                },
                "writing": {
                    "name": "寫日記 Journaling",
                    "description": "寫下你的想法和感受。Write down your thoughts and feelings.",
                    "duration": 10,
                    "age_range": [10, 17]
                },
                "physical": {
                    "name": "身體運動 Physical Activity",
                    "description": "做一些運動，如伸展、散步或跳繩。Do some exercise like stretching, walking, or jumping rope.",
                    "duration": 15,
                    "age_range": [6, 17]
                },
                "game": {
                    "name": "遊戲放鬆 Relaxation Game",
                    "description": "玩一個你喜歡的輕鬆遊戲。Play a calm game you enjoy.",
                    "duration": 20,
                    "age_range": [6, 17]
                },
                "music": {
                    "name": "聽音樂 Listen to Music",
                    "description": "聽一些讓你感覺舒服的音樂。Listen to calming music.",
                    "duration": 10,
                    "age_range": [6, 17]
                },
                "meditation": {
                    "name": "簡單冥想 Simple Meditation",
                    "description": "閉上眼睛，專注在你的呼吸上。Close your eyes and focus on your breathing.",
                    "duration": 5,
                    "age_range": [10, 17]
                },
                "talking": {
                    "name": "與信任的人聊天 Talk to Someone",
                    "description": "找一個你信任的人談談。Talk to someone you trust.",
                    "duration": 15,
                    "age_range": [6, 17]
                }
            }
            
            activity = activities.get(activity_type, activities["breathing"])
            
            # Adjust for age if provided
            if child_age and child_age not in range(activity["age_range"][0], activity["age_range"][1] + 1):
                # Find age-appropriate alternative
                for alt_type, alt_activity in activities.items():
                    if child_age in range(alt_activity["age_range"][0], alt_activity["age_range"][1] + 1):
                        activity = alt_activity
                        activity_type = alt_type
                        break
            
            return {
                "success": True,
                "activity": {
                    "type": activity_type,
                    "name": activity["name"],
                    "description": activity["description"],
                    "duration_minutes": duration_minutes or activity["duration"],
                    "instructions": self._get_activity_instructions(activity_type),
                    "benefits": self._get_activity_benefits(activity_type, current_emotion)
                },
                "message": f"建議活動：{activity['name']} Suggested activity: {activity['name']}"
            }
            
        except Exception as e:
            logger.error(f"Error suggesting activity: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def handle_alert_social_worker(
        self,
        priority: str,
        reason: str,
        child_message: str,
        recommended_action: Optional[str] = None,
        detected_risk_factors: Optional[List[str]] = None,
        user_id: Optional[int] = None,
        conversation_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        通知社工
        Alert social worker
        """
        try:
            alert_data = {
                "priority": priority,
                "reason": reason,
                "child_message": child_message,
                "recommended_action": recommended_action,
                "risk_factors": detected_risk_factors or [],
                "conversation_id": conversation_id,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "pending"
            }
            
            # Create high-priority audit log
            audit_entry = AuditLog(
                user_id=user_id,
                event_type="alert_social_worker",
                event_category="function_calling",
                event_description=f"AI alerted social worker: {priority} priority - {reason}",
                target_type="alert",
                target_id=str(user_id) if user_id else "anonymous",
                target_details=alert_data,
                result="success",
                severity_level="critical" if priority == "urgent" else "warning"
            )
            
            self.db.add(audit_entry)
            self.db.commit()
            
            logger.warning(
                f"Social worker alert created: priority={priority}, reason={reason}",
                extra={
                    "alert_id": audit_entry.id,
                    "priority": priority,
                    "user_id": user_id
                }
            )
            
            # Send email notification to social workers
            self._send_email_notification(
                alert_type="social_worker_alert",
                severity="critical" if priority == "urgent" else "warning",
                details={
                    "alert_id": audit_entry.id,
                    "priority": priority,
                    "reason": reason,
                    "child_message": child_message,
                    "recommended_action": recommended_action,
                    "risk_factors": detected_risk_factors or [],
                    "estimated_response_time": self._estimate_response_time(priority)
                }
            )
            
            return {
                "success": True,
                "alert_id": audit_entry.id,
                "message": f"已通知社工（{priority}級別）Social worker alerted ({priority} priority)",
                "estimated_response_time": self._estimate_response_time(priority)
            }
            
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            self.db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def handle_provide_resource(
        self,
        resource_type: str,
        topic: str,
        age_appropriate: bool = True,
        language: str = "zh-TW"
    ) -> Dict[str, Any]:
        """
        提供心理健康資源
        Provide mental health resources
        """
        try:
            # Resource database (can be moved to actual database)
            resources = {
                "hotline": {
                    "香港生命熱線": {
                        "phone": "2382 0000",
                        "hours": "24小時 24/7",
                        "languages": ["zh-TW", "en"],
                        "description": "提供情緒支援 Emotional support"
                    },
                    "撒瑪利亞防止自殺會": {
                        "phone": "2389 2222",
                        "hours": "24小時 24/7",
                        "languages": ["zh-TW", "en"],
                        "description": "自殺預防 Suicide prevention"
                    },
                    "協青社青年服務熱線": {
                        "phone": "9088 1023",
                        "hours": "星期一至六 Mon-Sat 2pm-10pm",
                        "languages": ["zh-TW"],
                        "description": "青少年服務 Youth services"
                    }
                },
                "website": {
                    "青協「關心一線」": {
                        "url": "https://27778899.hkfyg.org.hk",
                        "description": "青少年輔導服務 Youth counseling"
                    },
                    "衛生署學生健康服務": {
                        "url": "https://www.studenthealth.gov.hk",
                        "description": "學生健康資訊 Student health information"
                    }
                }
            }
            
            resource_list = resources.get(resource_type, {})
            
            return {
                "success": True,
                "resources": [
                    {
                        "name": name,
                        **details,
                        "topic": topic,
                        "resource_type": resource_type
                    }
                    for name, details in resource_list.items()
                ],
                "message": f"找到 {len(resource_list)} 個相關資源 Found {len(resource_list)} relevant resources"
            }
            
        except Exception as e:
            logger.error(f"Error providing resource: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def handle_track_behavior_pattern(
        self,
        pattern_type: str,
        frequency: str,
        duration: Optional[str] = None,
        severity_trend: str = "stable",
        notes: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        追蹤行為模式
        Track behavioral patterns
        """
        try:
            pattern_data = {
                "pattern_type": pattern_type,
                "frequency": frequency,
                "duration": duration,
                "severity_trend": severity_trend,
                "notes": notes,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            audit_entry = AuditLog(
                user_id=user_id,
                event_type="track_behavior_pattern",
                event_category="function_calling",
                event_description=f"AI tracked behavior pattern: {pattern_type}",
                target_type="behavior_pattern",
                target_id=str(user_id) if user_id else "anonymous",
                target_details=pattern_data,
                result="success",
                severity_level="info"
            )
            
            self.db.add(audit_entry)
            self.db.commit()
            
            # Analyze if pattern requires intervention
            requires_intervention = self._analyze_pattern_severity(
                pattern_type, frequency, severity_trend
            )
            
            return {
                "success": True,
                "pattern_id": audit_entry.id,
                "requires_intervention": requires_intervention,
                "message": "行為模式已記錄 Behavior pattern recorded",
                "recommendations": self._get_pattern_recommendations(pattern_type, frequency)
            }
            
        except Exception as e:
            logger.error(f"Error tracking pattern: {e}")
            self.db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    # =========================================================================
    # SOCIAL WORKER TOOLS HANDLERS (Simplified - can be expanded)
    # =========================================================================
    
    def handle_analyze_child_progress(
        self,
        child_id: str,
        time_range: str,
        metrics: Optional[List[str]] = None,
        include_visualization: bool = False
    ) -> Dict[str, Any]:
        """
        分析兒童進展
        Analyze child's progress
        """
        try:
            # Query data from the specified time range
            # This is a simplified version - would need actual implementation
            
            logger.info(f"Analyzing progress for child {child_id} over {time_range}")
            
            return {
                "success": True,
                "child_id": child_id,
                "time_range": time_range,
                "metrics_analyzed": metrics or ["emotion", "behavior"],
                "summary": "分析報告已生成 Analysis report generated",
                "message": "這是一個示例實現 This is a placeholder implementation"
            }
            
        except Exception as e:
            logger.error(f"Error analyzing progress: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _get_recommended_action(self, concern_type: str, severity: int) -> str:
        """獲取建議採取的行動 Get recommended action based on concern"""
        if severity >= 4:
            return "立即聯繫社工或監護人 Contact social worker or guardian immediately"
        elif severity >= 3:
            return "安排後續輔導 Schedule follow-up counseling"
        else:
            return "持續觀察和支持 Continue monitoring and support"
    
    def _trigger_urgent_alert(self, concern_id: int, concern_type: str, severity: int, summary: str):
        """觸發緊急通知 Trigger urgent alert"""
        logger.warning(
            f"URGENT ALERT: concern_id={concern_id}, type={concern_type}, severity={severity}",
            extra={
                "concern_id": concern_id,
                "summary": summary
            }
        )
        # TODO: Implement actual notification system
    
    def _analyze_emotion_pattern(self, user_id: Optional[int], emotion: str) -> Dict[str, Any]:
        """分析情緒模式 Analyze emotion patterns"""
        # Simplified - would query historical data
        return {
            "pattern_detected": False,
            "trend": "stable"
        }
    
    def _get_emotion_support_suggestions(self, emotion: str, intensity: int) -> List[str]:
        """獲取情緒支持建議 Get emotion support suggestions"""
        suggestions_map = {
            "sad": ["深呼吸練習 Deep breathing", "與朋友聊天 Talk to friends", "做喜歡的事 Do something you enjoy"],
            "angry": ["數到10 Count to 10", "運動 Exercise", "聽音樂 Listen to music"],
            "anxious": ["放鬆練習 Relaxation exercises", "寫下擔心 Write down worries", "尋求支持 Seek support"],
            "scared": ["找安全的人 Find a safe person", "深呼吸 Deep breathing", "提醒自己安全 Remind yourself you're safe"]
        }
        return suggestions_map.get(emotion, ["尋求支持 Seek support"])
    
    def _get_activity_instructions(self, activity_type: str) -> List[str]:
        """獲取活動指導步驟 Get activity instructions"""
        instructions = {
            "breathing": [
                "找一個舒服的地方坐下 Find a comfortable place to sit",
                "閉上眼睛 Close your eyes",
                "慢慢吸氣數到4 Slowly breathe in for 4 counts",
                "屏住呼吸數到4 Hold for 4 counts",
                "慢慢呼氣數到4 Slowly breathe out for 4 counts"
            ],
            "drawing": [
                "拿出紙和筆/顏色筆 Get paper and pencils/markers",
                "想想你現在的感受 Think about how you feel",
                "用顏色和形狀表達出來 Express it with colors and shapes",
                "不用擔心畫得好不好 Don't worry about making it perfect"
            ]
        }
        return instructions.get(activity_type, ["按照指示進行 Follow the instructions"])
    
    def _get_activity_benefits(self, activity_type: str, emotion: str) -> str:
        """獲取活動好處 Get activity benefits"""
        return f"這個活動可以幫助你處理{emotion}的感覺 This activity can help you deal with {emotion} feelings"
    
    def _estimate_response_time(self, priority: str) -> str:
        """估計回應時間 Estimate response time"""
        times = {
            "urgent": "15分鐘內 Within 15 minutes",
            "high": "1小時內 Within 1 hour",
            "medium": "4小時內 Within 4 hours",
            "low": "24小時內 Within 24 hours"
        }
        return times.get(priority, "24小時內 Within 24 hours")
    
    def _analyze_pattern_severity(self, pattern_type: str, frequency: str, trend: str) -> bool:
        """分析模式嚴重程度 Analyze pattern severity"""
        severe_patterns = ["self_harm", "aggression"]
        high_frequencies = ["daily", "constant"]
        
        return (
            pattern_type in severe_patterns or
            frequency in high_frequencies or
            trend == "worsening"
        )
    
    def _get_pattern_recommendations(self, pattern_type: str, frequency: str) -> List[str]:
        """獲取模式建議 Get pattern recommendations"""
        if frequency in ["daily", "constant"]:
            return [
                "考慮尋求專業評估 Consider professional assessment",
                "記錄詳細觸發因素 Track detailed triggers",
                "增加支持頻率 Increase support frequency"
            ]
        return [
            "持續監測 Continue monitoring",
            "提供支持策略 Provide coping strategies"
        ]
    
    def _send_email_notification(
        self,
        alert_type: str,
        severity: str,
        details: Dict[str, Any]
    ):
        """
        Send email notification to social workers
        
        This runs in a separate thread to avoid blocking the main execution
        """
        try:
            notification_service = get_notification_service()
            
            # Run async email sending in event loop
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                # If loop is already running, schedule task
                asyncio.create_task(
                    notification_service.send_critical_alert(
                        alert_type=alert_type,
                        severity=severity,
                        details=details
                    )
                )
            else:
                # Run in new loop
                loop.run_until_complete(
                    notification_service.send_critical_alert(
                        alert_type=alert_type,
                        severity=severity,
                        details=details
                    )
                )
            
            logger.info(f"Email notification sent for {alert_type}")
            
        except Exception as e:
            # Don't fail the main operation if email fails
            logger.error(f"Failed to send email notification: {e}")


# =============================================================================
# MAIN HANDLER FUNCTION
# =============================================================================

async def handle_tool_call(
    tool_name: str,
    tool_arguments: Dict[str, Any],
    user_id: Optional[int] = None,
    conversation_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    處理工具調用的主要函數
    Main function to handle tool calls
    
    Args:
        tool_name: Name of the tool to call
        tool_arguments: Arguments for the tool
        user_id: Optional user ID
        conversation_id: Optional conversation ID
    
    Returns:
        Result dictionary from the tool execution
    """
    with ToolHandler() as handler:
        # Add user_id and conversation_id to arguments if provided
        if user_id:
            tool_arguments["user_id"] = user_id
        if conversation_id:
            tool_arguments["conversation_id"] = conversation_id
        
        # Map tool names to handler methods
        handler_map = {
            # Child chat tools
            "record_concern": handler.handle_record_concern,
            "log_emotion": handler.handle_log_emotion,
            "suggest_coping_activity": handler.handle_suggest_coping_activity,
            "alert_social_worker": handler.handle_alert_social_worker,
            "provide_resource": handler.handle_provide_resource,
            "track_behavior_pattern": handler.handle_track_behavior_pattern,
            
            # Questionnaire tools
            "administer_questionnaire": lambda **kwargs: QUESTIONNAIRE_HANDLERS["administer_questionnaire"](**kwargs, db=handler.db),
            "get_next_question": lambda **kwargs: QUESTIONNAIRE_HANDLERS["get_next_question"](**kwargs, db=handler.db),
            
            # Social worker tools
            "analyze_child_progress": handler.handle_analyze_child_progress,
            # Add more handlers as needed
        }
        
        handler_func = handler_map.get(tool_name)
        
        if handler_func is None:
            logger.error(f"Unknown tool: {tool_name}")
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
                "message": f"工具不存在 Tool not found: {tool_name}"
            }
        
        try:
            result = handler_func(**tool_arguments)
            return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"執行工具時發生錯誤 Error executing tool: {tool_name}"
            }

