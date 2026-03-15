"""
Healthcare AI V2 Admin Metrics Service
Business logic for metrics collection and processing
"""

import asyncio
import psutil
import time
from typing import Dict, Any
from datetime import datetime, timedelta
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class MetricsService:
    """Service for collecting and processing admin metrics"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.cache = {}
        self.cache_ttl = 30  # 30 seconds cache
        self.last_update = {}
    
    async def get_admin_stats(self) -> Dict[str, Any]:
        """Get comprehensive admin statistics"""
        try:
            # Collect all metrics concurrently
            user_stats, org_stats, system_stats, pipeline_stats, security_stats = await asyncio.gather(
                self._get_user_stats(),
                self._get_organization_stats(),
                self._get_system_stats(),
                self._get_pipeline_stats(),
                self._get_security_stats(),
                return_exceptions=True
            )
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "users": user_stats if not isinstance(user_stats, Exception) else {"error": str(user_stats)},
                "organizations": org_stats if not isinstance(org_stats, Exception) else {"error": str(org_stats)},
                "system": system_stats if not isinstance(system_stats, Exception) else {"error": str(system_stats)},
                "pipeline": pipeline_stats if not isinstance(pipeline_stats, Exception) else {"error": str(pipeline_stats)},
                "security": security_stats if not isinstance(security_stats, Exception) else {"error": str(security_stats)}
            }
        except Exception as e:
            logger.error(f"Error collecting admin stats: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "users": {"total": 0, "active": 0, "admin": 0, "new_today": 0},
                "organizations": {"total": 0, "active": 0},
                "system": {"status": "error", "cpu_percent": 0, "memory_percent": 0},
                "pipeline": {"status": "error", "sources_online": 0, "total_sources": 0},
                "security": {"status": "error", "failed_logins_hour": 0, "alerts_today": 0}
            }
    
    async def _get_user_stats(self) -> Dict[str, Any]:
        """Get user statistics from database"""
        try:
            # Active users (logged in within last 24 hours)
            active_users_query = text("""
                SELECT COUNT(*) as count 
                FROM users 
                WHERE last_login > NOW() - INTERVAL '24 hours'
                AND is_active = true
            """)
            result = await self.db.execute(active_users_query)
            active_users = result.scalar() or 0
            
            # Total users
            total_users_query = text("SELECT COUNT(*) FROM users WHERE is_active = true")
            result = await self.db.execute(total_users_query)
            total_users = result.scalar() or 0
            
            # Admin users
            admin_users_query = text("""
                SELECT COUNT(*) FROM users 
                WHERE is_active = true 
                AND (is_admin = true OR role IN ('admin', 'super_admin'))
            """)
            result = await self.db.execute(admin_users_query)
            admin_users = result.scalar() or 0
            
            # New users today
            new_today_query = text("""
                SELECT COUNT(*) 
                FROM users 
                WHERE DATE(created_at) = CURRENT_DATE
            """)
            result = await self.db.execute(new_today_query)
            new_today = result.scalar() or 0
            
            return {
                "total": total_users,
                "active": active_users,
                "admin": admin_users,
                "new_today": new_today
            }
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {"total": 0, "active": 0, "admin": 0, "new_today": 0}
    
    async def _get_organization_stats(self) -> Dict[str, Any]:
        """Get organization statistics from database"""
        try:
            # Check if organizations table exists
            table_check = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'organizations'
                )
            """)
            result = await self.db.execute(table_check)
            table_exists = result.scalar()
            
            if not table_exists:
                logger.warning("Organizations table does not exist yet")
                return {"total": 0, "active": 0}
            
            # Total organizations
            total_orgs_query = text("SELECT COUNT(*) FROM organizations WHERE is_active = true")
            result = await self.db.execute(total_orgs_query)
            total_orgs = result.scalar() or 0
            
            # Active organizations (with at least one user)
            active_orgs_query = text("""
                SELECT COUNT(DISTINCT organization_id) 
                FROM users 
                WHERE organization_id IS NOT NULL 
                AND is_active = true
            """)
            result = await self.db.execute(active_orgs_query)
            active_orgs = result.scalar() or 0
            
            return {
                "total": total_orgs,
                "active": active_orgs
            }
        except Exception as e:
            logger.error(f"Error getting organization stats: {e}")
            return {"total": 0, "active": 0}
    
    async def _get_system_stats(self) -> Dict[str, Any]:
        """Get system performance metrics"""
        try:
            # Collect psutil metrics in a worker thread to avoid blocking the event loop
            def collect_stats():
                cpu_percent = psutil.cpu_percent(interval=0.5)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                boot_time = psutil.boot_time()
                return cpu_percent, memory, disk, boot_time
            
            cpu_percent, memory, disk, boot_time = await asyncio.to_thread(collect_stats)
            
            # Get database health
            try:
                start_time = time.time()
                await self.db.execute(text("SELECT 1"))
                db_response_time = (time.time() - start_time) * 1000
                db_status = "healthy"
            except Exception as e:
                db_response_time = 0
                db_status = f"error: {str(e)}"
            
            # Determine overall system status
            status = "healthy"
            if cpu_percent > 80 or memory.percent > 80:
                status = "warning"
            if cpu_percent > 95 or memory.percent > 95:
                status = "error"
            
            return {
                "status": status,
                "uptime_hours": (time.time() - boot_time) / 3600,
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "database": {
                    "status": db_status,
                    "response_time_ms": db_response_time
                }
            }
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {
                "status": "error",
                "uptime_hours": 0,
                "cpu_percent": 0,
                "memory_percent": 0,
                "disk_percent": 0,
                "database": {"status": "error", "response_time_ms": 0}
            }
    
    async def _get_pipeline_stats(self) -> Dict[str, Any]:
        """Get data pipeline metrics"""
        try:
            # This would connect to your Redis cache or monitoring system
            # For now, return simulated data
            return {
                "status": "healthy",
                "last_update": (datetime.utcnow() - timedelta(minutes=15)).isoformat(),
                "sources_online": 8,
                "total_sources": 11,
                "data_freshness_minutes": 15,
                "error_rate": 0.02
            }
        except Exception as e:
            logger.error(f"Error getting pipeline stats: {e}")
            return {
                "status": "error",
                "last_update": datetime.utcnow().isoformat(),
                "sources_online": 0,
                "total_sources": 0,
                "data_freshness_minutes": 0,
                "error_rate": 1.0
            }
    
    async def _get_security_stats(self) -> Dict[str, Any]:
        """Get security monitoring metrics"""
        try:
            # Failed logins in last hour
            failed_logins_query = text("""
                SELECT COUNT(*) 
                FROM audit_logs 
                WHERE event_type = 'failed_login' 
                AND created_at > NOW() - INTERVAL '1 hour'
            """)
            result = await self.db.execute(failed_logins_query)
            failed_logins = result.scalar() or 0
            
            # Security alerts today
            alerts_query = text("""
                SELECT COUNT(*) 
                FROM audit_logs 
                WHERE event_category = 'security' 
                AND severity_level IN ('high', 'critical')
                AND DATE(created_at) = CURRENT_DATE
            """)
            result = await self.db.execute(alerts_query)
            alerts_today = result.scalar() or 0
            
            # Determine security status
            status = "secure"
            if failed_logins > 10 or alerts_today > 5:
                status = "warning"
            if failed_logins > 50 or alerts_today > 20:
                status = "critical"
            
            return {
                "status": status,
                "failed_logins_hour": failed_logins,
                "alerts_today": alerts_today
            }
        except Exception as e:
            logger.error(f"Error getting security stats: {e}")
            return {
                "status": "unknown",
                "failed_logins_hour": 0,
                "alerts_today": 0
            }
    
    async def get_health_check(self) -> Dict[str, Any]:
        """Get system health check"""
        try:
            # Check database connectivity
            start_time = time.time()
            await self.db.execute(text("SELECT 1"))
            db_response_time = (time.time() - start_time) * 1000
            
            # Check system resources
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('/').percent
            
            # Determine overall health
            health_score = 100
            if db_response_time > 1000:  # > 1 second
                health_score -= 20
            if cpu_percent > 80:
                health_score -= 15
            if memory_percent > 80:
                health_score -= 15
            if disk_percent > 90:
                health_score -= 10
            
            status = "healthy"
            if health_score < 70:
                status = "warning"
            if health_score < 50:
                status = "critical"
            
            return {
                "status": status,
                "health_score": health_score,
                "timestamp": datetime.utcnow().isoformat(),
                "components": {
                    "database": {
                        "status": "healthy" if db_response_time < 1000 else "warning",
                        "response_time_ms": db_response_time
                    },
                    "cpu": {
                        "status": "healthy" if cpu_percent < 80 else "warning",
                        "usage_percent": cpu_percent
                    },
                    "memory": {
                        "status": "healthy" if memory_percent < 80 else "warning",
                        "usage_percent": memory_percent
                    },
                    "disk": {
                        "status": "healthy" if disk_percent < 90 else "warning",
                        "usage_percent": disk_percent
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            return {
                "status": "error",
                "health_score": 0,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def get_performance_metrics(self, time_range: str = "24h") -> Dict[str, Any]:
        """Get performance metrics for the specified time range"""
        try:
            # This would typically query a time-series database
            # For now, return simulated data
            return {
                "time_range": time_range,
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": {
                    "cpu": {
                        "current": psutil.cpu_percent(interval=0.1),
                        "average": 42,
                        "peak": 78,
                        "trend": "stable"
                    },
                    "memory": {
                        "current": psutil.virtual_memory().percent,
                        "average": 65,
                        "peak": 85,
                        "trend": "increasing"
                    },
                    "disk_io": {
                        "current": 23,
                        "average": 25,
                        "peak": 45,
                        "trend": "stable"
                    },
                    "network": {
                        "current": 12,
                        "average": 15,
                        "peak": 35,
                        "trend": "decreasing"
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {
                "time_range": time_range,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
