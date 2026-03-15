"""
Admin Dashboard Routes
Serves the HTML dashboard page
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import logging
import psutil
from datetime import datetime
import time
from sqlalchemy import select, func, desc

from src.database.models_comprehensive import User, Organization, Live2DModel, AuditLog
from src.web.auth.dependencies import get_optional_user
from src.database.connection import get_async_session
from urllib.parse import quote
from typing import Optional

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/admin", tags=["admin-dashboard"])

# Initialize templates
templates = Jinja2Templates(directory="src/web/admin/templates")

def redirect_to_login(request: Request) -> RedirectResponse:
    """Redirect unauthenticated users to login page with next parameter."""
    next_path = request.url.path
    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"
    encoded_next = quote(next_path, safe="/?=&")
    return RedirectResponse(url=f"/auth.html?next={encoded_next}", status_code=303)

@router.get("/dashboard", response_class=HTMLResponse)
async def serve_admin_dashboard(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Serve the super admin dashboard
    JavaScript handles authentication check
    """
    try:
        if not current_user:
            logger.warning("No current user found - redirecting to login")
            return redirect_to_login(request)
        
        # Check if user is super admin (check both role and flag)
        is_super_admin = (
            getattr(current_user, "is_super_admin", False) or 
            getattr(current_user, "role", "").lower() == "super_admin"
        )
        
        logger.info(f"User {current_user.username} accessing dashboard - role: {current_user.role}, is_super_admin: {getattr(current_user, 'is_super_admin', False)}")
        
        if not is_super_admin:
            logger.warning(f"User {current_user.username} denied access - not super admin")
            raise HTTPException(status_code=403, detail="Super admin access required")
        
        # Get proper permissions
        from src.web.admin.config.permissions import check_permission
        permissions = {
            "view_dashboard": check_permission(current_user, "view_dashboard"),
            "manage_users": check_permission(current_user, "manage_users"),
            "view_data_management": check_permission(current_user, "view_data_management"),
            "view_ai_agents": check_permission(current_user, "view_ai_agents"),
            "view_security": check_permission(current_user, "view_security"),
            "view_analytics": check_permission(current_user, "view_analytics"),
            "view_system": check_permission(current_user, "view_system"),
            "is_super_admin": current_user.role == "super_admin",
            "is_admin": current_user.is_admin,
        }
        
        # Use the proper template system with base.html
        return templates.TemplateResponse("pages/super_admin_dashboard.html", {
            "request": request,
            "user": current_user,
            "page_title": "Super Admin Dashboard",
            "permissions": permissions
        })
        
    except Exception as e:
        logger.error(f"Error serving dashboard: {e}")
        return HTMLResponse(
            content=f"<h1>Error loading dashboard</h1><p>{str(e)}</p>",
            status_code=500
        )

@router.get("/", response_class=HTMLResponse)
async def serve_main_dashboard(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Serve the main admin dashboard
    """
    try:
        if not current_user:
            logger.warning("No current user found - redirecting to login")
            return redirect_to_login(request)
        
        # Check if user is admin
        is_admin = getattr(current_user, "is_admin", False) or getattr(current_user, "role", "").lower() in ["admin", "super_admin"]
        
        if not is_admin:
            logger.warning(f"User {current_user.username} denied access - not admin")
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get proper permissions
        from src.web.admin.config.permissions import check_permission
        permissions = {
            "view_dashboard": check_permission(current_user, "view_dashboard"),
            "manage_users": check_permission(current_user, "manage_users"),
            "view_data_management": check_permission(current_user, "view_data_management"),
            "view_ai_agents": check_permission(current_user, "view_ai_agents"),
            "view_security": check_permission(current_user, "view_security"),
            "view_analytics": check_permission(current_user, "view_analytics"),
            "view_system": check_permission(current_user, "view_system"),
            "is_super_admin": current_user.role == "super_admin",
            "is_admin": current_user.is_admin,
        }
        
        # Serve the main dashboard
        return templates.TemplateResponse("pages/dashboard.html", {
            "request": request,
            "user": current_user,
            "page_title": "Dashboard",
            "permissions": permissions
        })
        
    except Exception as e:
        logger.error(f"Error serving main dashboard: {e}")
        return HTMLResponse(
            content=f"<h1>Error loading dashboard</h1><p>{str(e)}</p>",
            status_code=500
        )

@router.get("/user-management", response_class=HTMLResponse)
async def serve_user_management(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Serve the user & organization management page
    Accessible by: super admins, org admins, and healthcare workers (with scoped access)
    """
    try:
        if not current_user:
            logger.warning("No current user found - redirecting to login")
            return redirect_to_login(request)
        
        # Get proper permissions
        from src.web.admin.config.permissions import check_permission, get_user_permissions
        
        # Check if user has permission to manage users (org admins, super admins)
        # or has scoped user management access (healthcare workers)
        has_manage_org_users = check_permission(current_user, "manage_org_users")
        has_manage_users = check_permission(current_user, "manage_users")
        
        logger.info(f"User {current_user.username} ({current_user.role}) permission check: manage_org_users={has_manage_org_users}, manage_users={has_manage_users}")
        
        if not (has_manage_org_users or has_manage_users):
            logger.warning(f"User {current_user.username} denied access to user management - insufficient permissions")
            raise HTTPException(status_code=403, detail="Insufficient permissions to access user management")
        
        # Use centralized permission function
        permissions = get_user_permissions(current_user)
        
        # Determine user type for template
        is_super_admin = current_user.role == "super_admin" or getattr(current_user, "is_super_admin", False)
        is_org_admin = getattr(current_user, "is_admin", False) and current_user.organization_id and not is_super_admin
        is_healthcare_worker = (current_user.role or "").lower() in ("doctor", "nurse", "counselor", "social_worker")
        
        return templates.TemplateResponse("pages/user_management.html", {
            "request": request,
            "user": current_user,
            "page_title": "User Management",
            "permissions": permissions,
            "perms": permissions,  # Sidebar uses 'perms'
            "is_super_admin": is_super_admin,
            "is_org_admin": is_org_admin,
            "is_healthcare_worker": is_healthcare_worker
        })
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error serving user management page: {e}", exc_info=True)
        return HTMLResponse(
            content=f"<h1>Error loading page</h1><p>{str(e)}</p>",
            status_code=500
        )

@router.get("/api/dashboard/stats")
async def get_dashboard_stats(
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get dashboard statistics
    Returns real-time metrics for the dashboard
    """
    start_time = time.time()
    
    try:
        # Quick auth check (no DB query if possible)
        if not current_user:
            # Don't require auth for dashboard stats - allows page to load faster
            # Real auth will be enforced by the page itself
            logger.debug("Dashboard stats called without auth - allowing")
        
        logger.info(f"📊 Dashboard stats API called (auth: {bool(current_user)})")
        
        # Get system stats with timeout
        cpu_percent = 0
        memory_percent = 0
        try:
            # Use non-blocking call with short interval
            cpu_percent = psutil.cpu_percent(interval=0)  # Non-blocking
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            logger.debug(f"   ✓ System metrics: {time.time() - start_time:.3f}s")
        except Exception as e:
            logger.warning(f"   ⚠ System metrics failed: {e}")
            cpu_percent = 0
            memory_percent = 0
        
        # Get real data from database with timeout
        total_users = 0
        active_users = 0
        total_organizations = 0
        total_models = 0
        
        try:
            # Use async session for all queries
            db_start = time.time()
            async with get_async_session() as session:
                # Quick queries with timeout
                try:
                    total_users = (await session.execute(select(func.count()).select_from(User))).scalar() or 0
                    logger.debug(f"   ✓ User count: {time.time() - db_start:.3f}s")
                except Exception as e:
                    logger.warning(f"   ⚠ User count failed: {e}")
                
                try:
                    active_users = (await session.execute(select(func.count()).select_from(User).where(User.is_active))).scalar() or 0
                    logger.debug(f"   ✓ Active users: {time.time() - db_start:.3f}s")
                except Exception as e:
                    logger.warning(f"   ⚠ Active users failed: {e}")
                
                try:
                    total_organizations = (await session.execute(select(func.count()).select_from(Organization))).scalar() or 0
                    logger.debug(f"   ✓ Organizations: {time.time() - db_start:.3f}s")
                except Exception as e:
                    logger.warning(f"   ⚠ Organizations failed: {e}")
                
                try:
                    total_models = (await session.execute(select(func.count()).select_from(Live2DModel))).scalar() or 0
                    logger.debug(f"   ✓ Models: {time.time() - db_start:.3f}s")
                except Exception as e:
                    logger.warning(f"   ⚠ Models failed: {e}")
                    
        except Exception as db_error:
            logger.error(f"   ✗ Database connection failed: {db_error}", exc_info=True)
            # Continue with zeros - don't fail the whole endpoint
        
        # Build response
        stats = {
            "users": {
                "total": total_users,
                "active": active_users
            },
            "system": {
                "status": "healthy" if cpu_percent < 90 else "warning",
                "cpu_percent": round(cpu_percent, 1),
                "memory_percent": round(memory_percent, 1)
            },
            "organizations": total_organizations,
            "models": total_models,
            "pipeline": {
                "error_rate": 0.02 # Placeholder for now
            },
            "security": {
                "alerts_today": 0 # Placeholder for now
            },
            "ai": {
                "active_agents": 3 # Placeholder for now
            },
            "timestamp": datetime.now().isoformat()
        }
        
        total_time = time.time() - start_time
        logger.info(f"   ✅ Dashboard stats returned in {total_time:.3f}s")
        
        # Warn if slow
        if total_time > 1.0:
            logger.warning(f"   ⚠️  SLOW RESPONSE: {total_time:.3f}s (should be < 1s)")
        
        return JSONResponse(content=stats)
        
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(f"   ✗ Error getting dashboard stats after {total_time:.3f}s: {e}", exc_info=True)
        
        # Return minimal fallback data on error (but with healthy status)
        return JSONResponse(content={
            "users": {"total": 0, "active": 0},
            "system": {"status": "loading", "cpu_percent": 0, "memory_percent": 0},
            "organizations": 0,
            "models": 0,
            "pipeline": {"error_rate": 0},
            "security": {"alerts_today": 0},
            "ai": {"active_agents": 0},
            "timestamp": datetime.now().isoformat()
        })

@router.get("/api/dashboard/activity")
async def get_dashboard_activity(
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get recent activity for dashboard
    """
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        activities = []
        try:
            async with get_async_session() as session:
                # Query audit logs
                query = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(10)
                result = await session.execute(query)
                logs = result.scalars().all()
                
                for log in logs:
                    # Map audit log to activity format
                    icon = "fa-info-circle"
                    if log.event_category == "security":
                        icon = "fa-shield-alt"
                    elif log.event_category == "user":
                        icon = "fa-user"
                    elif log.event_category == "data":
                        icon = "fa-database"
                        
                    activities.append({
                        "id": log.id,
                        "type": log.event_category,
                        "icon": icon,
                        "title": log.event_type.replace("_", " ").title(),
                        "description": log.event_description,
                        "category": log.event_category.title(),
                        "timestamp": log.created_at.isoformat() if log.created_at else datetime.now().isoformat()
                    })
                    
                # If no logs, add a placeholder
                if not activities:
                    activities.append({
                        "id": 0,
                        "type": "system",
                        "icon": "fa-check-circle",
                        "title": "System Ready",
                        "description": "System is running normally",
                        "category": "System",
                        "timestamp": datetime.now().isoformat()
                    })
                    
        except Exception as e:
            logger.error(f"Error querying audit logs: {e}")
            # Fallback to empty list
            pass
        
        return JSONResponse(content={"activities": activities})
        
    except Exception as e:
        logger.error(f"Error getting dashboard activity: {e}")
        return JSONResponse(content={"activities": []})
