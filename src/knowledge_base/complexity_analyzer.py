"""
Content complexity analyzer for semantic chunking.

This module provides AI-powered analysis of content complexity to guide
adaptive chunk sizing. The ComplexityAnalyzer uses AI to evaluate text
based on vocabulary, sentence structure, concept density, and technical
terminology to classify content as low, medium, or high complexity.
"""

import json
import logging
from typing import Literal

from src.ai.ai_service import get_ai_service

logger = logging.getLogger(__name__)

# Type alias for complexity levels
ComplexityLevel = Literal["low", "medium", "high"]


class ComplexityAnalyzer:
    """
    Analyzes content complexity using AI to guide adaptive chunk sizing.
    
    This class uses AI to evaluate text complexity based on multiple factors:
    - Vocabulary complexity (simple vs. technical terms)
    - Sentence structure (simple vs. complex sentences)
    - Concept density (how many concepts per unit of text)
    - Technical terminology (domain-specific jargon)
    - Information density (amount of information conveyed)
    
    The complexity level determines target chunk sizes:
    - Low complexity: Simple explanatory text, basic concepts (target: 1000 chars)
    - Medium complexity: Standard informational content (target: 650 chars)
    - High complexity: Dense technical content, complex concepts (target: 450 chars)
    
    Attributes:
        ai_service: AI service instance for making complexity analysis calls
    
    Example:
        >>> analyzer = ComplexityAnalyzer()
        >>> await analyzer.initialize()
        >>> complexity = await analyzer.analyze_complexity(
        ...     "This is simple text about basic concepts.",
        ...     "en"
        ... )
        >>> complexity
        'low'
    """
    
    def __init__(self):
        """Initialize the ComplexityAnalyzer."""
        self.ai_service = None
    
    async def initialize(self):
        """
        Initialize the AI service connection.
        
        This method must be called before using analyze_complexity.
        It establishes the connection to the AI service.
        
        Example:
            >>> analyzer = ComplexityAnalyzer()
            >>> await analyzer.initialize()
        """
        self.ai_service = await get_ai_service()
        logger.info("ComplexityAnalyzer initialized with AI service")
    
    async def analyze_complexity(
        self,
        text: str,
        language: str
    ) -> ComplexityLevel:
        """
        Analyze content complexity using AI.
        
        Uses AI to evaluate the text and classify its complexity level based on
        vocabulary, sentence structure, concept density, technical terminology,
        and information density.
        
        Args:
            text: The text content to analyze (should be a representative sample)
            language: Language code (e.g., "en", "zh-HK")
            
        Returns:
            Complexity level: "low", "medium", or "high"
            
        Raises:
            ValueError: If AI service is not initialized or returns invalid response
            Exception: If AI service call fails
            
        Example:
            >>> analyzer = ComplexityAnalyzer()
            >>> await analyzer.initialize()
            >>> complexity = await analyzer.analyze_complexity(
            ...     "Quantum entanglement exhibits non-local correlations...",
            ...     "en"
            ... )
            >>> complexity
            'high'
        """
        if self.ai_service is None:
            raise ValueError(
                "AI service not initialized. Call initialize() first."
            )
        
        # VALIDATION: Sanitize input (Requirements 9.3)
        if not text or not text.strip():
            logger.warning("Empty text provided for complexity analysis")
            return "medium"  # Default to medium for empty text
        
        # VALIDATION: Sanitize content before AI call
        sanitized_text = self._sanitize_text(text)
        
        # Truncate text if too long (analyze first 500 chars for efficiency)
        analysis_text = sanitized_text[:500] if len(sanitized_text) > 500 else sanitized_text
        
        # Create AI prompt for complexity analysis
        prompt = self._create_complexity_prompt(analysis_text, language)
        
        try:
            # SECURITY: AI call with timeout handled by ai_service
            response = await self.ai_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a content complexity analyzer. Analyze text and classify its complexity level."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=50,
                temperature=0.1  # Low temperature for consistent classification
            )
            
            # Parse AI response
            complexity = self._parse_complexity_response(response)
            
            logger.debug(
                f"Complexity analysis complete: {complexity} "
                f"(text length: {len(analysis_text)}, language: {language})"
            )
            # PRIVACY: No text content in logs
            
            return complexity
            
        except Exception as e:
            logger.error(
                f"Complexity analysis failed: {e}. Defaulting to medium complexity."
            )
            # PRIVACY: No text content in error logs
            return "medium"  # Safe default on error
    
    def get_target_chunk_size(self, complexity: ComplexityLevel) -> int:
        """
        Calculate target chunk size based on complexity level.

        Returns the optimal target chunk size for the given complexity level:
        - Low complexity: 1000 characters (simple content can use larger chunks)
        - Medium complexity: 650 characters (standard informational content)
        - High complexity: 450 characters (dense content needs smaller chunks)

        This method is deterministic and does not require AI service calls.

        Args:
            complexity: Complexity level ("low", "medium", or "high")

        Returns:
            Target chunk size in characters

        Example:
            >>> analyzer = ComplexityAnalyzer()
            >>> analyzer.get_target_chunk_size("low")
            1000
            >>> analyzer.get_target_chunk_size("medium")
            650
            >>> analyzer.get_target_chunk_size("high")
            450
        """
        # VALIDATION: Ensure valid complexity level
        if complexity not in ["low", "medium", "high"]:
            logger.warning(
                f"Invalid complexity level '{complexity}'. Defaulting to medium."
            )
            complexity = "medium"

        # Map complexity to target chunk size
        target_sizes = {
            "low": 1000,     # Simple content - larger chunks
            "medium": 650,   # Standard content - medium chunks
            "high": 450      # Dense content - smaller chunks
        }

        target_size = target_sizes[complexity]

        logger.debug(f"Target chunk size for {complexity} complexity: {target_size}")

        return target_size
    
    def _create_complexity_prompt(self, text: str, language: str) -> str:
        """
        Create the AI prompt for complexity analysis.
        
        Args:
            text: Text to analyze
            language: Language code
            
        Returns:
            Formatted prompt string for AI analysis
        """
        return f"""Analyze the complexity of the following text and classify it as "low", "medium", or "high".

Consider these factors:
1. Vocabulary complexity: Are the words simple and common, or technical and specialized?
2. Sentence structure: Are sentences short and simple, or long and complex?
3. Concept density: How many distinct concepts are presented per sentence?
4. Technical terminology: Does the text use domain-specific jargon?
5. Information density: How much information is conveyed per unit of text?

Classification guidelines:
- LOW: Simple explanatory text with basic vocabulary, short sentences, and familiar concepts. Easy to understand for general audiences.
- MEDIUM: Standard informational content with moderate vocabulary, mixed sentence structures, and some specialized terms. Requires focused reading.
- HIGH: Dense technical content with specialized vocabulary, complex sentences, and high concept density. Requires expertise or careful study.

Language: {language}

Text to analyze:
{text}

Respond with ONLY ONE WORD: "low", "medium", or "high"."""
    
    def _parse_complexity_response(self, response: dict) -> ComplexityLevel:
        """
        Parse AI response to extract complexity level.
        
        Args:
            response: AI service response dictionary
            
        Returns:
            Complexity level: "low", "medium", or "high"
            
        Raises:
            ValueError: If response cannot be parsed or is invalid
        """
        if not response or not response.get("success", False):
            error_msg = response.get("error_message", "Unknown error")
            raise ValueError(f"AI service returned error: {error_msg}")
        
        content = response.get("content", "").strip().lower()
        
        # Extract complexity level from response
        if "low" in content:
            return "low"
        elif "high" in content:
            return "high"
        elif "medium" in content:
            return "medium"
        else:
            # Try to parse as JSON in case AI returned structured response
            try:
                data = json.loads(content)
                complexity = data.get("complexity", "").lower()
                if complexity in ["low", "medium", "high"]:
                    return complexity
            except json.JSONDecodeError:
                pass
            
            logger.warning(
                f"Could not parse complexity from AI response: '{content}'. "
                f"Defaulting to medium."
            )
            return "medium"  # Safe default
    
    def _sanitize_text(self, text: str) -> str:
        """
        Sanitize text before sending to AI service.
        
        Removes potentially problematic characters that could cause issues
        with AI processing.
        
        Args:
            text: Raw text string
            
        Returns:
            Sanitized text string safe for AI processing
            
        Note:
            - VALIDATION: Removes control characters (Requirements 9.3)
            - Preserves newlines, tabs, and carriage returns
        """
        import re
        
        # Remove null bytes
        sanitized = text.replace('\x00', '')
        
        # Remove control characters except newline, tab, carriage return
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', sanitized)
        
        # Normalize excessive whitespace
        sanitized = re.sub(r' {4,}', '   ', sanitized)
        sanitized = re.sub(r'\n{4,}', '\n\n\n', sanitized)
        
        return sanitized
