"""
Temporal smoothing for emotion predictions
"""

import time
import math
from typing import Dict, Optional
from collections import deque
from dataclasses import dataclass, field
import numpy as np

from .config import (
    EMA_ALPHA, MAJORITY_WINDOW, HYST_MIN_HOLD_MS, EMOTIONS, SMOOTHING_MODE,
    T1_THRESHOLD, T2_THRESHOLD, MIN_MARGIN_T1, MIN_MARGIN_T2, MIN_MARGIN_T3,
    EMA_RESET_THRESHOLD, ENTROPY_MAX, TIER_CONFIGS, NEUTRAL_STICKY_THRESHOLD,
    NEUTRAL_STICKY_MS, FPS_REFERENCE_MS, validate_config,
    MICRO_EXPRESSION_EMOTIONS, MICRO_EXPRESSION_THRESHOLD, MICRO_EXPRESSION_HOLD_MS
)


class EmaMajorityHysteresis:
    """
    Temporal smoothing using EMA, majority voting, and hysteresis
    
    Combines three techniques:
    1. Exponential Moving Average (EMA) on per-class probabilities
    2. Majority vote over recent predictions
    3. Hysteresis to prevent rapid emotion switching
    """
    
    def __init__(
        self,
        ema_alpha: float = EMA_ALPHA,
        majority_window: int = MAJORITY_WINDOW,
        min_hold_ms: int = HYST_MIN_HOLD_MS
    ):
        """
        Args:
            ema_alpha: EMA smoothing factor (0-1, higher = more responsive)
            majority_window: Window size for majority voting
            min_hold_ms: Minimum time to hold an emotion before switching (ms)
        """
        self.ema_alpha = ema_alpha
        self.majority_window = majority_window
        self.min_hold_ms = min_hold_ms
        
        # State
        self.ema_probs: Optional[Dict[str, float]] = None
        self.current_emotion: str = "neutral"
        self.last_switch_time: float = time.time()
        self.majority_buffer: deque = deque(maxlen=majority_window)
        self.candidate_emotion: Optional[str] = None
        self.candidate_start_time: Optional[float] = None
        
    def update(self, raw_probs: Dict[str, float]) -> Dict[str, float]:
        """
        Update smoothing with new probabilities
        
        Args:
            raw_probs: Raw probability dictionary from model {emotion: prob}
            
        Returns:
            Smoothed probability dictionary
        """
        # Initialize EMA on first frame
        if self.ema_probs is None:
            self.ema_probs = {e: raw_probs.get(e, 0.0) for e in EMOTIONS}
            return self.ema_probs.copy()
        
        # Apply EMA smoothing: p_ema_t = α*p_t + (1-α)*p_ema_{t-1}
        for emotion in EMOTIONS:
            p_raw = raw_probs.get(emotion, 0.0)
            p_ema_prev = self.ema_probs[emotion]
            self.ema_probs[emotion] = self.ema_alpha * p_raw + (1 - self.ema_alpha) * p_ema_prev
        
        return self.ema_probs.copy()
    
    def get_dominant_with_hysteresis(self, ema_probs: Dict[str, float]) -> Dict:
        """
        Determine dominant emotion with hysteresis to prevent rapid switching
        
        Args:
            ema_probs: EMA-smoothed probabilities
            
        Returns:
            Dictionary with dominant_emotion, confidence, and debug info
        """
        current_time = time.time()
        
        # Get candidate emotion (argmax of EMA probs)
        raw_candidate = max(ema_probs, key=lambda e: ema_probs.get(e, 0.0))
        
        # Add to majority buffer
        self.majority_buffer.append(raw_candidate)
        
        # Determine majority vote
        if len(self.majority_buffer) > 0:
            # Count occurrences
            counts = {}
            for e in self.majority_buffer:
                counts[e] = counts.get(e, 0) + 1
            majority_emotion = max(counts, key=counts.get)
        else:
            majority_emotion = raw_candidate
        
        # Hysteresis logic
        if majority_emotion != self.current_emotion:
            # Check if candidate has changed
            if majority_emotion != self.candidate_emotion:
                # New candidate
                self.candidate_emotion = majority_emotion
                self.candidate_start_time = current_time
            
            # Check if we should switch
            time_held_candidate = (current_time - (self.candidate_start_time or current_time)) * 1000
            
            # Switching conditions:
            # 1. Candidate prob > current prob + threshold
            # 2. Candidate has been held for min time
            prob_threshold = 0.08
            candidate_prob = ema_probs.get(majority_emotion, 0.0)
            current_prob = ema_probs.get(self.current_emotion, 0.0)
            
            should_switch = (
                candidate_prob >= current_prob + prob_threshold
                and time_held_candidate >= self.min_hold_ms
            )
            
            if should_switch:
                # Switch emotion
                self.current_emotion = majority_emotion
                self.last_switch_time = current_time
                self.candidate_emotion = None
                self.candidate_start_time = None
        else:
            # Reset candidate if majority matches current
            self.candidate_emotion = None
            self.candidate_start_time = None
        
        # Confidence is the EMA probability of the dominant emotion
        confidence = ema_probs.get(self.current_emotion, 0.0) * 100.0
        confidence = np.clip(confidence, 0.0, 100.0)
        
        return {
            "dominant_emotion": self.current_emotion,
            "confidence": float(confidence),
            "ema_probs": ema_probs,
            "candidate": majority_emotion,
            "is_candidate": majority_emotion != self.current_emotion
        }
    
    def process(self, raw_probs: Dict[str, float]) -> Dict:
        """
        Full processing pipeline: update EMA, apply hysteresis
        
        Args:
            raw_probs: Raw probabilities from model
            
        Returns:
            Dictionary with dominant_emotion, confidence, and scores
        """
        # Update EMA
        ema_probs = self.update(raw_probs)
        
        # Apply hysteresis
        result = self.get_dominant_with_hysteresis(ema_probs)
        
        # Convert to percentage scores
        scores = {e: float(ema_probs[e] * 100.0) for e in EMOTIONS}
        
        return {
            "dominant_emotion": result["dominant_emotion"],
            "confidence": result["confidence"],
            "scores": scores
        }
    
    def reset(self) -> None:
        """
        Reset smoother state
        """
        self.ema_probs = None
        self.current_emotion = "neutral"
        self.last_switch_time = time.time()
        self.majority_buffer.clear()
        self.candidate_emotion = None
        self.candidate_start_time = None


# ============================================================================
# 3-TIER ADAPTIVE SMOOTHING SYSTEM
# ============================================================================


@dataclass(slots=True)
class SmoothingState:
    """State for 3-tier adaptive smoother (using slots for performance)"""
    # Global state
    current_label: str = "neutral"
    last_change_ts_ms: int = 0
    cooldown_expiry_ms: int = 0
    last_ts_ms: int = 0  # Track last timestamp for dt calculation
    
    # EMA state
    ema_probs: Dict[str, float] = field(default_factory=dict)
    
    # Majority voting
    majority_buffer: deque = field(default_factory=lambda: deque(maxlen=9))
    
    # Candidate tracking
    candidate_emotion: Optional[str] = None
    candidate_start_ms: Optional[int] = None
    
    # Neutral stickiness tracking
    neutral_state_start_ms: Optional[int] = None
    low_confidence_start_ms: Optional[int] = None


@dataclass(slots=True)
class SmoothedResult:
    """Result from 3-tier adaptive smoother with diagnostics"""
    label: str
    confidence: float
    scores: Dict[str, float]
    tier: int
    alpha_eff: float
    margin: float
    entropy: float
    hold_ms_remaining: int
    cooldown_ms_left: int


def _sanitize_probs(raw_probs: Dict[str, float]) -> Dict[str, float]:
    """
    Guard NaN/negative/infinite values; renormalize; handle edge cases.
    Fail-closed to Tier 3 on invalid input.
    
    Args:
        raw_probs: Raw probability dictionary
        
    Returns:
        Sanitized and normalized probability dictionary
    """
    if not raw_probs:
        # Empty dict → default to neutral
        return {"neutral": 1.0}
    
    sanitized = {}
    for emotion, prob in raw_probs.items():
        # Replace NaN/inf with 0, clamp negatives to 0
        if math.isnan(prob) or math.isinf(prob) or prob < 0:
            sanitized[emotion] = 0.0
        else:
            sanitized[emotion] = float(prob)
    
    # Ensure all emotions present
    for emotion in EMOTIONS:
        if emotion not in sanitized:
            sanitized[emotion] = 0.0
    
    # Renormalize to sum=1.0
    total = sum(sanitized.values())
    if total > 0:
        sanitized = {e: v / total for e, v in sanitized.items()}
    else:
        # All zeros → default to neutral
        sanitized = {e: (1.0 if e == "neutral" else 0.0) for e in EMOTIONS}
    
    return sanitized


def _compute_entropy(probs: Dict[str, float]) -> float:
    """
    Compute normalized entropy H = -Σ p*log(p) / log(N).
    
    Args:
        probs: Probability dictionary (should be normalized)
        
    Returns:
        Normalized entropy in [0, 1] range (0=certain, 1=uniform)
    """
    entropy = 0.0
    for prob in probs.values():
        if prob > 0:
            entropy -= prob * math.log(prob)
    
    # Normalize by log(num_classes) for [0, 1] range
    num_classes = len(EMOTIONS)
    if num_classes > 1:
        max_entropy = math.log(num_classes)
        entropy = entropy / max_entropy
    
    return entropy


def _compute_alpha_eff(alpha: float, dt_ms: float) -> float:
    """
    Scale alpha by frame delta for FPS consistency.
    Formula: alpha_eff = 1 - (1 - alpha)^(dt_ms / 33.3)
    
    Args:
        alpha: Base alpha value from config
        dt_ms: Time delta since last frame in milliseconds
        
    Returns:
        FPS-scaled effective alpha
    """
    if dt_ms <= 0:
        return alpha
    
    # Clamp dt_ms to reasonable range (avoid extreme values)
    dt_ms = max(1.0, min(dt_ms, 1000.0))
    
    # Scale alpha by frame delta
    exponent = dt_ms / FPS_REFERENCE_MS
    alpha_eff = 1.0 - math.pow(1.0 - alpha, exponent)
    
    # Clamp to valid range
    return max(0.0, min(1.0, alpha_eff))


def _detect_tier(probs: Dict[str, float]) -> tuple[int, float, float, float]:
    """
    Classify into Tier 1/2/3 based on p_max, margin, and entropy.
    
    Args:
        probs: Sanitized probability dictionary
        
    Returns:
        Tuple of (tier, p_max, margin, entropy)
    """
    sanitized = _sanitize_probs(probs)
    
    # Calculate p_max and margin
    sorted_vals = sorted(sanitized.values(), reverse=True)
    p_max = sorted_vals[0]
    p_second = sorted_vals[1] if len(sorted_vals) > 1 else 0.0
    margin = p_max - p_second
    
    # Calculate entropy
    entropy = _compute_entropy(sanitized)
    
    # Entropy gate: force Tier 3 if too ambiguous
    if entropy > ENTROPY_MAX:
        return (3, p_max, margin, entropy)
    
    # Tier 1: High confidence OR high margin
    if p_max >= T1_THRESHOLD or (p_max >= 0.80 and margin >= MIN_MARGIN_T1):
        return (1, p_max, margin, entropy)
    
    # Tier 2: Medium confidence
    if p_max >= T2_THRESHOLD:
        return (2, p_max, margin, entropy)
    
    # Tier 3: Low confidence
    return (3, p_max, margin, entropy)


class AdaptiveThreeTierSmoother:
    """
    Production-grade 3-tier adaptive emotion smoother.
    
    Features:
    - FPS-invariant smoothing via alpha scaling
    - Entropy-based ambiguity detection
    - Tier-specific cooldown to prevent bounce
    - Margin-aware switching requirements
    - Input sanitization (NaN/inf/negative handling)
    - Neutral stickiness (scoped to neutral state)
    - Performance optimized with slots and preallocated structures
    """
    
    def __init__(self):
        """Initialize 3-tier adaptive smoother"""
        self.state = SmoothingState()
        
        # Validate config on initialization
        validate_config()
        
        # Cache tier configs for performance
        self.tier_configs = TIER_CONFIGS.copy()
    
    def _is_in_cooldown(self, ts_ms: int) -> bool:
        """Check if currently in cooldown period"""
        return ts_ms < self.state.cooldown_expiry_ms
    
    def _update_ema(self, raw_probs: Dict[str, float], alpha_eff: float) -> Dict[str, float]:
        """
        Update EMA with FPS-scaled alpha.
        
        Args:
            raw_probs: Raw probability dictionary
            alpha_eff: Effective alpha (FPS-scaled)
            
        Returns:
            Updated EMA probabilities
        """
        if not self.state.ema_probs:
            # Initialize EMA on first frame
            self.state.ema_probs = raw_probs.copy()
        else:
            # Update EMA: p_ema_t = alpha_eff * p_t + (1 - alpha_eff) * p_ema_{t-1}
            for emotion, p_raw in raw_probs.items():
                p_prev = self.state.ema_probs.get(emotion, 0.0)
                self.state.ema_probs[emotion] = alpha_eff * p_raw + (1.0 - alpha_eff) * p_prev
        
        return self.state.ema_probs.copy()
    
    def _reset_ema(self, raw_probs: Dict[str, float]):
        """Reset EMA state to current raw probs"""
        self.state.ema_probs = raw_probs.copy()
    
    def _get_dominant_emotion(self, probs: Dict[str, float]) -> str:
        """Get dominant emotion from probability dict"""
        return max(probs, key=probs.get)
    
    def _apply_tier1_logic(
        self,
        raw_probs: Dict[str, float],
        ts_ms: int,
        p_max: float,
        margin: float,
        entropy: float
    ) -> SmoothedResult:
        """
        Tier 1: Instant response for high-confidence emotions.
        
        Logic:
        - Skip EMA smoothing entirely
        - Reset EMA if emotion changes AND p_max >= EMA_RESET_THRESHOLD
        - Apply 120ms cooldown after switch
        - Use minimal window (2 frames) for majority voting
        """
        config = self.tier_configs[1]
        dt_ms = ts_ms - self.state.last_ts_ms if self.state.last_ts_ms > 0 else FPS_REFERENCE_MS
        alpha_eff = _compute_alpha_eff(config["alpha"], dt_ms)
        
        # Get raw dominant emotion
        raw_dominant = self._get_dominant_emotion(raw_probs)
        
        # Check if emotion changed
        emotion_changed = raw_dominant != self.state.current_label
        
        # Check cooldown before allowing switch
        if emotion_changed and not self._is_in_cooldown(ts_ms):
            # EMA reset logic: if p_max >= EMA_RESET_THRESHOLD
            if p_max >= EMA_RESET_THRESHOLD:
                self._reset_ema(raw_probs)
            
            # Allow switch
            self.state.current_label = raw_dominant
            self.state.last_change_ts_ms = ts_ms
            self.state.cooldown_expiry_ms = ts_ms + config["cooldown_ms"]
            self.state.candidate_emotion = None
            self.state.candidate_start_ms = None
        
        # Use raw probs (no smoothing) but update EMA for consistency
        self._update_ema(raw_probs, alpha_eff)
        
        # Calculate confidence and scores
        confidence = raw_probs.get(self.state.current_label, 0.0) * 100.0
        scores = {e: raw_probs[e] * 100.0 for e in EMOTIONS}
        
        # Calculate diagnostics
        hold_ms_remaining = 0  # Tier 1 doesn't use hold time
        cooldown_ms_left = max(0, self.state.cooldown_expiry_ms - ts_ms)
        
        return SmoothedResult(
            label=self.state.current_label,
            confidence=float(confidence),
            scores=scores,
            tier=1,
            alpha_eff=alpha_eff,
            margin=margin,
            entropy=entropy,
            hold_ms_remaining=hold_ms_remaining,
            cooldown_ms_left=cooldown_ms_left
        )
    
    def _apply_tier2_logic(
        self,
        raw_probs: Dict[str, float],
        ts_ms: int,
        p_max: float,
        margin: float,
        entropy: float
    ) -> SmoothedResult:
        """
        Tier 2: Minimal smoothing for medium-confidence emotions.
        
        Logic:
        - Apply light EMA (alpha=0.82)
        - Require margin >= 0.15 unless p_max >= 0.9
        - Use window=5, hold_ms=300, cooldown=180ms
        - FAST-PATH: Micro-expressions (surprise/fear) bypass hold time if > 65%
        """
        config = self.tier_configs[2]
        dt_ms = ts_ms - self.state.last_ts_ms if self.state.last_ts_ms > 0 else FPS_REFERENCE_MS
        alpha_eff = _compute_alpha_eff(config["alpha"], dt_ms)
        
        # Update EMA
        ema_probs = self._update_ema(raw_probs, alpha_eff)
        ema_dominant = self._get_dominant_emotion(ema_probs)
        
        # Check if should switch
        should_switch = False
        
        if ema_dominant != self.state.current_label:
            # MICRO-EXPRESSION FAST-PATH: Allow instant switch for surprise/fear if confidence high
            is_micro_expr = ema_dominant in MICRO_EXPRESSION_EMOTIONS
            candidate_prob = ema_probs.get(ema_dominant, 0.0)
            
            if is_micro_expr and candidate_prob >= MICRO_EXPRESSION_THRESHOLD:
                # Bypass normal hold time for transient emotions
                if not self._is_in_cooldown(ts_ms):
                    # Track candidate briefly
                    if self.state.candidate_emotion != ema_dominant:
                        self.state.candidate_emotion = ema_dominant
                        self.state.candidate_start_ms = ts_ms
                    
                    # Use minimal hold time
                    time_held = ts_ms - (self.state.candidate_start_ms or ts_ms)
                    if time_held >= MICRO_EXPRESSION_HOLD_MS:
                        should_switch = True
            # Normal path
            elif p_max >= 0.9 or margin >= MIN_MARGIN_T2:
                # Check cooldown
                if not self._is_in_cooldown(ts_ms):
                    # Track candidate
                    if self.state.candidate_emotion != ema_dominant:
                        self.state.candidate_emotion = ema_dominant
                        self.state.candidate_start_ms = ts_ms
                    
                    # Check hold time
                    time_held = ts_ms - (self.state.candidate_start_ms or ts_ms)
                    if time_held >= config["hold_ms"]:
                        should_switch = True
        else:
            # Reset candidate if matches current
            self.state.candidate_emotion = None
            self.state.candidate_start_ms = None
        
        # Apply switch if needed
        if should_switch:
            self.state.current_label = ema_dominant
            self.state.last_change_ts_ms = ts_ms
            self.state.cooldown_expiry_ms = ts_ms + config["cooldown_ms"]
            self.state.candidate_emotion = None
            self.state.candidate_start_ms = None
        
        # Calculate confidence and scores
        confidence = ema_probs.get(self.state.current_label, 0.0) * 100.0
        scores = {e: ema_probs[e] * 100.0 for e in EMOTIONS}
        
        # Calculate diagnostics
        hold_ms_remaining = 0
        if self.state.candidate_emotion and self.state.candidate_start_ms:
            time_held = ts_ms - self.state.candidate_start_ms
            hold_ms_remaining = max(0, config["hold_ms"] - time_held)
        cooldown_ms_left = max(0, self.state.cooldown_expiry_ms - ts_ms)
        
        return SmoothedResult(
            label=self.state.current_label,
            confidence=float(confidence),
            scores=scores,
            tier=2,
            alpha_eff=alpha_eff,
            margin=margin,
            entropy=entropy,
            hold_ms_remaining=hold_ms_remaining,
            cooldown_ms_left=cooldown_ms_left
        )
    
    def _apply_tier3_logic(
        self,
        raw_probs: Dict[str, float],
        ts_ms: int,
        p_max: float,
        margin: float,
        entropy: float
    ) -> SmoothedResult:
        """
        Tier 3: Full smoothing for low-confidence emotions.
        
        Logic:
        - Apply full EMA (alpha=0.62)
        - Require margin >= 0.20 unless p_max >= 0.9
        - Require uplift threshold (+0.08) to switch
        - Apply neutral stickiness (scoped to neutral state only)
        - Use window=9, hold_ms=500, cooldown=220ms
        - FAST-PATH: Micro-expressions (surprise/fear) bypass hold time if > 65%
        """
        config = self.tier_configs[3]
        dt_ms = ts_ms - self.state.last_ts_ms if self.state.last_ts_ms > 0 else FPS_REFERENCE_MS
        alpha_eff = _compute_alpha_eff(config["alpha"], dt_ms)
        
        # Update EMA
        ema_probs = self._update_ema(raw_probs, alpha_eff)
        ema_dominant = self._get_dominant_emotion(ema_probs)
        
        # Neutral stickiness logic (only when current == "neutral")
        # BUT: Allow micro-expressions to bypass neutral stickiness
        is_micro_expr = ema_dominant in MICRO_EXPRESSION_EMOTIONS
        candidate_prob = ema_probs.get(ema_dominant, 0.0)
        
        if self.state.current_label == "neutral" and not (is_micro_expr and candidate_prob >= MICRO_EXPRESSION_THRESHOLD):
            # Check if all probs below threshold
            all_below_threshold = all(p < NEUTRAL_STICKY_THRESHOLD for p in ema_probs.values())
            
            if all_below_threshold:
                # Track how long we've been in low-confidence neutral state
                if self.state.low_confidence_start_ms is None:
                    self.state.low_confidence_start_ms = ts_ms
                
                time_in_low_conf = ts_ms - self.state.low_confidence_start_ms
                if time_in_low_conf >= NEUTRAL_STICKY_MS:
                    # Stay neutral due to stickiness
                    confidence = ema_probs.get("neutral", 0.0) * 100.0
                    scores = {e: ema_probs[e] * 100.0 for e in EMOTIONS}
                    
                    return SmoothedResult(
                        label="neutral",
                        confidence=float(confidence),
                        scores=scores,
                        tier=3,
                        alpha_eff=alpha_eff,
                        margin=margin,
                        entropy=entropy,
                        hold_ms_remaining=0,
                        cooldown_ms_left=max(0, self.state.cooldown_expiry_ms - ts_ms)
                    )
            else:
                # Reset low confidence tracking
                self.state.low_confidence_start_ms = None
        else:
            # Not in neutral state, reset tracking
            self.state.low_confidence_start_ms = None
        
        # Check if should switch
        should_switch = False
        
        if ema_dominant != self.state.current_label:
            # MICRO-EXPRESSION FAST-PATH: Allow faster switch for surprise/fear
            if is_micro_expr and candidate_prob >= MICRO_EXPRESSION_THRESHOLD:
                # Relax requirements for transient emotions
                if not self._is_in_cooldown(ts_ms):
                    # Track candidate briefly
                    if self.state.candidate_emotion != ema_dominant:
                        self.state.candidate_emotion = ema_dominant
                        self.state.candidate_start_ms = ts_ms
                    
                    # Use minimal hold time (ignore margin/uplift requirements)
                    time_held = ts_ms - (self.state.candidate_start_ms or ts_ms)
                    if time_held >= MICRO_EXPRESSION_HOLD_MS:
                        should_switch = True
            else:
                # Normal path
                # Check margin requirement (unless p_max >= 0.9)
                margin_ok = (p_max >= 0.9 or margin >= MIN_MARGIN_T3)
                
                # Check uplift requirement
                current_prob = ema_probs.get(self.state.current_label, 0.0)
                uplift = candidate_prob - current_prob
                uplift_ok = uplift >= config["uplift"]
                
                if margin_ok and uplift_ok:
                    # Check cooldown
                    if not self._is_in_cooldown(ts_ms):
                        # Track candidate
                        if self.state.candidate_emotion != ema_dominant:
                            self.state.candidate_emotion = ema_dominant
                            self.state.candidate_start_ms = ts_ms
                        
                        # Check hold time
                        time_held = ts_ms - (self.state.candidate_start_ms or ts_ms)
                        if time_held >= config["hold_ms"]:
                            should_switch = True
        else:
            # Reset candidate if matches current
            self.state.candidate_emotion = None
            self.state.candidate_start_ms = None
        
        # Apply switch if needed
        if should_switch:
            self.state.current_label = ema_dominant
            self.state.last_change_ts_ms = ts_ms
            self.state.cooldown_expiry_ms = ts_ms + config["cooldown_ms"]
            self.state.candidate_emotion = None
            self.state.candidate_start_ms = None
            self.state.low_confidence_start_ms = None
        
        # Calculate confidence and scores
        confidence = ema_probs.get(self.state.current_label, 0.0) * 100.0
        scores = {e: ema_probs[e] * 100.0 for e in EMOTIONS}
        
        # Calculate diagnostics
        hold_ms_remaining = 0
        if self.state.candidate_emotion and self.state.candidate_start_ms:
            time_held = ts_ms - self.state.candidate_start_ms
            hold_ms_remaining = max(0, config["hold_ms"] - time_held)
        cooldown_ms_left = max(0, self.state.cooldown_expiry_ms - ts_ms)
        
        return SmoothedResult(
            label=self.state.current_label,
            confidence=float(confidence),
            scores=scores,
            tier=3,
            alpha_eff=alpha_eff,
            margin=margin,
            entropy=entropy,
            hold_ms_remaining=hold_ms_remaining,
            cooldown_ms_left=cooldown_ms_left
        )
    
    def update(self, raw_probs: Dict[str, float], ts_ms: int) -> SmoothedResult:
        """
        Main smoothing update with monotonic timestamp.
        
        Args:
            raw_probs: Raw probability dict {emotion: prob} (0-1 range)
            ts_ms: Monotonic timestamp in milliseconds
            
        Returns:
            SmoothedResult with diagnostics
        """
        # Sanitize input
        sanitized_probs = _sanitize_probs(raw_probs)
        
        # Detect tier
        tier, p_max, margin, entropy = _detect_tier(sanitized_probs)
        
        # Apply tier-specific logic
        if tier == 1:
            result = self._apply_tier1_logic(sanitized_probs, ts_ms, p_max, margin, entropy)
        elif tier == 2:
            result = self._apply_tier2_logic(sanitized_probs, ts_ms, p_max, margin, entropy)
        else:  # tier == 3
            result = self._apply_tier3_logic(sanitized_probs, ts_ms, p_max, margin, entropy)
        
        # Update last timestamp
        self.state.last_ts_ms = ts_ms
        
        return result
    
    def process(self, raw_probs: Dict[str, float]) -> Dict:
        """
        Legacy interface for backward compatibility.
        Auto-generates monotonic timestamp.
        
        Args:
            raw_probs: Raw probability dict {emotion: prob} (0-1 range)
            
        Returns:
            Dictionary with dominant_emotion, confidence, and scores
        """
        ts_ms = time.monotonic_ns() // 1_000_000
        result = self.update(raw_probs, ts_ms)
        
        return {
            "dominant_emotion": result.label,
            "confidence": result.confidence,
            "scores": result.scores
        }
    
    def reset(self) -> None:
        """Reset smoother state"""
        self.state = SmoothingState()


# ============================================================================
# FACTORY FUNCTION
# ============================================================================


def get_smoother(mode: str = SMOOTHING_MODE):
    """
    Factory function to create appropriate smoother based on mode.
    
    Args:
        mode: Smoothing mode ("basic" or "3tier")
        
    Returns:
        Smoother instance (EmaMajorityHysteresis or AdaptiveThreeTierSmoother)
    """
    if mode == "3tier":
        return AdaptiveThreeTierSmoother()
    else:
        return EmaMajorityHysteresis()

