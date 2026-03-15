"""
Social Worker Hub Admin Routes

Routes for the new Social Worker Hub dashboard and management pages.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.web.auth.dependencies import get_optional_user

templates = Jinja2Templates(directory="src/web/admin/templates")

router = APIRouter(prefix="/social-worker", tags=["Social Worker Hub"])


def check_sw_permission(user) -> bool:
    """Check if user has permission to access Social Worker Hub"""
    if not user:
        return False
    
    allowed_roles = ['social_worker', 'admin', 'super_admin', 'counselor']
    return user.role in allowed_roles


@router.get("/dashboard", response_class=HTMLResponse)
async def sw_hub_dashboard(request: Request, user = Depends(get_optional_user)):
    """Social Worker Hub Dashboard"""
    if not check_sw_permission(user):
        return RedirectResponse(url="/auth.html", status_code=303)
    
    return templates.TemplateResponse(
        "social_worker/dashboard.html",
        {"request": request, "user": user, "page_title": "Dashboard", "active_page": "dashboard"}
    )


@router.get("/cases", response_class=HTMLResponse)
async def sw_hub_cases(request: Request, user = Depends(get_optional_user)):
    """Social Worker Hub Cases List"""
    if not check_sw_permission(user):
        return RedirectResponse(url="/auth.html", status_code=303)
    
    return templates.TemplateResponse(
        "social_worker/cases.html",
        {"request": request, "user": user, "page_title": "Cases", "active_page": "cases"}
    )


@router.get("/cases/{case_id}", response_class=HTMLResponse)
async def sw_hub_case_detail(request: Request, case_id: int, user = Depends(get_optional_user)):
    """Social Worker Hub Case Detail"""
    if not check_sw_permission(user):
        return RedirectResponse(url="/auth.html", status_code=303)
    
    return templates.TemplateResponse(
        "social_worker/case_detail.html",
        {"request": request, "user": user, "page_title": f"Case #{case_id}", "active_page": "cases", "case_id": case_id}
    )


@router.get("/alerts", response_class=HTMLResponse)
async def sw_hub_alerts(request: Request, user = Depends(get_optional_user)):
    """Social Worker Hub Alerts"""
    if not check_sw_permission(user):
        return RedirectResponse(url="/auth.html", status_code=303)
    
    return templates.TemplateResponse(
        "social_worker/alerts.html",
        {"request": request, "user": user, "page_title": "Alerts", "active_page": "alerts"}
    )


@router.get("/analytics", response_class=HTMLResponse)
async def sw_hub_analytics(request: Request, user = Depends(get_optional_user)):
    """Social Worker Hub Analytics"""
    if not check_sw_permission(user):
        return RedirectResponse(url="/auth.html", status_code=303)
    
    return templates.TemplateResponse(
        "social_worker/analytics.html",
        {"request": request, "user": user, "page_title": "Analytics", "active_page": "analytics"}
    )


@router.get("/reports", response_class=HTMLResponse)
async def sw_hub_reports(request: Request, user = Depends(get_optional_user)):
    """Social Worker Hub Reports"""
    if not check_sw_permission(user):
        return RedirectResponse(url="/auth.html", status_code=303)
    
    return templates.TemplateResponse(
        "social_worker/reports.html",
        {"request": request, "user": user, "page_title": "Reports", "active_page": "reports"}
    )

