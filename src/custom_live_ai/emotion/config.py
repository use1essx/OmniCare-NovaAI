"""
Emotion detection configuration constants
"""

import logging

logger = logging.getLogger(__name__)

# ============================================================================
# SMOOTHING MODE (Feature Flag)
# ============================================================================
SMOOTHING_MODE = "none"  # Options: "basic" (legacy), "3tier" (adaptive), "none" (pure Face-API.js)

# ============================================================================
# LEGACY SMOOTHING PARAMETERS (for "basic" mode)
# ============================================================================
FEATURE_WINDOW = 30  # Number of frames for temporal statistics
EMA_ALPHA = 0.5  # Exponential moving average alpha
MAJORITY_WINDOW = 15  # Window size for majority voting
HYST_MIN_HOLD_MS = 400  # Minimum hold time before switching emotions (ms)
RANDOM_SEED = 42  # Random seed for reproducibility

# ============================================================================
# 3-TIER ADAPTIVE SMOOTHING PARAMETERS
# ============================================================================

# Tier Thresholds - ULTRA-MINIMAL SMOOTHING MODE (Face-API.js is already accurate)
T1_THRESHOLD = 0.50  # Trust Face-API.js at 50%+
T2_THRESHOLD = 0.35  # Medium confidence
MIN_MARGIN_T1 = 0.05  # Very small margin required
MIN_MARGIN_T2 = 0.03  # Almost no margin required
MIN_MARGIN_T3 = 0.05  # Small margin
EMA_RESET_THRESHOLD = 0.70  # Reset often to follow Face-API.js
ENTROPY_MAX = 2.5  # Allow more ambiguous states (trust Face-API.js)

# Tier-Specific Smoothing Parameters
# ULTRA-MINIMAL MODE - Face-API.js is already accurate, just filter single-frame noise
TIER_CONFIGS = {
    1: {  # Tier 1: Instant (no delay)
        "alpha": 0.99,  # Nearly raw Face-API.js scores
        "window": 1,     # No majority voting
        "hold_ms": 0,    # Zero hold time
        "cooldown_ms": 0  # Zero cooldown
    },
    2: {  # Tier 2: Ultra-light smoothing
        "alpha": 0.98,  # Almost raw
        "window": 1,     # No voting
        "hold_ms": 10,   # 10ms (imperceptible)
        "cooldown_ms": 10  # 10ms cooldown
    },
    3: {  # Tier 3: Light smoothing only
        "alpha": 0.95,  # Still very responsive
        "window": 2,     # Minimal voting
        "hold_ms": 30,   # 30ms
        "cooldown_ms": 30,  # Short cooldown
        "uplift": 0.01  # Very easy to switch
    }
}

# Neutral Stickiness - DISABLED (trust Face-API.js)
NEUTRAL_STICKY_THRESHOLD = 0.05  # Essentially disabled
NEUTRAL_STICKY_MS = 5000  # 5 seconds before sticking (almost never triggered)

# FPS Reference (for alpha scaling)
FPS_REFERENCE_MS = 33.3  # 30 FPS reference frame time

# ============================================================================
# EMOTION CLASSES
# ============================================================================
EMOTIONS = ["neutral", "happy", "sad", "angry", "surprise", "fear", "disgust"]

# ============================================================================
# MICRO-EXPRESSION FAST-PATH
# ============================================================================
# Transient emotions that need faster detection (bypass normal hold times)
MICRO_EXPRESSION_EMOTIONS = ["surprise", "fear"]  
MICRO_EXPRESSION_THRESHOLD = 0.50  # If surprise/fear > 50%, allow instant switch
MICRO_EXPRESSION_HOLD_MS = 0  # Zero hold time (instant)

# ============================================================================
# CONFIG VALIDATION
# ============================================================================

def validate_config() -> bool:
    """
    Validate 3-tier smoothing configuration parameters.
    
    Returns:
        True if config is valid, False if issues found (logs warnings)
    """
    is_valid = True
    
    # Validate tier thresholds
    if not (T1_THRESHOLD > T2_THRESHOLD):
        logger.warning("Config invalid: T1_THRESHOLD (%s) must be > T2_THRESHOLD (%s)", T1_THRESHOLD, T2_THRESHOLD)
        is_valid = False
    
    if not (T2_THRESHOLD > 0 and T1_THRESHOLD <= 1.0):
        logger.warning("Config invalid: Thresholds must be in (0, 1] range")
        is_valid = False
    
    # Validate tier configs
    for tier, config in TIER_CONFIGS.items():
        alpha = config.get("alpha", 0.0)
        if not (0 < alpha < 1):
            logger.warning("Config invalid: Tier %s alpha (%s) must be in (0, 1)", tier, alpha)
            is_valid = False
        
        window = config.get("window", 0)
        if window < 1:
            logger.warning("Config invalid: Tier %s window (%s) must be >= 1", tier, window)
            is_valid = False
        
        hold_ms = config.get("hold_ms", 0)
        if hold_ms < 0:
            logger.warning("Config invalid: Tier %s hold_ms (%s) must be >= 0", tier, hold_ms)
            is_valid = False
        
        cooldown_ms = config.get("cooldown_ms", 0)
        if cooldown_ms < 0:
            logger.warning("Config invalid: Tier %s cooldown_ms (%s) must be >= 0", tier, cooldown_ms)
            is_valid = False
    
    # Validate Tier 3 uplift
    uplift = TIER_CONFIGS[3].get("uplift", 0.0)
    if uplift <= 0:
        logger.warning("Config invalid: Tier 3 uplift (%s) must be > 0", uplift)
        is_valid = False
    
    # Validate margins
    if not (MIN_MARGIN_T1 > 0 and MIN_MARGIN_T2 > 0 and MIN_MARGIN_T3 > 0):
        logger.warning("Config invalid: All margin thresholds must be > 0")
        is_valid = False
    
    # Validate entropy
    if ENTROPY_MAX <= 0:
        logger.warning("Config invalid: ENTROPY_MAX (%s) must be > 0", ENTROPY_MAX)
        is_valid = False
    
    # Validate neutral stickiness
    if not (0 < NEUTRAL_STICKY_THRESHOLD < 1):
        logger.warning("Config invalid: NEUTRAL_STICKY_THRESHOLD must be in (0, 1)")
        is_valid = False
    
    if NEUTRAL_STICKY_MS < 0:
        logger.warning("Config invalid: NEUTRAL_STICKY_MS must be >= 0")
        is_valid = False
    
    if not is_valid:
        logger.warning("Using default safe configuration due to validation errors")
    
    return is_valid

# ============================================================================
# LOGGING & MODEL PATHS
# ============================================================================

# Logging configuration
ENABLE_LOGGING = False  # Toggle parquet logging (set via environment)

# Model paths
MODEL_PATH = "./models/emotion_model.joblib"
TRAINING_REPORT_PATH = "./models/last_train_report.json"

# Feature extraction
LANDMARK_COUNT = 468  # MediaPipe face mesh landmark count

