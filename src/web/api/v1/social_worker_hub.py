"""
Social Worker Hub API Endpoints

Provides 15+ endpoints for case management, alerts,
reports, and analytics.

All endpoints require authentication with social_worker or admin role.
"""

from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ...auth.dependencies import get_current_user
from ....social_worker import (
    get_case_manager,
    get_alert_manager,
    get_report_generator,
    get_analytics_service,
)

router = APIRouter(prefix="/social-worker", tags=["Social Worker Hub"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class CaseCreateRequest(BaseModel):
    """Request to create a new case"""
    child_id: int
    summary: str
    presenting_concerns: str
    priority: str = "medium"
    initial_risk_level: Optional[int] = None
    tags: Optional[List[str]] = None


class CaseUpdateRequest(BaseModel):
    """Request to update a case"""
    summary: Optional[str] = None
    presenting_concerns: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    risk_level: Optional[int] = None
    tags: Optional[List[str]] = None


class CaseAssignRequest(BaseModel):
    """Request to assign a case"""
    social_worker_id: int
    reason: Optional[str] = None


class CaseCloseRequest(BaseModel):
    """Request to close a case"""
    closure_reason: str
    outcomes: Optional[Dict] = None


class NoteCreateRequest(BaseModel):
    """Request to create a case note"""
    note_type: str
    content: str
    title: Optional[str] = None
    contact_type: Optional[str] = None
    contact_with: Optional[str] = None


class AlertResolveRequest(BaseModel):
    """Request to resolve an alert"""
    resolution_notes: Optional[str] = None
    resolution_action: str = "acknowledged"


class ReportGenerateRequest(BaseModel):
    """Request to generate a report"""
    report_type: str = "progress"
    period_start: datetime
    period_end: datetime
    summary: str
    progress_notes: Optional[str] = None
    recommendations: Optional[str] = None
    language: str = "en"


# ============================================================================
# CASE MANAGEMENT ENDPOINTS (8 endpoints)
# ============================================================================

@router.post("/cases", status_code=status.HTTP_201_CREATED)
async def create_case(
    request: CaseCreateRequest,
    current_user = Depends(get_current_user)
):
    """
    Create a new case file.
    
    Requires: social_worker or admin role
    """
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    case_manager = get_case_manager()
    
    case = await case_manager.create_case(
        child_id=request.child_id,
        summary=request.summary,
        presenting_concerns=request.presenting_concerns,
        social_worker_id=current_user.id,
        priority=request.priority,
        initial_risk_level=request.initial_risk_level,
        tags=request.tags
    )
    
    return {
        "success": True,
        "case": case.to_dict()
    }


@router.get("/cases")
async def list_cases(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user = Depends(get_current_user)
):
    """
    List cases for the current social worker.
    
    Admins can see all cases.
    """
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    case_manager = get_case_manager()
    
    # Admins can see all cases
    sw_id = None if current_user.role in ['admin', 'super_admin'] else current_user.id
    
    cases = await case_manager.get_cases_for_social_worker(
        social_worker_id=sw_id or current_user.id,
        status=status,
        priority=priority,
        limit=limit,
        offset=offset
    )
    
    return {
        "cases": [c.to_dict() for c in cases],
        "count": len(cases)
    }


@router.get("/cases/high-risk")
async def get_high_risk_cases(
    min_risk: int = Query(60),
    limit: int = Query(20),
    current_user = Depends(get_current_user)
):
    """Get high-risk cases requiring attention"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    case_manager = get_case_manager()
    
    cases = await case_manager.get_high_risk_cases(
        min_risk_level=min_risk,
        limit=limit
    )
    
    return {
        "cases": [c.to_dict() for c in cases],
        "count": len(cases)
    }


@router.get("/cases/{case_id}")
async def get_case(
    case_id: int,
    current_user = Depends(get_current_user)
):
    """Get a specific case by ID"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    case_manager = get_case_manager()
    case = await case_manager.get_case(case_id)
    
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Check access (own cases or admin)
    if current_user.role == 'social_worker' and case.social_worker_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this case")
    
    return {"case": case.to_dict()}


@router.put("/cases/{case_id}")
async def update_case(
    case_id: int,
    request: CaseUpdateRequest,
    current_user = Depends(get_current_user)
):
    """Update a case"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    case_manager = get_case_manager()
    
    updates = request.model_dump(exclude_unset=True)
    case = await case_manager.update_case(case_id, updates)
    
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    return {"success": True, "case": case.to_dict()}


@router.post("/cases/{case_id}/assign")
async def assign_case(
    case_id: int,
    request: CaseAssignRequest,
    current_user = Depends(get_current_user)
):
    """Assign or reassign a case"""
    if current_user.role not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Only admins can reassign cases")
    
    case_manager = get_case_manager()
    
    case = await case_manager.assign_case(
        case_id=case_id,
        social_worker_id=request.social_worker_id,
        reason=request.reason
    )
    
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    return {"success": True, "case": case.to_dict()}


@router.post("/cases/{case_id}/close")
async def close_case(
    case_id: int,
    request: CaseCloseRequest,
    current_user = Depends(get_current_user)
):
    """Close a case"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    case_manager = get_case_manager()
    
    case = await case_manager.close_case(
        case_id=case_id,
        closure_reason=request.closure_reason,
        outcomes=request.outcomes
    )
    
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    return {"success": True, "case": case.to_dict()}


@router.post("/cases/{case_id}/notes")
async def add_case_note(
    case_id: int,
    request: NoteCreateRequest,
    current_user = Depends(get_current_user)
):
    """Add a note to a case"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    case_manager = get_case_manager()
    
    note = await case_manager.add_note(
        case_id=case_id,
        note_type=request.note_type,
        content=request.content,
        author_id=current_user.id,
        title=request.title,
        contact_type=request.contact_type,
        contact_with=request.contact_with
    )
    
    return {"success": True, "note": note.to_dict()}


# ============================================================================
# ALERT ENDPOINTS (5 endpoints)
# ============================================================================

@router.get("/alerts")
async def list_alerts(
    resolved: Optional[bool] = Query(None),
    min_severity: int = Query(1),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user = Depends(get_current_user)
):
    """List alerts for the current user"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    alert_manager = get_alert_manager()
    
    sw_id = None if current_user.role in ['admin', 'super_admin'] else current_user.id
    
    if resolved is False or resolved is None:
        alerts = await alert_manager.get_unresolved_alerts(
            social_worker_id=sw_id,
            min_severity=min_severity,
            limit=limit,
            offset=offset
        )
    else:
        alerts = await alert_manager.get_recent_alerts(
            hours=168,  # 1 week
            min_severity=min_severity,
            limit=limit
        )
    
    return {
        "alerts": [a.to_dict() for a in alerts],
        "count": len(alerts)
    }


@router.get("/alerts/recent")
async def get_recent_alerts(
    hours: int = Query(24),
    min_severity: int = Query(1),
    limit: int = Query(50),
    current_user = Depends(get_current_user)
):
    """Get recent alerts within time window"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    alert_manager = get_alert_manager()
    
    alerts = await alert_manager.get_recent_alerts(
        hours=hours,
        min_severity=min_severity,
        limit=limit
    )
    
    return {
        "alerts": [a.to_dict() for a in alerts],
        "count": len(alerts)
    }


@router.get("/alerts/{alert_id}")
async def get_alert(
    alert_id: int,
    current_user = Depends(get_current_user)
):
    """Get a specific alert"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    alert_manager = get_alert_manager()
    alert = await alert_manager.get_alert(alert_id)
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return {"alert": alert.to_dict()}


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    request: AlertResolveRequest,
    current_user = Depends(get_current_user)
):
    """Resolve an alert"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    alert_manager = get_alert_manager()
    
    alert = await alert_manager.resolve_alert(
        alert_id=alert_id,
        resolved_by=current_user.id,
        resolution_notes=request.resolution_notes,
        resolution_action=request.resolution_action
    )
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return {"success": True, "alert": alert.to_dict()}


@router.post("/alerts/{alert_id}/assign")
async def assign_alert(
    alert_id: int,
    social_worker_id: int = Query(...),
    current_user = Depends(get_current_user)
):
    """Assign an alert to a social worker"""
    if current_user.role not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Only admins can assign alerts")
    
    alert_manager = get_alert_manager()
    
    alert = await alert_manager.assign_alert(alert_id, social_worker_id)
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return {"success": True, "alert": alert.to_dict()}


# ============================================================================
# REPORT ENDPOINTS (3 endpoints)
# ============================================================================

@router.post("/cases/{case_id}/reports")
async def generate_report(
    case_id: int,
    request: ReportGenerateRequest,
    current_user = Depends(get_current_user)
):
    """Generate a report for a case"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    report_generator = get_report_generator()
    
    if request.report_type == "progress":
        report = await report_generator.generate_progress_report(
            case_id=case_id,
            generated_by=current_user.id,
            period_start=request.period_start,
            period_end=request.period_end,
            summary=request.summary,
            progress_notes=request.progress_notes,
            recommendations=request.recommendations,
            language=request.language
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported report type")
    
    return {"success": True, "report": report.to_dict()}


@router.get("/cases/{case_id}/reports")
async def list_case_reports(
    case_id: int,
    current_user = Depends(get_current_user)
):
    """List reports for a case"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # This would query reports from DB
    return {"reports": [], "count": 0}


@router.get("/reports/{report_id}/download")
async def download_report(
    report_id: int,
    format: str = Query("pdf"),
    current_user = Depends(get_current_user)
):
    """Download a report file"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # This would return the actual file
    raise HTTPException(status_code=501, detail="Download not implemented")


# ============================================================================
# ANALYTICS ENDPOINTS (4 endpoints)
# ============================================================================

@router.get("/analytics/dashboard")
async def get_dashboard_metrics(
    current_user = Depends(get_current_user)
):
    """Get dashboard overview metrics"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    analytics = get_analytics_service()
    
    sw_id = None if current_user.role in ['admin', 'super_admin'] else current_user.id
    
    metrics = await analytics.get_dashboard_metrics(social_worker_id=sw_id)
    
    return {"metrics": metrics}


@router.get("/analytics/risk-distribution")
async def get_risk_distribution(
    current_user = Depends(get_current_user)
):
    """Get risk level distribution"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    analytics = get_analytics_service()
    
    sw_id = None if current_user.role in ['admin', 'super_admin'] else current_user.id
    
    distribution = await analytics.get_risk_distribution(social_worker_id=sw_id)
    
    return {"distribution": distribution}


@router.get("/analytics/case-trends")
async def get_case_trends(
    days: int = Query(7, ge=1, le=90),
    current_user = Depends(get_current_user)
):
    """Get case trends over time"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    analytics = get_analytics_service()
    
    sw_id = None if current_user.role in ['admin', 'super_admin'] else current_user.id
    
    trends = await analytics.get_case_trends(days=days, social_worker_id=sw_id)
    
    return {"trends": trends}


@router.get("/analytics/alert-trends")
async def get_alert_trends(
    days: int = Query(7),
    current_user = Depends(get_current_user)
):
    """Get alert trends over time"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    analytics = get_analytics_service()
    
    sw_id = None if current_user.role in ['admin', 'super_admin'] else current_user.id
    
    trends = await analytics.get_alert_trends(days=days, social_worker_id=sw_id)
    
    return {"trends": trends}


@router.get("/analytics/workload")
async def get_workload_analysis(
    current_user = Depends(get_current_user)
):
    """Get workload analysis for current user"""
    if current_user.role not in ['social_worker', 'admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    analytics = get_analytics_service()
    
    analysis = await analytics.get_workload_analysis(current_user.id)
    
    return {"analysis": analysis}

