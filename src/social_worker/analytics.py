"""
Analytics Service for Social Worker Hub

Provides dashboard metrics and analytics:
- Case statistics
- Alert trends
- Risk distribution
- Workload analysis
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, select

from .models import CaseFile, Alert, Intervention
from ..database.connection import get_async_db

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Provides analytics and metrics for the Social Worker Hub.
    
    Features:
    - Dashboard metrics
    - Risk distribution
    - Alert trends
    - Workload analysis
    - Intervention effectiveness
    """
    
    async def get_dashboard_metrics(
        self,
        social_worker_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get dashboard overview metrics.
        
        Args:
            social_worker_id: Filter by social worker
            
        Returns:
            Dict with various metrics
        """
        async for session in get_async_db():
            metrics = {}
            
            # Base filter
            sw_filter = CaseFile.social_worker_id == social_worker_id if social_worker_id else True
            
            # Active cases
            result = await session.execute(
                select(func.count(CaseFile.id)).where(
                    and_(
                        CaseFile.status.in_(['open', 'monitoring', 'escalated']),
                        sw_filter
                    )
                )
            )
            metrics['active_cases'] = result.scalar() or 0
            
            # High risk cases
            result = await session.execute(
                select(func.count(CaseFile.id)).where(
                    and_(
                        CaseFile.risk_level >= 60,
                        CaseFile.status.in_(['open', 'monitoring', 'escalated']),
                        sw_filter
                    )
                )
            )
            metrics['high_risk_cases'] = result.scalar() or 0
            
            # Unresolved alerts (last 24h)
            alert_sw_filter = Alert.assigned_to == social_worker_id if social_worker_id else True
            cutoff = datetime.utcnow() - timedelta(hours=24)
            
            result = await session.execute(
                select(func.count(Alert.id)).where(
                    and_(
                        not Alert.resolved,
                        Alert.created_at >= cutoff,
                        alert_sw_filter
                    )
                )
            )
            metrics['unresolved_alerts'] = result.scalar() or 0
            
            # New alerts today
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            result = await session.execute(
                select(func.count(Alert.id)).where(
                    and_(
                        Alert.created_at >= today_start,
                        alert_sw_filter
                    )
                )
            )
            metrics['new_alerts_today'] = result.scalar() or 0
            
            # Cases by status
            status_counts = {}
            for status in ['open', 'monitoring', 'review', 'escalated', 'closed']:
                result = await session.execute(
                    select(func.count(CaseFile.id)).where(
                        and_(
                            CaseFile.status == status,
                            sw_filter
                        )
                    )
                )
                status_counts[status] = result.scalar() or 0
            metrics['cases_by_status'] = status_counts
            
            # Cases by priority
            priority_counts = {}
            for priority in ['low', 'medium', 'high', 'urgent', 'critical']:
                result = await session.execute(
                    select(func.count(CaseFile.id)).where(
                        and_(
                            CaseFile.priority == priority,
                            CaseFile.status.in_(['open', 'monitoring', 'escalated']),
                            sw_filter
                        )
                    )
                )
                priority_counts[priority] = result.scalar() or 0
            metrics['cases_by_priority'] = priority_counts
            
            return metrics
    
    async def get_risk_distribution(
        self,
        social_worker_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get risk level distribution for active cases"""
        async for session in get_async_db():
            sw_filter = CaseFile.social_worker_id == social_worker_id if social_worker_id else True
            
            distribution = {
                'minimal': 0,  # 0-19
                'low': 0,      # 20-39
                'moderate': 0, # 40-59
                'high': 0,     # 60-79
                'critical': 0  # 80-100
            }
            
            # Get all active cases with risk levels
            result = await session.execute(
                select(CaseFile.risk_level).where(
                    and_(
                        CaseFile.risk_level.isnot(None),
                        CaseFile.status.in_(['open', 'monitoring', 'escalated']),
                        sw_filter
                    )
                )
            )
            
            for (risk_level,) in result.fetchall():
                if risk_level >= 80:
                    distribution['critical'] += 1
                elif risk_level >= 60:
                    distribution['high'] += 1
                elif risk_level >= 40:
                    distribution['moderate'] += 1
                elif risk_level >= 20:
                    distribution['low'] += 1
                else:
                    distribution['minimal'] += 1
            
            return distribution
    
    async def get_alert_trends(
        self,
        days: int = 7,
        social_worker_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get alert trends over time"""
        async for session in get_async_db():
            sw_filter = Alert.assigned_to == social_worker_id if social_worker_id else True
            
            trends = {
                'daily_counts': [],
                'by_type': {},
                'by_severity': {},
                'resolution_rate': 0
            }
            
            # Daily counts for last N days
            for i in range(days - 1, -1, -1):
                day_start = (datetime.utcnow() - timedelta(days=i)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                day_end = day_start + timedelta(days=1)
                
                result = await session.execute(
                    select(func.count(Alert.id)).where(
                        and_(
                            Alert.created_at >= day_start,
                            Alert.created_at < day_end,
                            sw_filter
                        )
                    )
                )
                count = result.scalar() or 0
                
                trends['daily_counts'].append({
                    'date': day_start.strftime('%Y-%m-%d'),
                    'count': count
                })
            
            # By type (last N days)
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            result = await session.execute(
                select(Alert.alert_type, func.count(Alert.id)).where(
                    and_(
                        Alert.created_at >= cutoff,
                        sw_filter
                    )
                ).group_by(Alert.alert_type)
            )
            
            for alert_type, count in result.fetchall():
                trends['by_type'][alert_type] = count
            
            # By severity
            result = await session.execute(
                select(Alert.severity, func.count(Alert.id)).where(
                    and_(
                        Alert.created_at >= cutoff,
                        sw_filter
                    )
                ).group_by(Alert.severity)
            )
            
            for severity, count in result.fetchall():
                trends['by_severity'][severity] = count
            
            # Resolution rate
            result = await session.execute(
                select(func.count(Alert.id)).where(
                    and_(
                        Alert.created_at >= cutoff,
                        sw_filter
                    )
                )
            )
            total = result.scalar() or 0
            
            result = await session.execute(
                select(func.count(Alert.id)).where(
                    and_(
                        Alert.created_at >= cutoff,
                        Alert.resolved,
                        sw_filter
                    )
                )
            )
            resolved = result.scalar() or 0
            
            trends['resolution_rate'] = (resolved / total * 100) if total > 0 else 0
            trends['total_alerts'] = total
            trends['resolved_alerts'] = resolved
            
            return trends
    
    async def get_intervention_stats(
        self,
        case_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get intervention statistics"""
        async for session in get_async_db():
            case_filter = Intervention.case_id == case_id if case_id else True
            
            stats = {
                'by_type': {},
                'by_status': {},
                'total': 0,
                'completion_rate': 0
            }
            
            # By type
            result = await session.execute(
                select(Intervention.intervention_type, func.count(Intervention.id)).where(
                    case_filter
                ).group_by(Intervention.intervention_type)
            )
            
            for int_type, count in result.fetchall():
                stats['by_type'][int_type] = count
            
            # By status
            for status in ['planned', 'active', 'paused', 'completed', 'discontinued']:
                result = await session.execute(
                    select(func.count(Intervention.id)).where(
                        and_(
                            Intervention.status == status,
                            case_filter
                        )
                    )
                )
                stats['by_status'][status] = result.scalar() or 0
            
            # Total and completion rate
            result = await session.execute(
                select(func.count(Intervention.id)).where(case_filter)
            )
            stats['total'] = result.scalar() or 0
            
            if stats['total'] > 0:
                completed = stats['by_status'].get('completed', 0)
                stats['completion_rate'] = (completed / stats['total']) * 100
            
            return stats
    
    async def get_case_trends(
        self,
        days: int = 7,
        social_worker_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get case trends over time"""
        async for session in get_async_db():
            sw_filter = CaseFile.social_worker_id == social_worker_id if social_worker_id else True
            
            trends = {
                'daily_new_cases': [],
                'daily_closed_cases': [],
                'by_status': {},
                'by_priority': {}
            }
            
            # Daily counts for last N days
            for i in range(days - 1, -1, -1):
                day_start = (datetime.utcnow() - timedelta(days=i)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                day_end = day_start + timedelta(days=1)
                
                # New cases opened on this day
                result = await session.execute(
                    select(func.count(CaseFile.id)).where(
                        and_(
                            CaseFile.created_at >= day_start,
                            CaseFile.created_at < day_end,
                            sw_filter
                        )
                    )
                )
                new_count = result.scalar() or 0
                
                # Cases closed on this day
                result = await session.execute(
                    select(func.count(CaseFile.id)).where(
                        and_(
                            CaseFile.closed_at >= day_start,
                            CaseFile.closed_at < day_end,
                            sw_filter
                        )
                    )
                )
                closed_count = result.scalar() or 0
                
                trends['daily_new_cases'].append({
                    'date': day_start.strftime('%Y-%m-%d'),
                    'count': new_count
                })
                trends['daily_closed_cases'].append({
                    'date': day_start.strftime('%Y-%m-%d'),
                    'count': closed_count
                })
            
            # By status
            datetime.utcnow() - timedelta(days=days)
            for status in ['open', 'monitoring', 'escalated', 'closed', 'pending_assignment']:
                result = await session.execute(
                    select(func.count(CaseFile.id)).where(
                        and_(
                            CaseFile.status == status,
                            sw_filter
                        )
                    )
                )
                trends['by_status'][status] = result.scalar() or 0
            
            # By priority
            for priority in ['low', 'medium', 'high', 'urgent', 'critical']:
                result = await session.execute(
                    select(func.count(CaseFile.id)).where(
                        and_(
                            CaseFile.priority == priority,
                            CaseFile.status.in_(['open', 'monitoring', 'escalated']),
                            sw_filter
                        )
                    )
                )
                trends['by_priority'][priority] = result.scalar() or 0
            
            return trends
    
    async def get_workload_analysis(
        self,
        social_worker_id: int
    ) -> Dict[str, Any]:
        """Get workload analysis for a social worker"""
        async for session in get_async_db():
            analysis = {
                'active_cases': 0,
                'high_priority_cases': 0,
                'pending_alerts': 0,
                'overdue_reviews': 0,
                'upcoming_reviews': 0,
                'case_load_score': 0
            }
            
            # Active cases
            result = await session.execute(
                select(func.count(CaseFile.id)).where(
                    and_(
                        CaseFile.social_worker_id == social_worker_id,
                        CaseFile.status.in_(['open', 'monitoring', 'escalated'])
                    )
                )
            )
            analysis['active_cases'] = result.scalar() or 0
            
            # High priority
            result = await session.execute(
                select(func.count(CaseFile.id)).where(
                    and_(
                        CaseFile.social_worker_id == social_worker_id,
                        CaseFile.priority.in_(['high', 'urgent', 'critical']),
                        CaseFile.status.in_(['open', 'monitoring', 'escalated'])
                    )
                )
            )
            analysis['high_priority_cases'] = result.scalar() or 0
            
            # Pending alerts
            result = await session.execute(
                select(func.count(Alert.id)).where(
                    and_(
                        Alert.assigned_to == social_worker_id,
                        not Alert.resolved
                    )
                )
            )
            analysis['pending_alerts'] = result.scalar() or 0
            
            # Overdue reviews
            result = await session.execute(
                select(func.count(CaseFile.id)).where(
                    and_(
                        CaseFile.social_worker_id == social_worker_id,
                        CaseFile.next_review < datetime.utcnow(),
                        CaseFile.status.in_(['open', 'monitoring'])
                    )
                )
            )
            analysis['overdue_reviews'] = result.scalar() or 0
            
            # Upcoming reviews (next 7 days)
            week_ahead = datetime.utcnow() + timedelta(days=7)
            
            result = await session.execute(
                select(func.count(CaseFile.id)).where(
                    and_(
                        CaseFile.social_worker_id == social_worker_id,
                        CaseFile.next_review >= datetime.utcnow(),
                        CaseFile.next_review <= week_ahead,
                        CaseFile.status.in_(['open', 'monitoring'])
                    )
                )
            )
            analysis['upcoming_reviews'] = result.scalar() or 0
            
            # Calculate load score (simple weighted formula)
            analysis['case_load_score'] = (
                analysis['active_cases'] * 1 +
                analysis['high_priority_cases'] * 2 +
                analysis['pending_alerts'] * 1.5 +
                analysis['overdue_reviews'] * 3
            )
            
            return analysis
    
    async def get_recent_activity(
        self,
        limit: int = 20,
        social_worker_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get recent activity feed"""
        async for session in get_async_db():
            activities = []
            
            # Recent alerts
            alert_filter = Alert.assigned_to == social_worker_id if social_worker_id else True
            
            result = await session.execute(
                select(Alert).where(alert_filter).order_by(
                    Alert.created_at.desc()
                ).limit(limit // 2)
            )
            
            for alert in result.scalars():
                activities.append({
                    'type': 'alert',
                    'title': alert.title,
                    'severity': alert.severity,
                    'timestamp': alert.created_at.isoformat(),
                    'resolved': alert.resolved
                })
            
            # Recent case updates
            case_filter = CaseFile.social_worker_id == social_worker_id if social_worker_id else True
            
            result = await session.execute(
                select(CaseFile).where(case_filter).order_by(
                    CaseFile.updated_at.desc()
                ).limit(limit // 2)
            )
            
            for case in result.scalars():
                activities.append({
                    'type': 'case_update',
                    'case_number': case.case_number,
                    'status': case.status,
                    'timestamp': case.updated_at.isoformat() if case.updated_at else None
                })
            
            # Sort by timestamp
            activities.sort(
                key=lambda x: x.get('timestamp', ''),
                reverse=True
            )
            
            return activities[:limit]


# Singleton
_analytics_service: Optional[AnalyticsService] = None


def get_analytics_service() -> AnalyticsService:
    """Get or create analytics service singleton"""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service

