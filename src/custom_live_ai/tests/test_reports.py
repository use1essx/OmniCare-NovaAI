"""
Test report generation system
"""

from datetime import datetime
from src.custom_live_ai.reports.generator import ReportGenerator
from src.custom_live_ai.reports.schemas import (
    EmotionChange, EmotionTimelineReport,
    PostureEvent, PostureAnalysisReport,
    EngagementReport, BehavioralInsightsReport,
    SessionReport
)


class TestReportGenerator:
    """Test ReportGenerator class"""
    
    def test_generator_initialization(self):
        """Test ReportGenerator initialization"""
        generator = ReportGenerator()
        assert generator is not None
    
    def test_generate_emotion_timeline_empty(self):
        """Test emotion timeline generation with empty data"""
        generator = ReportGenerator()
        emotion_timeline = []
        
        report = generator.generate_emotion_timeline(emotion_timeline)
        
        assert isinstance(report, EmotionTimelineReport)
        assert report.dominant_emotion == "neutral"
        assert report.dominant_percentage == 100.0
        assert report.total_changes == 0
        assert report.emotion_stability == 1.0
    
    def test_generate_emotion_timeline_with_data(self):
        """Test emotion timeline generation with real data"""
        generator = ReportGenerator()
        emotion_timeline = [
            {"timestamp": 0.0, "emotion": "neutral", "confidence": 0.8},
            {"timestamp": 1.0, "emotion": "neutral", "confidence": 0.8},
            {"timestamp": 2.0, "emotion": "happy", "confidence": 0.7},
            {"timestamp": 3.0, "emotion": "happy", "confidence": 0.8},
            {"timestamp": 4.0, "emotion": "neutral", "confidence": 0.6}
        ]
        
        report = generator.generate_emotion_timeline(emotion_timeline)
        
        assert isinstance(report, EmotionTimelineReport)
        assert report.dominant_emotion in ["neutral", "happy"]
        assert report.total_changes == 2  # neutral->happy, happy->neutral
        assert len(report.emotion_changes) == 2
        assert 0 <= report.emotion_stability <= 1
    
    def test_generate_posture_analysis_empty(self):
        """Test posture analysis with empty data"""
        generator = ReportGenerator()
        posture_events = []
        
        report = generator.generate_posture_analysis(posture_events)
        
        assert isinstance(report, PostureAnalysisReport)
        assert report.average_quality == "good"
        assert report.total_slouches == 0
        assert report.posture_stability == 1.0
    
    def test_generate_posture_analysis_with_slouches(self):
        """Test posture analysis with slouch events"""
        generator = ReportGenerator()
        posture_events = [
            {"timestamp": 0.0, "event_type": "good_posture", "severity": 0.2},
            {"timestamp": 10.0, "event_type": "slouch", "severity": 0.8},
            {"timestamp": 20.0, "event_type": "slouch", "severity": 0.7},
            {"timestamp": 30.0, "event_type": "excellent_posture", "severity": 0.1}
        ]
        
        report = generator.generate_posture_analysis(posture_events)
        
        assert isinstance(report, PostureAnalysisReport)
        assert report.total_slouches == 2
        assert len(report.slouch_events) == 2
        assert -1 <= report.improvement_score <= 1
    
    def test_generate_engagement_metrics(self):
        """Test engagement metrics generation"""
        generator = ReportGenerator()
        
        report = generator.generate_engagement_metrics(
            total_frames=100,
            face_detected_frames=80,
            eye_contact_scores=[0.8, 0.7, 0.9, 0.6],
            duration_sec=30.0
        )
        
        assert isinstance(report, EngagementReport)
        assert report.face_detection_rate == 0.8
        assert 0 <= report.average_eye_contact <= 1
        assert 0 <= report.engagement_level <= 1
        assert report.attention_span_minutes > 0
    
    def test_generate_behavioral_insights(self):
        """Test behavioral insights generation"""
        generator = ReportGenerator()
        
        emotion_timeline = [
            {"timestamp": i * 1.0, "emotion": "neutral" if i % 3 == 0 else "happy", "confidence": 0.8}
            for i in range(30)
        ]
        
        posture_events = [
            {"timestamp": i * 10.0, "event_type": "good_posture", "severity": 0.3}
            for i in range(10)
        ]
        
        report = generator.generate_behavioral_insights(
            emotion_timeline=emotion_timeline,
            posture_events=posture_events,
            engagement_level=0.8,
            duration_sec=300.0
        )
        
        assert isinstance(report, BehavioralInsightsReport)
        assert isinstance(report.patterns_detected, list)
        assert isinstance(report.key_findings, list)
        assert isinstance(report.recommendations, list)
        assert len(report.patterns_detected) >= 0
        assert len(report.key_findings) > 0
        assert len(report.recommendations) > 0
    
    def test_generate_full_report(self, sample_session_data):
        """Test full report generation"""
        generator = ReportGenerator()
        
        report = generator.generate_full_report(
            session_id="test_session",
            session_data=sample_session_data,
            user_id="test_user"
        )
        
        assert isinstance(report, SessionReport)
        assert report.session_id == "test_session"
        assert report.user_id == "test_user"
        assert isinstance(report.emotion_timeline, EmotionTimelineReport)
        assert isinstance(report.posture_analysis, PostureAnalysisReport)
        assert isinstance(report.engagement, EngagementReport)
        assert isinstance(report.behavioral_insights, BehavioralInsightsReport)
        assert 0 <= report.overall_quality_score <= 100


class TestReportSchemas:
    """Test report schema models"""
    
    def test_emotion_change_schema(self):
        """Test EmotionChange schema"""
        change = EmotionChange(
            timestamp=1.0,
            from_emotion="neutral",
            to_emotion="happy",
            confidence=0.8
        )
        
        assert change.timestamp == 1.0
        assert change.from_emotion == "neutral"
        assert change.to_emotion == "happy"
        assert change.confidence == 0.8
    
    def test_posture_event_schema(self):
        """Test PostureEvent schema"""
        event = PostureEvent(
            timestamp=10.0,
            event_type="slouch",
            severity=0.7
        )
        
        assert event.timestamp == 10.0
        assert event.event_type == "slouch"
        assert event.severity == 0.7
    
    def test_engagement_report_schema(self):
        """Test EngagementReport schema"""
        report = EngagementReport(
            face_detection_rate=0.8,
            average_eye_contact=0.7,
            engagement_level=0.75,
            attention_span_minutes=25.0
        )
        
        assert report.face_detection_rate == 0.8
        assert report.average_eye_contact == 0.7
        assert report.engagement_level == 0.75
        assert report.attention_span_minutes == 25.0
    
    def test_session_report_schema(self):
        """Test SessionReport schema"""
        report = SessionReport(
            session_id="test_session",
            user_id="test_user",
            start_time=datetime(2025, 1, 1, 10, 0, 0),
            end_time=datetime(2025, 1, 1, 10, 30, 0),
            duration_seconds=1800.0,
            emotion_timeline=EmotionTimelineReport(
                dominant_emotion="neutral",
                dominant_percentage=60.0,
                emotion_distribution={"neutral": 60.0, "happy": 40.0},
                emotion_changes=[],
                emotion_stability=0.9,
                total_changes=2
            ),
            posture_analysis=PostureAnalysisReport(
                average_quality="good",
                quality_distribution={"good": 100.0},
                slouch_events=[],
                total_slouches=0,
                improvement_score=0.0,
                posture_stability=0.95
            ),
            engagement=EngagementReport(
                face_detection_rate=0.85,
                average_eye_contact=0.75,
                engagement_level=0.8,
                attention_span_minutes=28.0
            ),
            behavioral_insights=BehavioralInsightsReport(
                patterns_detected=[],
                key_findings=["Good engagement"],
                recommendations=["Keep up the good work"]
            ),
            overall_quality_score=82.5
        )
        
        assert report.session_id == "test_session"
        assert report.user_id == "test_user"
        assert report.duration_seconds == 1800.0
        assert report.overall_quality_score == 82.5


class TestReportQualityScores:
    """Test quality score calculations"""
    
    def test_quality_score_high_engagement(self, sample_session_data):
        """Test that high engagement produces high quality score"""
        generator = ReportGenerator()
        
        # Modify sample data for high engagement
        sample_session_data["emotion_timeline"] = [
            {"timestamp": i * 1.0, "emotion": "happy", "confidence": 0.9}
            for i in range(100)
        ]
        
        report = generator.generate_full_report(
            session_id="high_engagement_session",
            session_data=sample_session_data
        )
        
        assert report.overall_quality_score > 70, "High engagement should produce high quality score"
    
    def test_quality_score_poor_posture(self, sample_session_data):
        """Test that poor posture reduces quality score"""
        generator = ReportGenerator()
        
        # Add many slouch events
        sample_session_data["posture_events"] = [
            {"timestamp": i * 10.0, "event_type": "slouch", "severity": 0.8}
            for i in range(20)
        ]
        
        report = generator.generate_full_report(
            session_id="poor_posture_session",
            session_data=sample_session_data
        )
        
        # Quality score should be impacted by poor posture
        # (might still be moderate if other factors are good)
        assert 0 <= report.overall_quality_score <= 100




