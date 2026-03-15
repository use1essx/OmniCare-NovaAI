from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from src.database.models_comprehensive import User
from src.web.auth.dependencies import get_optional_user
from src.web.admin.config.permissions import get_user_permissions

# Initialize templates
templates = Jinja2Templates(directory="src/web/admin/templates")

# Create admin router
admin_router = APIRouter(prefix="/admin", tags=["admin-v2"])

def redirect_to_login(request: Request) -> RedirectResponse:
    """Redirect unauthenticated users to the login page."""
    return RedirectResponse(url=f"/auth.html?next={request.url.path}", status_code=303)

async def render_page(request: Request, template_name: str, user: Optional[User], title: str, required_perm: str = None):
    """Helper to render admin pages with common context."""
    if not user:
        return redirect_to_login(request)
    
    permissions = get_user_permissions(user)
    
    if required_perm and not permissions.get(required_perm, False):
        return templates.TemplateResponse("errors/forbidden.html", {
            "request": request,
            "user": user,
            "permissions": permissions
        }, status_code=403)

    return templates.TemplateResponse(f"pages/{template_name}", {
        "request": request,
        "user": user,
        "page_title": title,
        "permissions": permissions,
        "perms": permissions
    })

# --- User Management ---
@admin_router.get("/user-management", response_class=HTMLResponse)
async def user_management(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "user_management.html", user, "User Management", "manage_org_users")

# --- Movement Analysis ---
@admin_router.get("/movement-analysis/rules", response_class=HTMLResponse)
async def movement_analysis_rules(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "movement_analysis_rules.html", user, "Assessment Rules", "view_assessment_rules")

# --- Questionnaires ---
@admin_router.get("/questionnaires/scores", response_class=HTMLResponse)
async def questionnaires_scores(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "questionnaire_scores.html", user, "Questionnaire Scores", "view_ai_agents")

@admin_router.get("/questionnaires", response_class=HTMLResponse)
async def questionnaires_manage(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "questionnaire_management.html", user, "Questionnaire Management", "view_ai_agents")

@admin_router.get("/ai-questionnaire-generator", response_class=HTMLResponse)
async def ai_questionnaire_generator(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "ai_questionnaire_generator.html", user, "AI Questionnaire Generator", "view_ai_agents")

@admin_router.get("/questionnaires/create", response_class=HTMLResponse)
async def questionnaire_creator(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "questionnaire_creator.html", user, "Create Questionnaire", "view_ai_agents")

@admin_router.get("/ai-questionnaire/console", response_class=HTMLResponse)
async def ai_console(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "ai_generation_console.html", user, "AI Generation Console", "view_ai_agents")

# --- Social Worker ---
@admin_router.get("/social-worker", response_class=HTMLResponse)
async def social_worker_hub(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "social_worker.html", user, "Social Worker Hub", "view_ai_agents")

# --- Voice Suite ---
@admin_router.get("/voice-test-suite", response_class=HTMLResponse)
async def voice_test_suite(request: Request, user: Optional[User] = Depends(get_optional_user)):
    """Serve the comprehensive voice input test suite with admin styling"""
    return await render_page(request, "voice_test_suite.html", user, "Voice Test Suite", "view_live2d")

@admin_router.get("/path-diagnostic", response_class=HTMLResponse)
async def admin_path_diagnostic(request: Request, user: Optional[User] = Depends(get_optional_user)):
    """Diagnostic page to test if Web Speech API works on /admin/ path"""
    return await render_page(request, "admin_path_diagnostic.html", user, "Admin Path Diagnostic", "view_live2d")

# --- System (Additional) ---
@admin_router.get("/system/logs", response_class=HTMLResponse)
@admin_router.get("/agents/performance", response_class=HTMLResponse)
async def agent_performance(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "coming_soon.html", user, "Agent Performance", "view_ai_agents")

@admin_router.get("/agents/logs", response_class=HTMLResponse)
async def agent_logs(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "coming_soon.html", user, "Agent Logs", "view_ai_agents")

@admin_router.get("/knowledge-base", response_class=HTMLResponse)
async def knowledge_base_page(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "knowledge_base.html", user, "Knowledge Base", "manage_data")

@admin_router.get("/agents/evals", response_class=HTMLResponse)
async def agent_evals(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "coming_soon.html", user, "Agent Evaluations", "view_ai_agents")

# --- Custom Live AI (Emotion Tracking & Video Analysis) ---
@admin_router.get("/custom-live-ai", response_class=HTMLResponse)
async def custom_live_ai_dashboard(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "custom_live_ai/dashboard.html", user, "Custom Live AI", "view_live2d")

@admin_router.get("/custom-live-ai/emotion-tracker", response_class=HTMLResponse)
async def emotion_tracker(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "custom_live_ai/emotion_tracker.html", user, "Emotion Tracker", "view_live2d")

@admin_router.get("/custom-live-ai/session-playback", response_class=HTMLResponse)
async def session_playback(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "custom_live_ai/session_playback.html", user, "Session Playback", "view_live2d")

@admin_router.get("/custom-live-ai/reports", response_class=HTMLResponse)
async def emotion_reports(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "custom_live_ai/reports.html", user, "Emotion Reports", "view_live2d")

# --- System (Additional) ---
@admin_router.get("/system/logs", response_class=HTMLResponse)
async def system_logs(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "coming_soon.html", user, "System Logs", "view_system")

@admin_router.get("/system/config", response_class=HTMLResponse)
async def system_config(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return await render_page(request, "coming_soon.html", user, "System Configuration", "view_system")
