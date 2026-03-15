"""
Text Report Formatter
Converts structured reports to compact, human-readable text format
"""

from typing import Dict, Any
from datetime import datetime


class TextReportFormatter:
    """
    Formats session reports as compact, readable text
    Reduces database storage by ~80% vs JSON
    """
    
    def format_report_for_storage(self, report_data: Dict[str, Any]) -> str:
        """
        Convert full report to compact text format for database storage
        
        Args:
            report_data: Complete report dictionary
            
        Returns:
            Formatted text string (much smaller than JSON)
        """
        sections = []
        
        # Header
        sections.append(self._format_header(report_data))
        
        # Summary metrics
        sections.append(self._format_summary(report_data))
        
        # AI Insights (if available)
        if report_data.get('ai_insights'):
            sections.append(self._format_ai_insights(report_data['ai_insights']))
        
        # Timeline highlights
        sections.append(self._format_timeline_highlights(report_data))
        
        # Recommendations
        sections.append(self._format_recommendations(report_data))
        
        return "\n\n".join(sections)
    
    def _format_header(self, report: Dict[str, Any]) -> str:
        """Format report header"""
        session_id = report.get('session_id', 'unknown')
        duration = report.get('duration_seconds', 0)
        start_time = report.get('start_time', '')
        
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        
        return f"""SESSION REPORT: {session_id}
Date: {start_time.strftime('%Y-%m-%d %H:%M:%S') if start_time else 'N/A'}
Duration: {duration:.1f}s ({duration/60:.1f} min)
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"""
    
    def _format_summary(self, report: Dict[str, Any]) -> str:
        """Format summary metrics"""
        quality = report.get('overall_quality_score', 0)
        emotion_timeline = report.get('emotion_timeline', {})
        posture = report.get('posture_analysis', {})
        engagement = report.get('engagement', {})
        
        dominant_emotion = emotion_timeline.get('dominant_emotion', 'unknown')
        emotion_stability = emotion_timeline.get('emotion_stability', 0) * 100
        
        posture_quality = posture.get('average_quality', 'unknown')
        posture_stability = posture.get('posture_stability', 0) * 100
        
        engagement_level = engagement.get('engagement_level', 0) * 100
        
        return f"""=== SUMMARY ===
Overall Quality: {quality:.0f}/100
Dominant Emotion: {dominant_emotion} (Stability: {emotion_stability:.0f}%)
Posture Quality: {posture_quality} (Stability: {posture_stability:.0f}%)
Engagement Level: {engagement_level:.0f}%"""
    
    def _format_ai_insights(self, ai_insights: Dict[str, Any]) -> str:
        """Format AI-generated insights"""
        sections = ["=== AI INSIGHTS ==="]
        
        # Executive Summary
        if ai_insights.get('executive_summary'):
            sections.append(f"\n📊 EXECUTIVE SUMMARY:\n{ai_insights['executive_summary']}")
        
        # Wellness Score
        if ai_insights.get('wellness_score'):
            score = ai_insights['wellness_score']
            explanation = ai_insights.get('wellness_explanation', '')
            sections.append(f"\n🎯 WELLNESS SCORE: {score}/100\n{explanation}")
        
        # Emotional Journey
        if ai_insights.get('emotional_journey'):
            sections.append(f"\n🌊 EMOTIONAL JOURNEY:\n{ai_insights['emotional_journey']}")
        
        # Key Moments
        key_moments = ai_insights.get('key_moments', [])
        if key_moments:
            sections.append("\n⏰ KEY MOMENTS:")
            for moment in key_moments[:5]:  # Top 5
                time = moment.get('time', '')
                event = moment.get('event', '')
                sections.append(f"  • {time}: {event}")
        
        # Behavioral Patterns
        patterns = ai_insights.get('behavioral_patterns', [])
        if patterns:
            sections.append("\n🔍 BEHAVIORAL PATTERNS:")
            for pattern in patterns[:3]:  # Top 3
                p = pattern.get('pattern', '')
                r = pattern.get('recommendation', '')
                sections.append(f"  • {p}\n    → {r}")
        
        # Recommendations
        recommendations = ai_insights.get('recommendations', [])
        if recommendations:
            sections.append("\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(recommendations[:6], 1):
                sections.append(f"  {i}. {rec}")
        
        # Positive Highlights
        highlights = ai_insights.get('positive_highlights', [])
        if highlights:
            sections.append("\n✅ POSITIVE HIGHLIGHTS:")
            for highlight in highlights:
                sections.append(f"  • {highlight}")
        
        # Areas for Improvement
        improvements = ai_insights.get('areas_for_improvement', [])
        if improvements:
            sections.append("\n📈 AREAS FOR IMPROVEMENT:")
            for improvement in improvements:
                sections.append(f"  • {improvement}")
        
        return "\n".join(sections)
    
    def _format_timeline_highlights(self, report: Dict[str, Any]) -> str:
        """Format timeline highlights (not full timeline)"""
        timeline = report.get('detailed_timeline', [])
        if not timeline:
            return "=== TIMELINE ===\nNo timeline data available"
        
        sections = ["=== TIMELINE HIGHLIGHTS ==="]
        
        # Group by minute
        by_minute: Dict[int, list] = {}
        for point in timeline:
            minute = point.get('minute', 0)
            if minute not in by_minute:
                by_minute[minute] = []
            by_minute[minute].append(point)
        
        # Show highlights (first, middle, last + any interventions)
        minutes = sorted(by_minute.keys())
        if len(minutes) <= 6:
            # Show all if short
            highlight_minutes = minutes
        else:
            # Show first 2, middle 2, last 2
            highlight_minutes = [
                minutes[0], minutes[1],
                minutes[len(minutes)//2], minutes[len(minutes)//2 + 1],
                minutes[-2], minutes[-1]
            ]
        
        # Add intervention minutes
        for point in timeline:
            if point.get('event_type') == 'intervention':
                minute = point.get('minute', 0)
                if minute not in highlight_minutes:
                    highlight_minutes.append(minute)
        
        highlight_minutes = sorted(set(highlight_minutes))
        
        for minute in highlight_minutes:
            events = by_minute[minute]
            sections.append(f"\nMinute {minute}:")
            for event in events:
                event_type = event.get('event_type', 'unknown')
                data = event.get('data', '')
                icon = {
                    'emotion': '😊',
                    'posture': '🪑',
                    'intervention': '🤖',
                    'engagement': '👁️'
                }.get(event_type, '•')
                sections.append(f"  {icon} {data}")
        
        if len(minutes) > len(highlight_minutes):
            sections.append(f"\n(Showing {len(highlight_minutes)} of {len(minutes)} minutes - full timeline in JSON file)")
        
        return "\n".join(sections)
    
    def _format_recommendations(self, report: Dict[str, Any]) -> str:
        """Format behavioral insights and recommendations"""
        behavioral = report.get('behavioral_insights', {})
        
        sections = ["=== BEHAVIORAL INSIGHTS ==="]
        
        # Patterns
        patterns = behavioral.get('patterns_detected', [])
        if patterns:
            sections.append("\n🔍 PATTERNS DETECTED:")
            for pattern in patterns:
                p_type = pattern.get('pattern_type', '')
                desc = pattern.get('description', '')
                sections.append(f"  • {p_type}: {desc}")
        
        # Key Findings
        findings = behavioral.get('key_findings', [])
        if findings:
            sections.append("\n📋 KEY FINDINGS:")
            for finding in findings:
                sections.append(f"  • {finding}")
        
        # Recommendations
        recommendations = behavioral.get('recommendations', [])
        if recommendations:
            sections.append("\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(recommendations, 1):
                sections.append(f"  {i}. {rec}")
        
        return "\n".join(sections)


def format_for_display(text_report: str) -> str:
    """
    Format stored text report for web display (add HTML/Markdown)
    
    Args:
        text_report: Stored text report from database
        
    Returns:
        HTML-formatted string for web display
    """
    # Simple markdown-like formatting
    lines = text_report.split('\n')
    html_lines = []
    
    for line in lines:
        # Headers
        if line.startswith('==='):
            html_lines.append(f'<h3>{line.replace("=", "").strip()}</h3>')
        # Bullet points
        elif line.strip().startswith('•'):
            html_lines.append(f'<li>{line.strip()[1:].strip()}</li>')
        # Numbered lists
        elif line.strip() and line.strip()[0].isdigit() and '. ' in line:
            html_lines.append(f'<li>{line.split(". ", 1)[1]}</li>')
        # Regular text
        else:
            html_lines.append(f'<p>{line}</p>')
    
    return '\n'.join(html_lines)

