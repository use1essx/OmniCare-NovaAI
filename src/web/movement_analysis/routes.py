"""
Healthcare AI V2 - Movement Analysis Web Routes
FastAPI routes for movement analysis pages (standalone interface)
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.database.models_comprehensive import User
from src.web.auth.dependencies import get_current_user, get_optional_user
from src.movement_analysis.access_control import (
    is_super_admin,
    is_org_admin,
    is_healthcare_staff,
    can_manage_assessment_rules,
)

logger = logging.getLogger(__name__)

# Initialize router
assessment_page_router = APIRouter(prefix="/movement-analysis", tags=["Movement Analysis Pages"])

# Templates directory
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def get_user_role_context(user: Optional[User]) -> dict:
    """Get role-based context for templates"""
    if not user:
        return {
            "is_authenticated": False,
            "is_staff": False,
            "is_admin": False,
            "is_super_admin": False,
            "can_manage_rules": False,
            "can_view_staff_reports": False,
        }
    
    _is_super = is_super_admin(user)
    _is_org = is_org_admin(user)
    _is_staff = is_healthcare_staff(user)
    
    return {
        "is_authenticated": True,
        "is_staff": _is_staff or _is_org or _is_super,
        "is_admin": _is_org or _is_super,
        "is_super_admin": _is_super,
        "can_manage_rules": can_manage_assessment_rules(user),
        "can_view_staff_reports": _is_staff or _is_org or _is_super,
    }


@assessment_page_router.get("/", response_class=HTMLResponse)
async def movement_analysis_home(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Movement Analysis home page - shows upload form and history
    """
    role_context = get_user_role_context(current_user)
    
    return templates.TemplateResponse("movement_analysis.html", {
        "request": request,
        "user": current_user,
        **role_context,
        "page_title": "Movement Analysis"
    })


@assessment_page_router.get("/history", response_class=HTMLResponse)
async def movement_analysis_history(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Movement Analysis history page - requires authentication
    """
    role_context = get_user_role_context(current_user)
    
    return templates.TemplateResponse("history.html", {
        "request": request,
        "user": current_user,
        **role_context,
        "page_title": "Movement Analysis History"
    })


@assessment_page_router.get("/{assessment_id}", response_class=HTMLResponse)
async def movement_analysis_detail(
    request: Request,
    assessment_id: int,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Movement Analysis detail/result page
    """
    role_context = get_user_role_context(current_user)
    
    return templates.TemplateResponse("result.html", {
        "request": request,
        "user": current_user,
        "assessment_id": assessment_id,
        **role_context,
        "page_title": "Movement Analysis Result"
    })

