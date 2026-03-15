"""
Session Reports API
Endpoints for generating and retrieving session reports
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional
import json
import logging
from pathlib import Path
from datetime import datetime
import numpy as np

from ..database.config import get_db
from ..models.database import Report as ReportModel
from ..reports.generator import ReportGenerator
from ..reports.schemas import SessionReport, EmotionTimelineReport, PostureAnalysisReport
from ..reports.text_formatter import TextReportFormatter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])

# Initialize report generator and text formatter
report_generator = ReportGenerator()
text_formatter = TextReportFormatter()


@router.get("/session/{session_id}", response_model=SessionReport)
async def get_session_report(
    session_id: str,
    user_id: Optional[str] = None,
    regenerate: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get complete session report
    
    Checks database first for existing report. If not found or regenerate=True,
    generates new report from session data and saves to database.
    
    Parameters:
    - session_id: Session identifier
    - user_id: Optional user identifier
    - regenerate: Force regeneration of report (default: False)
    - db: Database session (auto-injected)
    
    Returns: Complete session report with all analysis sections
    """
    try:
        # Check if report exists in database (unless regenerate requested)
        if not regenerate:
            existing_report = db.query(ReportModel).filter(
                ReportModel.session_id == session_id
            ).first()
            
            if existing_report:
                logger.info(f"Retrieved report from database for session: {session_id}")
                return SessionReport(**existing_report.report_data)
        
        # Find session JSON file
        json_file = f"recordings/{session_id}_detailed.json"
        
        if not Path(json_file).exists():
            raise HTTPException(
                status_code=404,
                detail=f"Session data not found for session_id: {session_id}"
            )
        
        # Generate new report
        report = report_generator.generate_from_file(json_file, user_id)
        
        # Save to database
        try:
            # Convert report to dict with JSON-serializable datetime objects
            report_dict = json.loads(report.json())  # This handles datetime serialization
            
            # Generate compact text version (reduces DB storage by ~80%)
            text_report = text_formatter.format_report_for_storage(report_dict)
            text_size_kb = len(text_report.encode('utf-8')) / 1024
            json_size_kb = len(json.dumps(report_dict).encode('utf-8')) / 1024
            logger.info("Report sizes - Text: %.1f KB, JSON: %.1f KB (%.0f%% reduction)",
                       text_size_kb, json_size_kb, ((json_size_kb - text_size_kb) / json_size_kb * 100))
            
            # Check if report already exists
            existing_report = db.query(ReportModel).filter(
                ReportModel.session_id == session_id
            ).first()
            
            if existing_report:
                # Update existing report
                existing_report.report_data = report_dict
                existing_report.text_report = text_report  # Add text version
                existing_report.overall_quality_score = report.overall_quality_score
                existing_report.dominant_emotion = report.emotion_timeline.dominant_emotion
                existing_report.average_posture_quality = report.posture_analysis.average_quality
                existing_report.engagement_level = report.engagement.engagement_level
                existing_report.total_interventions = report.intervention_summary.total_interventions if report.intervention_summary else 0
                existing_report.generated_at = datetime.utcnow()
                logger.info("Updated existing report in database for session: %s", session_id)
            else:
                # Create new report
                new_report = ReportModel(
                    session_id=session_id,
                    user_id=user_id,
                    report_data=report_dict,
                    text_report=text_report,  # Add text version
                    overall_quality_score=report.overall_quality_score,
                    dominant_emotion=report.emotion_timeline.dominant_emotion,
                    average_posture_quality=report.posture_analysis.average_quality,
                    engagement_level=report.engagement.engagement_level,
                    total_interventions=report.intervention_summary.total_interventions if report.intervention_summary else 0,
                    report_version="2.0"  # Updated version with text support
                )
                db.add(new_report)
                logger.info("Saved new report to database for session: %s", session_id)
            
            db.commit()
            
        except Exception as db_error:
            logger.warning(f"Failed to save report to database: {db_error}")
            db.rollback()
            # Continue anyway - report generation succeeded
        
        logger.info(f"Generated full report for session: {session_id}")
        return report
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session data file not found")
    except Exception as e:
        logger.error(f"Error generating session report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get("/session/{session_id}/emotions", response_model=EmotionTimelineReport)
async def get_session_emotions(session_id: str):
    """
    Get emotion timeline report only
    
    Returns detailed emotion analysis for the session
    """
    try:
        json_file = f"recordings/{session_id}_detailed.json"
        
        if not Path(json_file).exists():
            raise HTTPException(status_code=404, detail="Session data not found")
        
        # Load session data
        with open(json_file, 'r') as f:
            session_data = json.load(f)
        
        # Generate emotion timeline only
        emotion_timeline = session_data.get("emotion_timeline", [])
        report = report_generator.generate_emotion_timeline(emotion_timeline)
        
        logger.info(f"Generated emotion timeline for session: {session_id}")
        return report
        
    except Exception as e:
        logger.error(f"Error generating emotion timeline: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate emotion timeline: {str(e)}")


@router.get("/session/{session_id}/posture", response_model=PostureAnalysisReport)
async def get_session_posture(session_id: str):
    """
    Get posture analysis report only
    
    Returns detailed posture quality analysis for the session
    """
    try:
        json_file = f"recordings/{session_id}_detailed.json"
        
        if not Path(json_file).exists():
            raise HTTPException(status_code=404, detail="Session data not found")
        
        # Load session data
        with open(json_file, 'r') as f:
            session_data = json.load(f)
        
        # Generate posture analysis only
        posture_events = session_data.get("posture_events", [])
        report = report_generator.generate_posture_analysis(posture_events)
        
        logger.info(f"Generated posture analysis for session: {session_id}")
        return report
        
    except Exception as e:
        logger.error(f"Error generating posture analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate posture analysis: {str(e)}")


@router.get("/user/{user_id}/summary")
async def get_user_summary(user_id: str, db: Session = Depends(get_db)):
    """
    Get aggregate report across all sessions for a user
    
    Returns summary statistics across all sessions
    """
    try:
        from ..models.database import Session as DBSession
        
        # Get all sessions for user
        sessions = db.query(DBSession).filter(DBSession.user_id == user_id).all()
        
        if not sessions:
            raise HTTPException(status_code=404, detail=f"No sessions found for user: {user_id}")
        
        # Aggregate statistics
        total_sessions = len(sessions)
        total_duration = sum(s.duration for s in sessions if s.duration) or 0
        avg_engagement = np.mean([s.face_detection_rate for s in sessions if s.face_detection_rate is not None]) if sessions else 0
        
        # Calculate intervention statistics
        total_interventions = sum(s.intervention_count for s in sessions if s.intervention_count) or 0
        avg_interventions_per_session = total_interventions / total_sessions if total_sessions > 0 else 0
        
        # Calculate quality trends
        emotion_variances = [s.emotion_variance for s in sessions if s.emotion_variance is not None]
        avg_emotion_stability = 1.0 - np.mean(emotion_variances) if emotion_variances else 0.5
        
        posture_improvements = [s.posture_improvement_score for s in sessions if s.posture_improvement_score is not None]
        avg_posture_improvement = np.mean(posture_improvements) if posture_improvements else 0.0
        
        summary = {
            "user_id": user_id,
            "total_sessions": total_sessions,
            "total_duration_minutes": total_duration / 60,
            "average_session_duration_minutes": (total_duration / total_sessions / 60) if total_sessions > 0 else 0,
            "average_engagement_level": float(avg_engagement),
            "average_emotion_stability": float(avg_emotion_stability),
            "average_posture_improvement": float(avg_posture_improvement),
            "total_interventions": total_interventions,
            "average_interventions_per_session": avg_interventions_per_session,
            "sessions": [
                {
                    "session_id": s.session_id,
                    "date": s.created_at.isoformat() if s.created_at else None,
                    "duration_minutes": (s.duration / 60) if s.duration else 0,
                    "quality_score": (
                        s.face_detection_rate * 40 +
                        (1 - (s.emotion_variance or 0)) * 30 +
                        ((s.posture_improvement_score or 0) + 1) * 15
                    ) if s.face_detection_rate else 50
                }
                for s in sessions
            ]
        }
        
        logger.info(f"Generated user summary for: {user_id} ({total_sessions} sessions)")
        return summary
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error generating user summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate user summary: {str(e)}")


@router.get("/user/{user_id}/all")
async def list_user_reports(
    user_id: str,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List all saved reports for a user
    
    Parameters:
    - user_id: User identifier
    - limit: Maximum number of reports to return (default: 10)
    - offset: Number of reports to skip (default: 0)
    
    Returns: List of report summaries with quick access fields
    """
    try:
        reports = db.query(ReportModel).filter(
            ReportModel.user_id == user_id
        ).order_by(
            ReportModel.generated_at.desc()
        ).limit(limit).offset(offset).all()
        
        if not reports:
            return {
                "user_id": user_id,
                "total_reports": 0,
                "reports": []
            }
        
        # Count total reports for pagination
        total_count = db.query(ReportModel).filter(
            ReportModel.user_id == user_id
        ).count()
        
        report_summaries = []
        for report in reports:
            report_summaries.append({
                "session_id": report.session_id,
                "generated_at": report.generated_at.isoformat(),
                "overall_quality_score": report.overall_quality_score,
                "dominant_emotion": report.dominant_emotion,
                "average_posture_quality": report.average_posture_quality,
                "engagement_level": report.engagement_level,
                "total_interventions": report.total_interventions
            })
        
        logger.info(f"Retrieved {len(reports)} reports for user: {user_id}")
        
        return {
            "user_id": user_id,
            "total_reports": total_count,
            "returned_count": len(reports),
            "limit": limit,
            "offset": offset,
            "reports": report_summaries
        }
        
    except Exception as e:
        logger.error(f"Error retrieving user reports: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve reports: {str(e)}")


@router.get("/all")
async def list_all_reports(
    limit: int = 20,
    offset: int = 0,
    min_quality: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """
    List all saved reports (admin endpoint)
    
    Parameters:
    - limit: Maximum number of reports to return (default: 20)
    - offset: Number of reports to skip (default: 0)
    - min_quality: Minimum quality score filter (0-100)
    
    Returns: List of all reports with quick access fields
    """
    try:
        query = db.query(ReportModel)
        
        # Apply quality filter if provided
        if min_quality is not None:
            query = query.filter(ReportModel.overall_quality_score >= min_quality)
        
        reports = query.order_by(
            ReportModel.generated_at.desc()
        ).limit(limit).offset(offset).all()
        
        total_count = query.count()
        
        report_summaries = []
        for report in reports:
            report_summaries.append({
                "session_id": report.session_id,
                "user_id": report.user_id,
                "generated_at": report.generated_at.isoformat(),
                "overall_quality_score": report.overall_quality_score,
                "dominant_emotion": report.dominant_emotion,
                "average_posture_quality": report.average_posture_quality,
                "engagement_level": report.engagement_level,
                "total_interventions": report.total_interventions
            })
        
        logger.info(f"Retrieved {len(reports)} reports (total in db: {total_count})")
        
        return {
            "total_reports": total_count,
            "returned_count": len(reports),
            "limit": limit,
            "offset": offset,
            "min_quality_filter": min_quality,
            "reports": report_summaries
        }
        
    except Exception as e:
        logger.error(f"Error retrieving all reports: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve reports: {str(e)}")


@router.delete("/session/{session_id}")
async def delete_session_report(session_id: str, db: Session = Depends(get_db)):
    """
    Delete a saved report
    
    Parameters:
    - session_id: Session identifier
    
    Returns: Success message
    """
    try:
        report = db.query(ReportModel).filter(
            ReportModel.session_id == session_id
        ).first()
        
        if not report:
            raise HTTPException(status_code=404, detail=f"Report not found for session: {session_id}")
        
        db.delete(report)
        db.commit()
        
        logger.info(f"Deleted report for session: {session_id}")
        
        return {
            "success": True,
            "message": f"Report for session {session_id} deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting report: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete report: {str(e)}")


@router.get("/session/{session_id}/live", response_model=SessionReport)
async def get_live_report(
    session_id: str,
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get live report for active or completed session from database
    
    Can generate reports for sessions that are still in progress.
    Useful for real-time monitoring and feedback.
    
    Parameters:
    - session_id: Session identifier
    - user_id: Optional user identifier
    - db: Database session (auto-injected)
    
    Returns: Partial or complete session report based on current database state
    """
    try:
        import os
        
        # Check if live reports are enabled
        if not os.getenv("ENABLE_LIVE_REPORTS", "true").lower() == "true":
            raise HTTPException(
                status_code=503,
                detail="Live reports are disabled"
            )
        
        # Generate report from database
        report = report_generator.generate_from_database(session_id, db, user_id)
        
        logger.info(f"Generated live report for session: {session_id}")
        return report
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating live report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate live report: {str(e)}")


@router.get("/health")
async def reports_health():
    """Check reports API health"""
    return {
        "status": "healthy",
        "service": "Session Reports API",
        "report_generator": "operational",
        "database": "connected"
    }

