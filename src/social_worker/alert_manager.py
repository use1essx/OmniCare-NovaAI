"""
Alert Manager for Social Worker Hub

Handles alert creation, debouncing, and resolution:
- Smart debouncing to prevent alert spam
- Severity-based prioritization
- Real-time notification support
- Alert assignment and resolution tracking
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Alert
from ..database.connection import get_async_db

logger = logging.getLogger(__name__)


class AlertDebouncer:
    """
    Prevents alert spam by tracking recent alerts.
    
    Rules:
    - Same child + same alert type: 15 minute window
    - Same session: 5 minute window for similar alerts
    - Critical alerts bypass debouncing
    """
    
    # Debounce windows in seconds
    SAME_TYPE_WINDOW = 900  # 15 minutes
    SAME_SESSION_WINDOW = 300  # 5 minutes
    
    # Severity threshold that bypasses debouncing
    CRITICAL_SEVERITY = 5
    
    async def should_create_alert(
        self,
        session: AsyncSession,
        child_id: Optional[int],
        session_id: str,
        alert_type: str,
        severity: int
    ) -> tuple[bool, Optional[int]]:
        """
        Check if an alert should be created or debounced.
        
        Args:
            session: Database session
            child_id: Child ID
            session_id: Chat session ID
            alert_type: Type of alert
            severity: Alert severity (1-5)
            
        Returns:
            Tuple of (should_create, parent_alert_id)
        """
        # Critical alerts always go through
        if severity >= self.CRITICAL_SEVERITY:
            return True, None
        
        # Build debounce key
        debounce_key = f"{child_id or 'unknown'}:{alert_type}"
        
        # Check for recent similar alert
        cutoff_time = datetime.utcnow() - timedelta(seconds=self.SAME_TYPE_WINDOW)
        
        result = await session.execute(
            select(Alert).where(
                and_(
                    Alert.debounce_key == debounce_key,
                    Alert.created_at >= cutoff_time,
                    not Alert.resolved
                )
            ).order_by(Alert.created_at.desc()).limit(1)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Group with existing alert
            logger.debug(f"Debouncing alert: grouping with {existing.id}")
            return False, existing.id
        
        # Check same session window
        session_cutoff = datetime.utcnow() - timedelta(seconds=self.SAME_SESSION_WINDOW)
        
        result = await session.execute(
            select(Alert).where(
                and_(
                    Alert.session_id == session_id,
                    Alert.alert_type == alert_type,
                    Alert.created_at >= session_cutoff
                )
            ).limit(1)
        )
        session_alert = result.scalar_one_or_none()
        
        if session_alert:
            logger.debug("Debouncing alert: same session window")
            return False, session_alert.id
        
        return True, None


class AlertManager:
    """
    Manages alerts for social workers.
    
    Features:
    - Alert creation with debouncing
    - Severity-based prioritization
    - Assignment and resolution tracking
    - Statistics and analytics
    """
    
    def __init__(self):
        """Initialize alert manager"""
        self.debouncer = AlertDebouncer()
    
    async def create_alert(
        self,
        session_id: str,
        alert_type: str,
        message: str,
        severity: int,
        child_id: Optional[int] = None,
        case_id: Optional[int] = None,
        title: Optional[str] = None,
        context: Optional[Dict] = None,
        detected_by: Optional[str] = None,
        skill_involved: Optional[str] = None,
        trigger_reason: Optional[str] = None,
        recommended_action: Optional[str] = None,
        force_create: bool = False
    ) -> Optional[Alert]:
        """
        Create a new alert with debouncing.
        
        Args:
            session_id: Chat session ID
            alert_type: Type of alert
            message: Alert message
            severity: Severity level (1-5)
            child_id: Optional child ID
            case_id: Optional case ID
            title: Alert title
            context: Additional context data
            detected_by: What detected this alert
            skill_involved: Which skill was active
            trigger_reason: Why alert was triggered
            recommended_action: Suggested action
            force_create: Bypass debouncing
            
        Returns:
            Created Alert or None if debounced
        """
        async for db_session in get_async_db():
            try:
                # Check debouncing
                if not force_create:
                    should_create, parent_id = await self.debouncer.should_create_alert(
                        db_session, child_id, session_id, alert_type, severity
                    )
                    
                    if not should_create:
                        logger.info(
                            f"Alert debounced: {alert_type} for child {child_id}"
                        )
                        return None
                else:
                    parent_id = None
                
                # Determine priority from severity
                priority = self._severity_to_priority(severity)
                
                # Determine urgency
                action_urgency = self._get_action_urgency(severity, alert_type)
                
                # Build debounce key
                debounce_key = f"{child_id or 'unknown'}:{alert_type}"
                
                # Auto-generate title if not provided
                if not title:
                    title = self._generate_title(alert_type, severity)
                
                # Create alert
                alert = Alert(
                    session_id=session_id,
                    case_id=case_id,
                    child_id=child_id,
                    alert_type=alert_type,
                    severity=severity,
                    priority=priority,
                    title=title,
                    message=message,
                    context=context or {},
                    detected_by=detected_by,
                    skill_involved=skill_involved,
                    trigger_reason=trigger_reason,
                    trigger_data={},
                    recommended_action=recommended_action,
                    action_urgency=action_urgency,
                    debounce_key=debounce_key,
                    parent_alert_id=parent_id
                )
                
                db_session.add(alert)
                await db_session.commit()
                await db_session.refresh(alert)
                
                logger.warning(
                    f"Alert created: {alert_type} (severity {severity}) "
                    f"for child {child_id}"
                )
                
                return alert
                
            except Exception as e:
                await db_session.rollback()
                logger.error(f"Error creating alert: {e}")
                raise
    
    async def get_alert(self, alert_id: int) -> Optional[Alert]:
        """Get an alert by ID"""
        async for session in get_async_db():
            result = await session.execute(
                select(Alert).where(Alert.id == alert_id)
            )
            return result.scalar_one_or_none()
    
    async def get_unresolved_alerts(
        self,
        social_worker_id: Optional[int] = None,
        child_id: Optional[int] = None,
        min_severity: int = 1,
        limit: int = 50,
        offset: int = 0
    ) -> List[Alert]:
        """Get unresolved alerts with filtering"""
        async for session in get_async_db():
            query = select(Alert).where(
                and_(
                    not Alert.resolved,
                    Alert.severity >= min_severity
                )
            )
            
            if social_worker_id:
                query = query.where(Alert.assigned_to == social_worker_id)
            
            if child_id:
                query = query.where(Alert.child_id == child_id)
            
            query = query.order_by(
                Alert.severity.desc(),
                Alert.created_at.desc()
            ).offset(offset).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_recent_alerts(
        self,
        hours: int = 24,
        min_severity: int = 1,
        limit: int = 100
    ) -> List[Alert]:
        """Get recent alerts within time window"""
        async for session in get_async_db():
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
            result = await session.execute(
                select(Alert).where(
                    and_(
                        Alert.created_at >= cutoff,
                        Alert.severity >= min_severity
                    )
                ).order_by(Alert.created_at.desc()).limit(limit)
            )
            return list(result.scalars().all())
    
    async def resolve_alert(
        self,
        alert_id: int,
        resolved_by: int,
        resolution_notes: Optional[str] = None,
        resolution_action: str = "acknowledged"
    ) -> Optional[Alert]:
        """Resolve an alert"""
        async for session in get_async_db():
            try:
                result = await session.execute(
                    select(Alert).where(Alert.id == alert_id)
                )
                alert = result.scalar_one_or_none()
                
                if not alert:
                    return None
                
                alert.resolved = True
                alert.resolved_by = resolved_by
                alert.resolved_at = datetime.utcnow()
                alert.resolution_notes = resolution_notes
                alert.resolution_action = resolution_action
                
                await session.commit()
                await session.refresh(alert)
                
                logger.info(f"Alert {alert_id} resolved by user {resolved_by}")
                return alert
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error resolving alert: {e}")
                raise
    
    async def assign_alert(
        self,
        alert_id: int,
        assigned_to: int
    ) -> Optional[Alert]:
        """Assign an alert to a social worker"""
        async for session in get_async_db():
            try:
                result = await session.execute(
                    select(Alert).where(Alert.id == alert_id)
                )
                alert = result.scalar_one_or_none()
                
                if not alert:
                    return None
                
                alert.assigned_to = assigned_to
                alert.assigned_at = datetime.utcnow()
                
                await session.commit()
                await session.refresh(alert)
                
                return alert
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error assigning alert: {e}")
                raise
    
    async def get_alert_stats(
        self,
        social_worker_id: Optional[int] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get alert statistics"""
        async for session in get_async_db():
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            base_filter = Alert.created_at >= cutoff
            if social_worker_id:
                base_filter = and_(
                    base_filter,
                    Alert.assigned_to == social_worker_id
                )
            
            # Total alerts
            result = await session.execute(
                select(func.count(Alert.id)).where(base_filter)
            )
            total = result.scalar() or 0
            
            # Unresolved
            result = await session.execute(
                select(func.count(Alert.id)).where(
                    and_(base_filter, not Alert.resolved)
                )
            )
            unresolved = result.scalar() or 0
            
            # By severity
            severity_counts = {}
            for sev in range(1, 6):
                result = await session.execute(
                    select(func.count(Alert.id)).where(
                        and_(base_filter, Alert.severity == sev)
                    )
                )
                severity_counts[sev] = result.scalar() or 0
            
            # By type
            result = await session.execute(
                select(Alert.alert_type, func.count(Alert.id)).where(
                    base_filter
                ).group_by(Alert.alert_type)
            )
            type_counts = {row[0]: row[1] for row in result.fetchall()}
            
            return {
                'total': total,
                'unresolved': unresolved,
                'resolved': total - unresolved,
                'by_severity': severity_counts,
                'by_type': type_counts,
                'period_days': days
            }
    
    def _severity_to_priority(self, severity: int) -> str:
        """Convert severity to priority"""
        if severity >= 5:
            return 'urgent'
        elif severity >= 4:
            return 'high'
        elif severity >= 3:
            return 'medium'
        else:
            return 'low'
    
    def _get_action_urgency(self, severity: int, alert_type: str) -> str:
        """Determine action urgency"""
        # Emergency types always immediate
        if alert_type in ['emergency', 'safety_flag'] or severity >= 5:
            return 'immediate'
        elif severity >= 4:
            return 'within_hour'
        elif severity >= 3:
            return 'within_day'
        else:
            return 'when_possible'
    
    def _generate_title(self, alert_type: str, severity: int) -> str:
        """Generate alert title from type and severity"""
        type_labels = {
            'emotion_concern': 'Emotion Concern',
            'behavior_concern': 'Behavior Concern',
            'risk_detected': 'Risk Detected',
            'emergency': 'EMERGENCY',
            'safety_flag': 'Safety Flag',
            'session_flag': 'Session Flag',
            'questionnaire_flag': 'Questionnaire Flag',
            'pattern_detected': 'Pattern Detected',
            'intervention_needed': 'Intervention Needed',
            'follow_up_required': 'Follow-up Required',
            'milestone_reached': 'Milestone Reached'
        }
        
        base_title = type_labels.get(alert_type, alert_type.replace('_', ' ').title())
        
        if severity >= 5:
            return f"🚨 CRITICAL: {base_title}"
        elif severity >= 4:
            return f"⚠️ High Priority: {base_title}"
        else:
            return base_title


# Singleton
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create alert manager singleton"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager

