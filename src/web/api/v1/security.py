"""
Healthcare AI V2 - Security Monitoring API Endpoints
Real-time security dashboard and monitoring endpoints
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from pydantic import BaseModel, Field

from src.core.logging import get_logger
from src.security.monitoring import security_monitor
from src.security.events import security_event_tracker, AlertLevel, EventCategory
from src.web.auth.dependencies import require_role
from src.web.middleware.rate_limiter import rate_limiter
from src.database.models_comprehensive import User


logger = get_logger(__name__)
router = APIRouter()


class SecurityDashboardResponse(BaseModel):
    """Security dashboard response model"""
    timestamp: datetime
    system_status: str
    summary: Dict[str, Any]
    threat_levels: Dict[str, int]
    recent_events: List[Dict[str, Any]]
    blocked_ips: List[str]
    active_alerts: List[Dict[str, Any]]
    performance_metrics: Dict[str, Any]


class RateLimitStatusResponse(BaseModel):
    """Rate limit status response model"""
    client_id: str
    limits: Dict[str, Any]
    penalties: Dict[str, Any]
    timestamp: datetime


class SecurityEventRequest(BaseModel):
    """Security event creation request"""
    event_type: str = Field(..., description="Type of security event")
    description: str = Field(..., description="Event description")
    level: str = Field(default="info", description="Alert level")
    category: str = Field(default="system_security", description="Event category")
    technical_details: Optional[Dict[str, Any]] = Field(None, description="Technical details")
    affected_resources: Optional[List[str]] = Field(None, description="Affected resources")


class IPBlockRequest(BaseModel):
    """IP blocking request"""
    ip_address: str = Field(..., description="IP address to block")
    duration_minutes: int = Field(default=60, description="Block duration in minutes")
    reason: str = Field(default="Manual block", description="Reason for blocking")


@router.get(
    "/dashboard",
    response_model=SecurityDashboardResponse,
    dependencies=[Depends(require_role("admin"))],
    summary="Get security dashboard",
    description="Get comprehensive security dashboard with real-time metrics"
)
async def get_security_dashboard(
    current_user: User = Depends(require_role("admin"))
) -> SecurityDashboardResponse:
    """Get security dashboard data"""
    try:
        # Get security monitor dashboard
        monitor_data = await security_monitor.get_security_dashboard()
        
        # Get recent security alerts
        recent_alerts = await security_event_tracker.get_recent_alerts(hours=24)
        
        # Calculate system status
        critical_alerts = len([a for a in recent_alerts if a.get('level') == 'critical'])
        system_status = "critical" if critical_alerts > 0 else "normal"
        
        dashboard = SecurityDashboardResponse(
            timestamp=datetime.utcnow(),
            system_status=system_status,
            summary=monitor_data.get("summary", {}),
            threat_levels=monitor_data.get("threat_levels", {}),
            recent_events=monitor_data.get("recent_events", []),
            blocked_ips=monitor_data.get("top_blocked_ips", []),
            active_alerts=recent_alerts[:20],  # Last 20 alerts
            performance_metrics={
                "redis_available": monitor_data.get("redis_stats") is not None,
                "events_processed": len(monitor_data.get("recent_events", [])),
                "alerts_last_24h": len(recent_alerts)
            }
        )
        
        return dashboard
        
    except Exception as e:
        logger.error(f"Error getting security dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security dashboard"
        )


@router.get(
    "/events",
    dependencies=[Depends(require_role("admin"))],
    summary="Get security events",
    description="Get filtered security events"
)
async def get_security_events(
    hours: int = Query(default=24, description="Hours to look back"),
    level: Optional[str] = Query(None, description="Filter by alert level"),
    category: Optional[str] = Query(None, description="Filter by event category"),
    limit: int = Query(default=100, description="Maximum number of events"),
    current_user: User = Depends(require_role("admin"))
) -> List[Dict[str, Any]]:
    """Get security events with filtering"""
    try:
        alert_level = None
        if level:
            try:
                alert_level = AlertLevel(level.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid alert level: {level}"
                )
        
        events = await security_event_tracker.get_recent_alerts(
            hours=hours,
            level=alert_level
        )
        
        # Filter by category if specified
        if category:
            events = [e for e in events if e.get('category', '').lower() == category.lower()]
        
        return events[:limit]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting security events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security events"
        )


@router.post(
    "/events",
    dependencies=[Depends(require_role("admin"))],
    summary="Create security event",
    description="Manually create a security event"
)
async def create_security_event(
    request: Request,
    event_data: SecurityEventRequest,
    current_user: User = Depends(require_role("admin"))
) -> Dict[str, str]:
    """Create a manual security event"""
    try:
        # Parse alert level
        try:
            alert_level = AlertLevel(event_data.level.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid alert level: {event_data.level}"
            )
        
        # Parse event category
        try:
            event_category = EventCategory(event_data.category.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid event category: {event_data.category}"
            )
        
        # Get client IP
        client_ip = request.headers.get("x-forwarded-for")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
        else:
            client_ip = getattr(request.client, 'host', 'unknown') if hasattr(request, 'client') else 'unknown'
        
        # Track the event
        await security_event_tracker.track_event(
            event_type=event_data.event_type,
            description=event_data.description,
            level=alert_level,
            category=event_category,
            user_id=current_user.id,
            source_ip=client_ip,
            technical_details=event_data.technical_details,
            affected_resources=event_data.affected_resources
        )
        
        return {"message": "Security event created successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating security event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create security event"
        )


@router.get(
    "/rate-limits/{client_id}",
    response_model=RateLimitStatusResponse,
    dependencies=[Depends(require_role("admin"))],
    summary="Get rate limit status",
    description="Get rate limit status for specific client"
)
async def get_rate_limit_status(
    client_id: str,
    current_user: User = Depends(require_role("admin"))
) -> RateLimitStatusResponse:
    """Get rate limit status for a client"""
    try:
        status_data = await rate_limiter.get_rate_limit_status(client_id)
        
        return RateLimitStatusResponse(
            client_id=client_id,
            limits=status_data.get("limits", {}),
            penalties=status_data.get("penalties", {}),
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error getting rate limit status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve rate limit status"
        )


@router.post(
    "/ip-blocks",
    dependencies=[Depends(require_role("admin"))],
    summary="Block IP address",
    description="Manually block an IP address"
)
async def block_ip_address(
    request: Request,
    block_request: IPBlockRequest,
    current_user: User = Depends(require_role("admin"))
) -> Dict[str, str]:
    """Manually block an IP address"""
    try:
        # Validate IP address format
        import ipaddress
        try:
            ipaddress.ip_address(block_request.ip_address)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid IP address format"
            )
        
        # Block the IP
        duration = timedelta(minutes=block_request.duration_minutes)
        await security_monitor.block_ip(
            ip=block_request.ip_address,
            duration=duration,
            reason=f"Manual block by admin {current_user.username}: {block_request.reason}"
        )
        
        # Log the action
        await security_event_tracker.track_event(
            event_type="manual_ip_block",
            description=f"IP {block_request.ip_address} manually blocked by admin",
            level=AlertLevel.WARNING,
            category=EventCategory.INCIDENT_RESPONSE,
            user_id=current_user.id,
            technical_details={
                "blocked_ip": block_request.ip_address,
                "duration_minutes": block_request.duration_minutes,
                "reason": block_request.reason,
                "admin_user": current_user.username
            }
        )
        
        return {
            "message": f"IP {block_request.ip_address} blocked for {block_request.duration_minutes} minutes"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error blocking IP address: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to block IP address"
        )


@router.delete(
    "/ip-blocks/{ip_address}",
    dependencies=[Depends(require_role("admin"))],
    summary="Unblock IP address",
    description="Manually unblock an IP address"
)
async def unblock_ip_address(
    ip_address: str,
    current_user: User = Depends(require_role("admin"))
) -> Dict[str, str]:
    """Manually unblock an IP address"""
    try:
        # Validate IP address format
        import ipaddress
        try:
            ipaddress.ip_address(ip_address)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid IP address format"
            )
        
        # Unblock the IP
        await security_monitor.unblock_ip(ip_address)
        
        # Log the action
        await security_event_tracker.track_event(
            event_type="manual_ip_unblock",
            description=f"IP {ip_address} manually unblocked by admin",
            level=AlertLevel.INFO,
            category=EventCategory.INCIDENT_RESPONSE,
            user_id=current_user.id,
            technical_details={
                "unblocked_ip": ip_address,
                "admin_user": current_user.username
            }
        )
        
        return {"message": f"IP {ip_address} unblocked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unblocking IP address: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unblock IP address"
        )


@router.get(
    "/health",
    summary="Security system health check",
    description="Check health of security monitoring systems"
)
async def security_health_check() -> Dict[str, Any]:
    """Health check for security systems"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {}
        }
        
        # Check security monitor
        try:
            monitor_data = await security_monitor.get_security_dashboard()
            health_status["components"]["security_monitor"] = {
                "status": "healthy" if monitor_data else "degraded",
                "redis_available": monitor_data.get("redis_stats") is not None
            }
        except Exception as e:
            health_status["components"]["security_monitor"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Check event tracker
        try:
            recent_alerts = await security_event_tracker.get_recent_alerts(hours=1)
            health_status["components"]["event_tracker"] = {
                "status": "healthy",
                "recent_alerts_count": len(recent_alerts)
            }
        except Exception as e:
            health_status["components"]["event_tracker"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Check rate limiter
        try:
            await rate_limiter.get_rate_limit_status("health_check")
            health_status["components"]["rate_limiter"] = {
                "status": "healthy"
            }
        except Exception as e:
            health_status["components"]["rate_limiter"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Overall status
        unhealthy_components = [
            comp for comp, data in health_status["components"].items()
            if data["status"] == "unhealthy"
        ]
        
        if unhealthy_components:
            health_status["status"] = "degraded"
            health_status["unhealthy_components"] = unhealthy_components
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error in security health check: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }
