"""
Healthcare AI V2 Admin Page Routes
Serves HTML pages for the admin interface
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
import logging

from src.database.models_comprehensive import User
from src.web.auth.dependencies import get_optional_user
from ..config.permissions import check_permission, get_user_permissions

logger = logging.getLogger(__name__)

# Initialize router and templates
router = APIRouter(tags=["admin-pages"])
templates = Jinja2Templates(directory="src/web/admin/templates")


def redirect_to_login(request: Request) -> HTMLResponse:
    """Redirect unauthenticated users to login page"""
    from urllib.parse import quote
    next_path = request.url.path
    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"
    encoded_next = quote(next_path, safe="/?=&")
    return HTMLResponse(
        content=f'<meta http-equiv="refresh" content="0;url=/auth.html?next={encoded_next}">',
        status_code=302
    )


async def render_page(request: Request, template_name: str, user: Optional[User], title: str, required_perm: str = None):
    """Helper to render admin pages with common context."""
    if not user:
        return redirect_to_login(request)
    
    permissions = get_user_permissions(user)
    
    if required_perm and not permissions.get(required_perm, False):
        return templates.TemplateResponse("errors/forbidden.html", {
            "request": request,
            "user": user,
            "permissions": permissions,
            "perms": permissions
        }, status_code=403)

    return templates.TemplateResponse(f"pages/{template_name}", {
        "request": request,
        "user": user,
        "page_title": title,
        "permissions": permissions,
        "perms": permissions
    })


# =============================================================================
# OVERVIEW SECTION
# =============================================================================

@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Main admin dashboard"""
    if not current_user:
        return redirect_to_login(request)
    
    if not check_permission(current_user, "view_dashboard"):
        raise HTTPException(status_code=403, detail="Insufficient permissions to view dashboard")
    
    return templates.TemplateResponse("pages/dashboard.html", {
        "request": request,
        "user": current_user,
        "perms": get_user_permissions(current_user),
        "permissions": get_user_permissions(current_user),
        "page_title": "Healthcare AI V2 Dashboard"
    })


@router.get("/testing", response_class=HTMLResponse)
async def testing_dashboard(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Testing dashboard page - Super admins only"""
    if not current_user:
        return redirect_to_login(request)
    
    if not check_permission(current_user, "view_testing"):
        return templates.TemplateResponse("errors/forbidden.html", {
            "request": request,
            "user": current_user,
        }, status_code=403)
    
    user_perms = get_user_permissions(current_user)
    return templates.TemplateResponse("pages/testing_dashboard.html", {
        "request": request,
        "user": current_user,
        "permissions": user_perms,
        "perms": user_perms,
        "page_title": "Testing Dashboard"
    })


# =============================================================================
# OPERATIONS SECTION
# =============================================================================

@router.get("/users", response_class=HTMLResponse)
@router.get("/user-management", response_class=HTMLResponse)
async def user_management(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """User management page (accessible by admins and healthcare workers with scoped access)"""
    if not current_user:
        return redirect_to_login(request)
    
    has_manage_org_users = check_permission(current_user, "manage_org_users")
    has_manage_users = check_permission(current_user, "manage_users")
    
    if not (has_manage_org_users or has_manage_users):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to access user management"
        )
    
    user_perms = get_user_permissions(current_user)
    is_super_admin = current_user.role == "super_admin" or getattr(current_user, "is_super_admin", False)
    is_org_admin = getattr(current_user, "is_admin", False) and current_user.organization_id and not is_super_admin
    is_healthcare_worker = (current_user.role or "").lower() in ("doctor", "nurse", "counselor", "social_worker")
    
    return templates.TemplateResponse("pages/user_management.html", {
        "request": request,
        "user": current_user,
        "permissions": user_perms,
        "perms": user_perms,
        "page_title": "User Management",
        "is_super_admin": is_super_admin,
        "is_org_admin": is_org_admin,
        "is_healthcare_worker": is_healthcare_worker
    })


@router.get("/movement-analysis-rules", response_class=HTMLResponse)
@router.get("/movement-analysis/rules", response_class=HTMLResponse)
async def movement_analysis_rules_page(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Movement Analysis rules management page"""
    if not current_user:
        return redirect_to_login(request)
    
    user_perms = get_user_permissions(current_user)
    if not user_perms.get("view_assessment_rules", False):
        return templates.TemplateResponse("errors/forbidden.html", {
            "request": request,
            "user": current_user,
            "permissions": user_perms,
            "perms": user_perms,
        }, status_code=403)
    
    return templates.TemplateResponse("pages/movement_analysis_rules.html", {
        "request": request,
        "user": current_user,
        "permissions": user_perms,
        "perms": user_perms,
        "page_title": "Movement Analysis Rules"
    })


@router.get("/data", response_class=HTMLResponse)
@router.get("/data-management", response_class=HTMLResponse)
async def data_management(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Data management page"""
    if not current_user:
        return redirect_to_login(request)
    
    if not check_permission(current_user, "view_data_management"):
        raise HTTPException(status_code=403, detail="Insufficient permissions to view data management")
    
    # Placeholder stats for the template
    stats = {
        "total_documents": 1250,
        "pending_review": 45,
        "approved": 1180,
        "processing": 25
    }
    
    user_perms = get_user_permissions(current_user)
    return templates.TemplateResponse("pages/data_management.html", {
        "request": request,
        "user": current_user,
        "permissions": user_perms,
        "perms": user_perms,
        "page_title": "Data Management",
        "stats": stats
    })


@router.get("/hk-data", response_class=HTMLResponse)
async def hk_data_sources(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """HK Data Sources page"""
    return await render_page(request, "coming_soon.html", current_user, "HK Data Sources", "view_data_management")


@router.get("/data/quality", response_class=HTMLResponse)
async def data_quality(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Data Quality Review page"""
    return await render_page(request, "quality_review.html", current_user, "Data Quality Review", "view_data_management")


# =============================================================================
# INTELLIGENCE SECTION
# =============================================================================

@router.get("/questionnaires", response_class=HTMLResponse)
@router.get("/questionnaires/manage", response_class=HTMLResponse)
async def questionnaire_management(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Questionnaire management page"""
    if not current_user:
        return redirect_to_login(request)
    
    # Allow both regular admins and super admins
    if not (check_permission(current_user, "view_questionnaires") or check_permission(current_user, "view_ai_agents")):
        raise HTTPException(status_code=403, detail="Insufficient permissions to view questionnaires")
    
    user_perms = get_user_permissions(current_user)
    return templates.TemplateResponse("pages/questionnaire_management.html", {
        "request": request,
        "user": current_user,
        "permissions": user_perms,
        "perms": user_perms,
        "page_title": "Questionnaire Manager"
    })

@router.get("/questionnaires/scores", response_class=HTMLResponse)
async def questionnaire_scores(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Questionnaire scores page"""
    if not current_user:
        return redirect_to_login(request)
    
    # Allow both regular admins and super admins
    if not (check_permission(current_user, "view_questionnaires") or check_permission(current_user, "view_ai_agents")):
        raise HTTPException(status_code=403, detail="Insufficient permissions to view questionnaire scores")
    
    user_perms = get_user_permissions(current_user)
    return templates.TemplateResponse("pages/questionnaire_scores.html", {
        "request": request,
        "user": current_user,
        "permissions": user_perms,
    })

@router.get("/questionnaires/create", response_class=HTMLResponse)
async def questionnaire_creator(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Questionnaire creator page"""
    if not current_user:
        return redirect_to_login(request)
    
    if not check_permission(current_user, "view_ai_agents"):
        raise HTTPException(status_code=403, detail="Insufficient permissions to create questionnaires")
    
    user_perms = get_user_permissions(current_user)
    return templates.TemplateResponse("pages/questionnaire_creator.html", {
        "request": request,
        "user": current_user,
        "permissions": user_perms,
        "perms": user_perms,
        "page_title": "Questionnaire Creator"
    })


@router.get("/questionnaires/ai-generator", response_class=HTMLResponse)
@router.get("/ai-questionnaire-generator", response_class=HTMLResponse)
async def ai_questionnaire_generator(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """AI-powered questionnaire generator page"""
    if not current_user:
        return redirect_to_login(request)
    
    # Allow both regular admins and super admins
    if not (check_permission(current_user, "view_questionnaires") or check_permission(current_user, "view_ai_agents")):
        raise HTTPException(status_code=403, detail="Insufficient permissions to access AI questionnaire generator")
    
    user_perms = get_user_permissions(current_user)
    return templates.TemplateResponse("pages/ai_questionnaire_generator.html", {
        "request": request,
        "user": current_user,
        "permissions": user_perms,
        "perms": user_perms,
        "page_title": "AI Questionnaire Generator"
    })


@router.get("/questionnaires/ai-generator/console", response_class=HTMLResponse)
async def ai_questionnaire_console(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Superadmin AI Console for monitoring generation jobs"""
    if not current_user:
        return redirect_to_login(request)
    
    is_super_admin = current_user.role == "super_admin" or getattr(current_user, "is_super_admin", False)
    if not is_super_admin:
        raise HTTPException(status_code=403, detail="Only superadmins can access the AI Console")
    
    user_perms = get_user_permissions(current_user)
    return templates.TemplateResponse("pages/ai_generation_console.html", {
        "request": request,
        "user": current_user,
        "permissions": user_perms,
        "perms": user_perms,
        "page_title": "Superadmin AI Console"
    })


@router.get("/social-worker", response_class=HTMLResponse)
async def social_worker_hub(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Social worker patient management hub"""
    if not current_user:
        return redirect_to_login(request)
    
    if not check_permission(current_user, "view_ai_agents"):
        raise HTTPException(status_code=403, detail="Insufficient permissions to view social worker hub")
    
    user_perms = get_user_permissions(current_user)
    return templates.TemplateResponse("pages/social_worker.html", {
        "request": request,
        "user": current_user,
        "permissions": user_perms,
        "perms": user_perms,
        "page_title": "Social Worker Hub"
    })


@router.get("/adk-tools", response_class=HTMLResponse)
@router.get("/adk", response_class=HTMLResponse)
async def adk_tools_page(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """ADK diagnostic tools page"""
    if not current_user:
        return redirect_to_login(request)
    
    if not check_permission(current_user, "view_ai_agents"):
        raise HTTPException(status_code=403, detail="Insufficient permissions to view ADK tools")
    
    user_perms = get_user_permissions(current_user)
    return templates.TemplateResponse("pages/adk_tools.html", {
        "request": request,
        "user": current_user,
        "permissions": user_perms,
        "perms": user_perms,
        "page_title": "ADK Diagnostic Tools"
    })


@router.get("/function-calling", response_class=HTMLResponse)
async def function_calling_dashboard(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Function calling monitor dashboard"""
    if not current_user:
        return redirect_to_login(request)
    
    if not check_permission(current_user, "view_ai_agents"):
        raise HTTPException(status_code=403, detail="Insufficient permissions to view function calling dashboard")
    
    user_perms = get_user_permissions(current_user)
    return templates.TemplateResponse("pages/function_calling.html", {
        "request": request,
        "user": current_user,
        "permissions": user_perms,
        "perms": user_perms,
        "page_title": "Function Calling Monitor"
    })


@router.get("/live2d", response_class=HTMLResponse)
@router.get("/live2d-admin", response_class=HTMLResponse)
async def live2d_admin(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Live2D admin page"""
    if not current_user:
        return redirect_to_login(request)
    
    user_perms = get_user_permissions(current_user)
    if not user_perms.get("view_live2d", False):
        return templates.TemplateResponse("errors/forbidden.html", {
            "request": request,
            "user": current_user,
            "permissions": user_perms,
            "perms": user_perms,
        }, status_code=403)
    
    return templates.TemplateResponse("pages/live2d_admin.html", {
        "request": request,
        "user": current_user,
        "permissions": user_perms,
        "perms": user_perms,
        "page_title": "Live2D Configuration"
    })


@router.get("/voice-test-suite", response_class=HTMLResponse)
async def voice_test_suite(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Voice Detection Test Suite admin page"""
    if not current_user:
        return redirect_to_login(request)
    
    user_perms = get_user_permissions(current_user)
    if not user_perms.get("view_live2d", False):
        return templates.TemplateResponse("errors/forbidden.html", {
            "request": request,
            "user": current_user,
            "permissions": user_perms,
            "perms": user_perms,
        }, status_code=403)
    
    return templates.TemplateResponse("pages/voice_test_suite.html", {
        "request": request,
        "user": current_user,
        "permissions": user_perms,
        "perms": user_perms,
        "page_title": "Voice Test Suite"
    })


@router.get("/path-diagnostic", response_class=HTMLResponse)
async def admin_path_diagnostic(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Diagnostic page to test if Web Speech API works on /admin/ path"""
    if not current_user:
        return redirect_to_login(request)
    
    user_perms = get_user_permissions(current_user)
    if not user_perms.get("view_live2d", False):
        return templates.TemplateResponse("errors/forbidden.html", {
            "request": request,
            "user": current_user,
            "permissions": user_perms,
            "perms": user_perms,
        }, status_code=403)
    
    return templates.TemplateResponse("pages/admin_path_diagnostic.html", {
        "request": request,
        "user": current_user,
        "permissions": user_perms,
        "perms": user_perms,
        "page_title": "Admin Path Diagnostic"
    })


@router.get("/kb-sandbox", response_class=HTMLResponse)
@router.get("/knowledge-base/sandbox", response_class=HTMLResponse)
async def kb_sandbox(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """KB/RAG Sandbox - Dev-only UI for knowledge base testing"""
    return await render_page(request, "kb_sandbox.html", current_user, "KB/RAG Sandbox", "manage_data")


# =============================================================================
# AI AGENTS SECTION
# =============================================================================

@router.get("/agents/performance", response_class=HTMLResponse)
async def agent_performance(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Agent Performance page"""
    return await render_page(request, "coming_soon.html", current_user, "Agent Performance", "view_ai_agents")


@router.get("/agents/logs", response_class=HTMLResponse)
async def agent_logs(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Agent Logs page"""
    return await render_page(request, "coming_soon.html", current_user, "Agent Logs", "view_ai_agents")


@router.get("/agents/evals", response_class=HTMLResponse)
async def agent_evals(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Agent Evaluations page"""
    return await render_page(request, "coming_soon.html", current_user, "Agent Evaluations", "view_ai_agents")


# =============================================================================
# SYSTEM SECTION
# =============================================================================

@router.get("/system/logs", response_class=HTMLResponse)
async def system_logs(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """System Logs page"""
    return await render_page(request, "coming_soon.html", current_user, "System Logs", "view_system")


@router.get("/system/config", response_class=HTMLResponse)
async def system_config(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """System Configuration page"""
    return await render_page(request, "coming_soon.html", current_user, "System Configuration", "view_system")


@router.get("/super-admin", response_class=HTMLResponse)
async def super_admin_dashboard(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Super admin dashboard - Super admins only"""
    if not current_user:
        return redirect_to_login(request)
    
    if not check_permission(current_user, "view_system"):
        return templates.TemplateResponse("errors/forbidden.html", {
            "request": request,
            "user": current_user,
        }, status_code=403)
    
    user_perms = get_user_permissions(current_user)
    
    return templates.TemplateResponse("pages/super_admin_dashboard.html", {
        "request": request,
        "user": current_user,
        "permissions": user_perms,
        "perms": user_perms,
        "page_title": "Super Admin Dashboard"
    })


# =============================================================================
# Custom Live AI Pages (Emotion Tracking & Video Analysis)
# =============================================================================

@router.get("/custom-live-ai", response_class=HTMLResponse)
async def custom_live_ai_dashboard_page(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Custom Live AI Dashboard - Emotion tracking and video analysis"""
    return await render_page(request, "custom_live_ai/dashboard.html", current_user, "Custom Live AI", "view_live2d")


@router.get("/custom-live-ai/emotion-tracker", response_class=HTMLResponse)
async def emotion_tracker_page(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Real-time emotion tracking via webcam"""
    return await render_page(request, "custom_live_ai/emotion_tracker.html", current_user, "Emotion Tracker", "view_live2d")


@router.get("/custom-live-ai/session-playback", response_class=HTMLResponse)
async def session_playback_page(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Session playback and review"""
    return await render_page(request, "custom_live_ai/session_playback.html", current_user, "Session Playback", "view_live2d")


@router.get("/custom-live-ai/reports", response_class=HTMLResponse)
async def emotion_reports_page(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Emotion analysis reports"""
    return await render_page(request, "custom_live_ai/reports.html", current_user, "Emotion Reports", "view_live2d")


# =============================================================================
# ADDITIONAL ADMIN PAGES
# =============================================================================

@router.get("/organizations", response_class=HTMLResponse)
async def organizations_page(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Organization management page"""
    return await render_page(request, "organizations.html", current_user, "Organizations", "manage_users")


@router.get("/ai-settings", response_class=HTMLResponse)
async def ai_settings_page(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """AI Settings configuration page"""
    return await render_page(request, "ai_settings.html", current_user, "AI Settings", "view_dashboard")


@router.get("/security", response_class=HTMLResponse)
async def security_page(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Security dashboard page"""
    return await render_page(request, "security_dashboard.html", current_user, "Security Dashboard", "view_dashboard")
