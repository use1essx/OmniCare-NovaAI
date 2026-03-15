"""
Overlap Calculator for AI-Enhanced Semantic Chunking

This module implements the OverlapCalculator component that calculates
intelligent overlap between consecutive chunks based on boundary strength.
The overlap helps preserve context across chunk boundaries while avoiding
duplication of complete semantic units.

Strong boundaries (topic changes) get minimal overlap, while weak boundaries
(continuous concepts) get larger overlap to maintain context.
"""

import re
from typing import Optional

# VALIDATION: Maximum overlap size in characters
MAX_OVERLAP_SIZE = 150

# Overlap size ranges based on boundary strength
# Strong boundaries (0.8-1.0): minimal overlap (20-50 chars)
# Medium boundaries (0.3-0.8): moderate overlap (50-100 chars)
# Weak boundaries (0.0-0.3): larger overlap (100-150 chars)
STRONG_BOUNDARY_MIN = 20
STRONG_BOUNDARY_MAX = 50
MEDIUM_BOUNDARY_MIN = 50
MEDIUM_BOUNDARY_MAX = 100
WEAK_BOUNDARY_MIN = 100
WEAK_BOUNDARY_MAX = 150


class OverlapCalculator:
    """
    Calculates intelligent overlap between consecutive chunks.
    
    This class determines the appropriate overlap size based on boundary
    strength and ensures the overlap contains complete sentences. Strong
    semantic boundaries (clear topic changes) receive minimal overlap,
    while weak boundaries (continuous concepts) receive larger overlap
    to preserve context.
    
    The calculator is language-aware and handles both English and Chinese
    text, correctly identifying sentence boundaries in each language.
    
    Attributes:
        None (stateless calculator)
    
    Example:
        >>> calculator = OverlapCalculator()
        >>> overlap = calculator.calculate_overlap(
        ...     prev_chunk="First paragraph. Second paragraph.",
        ...     next_chunk="Third paragraph. Fourth paragraph.",
        ...     boundary_strength=0.9,
        ...     language="en"
        ... )
        >>> print(overlap)
        'Second paragraph.'
    """
    
    # Regex patterns for sentence detection
    # English: sentences end with . ! ? ; followed by space or end of string
    ENGLISH_SENTENCE_PATTERN = re.compile(r'[.!?;](?:\s|$)')
    
    # Chinese: sentences end with 。！？；
    CHINESE_SENTENCE_PATTERN = re.compile(r'[。！？；]')
    
    def calculate_overlap(
        self,
        prev_chunk_text: str,
        next_chunk_text: str,
        boundary_strength: float,
        language: str
    ) -> str:
        """
        Calculate intelligent overlap between consecutive chunks.
        
        Determines the appropriate overlap size based on boundary strength
        and extracts complete sentences from the end of the previous chunk.
        Strong boundaries get minimal overlap, weak boundaries get larger
        overlap to preserve context.
        
        Boundary strength mapping:
        - Strong (0.8-1.0): 20-50 characters (clear topic change)
        - Medium (0.3-0.8): 50-100 characters (related concepts)
        - Weak (0.0-0.3): 100-150 characters (continuous concept)
        
        Args:
            prev_chunk_text: Text of the previous chunk
            next_chunk_text: Text of the next chunk (for context, not used currently)
            boundary_strength: Strength of semantic boundary (0.0 to 1.0)
                             0.0 = very weak boundary (continuous concept)
                             1.0 = very strong boundary (clear topic change)
            language: Language code (e.g., "en", "zh-HK", "zh")
        
        Returns:
            Overlap text containing complete sentences from end of prev_chunk.
            Empty string if no suitable overlap found or chunks are too short.
        
        Raises:
            ValueError: If boundary_strength is not between 0.0 and 1.0
        
        Example:
            >>> calculator = OverlapCalculator()
            >>> prev = "Introduction to the topic. Key concepts explained. Details follow."
            >>> next = "More details here. Additional information."
            >>> overlap = calculator.calculate_overlap(prev, next, 0.5, "en")
            >>> print(overlap)
            'Details follow.'
        
        Note:
            - VALIDATION: Boundary strength must be between 0.0 and 1.0
            - Overlap is limited to MAX_OVERLAP_SIZE (150 characters)
            - Returns empty string if prev_chunk is too short
            - Ensures overlap contains only complete sentences
        """
        # VALIDATION: Check boundary_strength is in valid range
        if not 0.0 <= boundary_strength <= 1.0:
            raise ValueError(
                f"boundary_strength must be between 0.0 and 1.0, "
                f"got {boundary_strength}"
            )
        
        # VALIDATION: Check if previous chunk is long enough for overlap
        if len(prev_chunk_text) < 50:
            return ""
        
        # Determine target overlap size based on boundary strength
        target_size = self._get_target_overlap_size(boundary_strength)
        
        # Extract overlap from end of previous chunk
        overlap = self._extract_overlap(
            prev_chunk_text,
            target_size,
            language
        )
        
        return overlap
    
    def _get_target_overlap_size(self, boundary_strength: float) -> int:
        """
        Determine target overlap size based on boundary strength.
        
        Maps boundary strength to an appropriate overlap size:
        - Strong boundaries (0.8-1.0): 20-50 chars (minimal overlap)
        - Medium boundaries (0.3-0.8): 50-100 chars (moderate overlap)
        - Weak boundaries (0.0-0.3): 100-150 chars (larger overlap)
        
        Uses linear interpolation within each range for smooth transitions.
        
        Args:
            boundary_strength: Boundary strength value (0.0 to 1.0)
        
        Returns:
            Target overlap size in characters
        
        Example:
            >>> calculator = OverlapCalculator()
            >>> calculator._get_target_overlap_size(0.9)  # Strong
            35
            >>> calculator._get_target_overlap_size(0.5)  # Medium
            75
            >>> calculator._get_target_overlap_size(0.1)  # Weak
            125
        """
        if boundary_strength >= 0.8:
            # Strong boundary: minimal overlap (20-50 chars)
            # Linear interpolation: 0.8 -> 50, 1.0 -> 20
            ratio = (boundary_strength - 0.8) / 0.2
            size = int(STRONG_BOUNDARY_MAX - ratio * (STRONG_BOUNDARY_MAX - STRONG_BOUNDARY_MIN))
            # Ensure minimum size
            return max(size, STRONG_BOUNDARY_MIN)
        
        elif boundary_strength >= 0.3:
            # Medium boundary: moderate overlap (50-100 chars)
            # Linear interpolation: 0.3 -> 100, 0.8 -> 50
            ratio = (boundary_strength - 0.3) / 0.5
            return int(MEDIUM_BOUNDARY_MAX - ratio * (MEDIUM_BOUNDARY_MAX - MEDIUM_BOUNDARY_MIN))
        
        else:
            # Weak boundary: larger overlap (100-150 chars)
            # Linear interpolation: 0.0 -> 150, 0.3 -> 100
            ratio = boundary_strength / 0.3
            return int(WEAK_BOUNDARY_MAX - ratio * (WEAK_BOUNDARY_MAX - WEAK_BOUNDARY_MIN))
    
    def _extract_overlap(
        self,
        text: str,
        target_size: int,
        language: str
    ) -> str:
        """
        Extract overlap text containing complete sentences from end of text.
        
        Extracts approximately target_size characters from the end of the text,
        ensuring the overlap contains only complete sentences. The actual size
        may be smaller than target_size to respect sentence boundaries.
        
        Args:
            text: Source text to extract overlap from
            target_size: Target overlap size in characters
            language: Language code for sentence detection
        
        Returns:
            Overlap text with complete sentences, or empty string if no
            suitable overlap found
        
        Example:
            >>> calculator = OverlapCalculator()
            >>> text = "First sentence. Second sentence. Third sentence."
            >>> overlap = calculator._extract_overlap(text, 30, "en")
            >>> print(overlap)
            'Third sentence.'
        """
        # VALIDATION: Ensure target size doesn't exceed maximum
        target_size = min(target_size, MAX_OVERLAP_SIZE)
        
        # Calculate starting position for overlap extraction
        # Extract a bit more than target to ensure we have complete sentences
        search_start = max(0, len(text) - target_size - 100)
        search_text = text[search_start:]
        
        # Find all sentence boundaries in the search text
        sentence_boundaries = self._find_sentence_boundaries(
            search_text,
            language
        )
        
        if not sentence_boundaries:
            # No sentence boundaries found, return empty string
            return ""
        
        # Find the best sentence boundary for the target size
        # We want the overlap to be as close to target_size as possible
        # but not exceed MAX_OVERLAP_SIZE
        best_boundary = self._find_best_boundary(
            sentence_boundaries,
            len(search_text),
            target_size
        )
        
        if best_boundary is None:
            return ""
        
        # Extract overlap from the best boundary to the end
        overlap = search_text[best_boundary:].strip()
        
        # VALIDATION: Ensure overlap doesn't exceed maximum size
        if len(overlap) > MAX_OVERLAP_SIZE:
            # Truncate to last complete sentence within limit
            overlap = self._truncate_to_sentence(overlap, MAX_OVERLAP_SIZE, language)
        
        return overlap
    
    def _find_sentence_boundaries(
        self,
        text: str,
        language: str
    ) -> list:
        """
        Find all sentence boundary positions in text.
        
        Identifies positions where sentences end based on language-specific
        punctuation patterns.
        
        Args:
            text: Text to analyze
            language: Language code
        
        Returns:
            List of character positions where sentences end (after punctuation)
        
        Example:
            >>> calculator = OverlapCalculator()
            >>> boundaries = calculator._find_sentence_boundaries(
            ...     "First. Second. Third.",
            ...     "en"
            ... )
            >>> print(boundaries)
            [6, 14, 21]
        """
        # Select appropriate pattern based on language
        if language.startswith("zh"):
            pattern = self.CHINESE_SENTENCE_PATTERN
        else:
            pattern = self.ENGLISH_SENTENCE_PATTERN
        
        # Find all sentence endings
        boundaries = []
        for match in pattern.finditer(text):
            # Record position after the sentence ending
            boundaries.append(match.end())
        
        return boundaries
    
    def _find_best_boundary(
        self,
        boundaries: list,
        text_length: int,
        target_size: int
    ) -> Optional[int]:
        """
        Find the best sentence boundary for the target overlap size.
        
        Selects a sentence boundary that produces an overlap as close to
        target_size as possible, preferring slightly smaller overlaps over
        larger ones.
        
        Args:
            boundaries: List of sentence boundary positions
            text_length: Total length of the text
            target_size: Target overlap size
        
        Returns:
            Position of best boundary, or None if no suitable boundary found
        
        Example:
            >>> calculator = OverlapCalculator()
            >>> boundaries = [10, 25, 40, 60]
            >>> text_length = 70
            >>> best = calculator._find_best_boundary(boundaries, text_length, 30)
            >>> print(best)
            40
        """
        if not boundaries:
            return None
        
        # Calculate desired start position for overlap
        desired_start = text_length - target_size
        
        # Find boundary closest to desired start
        best_boundary = None
        best_distance = float('inf')
        
        for boundary in boundaries:
            # Calculate overlap size if we use this boundary
            overlap_size = text_length - boundary
            
            # Skip if overlap would be too large
            if overlap_size > MAX_OVERLAP_SIZE:
                continue
            
            # Skip if overlap would be too small (less than 15 chars)
            if overlap_size < 15:
                continue
            
            # Calculate distance from target
            distance = abs(boundary - desired_start)
            
            # Prefer boundaries that give us overlap closer to target
            if distance < best_distance:
                best_distance = distance
                best_boundary = boundary
        
        return best_boundary
    
    def _truncate_to_sentence(
        self,
        text: str,
        max_length: int,
        language: str
    ) -> str:
        """
        Truncate text to last complete sentence within max_length.
        
        Args:
            text: Text to truncate
            max_length: Maximum length in characters
            language: Language code
        
        Returns:
            Truncated text ending at a sentence boundary
        
        Example:
            >>> calculator = OverlapCalculator()
            >>> text = "First sentence. Second sentence. Third sentence."
            >>> truncated = calculator._truncate_to_sentence(text, 30, "en")
            >>> print(truncated)
            'First sentence.'
        """
        if len(text) <= max_length:
            return text
        
        # Find all sentence boundaries up to max_length
        truncated_text = text[:max_length]
        boundaries = self._find_sentence_boundaries(truncated_text, language)
        
        if not boundaries:
            # No sentence boundary found, return empty string
            return ""
        
        # Use the last sentence boundary
        last_boundary = boundaries[-1]
        return text[:last_boundary].strip()
