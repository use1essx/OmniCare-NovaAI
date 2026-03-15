"""
Language Manager

Handles language preferences and injects appropriate language instructions
into AI prompts to ensure responses are in the correct language.

Supports:
- English (en)
- Traditional Chinese - Hong Kong (zh-HK)

Note: Simplified Chinese (zh-CN) requests are automatically converted to zh-HK.

Priority:
1. User profile language_preference (if logged in)
2. Request language parameter
3. Auto-detect from message content
4. Default to English
"""

import logging
import re
from typing import Optional, Dict

from src.core.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


class LanguageManager:
    """
    Manages language preferences and provides language-aware prompts.
    """
    
    # Supported languages (English and Traditional Chinese - Hong Kong only)
    SUPPORTED_LANGUAGES = ["en", "zh-HK"]
    DEFAULT_LANGUAGE = "en"
    
    # Language detection patterns
    CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]+')
    
    def __init__(self):
        """Initialize language manager and load prompts."""
        self._language_prompts: Dict[str, str] = {}
        self._load_language_prompts()
    
    def _load_language_prompts(self):
        """Load language instruction prompts from files."""
        for lang in self.SUPPORTED_LANGUAGES:
            prompt = load_prompt(f"language/{lang}", default="")
            if prompt:
                self._language_prompts[lang] = prompt
                logger.debug(f"Loaded language prompt for: {lang}")
            else:
                logger.warning(f"No language prompt found for: {lang}")
    
    def detect_language(self, message: str) -> str:
        """
        Auto-detect language from message content.
        
        Args:
            message: User message text
            
        Returns:
            Detected language code
        """
        if not message:
            return self.DEFAULT_LANGUAGE
        
        # Check for Chinese characters
        chinese_chars = self.CHINESE_PATTERN.findall(message)
        if chinese_chars:
            total_chars = len(message.replace(" ", ""))
            chinese_ratio = sum(len(c) for c in chinese_chars) / total_chars if total_chars > 0 else 0
            
            if chinese_ratio > 0.3:
                # Predominantly Chinese - default to HK Traditional
                return "zh-HK"
        
        return "en"
    
    def resolve_language(
        self,
        request_language: Optional[str] = None,
        user_preference: Optional[str] = None,
        message: Optional[str] = None,
        auto_detect: bool = True
    ) -> str:
        """
        Resolve which language to use based on priority.
        
        Priority:
        1. Request language parameter (user's explicit selection)
        2. User profile preference (if available)
        3. Auto-detect from message
        4. Default
        
        Args:
            request_language: Language from the request
            user_preference: User's profile language preference
            message: User message for auto-detection
            auto_detect: Whether to auto-detect from message
            
        Returns:
            Resolved language code
        """
        # Priority 1: Request language (user's explicit selection takes highest priority)
        if request_language and request_language in self.SUPPORTED_LANGUAGES:
            logger.debug(f"Using request language: {request_language}")
            return request_language
        
        # Priority 2: User profile preference
        if user_preference and user_preference in self.SUPPORTED_LANGUAGES:
            logger.debug(f"Using user profile language: {user_preference}")
            return user_preference
        
        # Priority 3: Auto-detect
        if auto_detect and message:
            detected = self.detect_language(message)
            logger.debug(f"Auto-detected language: {detected}")
            return detected
        
        # Priority 4: Default
        return self.DEFAULT_LANGUAGE
    
    def get_language_instruction(self, language: str) -> str:
        """
        Get the language instruction prompt for a specific language.
        
        Args:
            language: Language code
            
        Returns:
            Language instruction text
        """
        if language not in self._language_prompts:
            # Try to load it
            prompt = load_prompt(f"language/{language}", default="")
            if prompt:
                self._language_prompts[language] = prompt
        
        return self._language_prompts.get(language, "")
    
    def inject_language_instruction(
        self,
        system_prompt: str,
        language: str
    ) -> str:
        """
        Inject language instruction into the system prompt.
        
        Args:
            system_prompt: Original system prompt
            language: Target language code
            
        Returns:
            System prompt with language instruction prepended
        """
        instruction = self.get_language_instruction(language)
        
        if not instruction:
            return system_prompt
        
        # Add language instruction at the beginning
        return f"{instruction}\n\n---\n\n{system_prompt}"
    
    def get_language_name(self, language: str) -> str:
        """Get human-readable language name."""
        names = {
            "en": "English",
            "zh-HK": "繁體中文（香港）"
        }
        return names.get(language, language)
    
    def normalize_language(self, language: str) -> str:
        """
        Normalize language code to supported format.
        
        Args:
            language: Input language code (various formats)
            
        Returns:
            Normalized language code
        """
        if not language:
            return self.DEFAULT_LANGUAGE
        
        language = language.lower().strip()
        
        # Map common variants (all Chinese variants map to zh-HK Traditional)
        mappings = {
            "en": "en",
            "en-us": "en",
            "en-gb": "en",
            "english": "en",
            "zh": "zh-HK",
            "zh-hk": "zh-HK",
            "zh-tw": "zh-HK",
            "zh-cn": "zh-HK",  # Map Simplified to Traditional HK
            "chinese": "zh-HK",
            "cantonese": "zh-HK",
            "mandarin": "zh-HK",  # Map Mandarin to Traditional HK
        }
        
        return mappings.get(language, self.DEFAULT_LANGUAGE)


# Singleton instance
_language_manager: Optional[LanguageManager] = None


def get_language_manager() -> LanguageManager:
    """Get or create the language manager singleton."""
    global _language_manager
    if _language_manager is None:
        _language_manager = LanguageManager()
    return _language_manager


def resolve_language(
    request_language: Optional[str] = None,
    user_preference: Optional[str] = None,
    message: Optional[str] = None
) -> str:
    """
    Convenience function to resolve language.
    
    Args:
        request_language: Language from request
        user_preference: User profile preference
        message: Message for auto-detection
        
    Returns:
        Resolved language code
    """
    return get_language_manager().resolve_language(
        request_language=request_language,
        user_preference=user_preference,
        message=message
    )


def inject_language_instruction(system_prompt: str, language: str) -> str:
    """
    Convenience function to inject language instruction.
    
    Args:
        system_prompt: Original prompt
        language: Target language
        
    Returns:
        Prompt with language instruction
    """
    return get_language_manager().inject_language_instruction(system_prompt, language)

