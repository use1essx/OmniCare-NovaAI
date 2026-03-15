"""
Reply Tone Guardrails for Healthcare AI

Provides lightweight quality checks on AI replies to ensure they match
the intended ToneProfile. For internal/dev mode logging only.

These checks run after the LLM generates a reply but before returning
to the frontend, logging warnings for replies that don't match expectations.
"""

import re
import logging
from dataclasses import dataclass
from typing import List, Optional
from src.core.tone_profile import ToneProfile, ToneProfileManager

logger = logging.getLogger(__name__)


@dataclass
class ToneCheckResult:
    """Result of tone quality check on a reply."""
    
    is_valid: bool  # True if all checks pass
    warnings: List[str]  # List of warning messages
    metrics: dict  # Computed metrics
    
    def log_warnings(self):
        """Log any warnings at INFO level for dev/internal monitoring."""
        for warning in self.warnings:
            logger.info(f"[ToneCheck] {warning}")


class ReplyToneChecker:
    """
    Checks if AI replies match the expected ToneProfile.
    
    This is a lightweight QA layer for internal monitoring.
    It does NOT block replies, only logs warnings.
    """
    
    def __init__(self, tone_profile: Optional[ToneProfile] = None):
        """
        Initialize checker with a ToneProfile.
        
        Args:
            tone_profile: ToneProfile to check against (uses default if None)
        """
        self.tone_profile = tone_profile or ToneProfile()
    
    @classmethod
    def from_user_profile(cls, user_profile: Optional[dict]) -> "ReplyToneChecker":
        """
        Create a checker from a user profile.
        
        Args:
            user_profile: User profile dict with age_group, etc.
        
        Returns:
            ReplyToneChecker configured for the user's age group
        """
        tone_profile = ToneProfileManager.from_user_profile(user_profile)
        return cls(tone_profile)
    
    def check_reply(self, reply: str) -> ToneCheckResult:
        """
        Check if a reply matches the expected ToneProfile.
        
        Args:
            reply: The AI-generated reply text
        
        Returns:
            ToneCheckResult with metrics and any warnings
        """
        metrics = self._compute_metrics(reply)
        warnings = self._generate_warnings(metrics)
        
        return ToneCheckResult(
            is_valid=len(warnings) == 0,
            warnings=warnings,
            metrics=metrics,
        )
    
    def _compute_metrics(self, reply: str) -> dict:
        """
        Compute simple metrics from the reply text.
        
        Args:
            reply: Reply text
        
        Returns:
            Dict with sentence_count, bullet_count, emoji_count, word_count
        """
        return {
            "sentence_count": count_sentences(reply),
            "bullet_count": count_bullets(reply),
            "emoji_count": count_emojis(reply),
            "word_count": count_words(reply),
            "age_group": self.tone_profile.age_group,
        }
    
    def _generate_warnings(self, metrics: dict) -> List[str]:
        """
        Generate warnings based on metrics vs ToneProfile expectations.
        
        Args:
            metrics: Computed metrics dict
        
        Returns:
            List of warning messages
        """
        warnings = []
        age_group = self.tone_profile.age_group or "adult"
        
        # Check sentence count
        if metrics["sentence_count"] > self.tone_profile.max_sentences:
            warnings.append(
                f"reply_too_long_for_{age_group}: "
                f"{metrics['sentence_count']} sentences > max {self.tone_profile.max_sentences}"
            )
        
        # Check bullet count
        if metrics["bullet_count"] > self.tone_profile.max_bullets:
            warnings.append(
                f"too_many_bullets_for_{age_group}: "
                f"{metrics['bullet_count']} bullets > max {self.tone_profile.max_bullets}"
            )
        
        # Age-specific checks
        if age_group == "child":
            # Child replies should have at least some emojis (not too dry)
            if metrics["emoji_count"] == 0 and metrics["word_count"] > 20:
                warnings.append(
                    "too_dry_for_child: no emojis in substantive reply"
                )
            
            # Child replies that are too long are especially problematic
            if metrics["sentence_count"] > 5:
                warnings.append(
                    "way_too_long_for_child: >5 sentences feels like a lecture"
                )
        
        elif age_group == "teen":
            # Teen replies shouldn't be too short (needs validation)
            if metrics["sentence_count"] < 2 and metrics["word_count"] < 20:
                warnings.append(
                    "too_short_for_teen: reply too brief for proper validation"
                )
        
        elif age_group == "adult":
            # Adult replies need substance
            if metrics["sentence_count"] <= 2 and metrics["bullet_count"] == 0:
                if metrics["word_count"] > 5:  # Not just "Okay" or similar
                    warnings.append(
                        "too_shallow_for_adult: short reply with no options/structure"
                    )
        
        elif age_group == "elder":
            # Elder replies should not be too complex
            if metrics["bullet_count"] > 6:
                warnings.append(
                    "too_complex_for_elder: too many bullet points may overwhelm"
                )
        
        return warnings


def count_sentences(text: str) -> int:
    """
    Count approximate number of sentences in text.
    
    Uses simple heuristics: splits on .!? followed by space or end.
    """
    if not text:
        return 0
    
    # Remove common abbreviations that contain periods
    text = re.sub(r'\b(Mr|Mrs|Ms|Dr|Prof|vs|etc|e\.g|i\.e)\.\s*', r'\1 ', text)
    
    # Split on sentence-ending punctuation
    sentences = re.split(r'[.!?]+(?:\s|$)', text.strip())
    
    # Filter out empty strings
    sentences = [s.strip() for s in sentences if s.strip()]
    
    return len(sentences)


def count_bullets(text: str) -> int:
    """
    Count bullet points in text.
    
    Looks for lines starting with -, *, •, or numbered lists.
    """
    if not text:
        return 0
    
    # Match common bullet patterns
    bullet_pattern = r'^\s*[-*•]\s+|^\s*\d+[.)]\s+'
    
    lines = text.split('\n')
    bullet_count = sum(1 for line in lines if re.match(bullet_pattern, line))
    
    return bullet_count


def count_emojis(text: str) -> int:
    """
    Count emoji characters in text.
    
    Uses a broad regex pattern for common emoji ranges.
    """
    if not text:
        return 0
    
    # Common emoji unicode ranges (simplified)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # Emoticons
        "\U0001F300-\U0001F5FF"  # Symbols & pictographs
        "\U0001F680-\U0001F6FF"  # Transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # Flags
        "\U00002702-\U000027B0"  # Dingbats
        "\U0001F900-\U0001F9FF"  # Supplemental symbols
        "\U0001FA00-\U0001FA6F"  # Chess symbols
        "\U0001FA70-\U0001FAFF"  # Extended symbols
        "\U00002600-\U000026FF"  # Misc symbols
        "]+",
        flags=re.UNICODE
    )
    
    emojis = emoji_pattern.findall(text)
    return sum(len(e) for e in emojis)


def count_words(text: str) -> int:
    """Count words in text."""
    if not text:
        return 0
    
    words = text.split()
    return len(words)


def check_reply_against_profile(
    reply: str,
    user_profile: Optional[dict] = None,
    log_warnings: bool = True,
) -> ToneCheckResult:
    """
    Convenience function to check a reply against a user profile.
    
    Args:
        reply: AI-generated reply text
        user_profile: User profile dict (optional)
        log_warnings: Whether to log warnings (default True)
    
    Returns:
        ToneCheckResult with metrics and warnings
    """
    checker = ReplyToneChecker.from_user_profile(user_profile)
    result = checker.check_reply(reply)
    
    if log_warnings and result.warnings:
        result.log_warnings()
    
    return result
