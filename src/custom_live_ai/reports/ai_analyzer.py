"""
AI-Powered Report Analyzer
Uses AWS Nova (via unified AI client) to generate personalized insights from session data
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any

from src.ai.unified_ai_client import AIRequest, AIResponse
from src.ai.providers.nova_bedrock_client import NovaBedrockClient
from src.core.logging import get_logger

logger = get_logger(__name__)


class AIReportAnalyzer:
    """
    Generate AI-powered insights from session data using AWS Nova
    """
    
    def __init__(self):
        """Initialize AI analyzer with Nova client"""
        self.enabled = os.getenv("AI_REPORTS_ENABLED", "true").lower() == "true"
        self.max_tokens = int(os.getenv("AI_MAX_TOKENS", "2000"))
        self.temperature = float(os.getenv("AI_TEMPERATURE", "0.7"))
        
        try:
            self.client = NovaBedrockClient()
            if self.enabled:
                logger.info("✅ AI Report Analyzer initialized with Nova")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize Nova client: {e}. AI insights will be disabled.")
            self.enabled = False
            self.client = None
        
        if not self.enabled:
            logger.info("ℹ️ AI Report Analyzer disabled")
    
    async def generate_insights(
        self,
        session_data: Dict[str, Any],
        report_type: str = "comprehensive"
    ) -> Optional[Dict[str, Any]]:
        """
        Generate AI insights from session data using Nova
        
        Args:
            session_data: Complete session data including timeline
            report_type: Type of analysis (comprehensive, behavioral, recommendations)
            
        Returns:
            Dictionary with AI-generated insights or None if disabled/failed
        """
        if not self.enabled or not self.client:
            return None
        
        try:
            # Build prompt based on report type
            prompt = self._build_prompt(session_data, report_type)
            
            # Use unified AI client with Nova
            request = AIRequest(
                system_prompt="You are a compassionate healthcare AI assistant specializing in wellness and behavioral analysis. Provide thoughtful, evidence-based insights. Return ONLY valid JSON, no markdown formatting.",
                user_prompt=prompt,
                task_type="report_generation",  # Uses Nova Pro for detailed analysis
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                session_id=session_data.get('session_id')
            )
            
            # Execute request through Nova
            response: AIResponse = await self.client.make_request(request=request)
            
            if response.success:
                # Parse JSON response
                try:
                    insights = json.loads(response.content)
                    logger.info(
                        "✅ Generated AI insights for session",
                        extra={
                            "session_id": session_data.get('session_id', 'unknown'),
                            "model": response.model,
                            "cost": float(response.cost),
                            "tokens": response.total_tokens
                        }
                    )
                    return insights
                except json.JSONDecodeError:
                    logger.error(
                        "Failed to parse AI response as JSON",
                        extra={"content_preview": response.content[:200]}
                    )
                    return None
            else:
                logger.error(
                    "❌ Failed to generate AI insights",
                    extra={"error": response.error_message}
                )
                return None
                
        except Exception as e:
            logger.error(f"Error generating AI insights: {str(e)}")
            return None
    
    def _build_prompt(self, session_data: Dict[str, Any], report_type: str) -> str:
        """
        Build prompt for AI based on session data and report type
        """
        if report_type == "comprehensive":
            return self._build_comprehensive_prompt(session_data)
        elif report_type == "behavioral":
            return self._build_behavioral_prompt(session_data)
        elif report_type == "recommendations":
            return self._build_recommendations_prompt(session_data)
        else:
            return self._build_comprehensive_prompt(session_data)
    
    def _build_comprehensive_prompt(self, data: Dict[str, Any]) -> str:
        """
        Build comprehensive analysis prompt with detailed timeline
        """
        session_id = data.get('session_id', 'unknown')
        duration = data.get('duration_seconds', 0)
        
        # Build detailed timeline
        timeline_str = self._format_timeline(data)
        
        # Build emotion summary
        emotion_dist = data.get('emotion_distribution', {})
        emotion_summary = ", ".join([f"{e}: {p:.1f}%" for e, p in emotion_dist.items()])
        
        # Build posture summary
        posture_quality = data.get('average_posture_quality', 'unknown')
        posture_events = data.get('posture_events', [])
        
        # Build engagement summary
        engagement = data.get('engagement_level', 0) * 100
        
        # Build intervention summary
        interventions = data.get('interventions', [])
        
        prompt = f"""You are a healthcare AI assistant analyzing a therapy/wellness session. Generate a comprehensive, empathetic report.

📊 SESSION OVERVIEW:
- Session ID: {session_id}
- Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)
- Overall Engagement: {engagement:.0f}%
- Posture Quality: {posture_quality}
- Emotions: {emotion_summary}

📅 DETAILED TIMELINE (What happened minute-by-minute):
{timeline_str}

🎯 POSTURE EVENTS:
{self._format_posture_events(posture_events)}

🤖 INTERVENTIONS TRIGGERED:
{self._format_interventions(interventions)}

📝 YOUR TASK:
Generate a detailed, personalized report in JSON format with:

1. **executive_summary**: A warm, empathetic 2-3 sentence overview of the session
2. **emotional_journey**: Describe the emotional progression throughout the session, noting key moments and transitions
3. **key_moments**: Array of 3-5 significant moments with:
   - time: When it happened (e.g., "5:30 into session")
   - event: What happened
   - significance: Why it matters
4. **behavioral_patterns**: Array of 2-4 patterns observed:
   - pattern: The pattern observed
   - frequency: How often
   - recommendation: What to do about it
5. **posture_insights**: Analysis of posture quality and ergonomics
6. **engagement_analysis**: How engaged the user was and when engagement changed
7. **wellness_score**: Overall wellness score (0-100) with brief explanation
8. **recommendations**: Array of 4-6 actionable, personalized recommendations
9. **positive_highlights**: 2-3 things the user did well
10. **areas_for_improvement**: 2-3 gentle suggestions for improvement

Return ONLY valid JSON, no markdown formatting.

Example format:
{{
  "executive_summary": "...",
  "emotional_journey": "...",
  "key_moments": [
    {{"time": "2:30", "event": "...", "significance": "..."}},
  ],
  "behavioral_patterns": [
    {{"pattern": "...", "frequency": "...", "recommendation": "..."}}
  ],
  "posture_insights": "...",
  "engagement_analysis": "...",
  "wellness_score": 85,
  "wellness_explanation": "...",
  "recommendations": ["...", "..."],
  "positive_highlights": ["...", "..."],
  "areas_for_improvement": ["...", "..."]
}}"""
        
        return prompt
    
    def _build_behavioral_prompt(self, data: Dict[str, Any]) -> str:
        """
        Build behavioral analysis prompt focusing on patterns
        """
        timeline_str = self._format_timeline(data)
        
        prompt = f"""Analyze the behavioral patterns in this session and provide deep insights.

TIMELINE:
{timeline_str}

Focus on:
1. Recurring patterns (posture, emotion, engagement)
2. Triggers for emotional changes
3. Correlation between posture and emotion
4. Optimal session length based on engagement
5. Best times for breaks

Return JSON with:
- patterns: Array of detected patterns
- triggers: Emotional/behavioral triggers
- correlations: Relationships between metrics
- recommendations: Based on patterns

Return ONLY valid JSON."""
        
        return prompt
    
    def _build_recommendations_prompt(self, data: Dict[str, Any]) -> str:
        """
        Build recommendations prompt for actionable advice
        """
        timeline_str = self._format_timeline(data)
        
        prompt = f"""Based on this session data, provide personalized wellness recommendations.

TIMELINE:
{timeline_str}

Generate specific, actionable recommendations for:
1. Break timing and frequency
2. Posture improvement exercises
3. Emotional regulation techniques
4. Engagement optimization
5. Environmental adjustments

Return JSON with:
- immediate_actions: Do these now
- daily_habits: Build these habits
- weekly_goals: Aim for these
- resources: Helpful links/tools

Return ONLY valid JSON."""
        
        return prompt
    
    def _format_timeline(self, data: Dict[str, Any]) -> str:
        """
        Format session timeline into readable text for AI
        """
        timeline_parts = []
        
        # Get emotion timeline
        emotion_timeline = data.get('emotion_timeline', [])
        posture_events = data.get('posture_events', [])
        interventions = data.get('interventions', [])
        
        # Combine all events with timestamps
        all_events = []
        
        for emotion_point in emotion_timeline:
            timestamp = emotion_point.get('timestamp', 0)
            emotion = emotion_point.get('emotion', 'unknown')
            confidence = emotion_point.get('confidence', 0) * 100
            all_events.append({
                'time': timestamp,
                'type': 'emotion',
                'data': f"Emotion: {emotion} ({confidence:.0f}% confidence)"
            })
        
        for posture_event in posture_events:
            timestamp = posture_event.get('timestamp', 0)
            quality = posture_event.get('quality', 'unknown')
            all_events.append({
                'time': timestamp,
                'type': 'posture',
                'data': f"Posture: {quality}"
            })
        
        for intervention in interventions:
            timestamp = intervention.get('timestamp', 0)
            itype = intervention.get('type', 'unknown')
            reason = intervention.get('reason', '')
            all_events.append({
                'time': timestamp,
                'type': 'intervention',
                'data': f"Intervention: {itype} - {reason}"
            })
        
        # Sort by time
        all_events.sort(key=lambda x: x['time'])
        
        # Format as timeline
        if not all_events:
            return "No timeline data available"
        
        # Group by minute for readability
        current_minute = -1
        for event in all_events:
            minute = int(event['time'] / 60)
            if minute != current_minute:
                timeline_parts.append(f"\n⏰ Minute {minute}:")
                current_minute = minute
            timeline_parts.append(f"  - {event['data']}")
        
        return "\n".join(timeline_parts)
    
    def _format_posture_events(self, events: List[Dict]) -> str:
        """Format posture events for prompt"""
        if not events:
            return "No posture events recorded"
        
        lines = []
        for event in events:
            timestamp = event.get('timestamp', 0)
            quality = event.get('quality', 'unknown')
            duration = event.get('duration', 0)
            minute = int(timestamp / 60)
            lines.append(f"  - Minute {minute}: {quality} posture (lasted {duration:.1f}s)")
        
        return "\n".join(lines) if lines else "No posture events"
    
    def _format_interventions(self, interventions: List[Dict]) -> str:
        """Format interventions for prompt"""
        if not interventions:
            return "No interventions triggered"
        
        lines = []
        for intervention in interventions:
            timestamp = intervention.get('timestamp', 0)
            itype = intervention.get('type', 'unknown')
            reason = intervention.get('reason', '')
            minute = int(timestamp / 60)
            lines.append(f"  - Minute {minute}: {itype} intervention - {reason}")
        
        return "\n".join(lines) if lines else "No interventions"
    

    
    def is_enabled(self) -> bool:
        """Check if AI reports are enabled"""
        return self.enabled

