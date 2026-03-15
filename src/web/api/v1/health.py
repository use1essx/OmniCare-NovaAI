"""
Healthcare AI V2 - Health Check Endpoints
System health monitoring and status endpoints
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.core.config import settings
from src.database.connection import check_database_health
from src.core.logging import get_logger
from src.security.api import APIKeyManager, log_api_operation
from src.web.auth.dependencies import get_optional_user

logger = get_logger(__name__)
router = APIRouter()


class HealthStatus(BaseModel):
    """Health status response model"""
    status: str
    timestamp: datetime
    version: str
    environment: str
    uptime_seconds: float
    checks: Dict[str, Any]


class DetailedHealthStatus(BaseModel):
    """Detailed health status response model"""
    status: str
    timestamp: datetime
    version: str
    environment: str
    uptime_seconds: float
    system_info: Dict[str, Any]
    database: Dict[str, Any]
    external_services: Dict[str, Any]
    performance_metrics: Dict[str, Any]


# Track application start time
app_start_time = time.time()


@router.get("/health", response_model=HealthStatus)
async def health_check():
    """
    Basic health check endpoint
    Returns simple status for load balancers and monitoring
    """
    try:
        # Quick database check
        db_status = await check_database_health()
        
        # Determine overall status
        overall_status = "healthy"
        if db_status["status"] != "healthy":
            overall_status = "unhealthy"
        
        uptime = time.time() - app_start_time
        
        return HealthStatus(
            status=overall_status,
            timestamp=datetime.utcnow(),
            version=settings.app_version,
            environment=settings.environment,
            uptime_seconds=uptime,
            checks={
                "database": db_status["status"],
                "api": "healthy"
            }
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Service unavailable"
        )


@router.get("/health/detailed", response_model=DetailedHealthStatus)
async def detailed_health_check():
    """
    Detailed health check endpoint
    Returns comprehensive system status information
    """
    try:
        start_time = time.time()
        
        # Gather all health information
        db_health, system_info, external_services = await asyncio.gather(
            check_database_health(),
            get_system_info(),
            check_external_services(),
            return_exceptions=True
        )
        
        # Handle exceptions in parallel tasks
        if isinstance(db_health, Exception):
            logger.error(f"Database health check failed: {db_health}")
            db_health = {"status": "unhealthy", "error": str(db_health)}
        
        if isinstance(system_info, Exception):
            logger.error(f"System info gathering failed: {system_info}")
            system_info = {"error": str(system_info)}
        
        if isinstance(external_services, Exception):
            logger.error(f"External services check failed: {external_services}")
            external_services = {"error": str(external_services)}
        
        # Calculate performance metrics
        check_duration = time.time() - start_time
        uptime = time.time() - app_start_time
        
        performance_metrics = {
            "health_check_duration_ms": int(check_duration * 1000),
            "uptime_seconds": uptime,
            "uptime_human": format_duration(uptime)
        }
        
        # Determine overall status
        overall_status = "healthy"
        if db_health.get("status") != "healthy":
            overall_status = "unhealthy"
        elif any(service.get("status") == "unhealthy" for service in external_services.values() if isinstance(service, dict)):
            overall_status = "degraded"
        
        return DetailedHealthStatus(
            status=overall_status,
            timestamp=datetime.utcnow(),
            version=settings.app_version,
            environment=settings.environment,
            uptime_seconds=uptime,
            system_info=system_info,
            database=db_health,
            external_services=external_services,
            performance_metrics=performance_metrics
        )
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Service unavailable"
        )


@router.get("/health/live")
async def liveness_probe():
    """
    Kubernetes liveness probe endpoint
    Returns 200 if the application is running
    """
    return {"status": "alive", "timestamp": datetime.utcnow()}


@router.get("/health/ready")
async def readiness_probe():
    """
    Kubernetes readiness probe endpoint
    Returns 200 if the application is ready to serve requests
    """
    try:
        # Check critical dependencies
        db_health = await check_database_health()
        
        if db_health["status"] != "healthy":
            raise HTTPException(
                status_code=503,
                detail="Database not ready"
            )
        
        return {
            "status": "ready",
            "timestamp": datetime.utcnow(),
            "checks": {
                "database": "ready"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Service not ready"
        )


@router.get("/health/startup")
async def startup_probe():
    """
    Kubernetes startup probe endpoint
    Returns 200 when the application has finished starting up
    """
    try:
        # Check if application has been running for at least 10 seconds
        uptime = time.time() - app_start_time
        if uptime < 10:
            raise HTTPException(
                status_code=503,
                detail="Application still starting up"
            )
        
        # Check database connection
        db_health = await check_database_health()
        if not db_health["async_connection"] or not db_health["sync_connection"]:
            raise HTTPException(
                status_code=503,
                detail="Database connections not established"
            )
        
        return {
            "status": "started",
            "timestamp": datetime.utcnow(),
            "uptime_seconds": uptime
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Startup check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Startup check failed"
        )


async def get_system_info() -> Dict[str, Any]:
    """Get system information"""
    import psutil
    import platform
    
    try:
        return {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "architecture": platform.architecture()[0],
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "memory_available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage_percent": psutil.disk_usage('/').percent,
            "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
        }
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        return {"error": str(e)}


async def check_external_services() -> Dict[str, Any]:
    """Check external service health"""
    import httpx
    
    services = {}
    
    # Check microservices
    microservices = {
        "stt_service": "http://stt_server:8790/health",
        "motion_capture": "http://motion_capture:8001/health",
        "assessment_service": "http://assessment:8002/health"
    }
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for service_name, url in microservices.items():
            try:
                response = await client.get(url)
                services[service_name] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                    "status_code": response.status_code
                }
            except Exception as e:
                services[service_name] = {
                    "status": "unreachable",
                    "error": str(e)
                }
    
    # Check Redis
    try:
        import redis.asyncio as redis_client
        from src.core.config import settings
        
        if settings.redis_url:
            redis = redis_client.from_url(settings.redis_url, decode_responses=True)
            await redis.ping()
            await redis.close()
            services["redis"] = {"status": "healthy"}
        else:
            services["redis"] = {"status": "not_configured"}
    except Exception as e:
        services["redis"] = {"status": "unhealthy", "error": str(e)}
    
    return services


@router.get("/health/deployment")
async def deployment_verification():
    """
    Comprehensive deployment verification endpoint
    Checks all critical components for successful deployment
    """
    try:
        checks = {}
        overall_status = "healthy"
        
        # 1. Database Connection
        try:
            db_health = await check_database_health()
            checks["database"] = {
                "status": "✅" if db_health["status"] == "healthy" else "❌",
                "details": db_health
            }
            if db_health["status"] != "healthy":
                overall_status = "unhealthy"
        except Exception as e:
            checks["database"] = {"status": "❌", "error": str(e)}
            overall_status = "unhealthy"
        
        # 2. Database Tables
        try:
            from src.database.connection import get_sync_db
            from sqlalchemy import text
            db = next(get_sync_db())
            
            # Count tables
            result = db.execute(text("SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'"))
            table_count = result.scalar()
            
            checks["database_tables"] = {
                "status": "✅" if table_count >= 20 else "⚠️",
                "count": table_count,
                "expected": "20+"
            }
            if table_count < 20:
                overall_status = "degraded"
        except Exception as e:
            checks["database_tables"] = {"status": "❌", "error": str(e)}
            overall_status = "unhealthy"
        
        # 3. Super Admin User
        try:
            from src.database.connection import get_sync_db
            from src.database.models_comprehensive import User
            db = next(get_sync_db())
            
            admin = db.query(User).filter(
                User.username == "admin",
                User.is_super_admin == True
            ).first()
            
            checks["super_admin"] = {
                "status": "✅" if admin else "❌",
                "exists": bool(admin),
                "username": admin.username if admin else None
            }
            if not admin:
                overall_status = "unhealthy"
        except Exception as e:
            checks["super_admin"] = {"status": "❌", "error": str(e)}
            overall_status = "unhealthy"
        
        # 4. Organizations
        try:
            from src.database.connection import get_sync_db
            from src.database.models_comprehensive import Organization
            db = next(get_sync_db())
            
            org_count = db.query(Organization).count()
            
            checks["organizations"] = {
                "status": "✅" if org_count >= 4 else "⚠️",
                "count": org_count,
                "expected": "4"
            }
            if org_count < 4:
                overall_status = "degraded"
        except Exception as e:
            checks["organizations"] = {"status": "❌", "error": str(e)}
        
        # 5. Redis
        try:
            import redis.asyncio as redis_client
            from src.core.config import settings
            
            if settings.redis_url:
                redis = redis_client.from_url(settings.redis_url, decode_responses=True)
                await redis.ping()
                await redis.close()
                checks["redis"] = {"status": "✅", "connected": True}
            else:
                checks["redis"] = {"status": "⚠️", "connected": False, "message": "Not configured"}
        except Exception as e:
            checks["redis"] = {"status": "⚠️", "error": str(e)}
        
        # 6. Microservices
        try:
            external_services = await check_external_services()
            
            for service_name, service_status in external_services.items():
                if service_name in ["stt_service", "motion_capture", "assessment_service"]:
                    status_icon = "✅" if service_status.get("status") == "healthy" else "⚠️"
                    checks[service_name] = {
                        "status": status_icon,
                        "details": service_status
                    }
        except Exception as e:
            checks["microservices"] = {"status": "⚠️", "error": str(e)}
        
        # 7. Nova Configuration
        try:
            from src.core.config import settings
            nova_configured = bool(
                settings.use_bedrock and 
                settings.aws_access_key_id and 
                settings.aws_secret_access_key
            )
            checks["nova_configuration"] = {
                "status": "✅" if nova_configured else "⚠️",
                "use_bedrock": settings.use_bedrock,
                "aws_configured": bool(settings.aws_access_key_id and settings.aws_secret_access_key),
                "region": settings.aws_region
            }
            if not nova_configured:
                overall_status = "degraded"
        except Exception as e:
            checks["nova_configuration"] = {"status": "⚠️", "error": str(e)}
        
        # 8. Budget Status
        try:
            from src.database.connection import get_sync_db
            from src.ai.budget_middleware import BudgetProtectionMiddleware
            db = next(get_sync_db())
            budget_middleware = BudgetProtectionMiddleware(db)
            budget_status = budget_middleware.get_budget_status()
            
            # Determine budget status icon
            alert_level = budget_status.get('alert_level')
            if alert_level == 'exceeded':
                budget_icon = "❌"
                overall_status = "unhealthy"
            elif alert_level in ['critical', 'final']:
                budget_icon = "⚠️"
                if overall_status == "healthy":
                    overall_status = "degraded"
            else:
                budget_icon = "✅"
            
            checks["budget_status"] = {
                "status": budget_icon,
                "current_total": budget_status['current_total'],
                "budget_limit": budget_status['budget_limit'],
                "remaining": budget_status['remaining'],
                "percentage_used": round(budget_status['percentage_used'], 2),
                "alert_level": alert_level or "ok"
            }
        except Exception as e:
            checks["budget_status"] = {"status": "⚠️", "error": str(e)}
        
        # Summary
        summary = {
            "overall_status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "deployment_ready": overall_status == "healthy",
            "checks_passed": sum(1 for c in checks.values() if c.get("status") == "✅"),
            "checks_total": len(checks)
        }
        
        return {
            "summary": summary,
            "checks": checks,
            "message": _get_deployment_message(overall_status)
        }
        
    except Exception as e:
        logger.error(f"Deployment verification failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Deployment verification failed: {str(e)}"
        )


def _get_deployment_message(status: str) -> str:
    """Get deployment status message"""
    messages = {
        "healthy": "🎉 All services ready! Deployment successful.",
        "degraded": "⚠️ Deployment partially successful. Some optional services unavailable.",
        "unhealthy": "❌ Deployment failed. Critical services unavailable."
    }
    return messages.get(status, "Unknown deployment status")


@router.get("/api-key-status")
async def api_key_status(current_user = Depends(get_optional_user)) -> Dict[str, Any]:
    """
    Check AWS Nova configuration status without exposing sensitive data
    Available to both authenticated and anonymous users
    """
    try:
        # Get secure AWS credential status
        status = APIKeyManager.get_safe_status()
        
        # Log the check (without exposing sensitive data)
        log_api_operation(
            operation="nova_config_status_check",
            success=True,
            details=f"Status check by {'authenticated' if current_user else 'anonymous'} user"
        )
        
        # Return safe status information
        return {
            "configured": status["configured"],
            "format_valid": status["format_valid"],
            "status": status["status"],
            "key_prefix": status["key_prefix"],
            "key_suffix": status["key_suffix"],
            "key_length": status["key_length"],
            "source": status["source"],
            "last_checked": status["last_checked"],
            "message": _get_status_message(status["status"])
        }
        
    except Exception as e:
        logger.error(f"Nova config status check failed: {e}")
        log_api_operation(
            operation="nova_config_status_check",
            success=False,
            details=f"Error: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Could not check Nova configuration status")


def _get_status_message(status: str) -> str:
    """Get user-friendly status message"""
    messages = {
        "configured": "AWS Nova is properly configured and ready to use",
        "not_configured": "AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables",
        "invalid_format": "AWS credentials format appears invalid. Please check your AWS access key and secret key"
    }
    return messages.get(status, f"Unknown status: {status}")


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable string"""
    duration = timedelta(seconds=int(seconds))
    
    days = duration.days
    hours, remainder = divmod(duration.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    
    return " ".join(parts)
