"""
AI-Enhanced Semantic Chunking Configuration

This module provides configuration constants and utilities for the AI-enhanced
semantic chunking feature in the knowledge base document ingestion system.

Configuration is loaded from environment variables via the main Settings class,
with sensible defaults for backward compatibility.
"""

import os
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# FEATURE FLAG
# =============================================================================

def is_semantic_chunking_enabled() -> bool:
    """
    Check if AI semantic chunking is enabled.
    
    Returns:
        bool: True if AI semantic chunking is enabled, False otherwise
        
    Note:
        Defaults to False for backward compatibility with simple chunking.
    """
    # DIAGNOSTIC: Log feature flag check
    env_value = os.getenv("AI_SEMANTIC_CHUNKING_ENABLED")
    settings_value = settings.ai_semantic_chunking_enabled
    
    logger.debug(
        "Feature flag check: AI_SEMANTIC_CHUNKING_ENABLED",
        extra={
            "env_variable": env_value,
            "settings_value": settings_value,
            "final_value": settings_value
        }
    )
    
    if env_value and env_value.lower() != str(settings_value).lower():
        logger.warning(
            "Discrepancy between environment variable and settings",
            extra={
                "env_variable": env_value,
                "settings_value": settings_value
            }
        )
    
    return settings_value


# =============================================================================
# AI SERVICE CONFIGURATION
# =============================================================================

# Timeout for AI service calls during chunking (seconds)
SEMANTIC_CHUNK_TIMEOUT: int = settings.semantic_chunk_timeout

# Maximum concurrent AI requests for metadata generation
SEMANTIC_CHUNK_MAX_CONCURRENT: int = settings.semantic_chunk_max_concurrent


# =============================================================================
# CHUNK SIZE CONFIGURATION
# =============================================================================

# Minimum chunk size in characters
SEMANTIC_CHUNK_MIN_SIZE: int = 200

# Maximum chunk size in characters
SEMANTIC_CHUNK_MAX_SIZE: int = 1200

# Target chunk sizes by content complexity
SEMANTIC_CHUNK_TARGET_LOW: int = 1000      # Simple content
SEMANTIC_CHUNK_TARGET_MEDIUM: int = 650    # Standard content
SEMANTIC_CHUNK_TARGET_HIGH: int = 450      # Complex/dense content

# Maximum overlap between consecutive chunks (characters)
SEMANTIC_CHUNK_MAX_OVERLAP: int = 150


# =============================================================================
# CONFIGURATION SUMMARY
# =============================================================================

def get_chunking_config() -> dict:
    """
    Get complete chunking configuration as a dictionary.
    
    Returns:
        dict: All chunking configuration values
        
    Example:
        >>> config = get_chunking_config()
        >>> print(f"Semantic chunking enabled: {config['enabled']}")
        >>> print(f"Min chunk size: {config['min_size']}")
    """
    return {
        "enabled": is_semantic_chunking_enabled(),
        "timeout": SEMANTIC_CHUNK_TIMEOUT,
        "max_concurrent": SEMANTIC_CHUNK_MAX_CONCURRENT,
        "min_size": SEMANTIC_CHUNK_MIN_SIZE,
        "max_size": SEMANTIC_CHUNK_MAX_SIZE,
        "target_low": SEMANTIC_CHUNK_TARGET_LOW,
        "target_medium": SEMANTIC_CHUNK_TARGET_MEDIUM,
        "target_high": SEMANTIC_CHUNK_TARGET_HIGH,
        "max_overlap": SEMANTIC_CHUNK_MAX_OVERLAP,
    }
