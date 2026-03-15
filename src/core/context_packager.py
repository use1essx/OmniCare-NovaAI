"""
Context Packager for Healthcare AI

Builds age-aware session context summaries for LLM prompts.
Respects session-only memory policy and creates concise summaries
tuned to user age group.
"""

from typing import List, Dict, Any, Optional
from src.core.tone_profile import ToneProfile, ToneProfileManager


def build_session_context_summary(
    conversation_history: List[Dict[str, Any]],
    user_profile: Optional[Dict[str, Any]],
    tone_profile: Optional[ToneProfile] = None,
) -> str:
    """
    Build a short, age-aware summary of session context.
    
    Creates bullet-point summary of conversation history with
    age-appropriate density and language complexity.
    
    Args:
        conversation_history: List of conversation turns (dicts with 'role' and 'content')
        user_profile: User profile dict with display_name, age_group, etc.
        tone_profile: ToneProfile for age-specific settings (derived if not provided)
    
    Returns:
        Formatted context summary string, or empty string if no history
    """
    if not conversation_history:
        return ""
    
    # Get or derive tone profile
    if tone_profile is None:
        tone_profile = ToneProfileManager.from_user_profile(user_profile)
    
    age_group = tone_profile.age_group or "adult"
    
    # Determine max bullets based on age group
    max_bullets = _get_max_context_bullets(age_group)
    
    # Extract key points from conversation
    key_points = _extract_key_points(conversation_history, user_profile, max_bullets)
    
    if not key_points:
        return ""
    
    # Build the summary section
    lines = ["### Conversation context (session-only)"]
    lines.extend([f"- {point}" for point in key_points[:max_bullets]])
    
    return "\n".join(lines)


def _get_max_context_bullets(age_group: str) -> int:
    """
    Get maximum context bullets based on age group.
    
    Args:
        age_group: User's age group
    
    Returns:
        Maximum number of bullets for context summary
    """
    bullet_limits = {
        "child": 3,
        "teen": 4,
        "adult": 6,
        "elder": 5,
    }
    return bullet_limits.get(age_group, 5)  # Default to 5


def _extract_key_points(
    conversation_history: List[Dict[str, Any]],
    user_profile: Optional[Dict[str, Any]],
    max_points: int,
) -> List[str]:
    """
    Extract key points from conversation history.
    
    Builds a list of concise summary points from recent conversation turns.
    
    Args:
        conversation_history: List of conversation turns
        user_profile: User profile dict
        max_points: Maximum number of points to extract
    
    Returns:
        List of key point strings
    """
    points = []
    
    # Add user name and topic if available
    user_name = None
    if user_profile:
        user_name = user_profile.get('display_name')
        age = user_profile.get('age')
        age_group = user_profile.get('age_group')
        
        if user_name:
            name_point = f"You are talking to {user_name}"
            if age:
                name_point += f", age {age}"
            elif age_group:
                name_point += f" ({age_group})"
            points.append(name_point + ".")
    
    # Extract recent user messages and AI suggestions
    user_messages = []
    ai_suggestions = []
    
    for turn in conversation_history:
        role = turn.get('role', '')
        content = turn.get('content', '')
        
        if not content:
            continue
        
        if role == 'user':
            # Truncate long messages
            summary = _summarize_message(content, max_length=100)
            user_messages.append(summary)
        elif role == 'assistant':
            # Extract suggestion summary
            summary = _summarize_message(content, max_length=80)
            ai_suggestions.append(summary)
    
    # Add most recent user context
    if user_messages:
        # Take last 1-2 user messages depending on space
        recent_user = user_messages[-2:] if len(user_messages) > 1 else user_messages
        for msg in recent_user:
            if len(points) < max_points:
                points.append(f"They said: \"{msg}\"")
    
    # Add AI suggestion summary if space
    if ai_suggestions and len(points) < max_points:
        recent_suggestion = ai_suggestions[-1]
        points.append(f"You suggested: {recent_suggestion}")
    
    return points[:max_points]


def _summarize_message(content: str, max_length: int = 100) -> str:
    """
    Summarize a message to a short excerpt.
    
    Args:
        content: Full message content
        max_length: Maximum length of summary
    
    Returns:
        Truncated/summarized message
    """
    # Remove extra whitespace
    content = ' '.join(content.split())
    
    # Truncate if too long
    if len(content) > max_length:
        # Try to cut at a word boundary
        truncated = content[:max_length].rsplit(' ', 1)[0]
        return truncated + "..."
    
    return content
