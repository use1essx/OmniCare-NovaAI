"""
Report Generator
Generates comprehensive post-session reports from recorded data
"""

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import numpy as np
import asyncio

from .schemas import (
    EmotionChange,
    EmotionTimelineReport,
    PostureEvent,
    PostureAnalysisReport,
    EngagementReport,
    BehavioralPattern,
    BehavioralInsightsReport,
    InterventionSummary,
    SessionReport,
    AIInsights,
    DetailedTimelinePoint,
    KeyMoment,
    BehavioralPatternAI
)
from .ai_analyzer import AIReportAnalyzer

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generates comprehensive reports from session data with AI insights
    """
    
    def __init__(self):
        """Initialize report generator with AI analyzer"""
        self.ai_analyzer = AIReportAnalyzer()
        ai_status = 'enabled' if self.ai_analyzer.is_enabled() else 'disabled'
        logger.info("ReportGenerator initialized (AI: %s)", ai_status)
    
    def generate_emotion_timeline(
        self,
        emotion_timeline: List[Dict]
    ) -> EmotionTimelineReport:
        """
        Generate emotion timeline report
        
        Args:
            emotion_timeline: List of {timestamp, emotion, confidence}
            
        Returns:
            EmotionTimelineReport
        """
        if not emotion_timeline:
            return EmotionTimelineReport(
                dominant_emotion="neutral",
                dominant_percentage=100.0,
                emotion_distribution={"neutral": 100.0},
                emotion_changes=[],
                emotion_stability=1.0,
                total_changes=0
            )
        
        # Calculate emotion distribution
        emotion_counts: Dict[str, int] = {}
        for point in emotion_timeline:
            emotion = point["emotion"]
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        
        total = len(emotion_timeline)
        distribution = {
            emotion: (count / total) * 100
            for emotion, count in emotion_counts.items()
        }
        
        # Find dominant emotion
        dominant = max(distribution.items(), key=lambda x: x[1])
        
        # Detect emotion changes
        changes = []
        for i in range(1, len(emotion_timeline)):
            if emotion_timeline[i]["emotion"] != emotion_timeline[i-1]["emotion"]:
                changes.append(EmotionChange(
                    timestamp=emotion_timeline[i]["timestamp"],
                    from_emotion=emotion_timeline[i-1]["emotion"],
                    to_emotion=emotion_timeline[i]["emotion"],
                    confidence=emotion_timeline[i]["confidence"]
                ))
        
        # Calculate stability (inverse of change rate)
        stability = 1.0 - (len(changes) / total if total > 0 else 0)
        
        return EmotionTimelineReport(
            dominant_emotion=dominant[0],
            dominant_percentage=dominant[1],
            emotion_distribution=distribution,
            emotion_changes=changes,
            emotion_stability=stability,
            total_changes=len(changes)
        )
    
    def generate_posture_analysis(
        self,
        posture_events: List[Dict]
    ) -> PostureAnalysisReport:
        """
        Generate posture analysis report
        
        Args:
            posture_events: List of {timestamp, event_type, severity}
            
        Returns:
            PostureAnalysisReport
        """
        if not posture_events:
            return PostureAnalysisReport(
                average_quality="good",
                quality_distribution={"good": 100.0},
                slouch_events=[],
                total_slouches=0,
                improvement_score=0.0,
                posture_stability=1.0
            )
        
        # Extract quality events (excluding slouch events)
        quality_events = [
            e for e in posture_events
            if e["event_type"].endswith("_posture")
        ]
        
        # Calculate quality distribution
        quality_counts: Dict[str, int] = {}
        for event in quality_events:
            quality = event["event_type"].replace("_posture", "")
            quality_counts[quality] = quality_counts.get(quality, 0) + 1
        
        total_quality = len(quality_events) if quality_events else 1
        quality_distribution = {
            quality: (count / total_quality) * 100
            for quality, count in quality_counts.items()
        }
        
        # Determine average quality
        quality_scores = {"excellent": 4, "good": 3, "fair": 2, "poor": 1}
        if quality_distribution:
            avg_score = sum(
                quality_scores.get(q, 2) * (pct / 100)
                for q, pct in quality_distribution.items()
            )
            if avg_score >= 3.5:
                average_quality = "excellent"
            elif avg_score >= 2.5:
                average_quality = "good"
            elif avg_score >= 1.5:
                average_quality = "fair"
            else:
                average_quality = "poor"
        else:
            average_quality = "good"
        
        # Extract slouch events
        slouch_events_list = [
            PostureEvent(
                timestamp=e["timestamp"],
                event_type=e["event_type"],
                severity=e["severity"]
            )
            for e in posture_events
            if e["event_type"] == "slouch"
        ]
        
        # Calculate improvement score
        if len(posture_events) >= 10:
            mid = len(posture_events) // 2
            first_half = posture_events[:mid]
            second_half = posture_events[mid:]
            
            first_avg = np.mean([e["severity"] for e in first_half])
            second_avg = np.mean([e["severity"] for e in second_half])
            
            improvement = first_avg - second_avg  # Positive = improved
        else:
            improvement = 0.0
        
        # Calculate stability
        if len(posture_events) > 1:
            severity_changes = sum(
                1 for i in range(1, len(posture_events))
                if abs(posture_events[i]["severity"] - posture_events[i-1]["severity"]) > 0.2
            )
            stability = 1.0 - (severity_changes / len(posture_events))
        else:
            stability = 1.0
        
        return PostureAnalysisReport(
            average_quality=average_quality,
            quality_distribution=quality_distribution,
            slouch_events=slouch_events_list,
            total_slouches=len(slouch_events_list),
            improvement_score=max(-1.0, min(1.0, improvement)),
            posture_stability=stability
        )
    
    def generate_engagement_metrics(
        self,
        total_frames: int,
        face_detected_frames: int,
        eye_contact_scores: Optional[List[float]] = None,
        duration_sec: float = 0
    ) -> EngagementReport:
        """
        Generate engagement metrics report
        
        Args:
            total_frames: Total number of frames
            face_detected_frames: Number of frames with face detected
            eye_contact_scores: List of eye contact scores (optional)
            duration_sec: Session duration in seconds
            
        Returns:
            EngagementReport
        """
        # Face detection rate
        face_rate = face_detected_frames / total_frames if total_frames > 0 else 0
        
        # Eye contact average
        eye_contact_avg = None
        if eye_contact_scores:
            eye_contact_avg = np.mean(eye_contact_scores)
        
        # Overall engagement level
        if eye_contact_avg is not None:
            engagement = 0.6 * face_rate + 0.4 * eye_contact_avg
        else:
            engagement = face_rate
        
        # Estimate attention span (time until engagement drops below 70%)
        # Simplified: use session duration if engagement is good
        attention_span = duration_sec / 60 if engagement >= 0.7 else (duration_sec / 60) * 0.5
        
        return EngagementReport(
            face_detection_rate=face_rate,
            average_eye_contact=eye_contact_avg,
            engagement_level=engagement,
            attention_span_minutes=attention_span
        )
    
    def generate_behavioral_insights(
        self,
        emotion_timeline: List[Dict],
        posture_events: List[Dict],
        engagement_level: float,
        duration_sec: float
    ) -> BehavioralInsightsReport:
        """
        Generate behavioral insights and patterns
        
        Args:
            emotion_timeline: Emotion timeline data
            posture_events: Posture events data
            engagement_level: Overall engagement level
            duration_sec: Session duration in seconds
            
        Returns:
            BehavioralInsightsReport
        """
        patterns = []
        findings = []
        recommendations = []
        
        # Pattern 1: Emotion stability
        if len(emotion_timeline) > 10:
            changes = sum(
                1 for i in range(1, len(emotion_timeline))
                if emotion_timeline[i]["emotion"] != emotion_timeline[i-1]["emotion"]
            )
            change_rate = changes / len(emotion_timeline)
            
            if change_rate > 0.3:
                patterns.append(BehavioralPattern(
                    pattern_type="high_emotion_variability",
                    description="Emotions change frequently during the session",
                    confidence=0.8,
                    recommendation="Consider shorter, more focused sessions"
                ))
                findings.append("High emotional variability detected")
            elif change_rate < 0.1:
                patterns.append(BehavioralPattern(
                    pattern_type="stable_emotions",
                    description="Emotions remain very stable throughout session",
                    confidence=0.9
                ))
                findings.append("Excellent emotional stability")
        
        # Pattern 2: Posture decline over time
        if len(posture_events) >= 10:
            mid = len(posture_events) // 2
            first_half_severity = np.mean([e["severity"] for e in posture_events[:mid]])
            second_half_severity = np.mean([e["severity"] for e in posture_events[mid:]])
            
            if second_half_severity > first_half_severity + 0.2:
                patterns.append(BehavioralPattern(
                    pattern_type="posture_fatigue",
                    description="Posture quality declines as session progresses",
                    confidence=0.75,
                    recommendation="Take regular breaks to maintain good posture"
                ))
                findings.append("Posture tends to worsen over time")
                recommendations.append("Set up posture reminders every 15 minutes")
        
        # Pattern 3: Low engagement
        if engagement_level < 0.5:
            patterns.append(BehavioralPattern(
                pattern_type="low_engagement",
                description="Overall engagement level is below optimal",
                confidence=0.85,
                recommendation="Adjust camera position and lighting"
            ))
            findings.append("Low engagement detected")
            recommendations.append("Ensure proper camera setup and good lighting")
        
        # Pattern 4: Long session without breaks
        if duration_sec > 2700 and len([p for p in patterns if p.pattern_type == "posture_fatigue"]) > 0:  # 45 minutes
            recommendations.append("Consider taking breaks every 30 minutes")
            findings.append("Extended session may benefit from scheduled breaks")
        
        # General recommendations
        if not recommendations:
            recommendations.append("Maintain current practices - session quality is good")
        
        if not findings:
            findings.append("No significant behavioral patterns detected")
        
        return BehavioralInsightsReport(
            patterns_detected=patterns,
            key_findings=findings,
            recommendations=recommendations
        )
    
    def generate_full_report(
        self,
        session_id: str,
        session_data: Dict,
        user_id: Optional[str] = None
    ) -> SessionReport:
        """
        Generate complete session report
        
        Args:
            session_id: Session identifier
            session_data: Complete session data from recorder
            user_id: User identifier (optional)
            
        Returns:
            Complete SessionReport
        """
        # Extract data
        emotion_timeline = session_data.get("emotion_timeline", [])
        posture_events = session_data.get("posture_events", [])
        frames = session_data.get("frames", [])
        interventions = session_data.get("intervention_triggers", [])
        
        # Calculate metadata
        start_time = datetime.fromisoformat(session_data.get("start_datetime", datetime.utcnow().isoformat()))
        duration = session_data.get("duration", 0)
        end_time = datetime.fromtimestamp(start_time.timestamp() + duration)
        
        # Count face detected frames
        face_detected_frames = sum(
            1 for f in frames
            if f.get("faceMesh", {}).get("landmarks")
        )
        
        # Generate sub-reports
        emotion_report = self.generate_emotion_timeline(emotion_timeline)
        posture_report = self.generate_posture_analysis(posture_events)
        engagement_report = self.generate_engagement_metrics(
            total_frames=len(frames),
            face_detected_frames=face_detected_frames,
            duration_sec=duration
        )
        behavioral_report = self.generate_behavioral_insights(
            emotion_timeline=emotion_timeline,
            posture_events=posture_events,
            engagement_level=engagement_report.engagement_level,
            duration_sec=duration
        )
        
        # Intervention summary
        intervention_summary = None
        if interventions:
            intervention_types: Dict[str, int] = {}
            for trigger in interventions:
                itype = trigger.get("trigger_type", "unknown")
                intervention_types[itype] = intervention_types.get(itype, 0) + 1
            
            intervention_summary = InterventionSummary(
                total_interventions=len(interventions),
                interventions_by_type=intervention_types,
                intervention_effectiveness=0.7  # Placeholder - would calculate from actual data
            )
        
        # Calculate overall quality score (0-100)
        # Note: engagement_level, emotion_stability, posture_stability are 0-1 decimals
        # Weights sum to 100, so we get a 0-100 score directly
        quality_score = (
            (engagement_report.engagement_level * 40) +  # 40% weight
            (emotion_report.emotion_stability * 30) +     # 30% weight
            (posture_report.posture_stability * 30)       # 30% weight
        )
        
        # Build detailed timeline showing what happened minute-by-minute
        detailed_timeline = self._build_detailed_timeline(
            emotion_timeline=emotion_timeline,
            posture_events=posture_events,
            interventions=interventions,
            frames=frames
        )
        
        # Generate AI insights (async call wrapped in sync context)
        ai_insights = None
        if self.ai_analyzer.is_enabled():
            try:
                # Prepare session data for AI
                ai_session_data = {
                    "session_id": session_id,
                    "duration_seconds": duration,
                    "emotion_timeline": emotion_timeline,
                    "emotion_distribution": emotion_report.emotion_distribution,
                    "posture_events": posture_events,
                    "average_posture_quality": posture_report.average_quality,
                    "engagement_level": engagement_report.engagement_level,
                    "interventions": interventions,
                    "quality_score": quality_score
                }
                
                # Call AI analyzer
                ai_result = asyncio.run(self.ai_analyzer.generate_insights(ai_session_data))
                
                if ai_result:
                    # Convert AI result to AIInsights schema
                    ai_insights = AIInsights(
                        executive_summary=ai_result.get("executive_summary", ""),
                        emotional_journey=ai_result.get("emotional_journey", ""),
                        key_moments=[
                            KeyMoment(**moment) for moment in ai_result.get("key_moments", [])
                        ],
                        behavioral_patterns=[
                            BehavioralPatternAI(**pattern) for pattern in ai_result.get("behavioral_patterns", [])
                        ],
                        posture_insights=ai_result.get("posture_insights", ""),
                        engagement_analysis=ai_result.get("engagement_analysis", ""),
                        wellness_score=ai_result.get("wellness_score", int(quality_score)),
                        wellness_explanation=ai_result.get("wellness_explanation", ""),
                        recommendations=ai_result.get("recommendations", []),
                        positive_highlights=ai_result.get("positive_highlights", []),
                        areas_for_improvement=ai_result.get("areas_for_improvement", []),
                        tokens_used=None,  # Token count available in response metadata
                        model_used=self.ai_analyzer.model
                    )
                    logger.info("✅ AI insights generated for session %s", session_id)
                else:
                    logger.warning("⚠️ AI insights generation returned None for session %s", session_id)
            except Exception as e:
                logger.error("❌ Failed to generate AI insights: %s", str(e))
                ai_insights = None
        
        return SessionReport(
            session_id=session_id,
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            emotion_timeline=emotion_report,
            posture_analysis=posture_report,
            engagement=engagement_report,
            ai_insights=ai_insights,
            detailed_timeline=detailed_timeline,
            behavioral_insights=behavioral_report,
            intervention_summary=intervention_summary,
            overall_quality_score=quality_score
        )
    
    def _build_detailed_timeline(
        self,
        emotion_timeline: List[Dict],
        posture_events: List[Dict],
        interventions: List[Dict],
        frames: List[Dict]
    ) -> List[DetailedTimelinePoint]:
        """
        Build minute-by-minute timeline of session events
        
        Args:
            emotion_timeline: Emotion changes
            posture_events: Posture quality events
            interventions: Intervention triggers
            frames: Frame data
            
        Returns:
            List of DetailedTimelinePoint
        """
        timeline_points = []
        
        # Add emotion changes
        for emotion_point in emotion_timeline:
            timestamp = emotion_point.get('timestamp', 0)
            emotion = emotion_point.get('emotion', 'unknown')
            confidence = emotion_point.get('confidence', 0) * 100
            minute = int(timestamp / 60)
            
            timeline_points.append(DetailedTimelinePoint(
                timestamp=timestamp,
                minute=minute,
                event_type='emotion',
                data=f"Emotion changed to {emotion} ({confidence:.0f}% confidence)",
                metadata={'emotion': emotion, 'confidence': confidence}
            ))
        
        # Add posture events
        for posture_event in posture_events:
            timestamp = posture_event.get('timestamp', 0)
            quality = posture_event.get('quality', 'unknown')
            event_type = posture_event.get('event_type', 'quality_check')
            minute = int(timestamp / 60)
            
            timeline_points.append(DetailedTimelinePoint(
                timestamp=timestamp,
                minute=minute,
                event_type='posture',
                data=f"Posture quality: {quality}",
                metadata={'quality': quality, 'event_type': event_type}
            ))
        
        # Add interventions
        for intervention in interventions:
            timestamp = intervention.get('timestamp', 0)
            trigger_type = intervention.get('type', 'unknown')
            reason = intervention.get('reason', '')
            minute = int(timestamp / 60)
            
            timeline_points.append(DetailedTimelinePoint(
                timestamp=timestamp,
                minute=minute,
                event_type='intervention',
                data=f"Intervention triggered: {trigger_type} - {reason}",
                metadata={'type': trigger_type, 'reason': reason}
            ))
        
        # Add engagement markers every 30 seconds from frames
        if frames:
            last_minute = -1
            for i, frame in enumerate(frames):
                if i % 15 == 0:  # Sample every 15th frame (~2 sec if 30fps)
                    timestamp = frame.get('timestamp', i * 0.033)  # Assume 30fps
                    minute = int(timestamp / 60)
                    
                    # Only add if it's a new minute
                    if minute != last_minute:
                        face_detected = bool(frame.get('faceMesh', {}).get('landmarks'))
                        
                        timeline_points.append(DetailedTimelinePoint(
                            timestamp=timestamp,
                            minute=minute,
                            event_type='engagement',
                            data=f"Face {'detected' if face_detected else 'not detected'}",
                            metadata={'face_detected': face_detected}
                        ))
                        last_minute = minute
        
        # Sort by timestamp
        timeline_points.sort(key=lambda x: x.timestamp)
        
        return timeline_points
    
    def generate_from_file(self, json_filepath: str, user_id: Optional[str] = None) -> SessionReport:
        """
        Generate report from saved JSON file
        
        Args:
            json_filepath: Path to session JSON file
            user_id: User identifier (optional)
            
        Returns:
            SessionReport
        """
        with open(json_filepath, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        
        session_id = session_data.get("session_id", Path(json_filepath).stem)
        
        return self.generate_full_report(session_id, session_data, user_id)
    
    def generate_from_database(self, session_id: str, db_session, user_id: Optional[str] = None) -> SessionReport:
        """
        Generate report directly from database
        
        Args:
            session_id: Session identifier
            db_session: SQLAlchemy database session
            user_id: User identifier (optional)
            
        Returns:
            SessionReport
        """
        try:
            from src.custom_live_ai.models.database import Session as DBSession, Frame, SessionTimeline
            
            # Query session record
            db_session_record = db_session.query(DBSession).filter(
                DBSession.session_id == session_id
            ).first()
            
            if not db_session_record:
                raise ValueError(f"Session {session_id} not found in database")
            
            # Query timeline events
            timeline_events = db_session.query(SessionTimeline).filter(
                SessionTimeline.session_id == session_id
            ).order_by(SessionTimeline.timestamp).all()
            
            # Query frames for engagement metrics
            frames = db_session.query(Frame).filter(
                Frame.session_id == session_id
            ).order_by(Frame.frame_number).all()
            
            # Build timeline data
            emotion_timeline = []
            posture_events = []
            intervention_triggers = []
            
            for event in timeline_events:
                if event.event_type == "emotion":
                    emotion_timeline.append({
                        "timestamp": event.timestamp,
                        "emotion": event.data.get("emotion", "unknown"),
                        "confidence": event.data.get("confidence", 0)
                    })
                elif event.event_type == "posture":
                    posture_events.append({
                        "timestamp": event.timestamp,
                        "event_type": event.data.get("event_type", "unknown"),
                        "severity": event.data.get("severity", 0)
                    })
                elif event.event_type == "intervention":
                    intervention_triggers.append({
                        "timestamp": event.timestamp,
                        "trigger_type": event.data.get("trigger_type", "unknown")
                    })
            
            # Build frames data for engagement
            frames_data = []
            for frame in frames:
                frames_data.append({
                    "frame_number": frame.frame_number,
                    "timestamp": frame.timestamp,
                    "faceMesh": frame.face_mesh_landmarks
                })
            
            # Build session_data dictionary
            session_data = {
                "session_id": session_id,
                "start_datetime": db_session_record.start_time.isoformat() if db_session_record.start_time else "",
                "duration": db_session_record.duration or 0,
                "emotion_timeline": emotion_timeline,
                "posture_events": posture_events,
                "intervention_triggers": intervention_triggers,
                "frames": frames_data
            }
            
            logger.info(f"📊 Generating report from database for session: {session_id}")
            return self.generate_full_report(session_id, session_data, user_id)
            
        except Exception as e:
            logger.error(f"Failed to generate report from database: {e}")
            raise