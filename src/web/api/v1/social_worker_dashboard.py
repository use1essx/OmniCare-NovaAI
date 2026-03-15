"""
Social Worker Dashboard API
API endpoints for social workers to manage their assigned patients and view alerts
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func

from src.database.connection import get_sync_db
from src.database.models_comprehensive import (
    User,
    Conversation,
    AuditLog
)

router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class PatientSummary(BaseModel):
    """Summary of a patient's current status"""
    patient_id: int
    username: str
    full_name: Optional[str]
    email: str
    last_conversation: Optional[datetime]
    total_conversations: int
    urgent_alerts: int
    critical_alerts: int
    recent_concerns: List[Dict[str, Any]]
    last_emotion: Optional[str]
    risk_level: str  # "low", "medium", "high", "critical"
    
    class Config:
        from_attributes = True


class AlertDetail(BaseModel):
    """Detailed information about an alert"""
    alert_id: int
    patient_id: int
    patient_name: str
    alert_type: str  # "bullying", "self_harm", "family_violence", etc.
    severity_level: str  # "info", "warning", "critical"
    event_description: str
    details: Dict[str, Any]
    created_at: datetime
    is_read: bool
    is_resolved: bool
    
    class Config:
        from_attributes = True


class PatientAssignment(BaseModel):
    """Request to assign/unassign a patient"""
    patient_id: int
    social_worker_id: int


class DashboardStats(BaseModel):
    """Overall statistics for social worker dashboard"""
    total_patients: int
    active_patients_24h: int
    total_alerts: int
    unread_alerts: int
    critical_alerts: int
    patients_at_risk: int
    
    
# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_risk_level(
    urgent_alerts: int,
    critical_alerts: int,
    recent_conversations: int,
    last_conversation_hours: Optional[float]
) -> str:
    """Calculate patient risk level based on various factors"""
    
    # Critical: Has critical alerts or very urgent situation
    if critical_alerts > 0:
        return "critical"
    
    # High: Multiple urgent alerts or recent concerning activity
    if urgent_alerts >= 3 or (urgent_alerts >= 1 and last_conversation_hours and last_conversation_hours < 2):
        return "high"
    
    # Medium: Some urgent alerts or lack of recent activity
    if urgent_alerts > 0 or (last_conversation_hours and last_conversation_hours > 72):
        return "medium"
    
    # Low: No alerts and regular activity
    return "low"


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/social-worker/dashboard/stats", response_model=DashboardStats)
async def get_social_worker_stats(
    social_worker_id: int = Query(..., description="Social worker user ID"),
    db: Session = Depends(get_sync_db)
):
    """
    Get overall statistics for social worker dashboard
    
    This endpoint provides a summary of all patients assigned to the social worker
    and their current alert status.
    """
    
    # Verify social worker exists
    social_worker = db.query(User).filter(User.id == social_worker_id).first()
    if not social_worker:
        raise HTTPException(status_code=404, detail="Social worker not found")
    
    # Get all patients assigned to this social worker
    patients = db.query(User).filter(
        User.assigned_caregiver_id == social_worker_id
    ).all()
    
    patient_ids = [p.id for p in patients]
    
    # Calculate stats
    total_patients = len(patients)
    
    # Active patients in last 24h
    last_24h = datetime.utcnow() - timedelta(hours=24)
    active_patients = db.query(func.count(func.distinct(Conversation.user_id))).filter(
        and_(
            Conversation.user_id.in_(patient_ids),
            Conversation.created_at >= last_24h
        )
    ).scalar() or 0
    
    # Total alerts (last 7 days)
    last_7days = datetime.utcnow() - timedelta(days=7)
    total_alerts = db.query(func.count(AuditLog.id)).filter(
        and_(
            AuditLog.user_id.in_(patient_ids),
            AuditLog.event_type.in_(['alert_social_worker', 'record_concern']),
            AuditLog.created_at >= last_7days
        )
    ).scalar() or 0
    
    # Unread alerts (not marked as read - we'll add this field later)
    # For now, count alerts from last 24 hours as "unread"
    unread_alerts = db.query(func.count(AuditLog.id)).filter(
        and_(
            AuditLog.user_id.in_(patient_ids),
            AuditLog.event_type.in_(['alert_social_worker', 'record_concern']),
            AuditLog.created_at >= last_24h
        )
    ).scalar() or 0
    
    # Critical alerts
    critical_alerts = db.query(func.count(AuditLog.id)).filter(
        and_(
            AuditLog.user_id.in_(patient_ids),
            AuditLog.severity_level == 'critical',
            AuditLog.created_at >= last_7days
        )
    ).scalar() or 0
    
    # Count patients at risk (have critical or multiple urgent alerts)
    patients_at_risk = 0
    for patient_id in patient_ids:
        patient_critical = db.query(func.count(AuditLog.id)).filter(
            and_(
                AuditLog.user_id == patient_id,
                AuditLog.severity_level == 'critical',
                AuditLog.created_at >= last_7days
            )
        ).scalar() or 0
        
        patient_urgent = db.query(func.count(AuditLog.id)).filter(
            and_(
                AuditLog.user_id == patient_id,
                AuditLog.severity_level.in_(['warning', 'high']),
                AuditLog.created_at >= last_7days
            )
        ).scalar() or 0
        
        if patient_critical > 0 or patient_urgent >= 2:
            patients_at_risk += 1
    
    return DashboardStats(
        total_patients=total_patients,
        active_patients_24h=active_patients,
        total_alerts=total_alerts,
        unread_alerts=unread_alerts,
        critical_alerts=critical_alerts,
        patients_at_risk=patients_at_risk
    )


@router.get("/social-worker/patients", response_model=List[PatientSummary])
async def get_assigned_patients(
    social_worker_id: int = Query(..., description="Social worker user ID"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    db: Session = Depends(get_sync_db)
):
    """
    Get all patients assigned to a social worker with their current status
    
    This endpoint returns detailed information about each patient including:
    - Recent activity
    - Alert counts
    - Risk level assessment
    """
    
    # Get all patients assigned to this social worker
    patients = db.query(User).filter(
        User.assigned_caregiver_id == social_worker_id
    ).all()
    
    patient_summaries = []
    last_7days = datetime.utcnow() - timedelta(days=7)
    
    for patient in patients:
        # Get last conversation
        last_conv = db.query(Conversation).filter(
            Conversation.user_id == patient.id
        ).order_by(desc(Conversation.created_at)).first()
        
        # Total conversations
        total_convs = db.query(func.count(Conversation.id)).filter(
            Conversation.user_id == patient.id
        ).scalar() or 0
        
        # Count urgent and critical alerts (last 7 days)
        urgent_count = db.query(func.count(AuditLog.id)).filter(
            and_(
                AuditLog.user_id == patient.id,
                AuditLog.severity_level.in_(['warning', 'high']),
                AuditLog.created_at >= last_7days
            )
        ).scalar() or 0
        
        critical_count = db.query(func.count(AuditLog.id)).filter(
            and_(
                AuditLog.user_id == patient.id,
                AuditLog.severity_level == 'critical',
                AuditLog.created_at >= last_7days
            )
        ).scalar() or 0
        
        # Get recent concerns
        recent_alerts = db.query(AuditLog).filter(
            and_(
                AuditLog.user_id == patient.id,
                AuditLog.event_type.in_(['alert_social_worker', 'record_concern']),
                AuditLog.created_at >= last_7days
            )
        ).order_by(desc(AuditLog.created_at)).limit(5).all()
        
        recent_concerns = []
        for alert in recent_alerts:
            recent_concerns.append({
                "type": alert.event_type,
                "description": alert.event_description[:100],
                "severity": alert.severity_level,
                "created_at": alert.created_at.isoformat()
            })
        
        # Get last detected emotion (from most recent log_emotion event)
        last_emotion_log = db.query(AuditLog).filter(
            and_(
                AuditLog.user_id == patient.id,
                AuditLog.event_type == 'log_emotion'
            )
        ).order_by(desc(AuditLog.created_at)).first()
        
        last_emotion = None
        if last_emotion_log and last_emotion_log.target_details:
            last_emotion = last_emotion_log.target_details.get('emotion_type')
        
        # Calculate hours since last conversation
        hours_since_last = None
        if last_conv:
            hours_since_last = (datetime.utcnow() - last_conv.created_at).total_seconds() / 3600
        
        # Calculate risk level
        risk = calculate_risk_level(
            urgent_alerts=urgent_count,
            critical_alerts=critical_count,
            recent_conversations=total_convs,
            last_conversation_hours=hours_since_last
        )
        
        # Apply filter if specified
        if risk_level and risk != risk_level:
            continue
        
        patient_summaries.append(PatientSummary(
            patient_id=patient.id,
            username=patient.username,
            full_name=patient.full_name,
            email=patient.email,
            last_conversation=last_conv.created_at if last_conv else None,
            total_conversations=total_convs,
            urgent_alerts=urgent_count,
            critical_alerts=critical_count,
            recent_concerns=recent_concerns,
            last_emotion=last_emotion,
            risk_level=risk
        ))
    
    # Sort by risk level (critical first)
    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    patient_summaries.sort(key=lambda x: risk_order.get(x.risk_level, 999))
    
    return patient_summaries


@router.get("/social-worker/alerts", response_model=List[AlertDetail])
async def get_patient_alerts(
    social_worker_id: int = Query(..., description="Social worker user ID"),
    patient_id: Optional[int] = Query(None, description="Filter by specific patient"),
    severity: Optional[str] = Query(None, description="Filter by severity level"),
    days: int = Query(7, description="Number of days to look back"),
    db: Session = Depends(get_sync_db)
):
    """
    Get all alerts for patients assigned to a social worker
    
    This endpoint returns detailed alert information including:
    - Alert type and severity
    - Patient information
    - Full event details
    """
    
    # Get all patients assigned to this social worker
    patients = db.query(User).filter(
        User.assigned_caregiver_id == social_worker_id
    ).all()
    
    patient_ids = [p.id for p in patients]
    patient_map = {p.id: p for p in patients}
    
    # Apply patient filter if specified
    if patient_id:
        if patient_id not in patient_ids:
            raise HTTPException(status_code=403, detail="Patient not assigned to this social worker")
        patient_ids = [patient_id]
    
    # Build query
    lookback = datetime.utcnow() - timedelta(days=days)
    query = db.query(AuditLog).filter(
        and_(
            AuditLog.user_id.in_(patient_ids),
            AuditLog.event_type.in_(['alert_social_worker', 'record_concern']),
            AuditLog.created_at >= lookback
        )
    )
    
    # Apply severity filter
    if severity:
        query = query.filter(AuditLog.severity_level == severity)
    
    # Get alerts ordered by newest first
    alerts = query.order_by(desc(AuditLog.created_at)).all()
    
    # Format response
    alert_details = []
    for alert in alerts:
        patient = patient_map.get(alert.user_id)
        patient_name = patient.full_name or patient.username if patient else "Unknown"
        
        # Determine alert type from details
        alert_type = "general"
        if alert.target_details:
            alert_type = alert.target_details.get('concern_type') or alert.target_details.get('alert_type', 'general')
        
        alert_details.append(AlertDetail(
            alert_id=alert.id,
            patient_id=alert.user_id or 0,
            patient_name=patient_name,
            alert_type=alert_type,
            severity_level=alert.severity_level or "info",
            event_description=alert.event_description,
            details=alert.target_details or {},
            created_at=alert.created_at,
            is_read=False,  # TODO: Add read tracking
            is_resolved=False  # TODO: Add resolution tracking
        ))
    
    return alert_details


# =============================================================================
# COMPATIBILITY ENDPOINTS (for admin UI)
# The admin UI expects path-parameter endpoints like:
#   /api/v1/social-worker/info/{id}
#   /api/v1/social-worker/patients/{id}
#   /api/v1/social-worker/alerts/{id}
# Provide thin wrappers that delegate to the canonical query-param endpoints.
# =============================================================================

@router.get("/social-worker/info/{social_worker_id}")
async def get_social_worker_info_compat(
    social_worker_id: int,
    db: Session = Depends(get_sync_db)
):
    """Compatibility wrapper that returns dashboard stats for a social worker."""
    return await get_social_worker_stats(social_worker_id=social_worker_id, db=db)


@router.get("/social-worker/patients/{social_worker_id}")
async def get_assigned_patients_compat(
    social_worker_id: int,
    db: Session = Depends(get_sync_db)
):
    """Compatibility wrapper that returns patients assigned to a social worker."""
    return await get_assigned_patients(social_worker_id=social_worker_id, db=db)


@router.get("/social-worker/alerts/{social_worker_id}")
async def get_patient_alerts_compat(
    social_worker_id: int,
    db: Session = Depends(get_sync_db)
):
    """Compatibility wrapper that returns alerts for a social worker's patients."""
    try:
        return await get_patient_alerts(social_worker_id=social_worker_id, db=db)
    except HTTPException as exc:
        # For admin UI friendliness: if forbidden or not available, return empty list
        if exc.status_code in (403, 404):
            return []
        raise

@router.post("/social-worker/assign-patient")
async def assign_patient_to_social_worker(
    assignment: PatientAssignment,
    db: Session = Depends(get_sync_db)
):
    """
    Assign a patient to a social worker
    
    This allows administrators to assign patients to specific social workers
    for case management.
    """
    
    # Verify both users exist
    social_worker = db.query(User).filter(User.id == assignment.social_worker_id).first()
    if not social_worker:
        raise HTTPException(status_code=404, detail="Social worker not found")
    
    patient = db.query(User).filter(User.id == assignment.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Update patient's assigned caregiver
    patient.assigned_caregiver_id = assignment.social_worker_id
    patient.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Patient {patient.username} assigned to social worker {social_worker.username}",
        "patient_id": patient.id,
        "social_worker_id": social_worker.id
    }


@router.delete("/social-worker/unassign-patient/{patient_id}")
async def unassign_patient(
    patient_id: int,
    db: Session = Depends(get_sync_db)
):
    """
    Remove a patient's assignment from their social worker
    """
    
    patient = db.query(User).filter(User.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    if not patient.assigned_caregiver_id:
        raise HTTPException(status_code=400, detail="Patient is not assigned to any social worker")
    
    patient.assigned_caregiver_id = None
    patient.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Patient {patient.username} unassigned from social worker",
        "patient_id": patient.id
    }


@router.get("/social-worker/patient/{patient_id}/history")
async def get_patient_conversation_history(
    patient_id: int,
    social_worker_id: int = Query(..., description="Social worker user ID"),
    days: int = Query(30, description="Number of days to look back"),
    db: Session = Depends(get_sync_db)
):
    """
    Get full conversation history for a specific patient
    
    This allows social workers to review all conversations and interactions
    with their assigned patients.
    """
    
    # Verify patient is assigned to this social worker
    patient = db.query(User).filter(User.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    if patient.assigned_caregiver_id != social_worker_id:
        raise HTTPException(status_code=403, detail="Patient not assigned to this social worker")
    
    # Get conversation history
    lookback = datetime.utcnow() - timedelta(days=days)
    conversations = db.query(Conversation).filter(
        and_(
            Conversation.user_id == patient_id,
            Conversation.created_at >= lookback
        )
    ).order_by(desc(Conversation.created_at)).all()
    
    # Get alert history
    alerts = db.query(AuditLog).filter(
        and_(
            AuditLog.user_id == patient_id,
            AuditLog.created_at >= lookback
        )
    ).order_by(desc(AuditLog.created_at)).all()
    
    return {
        "patient_id": patient_id,
        "patient_name": patient.full_name or patient.username,
        "total_conversations": len(conversations),
        "total_alerts": len(alerts),
        "conversations": [
            {
                "id": conv.id,
                "user_input": conv.user_input,
                "agent_response": conv.agent_response,
                "agent_type": conv.agent_type,
                "urgency_level": conv.urgency_level,
                "sentiment_score": float(conv.sentiment_score) if conv.sentiment_score else None,
                "created_at": conv.created_at.isoformat()
            }
            for conv in conversations
        ],
        "alerts": [
            {
                "id": alert.id,
                "event_type": alert.event_type,
                "severity_level": alert.severity_level,
                "event_description": alert.event_description,
                "details": alert.target_details,
                "created_at": alert.created_at.isoformat()
            }
            for alert in alerts
        ]
    }

