"""
Healthcare AI V2 - API Security
Secure API key management and monitoring for AWS Bedrock
"""

import logging
from datetime import datetime
from typing import Optional
from src.core.config import settings

logger = logging.getLogger(__name__)


class APIKeyManager:
    """Secure API key management utilities"""
    
    @staticmethod
    def get_aws_credentials() -> tuple[Optional[str], Optional[str]]:
        """
        Safely retrieve AWS credentials from environment
        Never logs or exposes the actual credential values
        
        Returns:
            Tuple of (access_key_id, secret_access_key)
        """
        try:
            access_key = settings.aws_access_key_id
            secret_key = settings.aws_secret_access_key
            
            if access_key and secret_key:
                # SECURITY: Only log that we found credentials, never the actual values
                logger.debug("AWS credentials loaded from environment")
                return access_key, secret_key
            else:
                logger.warning("AWS credentials not found in environment variables")
                return None, None
        except Exception as e:
            logger.error(f"Error loading AWS credentials: {e}")
            return None, None
    
    @staticmethod
    def mask_api_key(api_key: str) -> str:
        """
        Safely mask an API key for logging purposes
        Shows only the prefix and suffix for identification
        """
        if not api_key or len(api_key) < 10:
            return "***hidden***"
        
        # Show first 6 characters and last 4, mask the middle
        masked = api_key[:6] + "*" * (len(api_key) - 10) + api_key[-4:]
        return masked
    
    @staticmethod
    def validate_aws_credentials(access_key: str, secret_key: str) -> bool:
        """
        Validate AWS credential format without exposing the keys
        Returns True if format looks correct
        
        Args:
            access_key: AWS access key ID
            secret_key: AWS secret access key
            
        Returns:
            True if credentials format is valid
        """
        if not access_key or not secret_key:
            return False
        
        # AWS access keys should start with 'AKIA' and be 20 characters
        # AWS secret keys should be 40 characters
        if access_key.startswith('AKIA') and len(access_key) == 20:
            if len(secret_key) == 40:
                return True
        
        return False
    
    @staticmethod
    def is_aws_configured() -> bool:
        """
        Check if AWS credentials are configured without exposing them
        
        Returns:
            True if AWS credentials are properly configured
        """
        access_key, secret_key = APIKeyManager.get_aws_credentials()
        if not access_key or not secret_key:
            return False
        return APIKeyManager.validate_aws_credentials(access_key, secret_key)
    
    @staticmethod
    def get_safe_status() -> dict:
        """
        Get AWS credential status for monitoring without exposing sensitive data
        
        Returns:
            Dictionary with credential status information
        """
        access_key, secret_key = APIKeyManager.get_aws_credentials()
        
        if not access_key or not secret_key:
            return {
                "configured": False,
                "format_valid": False,
                "status": "not_configured",
                "key_prefix": "***",
                "key_suffix": "***",
                "key_length": 0,
                "source": "environment_variable",
                "provider": "aws_bedrock",
                "last_checked": datetime.now().isoformat()
            }
        
        format_valid = APIKeyManager.validate_aws_credentials(access_key, secret_key)
        
        return {
            "configured": True,
            "format_valid": format_valid,
            "status": "configured" if format_valid else "invalid_format",
            "key_prefix": access_key[:6] if len(access_key) >= 6 else "***",
            "key_suffix": access_key[-4:] if len(access_key) >= 4 else "***",
            "key_length": len(access_key),
            "source": "environment_variable",
            "provider": "aws_bedrock",
            "last_checked": datetime.now().isoformat()
        }


def log_api_operation(operation: str, success: bool, details: str = None):
    """
    Log API operations securely without exposing sensitive data
    """
    if success:
        logger.info(f"API operation successful: {operation}")
    else:
        logger.error(f"API operation failed: {operation} - {details or 'Unknown error'}")


# Security reminder for developers
def _security_reminder():
    """
    Development reminder about API key security
    """
    logger.info(
        "🔒 API Security Reminder: Never log, print, or expose actual AWS credential values. "
        "Use APIKeyManager utilities for safe handling."
    )


# Initialize security reminder in development
if settings.debug:
    _security_reminder()


__all__ = [
    "APIKeyManager",
    "log_api_operation",
]










