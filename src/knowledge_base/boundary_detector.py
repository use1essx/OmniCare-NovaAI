"""
Boundary Detector for AI-Enhanced Semantic Chunking

This module implements the BoundaryDetector component that uses AI to identify
natural semantic boundaries in text where topics change. The detector analyzes
content to find positions where one concept ends and another begins, marking
natural topic transitions that are ideal for splitting chunks.

The BoundaryDetector is a core component of the semantic chunking system,
working alongside ComplexityAnalyzer and MetadataGenerator to create
semantically-aware document chunks.
"""

import json
import logging
import re
from typing import List, Optional, TYPE_CHECKING

from src.ai.ai_service import HealthcareAIService
from src.knowledge_base.chunking_config import SEMANTIC_CHUNK_TIMEOUT

if TYPE_CHECKING:
    from src.knowledge_base.semantic_types import StructureInfo

logger = logging.getLogger(__name__)


class BoundaryDetector:
    """
    Detects semantic boundaries in text using AI analysis.
    
    This class uses AI to identify natural break points in text where topics
    transition. It analyzes content to find positions where one concept ends
    and another begins, ensuring boundaries fall at sentence endings and
    respect document structure.
    
    The detector is language-aware and handles both English and Chinese text,
    correctly identifying sentence boundaries in each language.
    
    Attributes:
        ai_service: HealthcareAIService instance for AI calls
        timeout: Timeout for AI service calls in seconds
    
    Example:
        >>> detector = BoundaryDetector(ai_service)
        >>> boundaries = await detector.detect_boundaries(content, "en")
        >>> print(f"Found {len(boundaries)} semantic boundaries")
    """
    
    def __init__(self, ai_service: HealthcareAIService):
        """
        Initialize BoundaryDetector with AI service.
        
        Args:
            ai_service: HealthcareAIService instance for making AI calls
        """
        self.ai_service = ai_service
        self.timeout = SEMANTIC_CHUNK_TIMEOUT
    
    async def detect_boundaries(
        self,
        content: str,
        language: str,
        structure_info: Optional['StructureInfo'] = None
    ) -> List[int]:
        """
        Detect semantic boundaries in content using AI analysis.
        
        This method analyzes text to identify natural topic transitions where
        chunks should be split. It uses AI to understand semantic flow and
        marks positions where one concept ends and another begins.
        
        The method ensures boundaries fall at sentence endings and returns
        character positions suitable for splitting the content.
        
        Args:
            content: Document text content to analyze
            language: Language code (e.g., "en", "zh-HK", "zh")
            structure_info: Optional StructureInfo object for structure-aware
                          boundary adjustment
        
        Returns:
            List of character positions representing semantic boundaries,
            sorted in ascending order. Empty list if no boundaries detected.
        
        Raises:
            Exception: If AI service call fails or response cannot be parsed
        
        Example:
            >>> boundaries = await detector.detect_boundaries(
            ...     "First topic here. Second topic starts. Third topic.",
            ...     "en"
            ... )
            >>> print(boundaries)
            [18, 38]
        
        Note:
            - PRIVACY: No document content is logged, only document length
            - Boundaries are validated to fall at sentence endings
            - Returns empty list if content is too short for meaningful boundaries
            - If structure_info is provided, boundaries are adjusted to respect
              document structure (headings, lists, tables, code blocks)
        """
        # PRIVACY: Log only content length, not actual content
        logger.debug(f"Detecting boundaries for content of length {len(content)}")
        
        # VALIDATION: Check if content is long enough for boundary detection
        if len(content) < 400:
            logger.debug("Content too short for boundary detection")
            return []
        
        # VALIDATION: Sanitize content before AI call (Requirements 9.3)
        # Remove null bytes and control characters that could cause issues
        sanitized_content = self._sanitize_content(content)
        
        try:
            # Call AI service to detect boundaries
            boundaries = await self._detect_boundaries(sanitized_content, language)
            
            # Validate and adjust boundaries to sentence endings
            validated_boundaries = self._validate_boundaries(
                content,
                boundaries,
                language
            )
            
            # Adjust boundaries for document structure if provided
            if structure_info is not None:
                validated_boundaries = self.adjust_boundaries_for_structure(
                    validated_boundaries,
                    structure_info,
                    content
                )
            
            logger.debug(
                f"Detected {len(validated_boundaries)} semantic boundaries"
            )
            return validated_boundaries
            
        except Exception as e:
            logger.error(
                f"Boundary detection failed: {e}",
                exc_info=True
            )
            raise
    
    async def _detect_boundaries(
        self,
        content: str,
        language: str
    ) -> List[int]:
        """
        Internal method to detect boundaries using AI.
        
        Creates an AI prompt for boundary detection and parses the response
        to extract boundary positions.
        
        Args:
            content: Document text content
            language: Language code
        
        Returns:
            List of character positions from AI analysis
        
        Raises:
            Exception: If AI call fails or response parsing fails
        """
        # Create AI prompt for boundary detection
        prompt = self._create_boundary_prompt(content, language)
        
        # Make AI service call
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a document analysis expert specializing in "
                    "identifying semantic boundaries where topics change. "
                    "Analyze text and identify natural break points where "
                    "one concept ends and another begins."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        response = await self.ai_service.chat_completion(
            messages=messages,
            max_tokens=500,
            temperature=0.2
        )
        
        # Parse AI response to extract boundary positions
        boundaries = self._parse_boundary_response(response)
        
        return boundaries
    
    def _create_boundary_prompt(
        self,
        content: str,
        language: str
    ) -> str:
        """
        Create AI prompt for boundary detection.
        
        Args:
            content: Document text content
            language: Language code
        
        Returns:
            Formatted prompt string for AI analysis
        """
        language_name = "Chinese" if language.startswith("zh") else "English"
        
        prompt = f"""Analyze this {language_name} text and identify natural semantic boundaries where topics change.

Mark character positions where one concept ends and another begins. These positions should represent natural topic transitions that would be good places to split the text into chunks.

Requirements:
1. Identify positions where the topic or focus shifts
2. Ensure boundaries fall at sentence endings (after periods, question marks, or exclamation marks)
3. Look for transitions between different concepts or ideas
4. Consider paragraph breaks as potential boundaries
5. Return 3-8 boundary positions if the text is long enough

Text to analyze:
{content}

Return your response as a JSON array of character positions (integers only):
[position1, position2, position3, ...]

Example response format:
[245, 512, 789]

Only return the JSON array, no additional text."""
        
        return prompt
    
    def _parse_boundary_response(
        self,
        response: dict
    ) -> List[int]:
        """
        Parse AI response to extract boundary positions.
        
        Args:
            response: AI service response dictionary
        
        Returns:
            List of boundary positions as integers
        
        Raises:
            ValueError: If response cannot be parsed
        """
        if not response.get("success"):
            error_msg = response.get("error_message", "Unknown error")
            raise ValueError(f"AI service call failed: {error_msg}")
        
        content = response.get("content", "").strip()
        
        if not content:
            logger.warning("Empty response from AI service")
            return []
        
        try:
            # Try to extract JSON array from response
            # Handle cases where AI includes extra text
            json_match = re.search(r'\[[\d,\s]+\]', content)
            if json_match:
                json_str = json_match.group(0)
                boundaries = json.loads(json_str)
            else:
                # Try parsing the entire content as JSON
                boundaries = json.loads(content)
            
            # Validate that we got a list of integers
            if not isinstance(boundaries, list):
                raise ValueError("Response is not a list")
            
            # Convert all items to integers and filter out invalid values
            boundaries = [
                int(b) for b in boundaries
                if isinstance(b, (int, float, str)) and str(b).strip().isdigit()
            ]
            
            # Sort boundaries in ascending order
            boundaries.sort()
            
            return boundaries
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                f"Failed to parse boundary response: {e}. "
                f"Response content: {content[:100]}..."
            )
            return []
    
    def _validate_boundaries(
        self,
        content: str,
        boundaries: List[int],
        language: str
    ) -> List[int]:
        """
        Validate and adjust boundaries to fall at sentence endings.
        
        Ensures that all boundaries fall at natural sentence breaks and are
        within the content bounds.
        
        Args:
            content: Document text content
            boundaries: List of proposed boundary positions
            language: Language code
        
        Returns:
            List of validated boundary positions
        """
        if not boundaries:
            return []
        
        validated = []
        content_length = len(content)
        
        # Define sentence ending patterns for different languages
        if language.startswith("zh"):
            # Chinese sentence endings: 。！？；
            sentence_endings = r'[。！？；]'
        else:
            # English sentence endings: . ! ? ; (optionally followed by space)
            # This handles both mid-text and end-of-text cases
            sentence_endings = r'[.!?;](?:\s|$)'
        
        for boundary in boundaries:
            # Skip invalid positions
            if boundary <= 0 or boundary >= content_length:
                continue
            
            # Find the nearest sentence ending after this position
            adjusted_boundary = self._find_nearest_sentence_ending(
                content,
                boundary,
                sentence_endings
            )
            
            if adjusted_boundary is not None:
                # Avoid duplicate boundaries
                if not validated or adjusted_boundary != validated[-1]:
                    validated.append(adjusted_boundary)
        
        return validated
    
    def _find_nearest_sentence_ending(
        self,
        content: str,
        position: int,
        sentence_endings: str
    ) -> Optional[int]:
        """
        Find the nearest sentence ending after the given position.
        
        Args:
            content: Document text content
            position: Starting position to search from
            sentence_endings: Regex pattern for sentence endings
        
        Returns:
            Position of nearest sentence ending, or None if not found
        """
        # Search forward up to 200 characters for a sentence ending
        search_end = min(position + 200, len(content))
        search_text = content[position:search_end]
        
        match = re.search(sentence_endings, search_text)
        if match:
            # Return position after the sentence ending
            return position + match.end()
        
        # If no sentence ending found nearby, search backward
        search_start = max(0, position - 100)
        search_text = content[search_start:position]
        
        # Find all matches and take the last one
        matches = list(re.finditer(sentence_endings, search_text))
        if matches:
            last_match = matches[-1]
            return search_start + last_match.end()
        
        return None
    
    def adjust_boundaries_for_structure(
        self,
        boundaries: List[int],
        structure_info: 'StructureInfo',
        content: str
    ) -> List[int]:
        """
        Adjust boundaries to respect document structure.
        
        This method takes AI-detected boundaries and adjusts them to avoid
        splitting within structural elements like lists, tables, and code blocks.
        It also prefers boundaries at heading positions when possible.
        
        The adjustment strategy:
        1. If a boundary falls within a structural element (list, table, code block),
           move it to before or after the structure
        2. Prefer boundaries at heading positions (natural topic transitions)
        3. Keep list items together
        4. Keep table rows together
        5. Keep code blocks intact
        
        Args:
            boundaries: List of AI-detected boundary positions
            structure_info: StructureInfo object with detected structural elements
            content: Document text content
        
        Returns:
            List of adjusted boundary positions that respect document structure
        
        Example:
            >>> boundaries = [150, 300, 450]
            >>> # If 300 falls in middle of a list at positions 280-350
            >>> adjusted = detector.adjust_boundaries_for_structure(
            ...     boundaries, structure_info, content
            ... )
            >>> # Returns [150, 280, 450] or [150, 350, 450]
        
        Note:
            - SECURITY: Validates all positions are within content bounds
            - Boundaries may be moved significantly to respect structure
            - Duplicate boundaries are removed after adjustment
            - Heading positions are preferred as natural boundaries
        """
        if not boundaries:
            return []
        
        adjusted_boundaries = []
        content_length = len(content)
        
        # Create a set of heading positions for quick lookup
        heading_positions = {pos for pos, _, _ in structure_info.headings}
        
        for boundary in boundaries:
            # SECURITY: Validate boundary is within content bounds
            # Also filter out position 0 (start of document) as it's not a valid boundary
            if boundary <= 0 or boundary >= content_length:
                continue
            
            # Check if boundary is already at a heading position (ideal case)
            if boundary in heading_positions:
                adjusted_boundaries.append(boundary)
                continue
            
            # Check if boundary falls within any structural element
            adjusted_boundary = self._adjust_for_structures(
                boundary,
                structure_info,
                content,
                heading_positions
            )
            
            adjusted_boundaries.append(adjusted_boundary)
        
        # Remove duplicates and sort
        adjusted_boundaries = sorted(set(adjusted_boundaries))
        
        # Filter out boundaries that are too close together (< 100 chars)
        filtered_boundaries = []
        for boundary in adjusted_boundaries:
            if not filtered_boundaries or boundary - filtered_boundaries[-1] >= 100:
                filtered_boundaries.append(boundary)
        
        logger.debug(
            f"Adjusted {len(boundaries)} boundaries to {len(filtered_boundaries)} "
            f"structure-aware boundaries"
        )
        
        return filtered_boundaries
    
    def _adjust_for_structures(
        self,
        boundary: int,
        structure_info: 'StructureInfo',
        content: str,
        heading_positions: set
    ) -> int:
        """
        Adjust a single boundary to avoid splitting structural elements.
        
        Checks if the boundary falls within lists, tables, or code blocks,
        and moves it to before or after the structure. Prefers heading
        positions when available nearby.
        
        Args:
            boundary: Original boundary position
            structure_info: StructureInfo with structural elements
            content: Document text content
            heading_positions: Set of heading positions for quick lookup
        
        Returns:
            Adjusted boundary position
        """
        # Check if boundary falls within a code block (highest priority)
        for start, end in structure_info.code_blocks:
            if start <= boundary <= end:
                # Move to before or after code block
                return self._choose_best_position(
                    boundary, start, end, heading_positions
                )
        
        # Check if boundary falls within a table
        for start, end in structure_info.tables:
            if start <= boundary <= end:
                # Move to before or after table
                return self._choose_best_position(
                    boundary, start, end, heading_positions
                )
        
        # Check if boundary falls within a list
        for start, end in structure_info.lists:
            if start <= boundary <= end:
                # Move to before or after list
                return self._choose_best_position(
                    boundary, start, end, heading_positions
                )
        
        # Check if there's a heading nearby (within 100 chars)
        # But exclude position 0 (start of document) as it's not a valid boundary
        nearby_heading = self._find_nearby_heading(
            boundary, heading_positions, max_distance=100
        )
        if nearby_heading is not None and nearby_heading > 0:
            return nearby_heading
        
        # No structural conflict, return original boundary
        return boundary
    
    def _choose_best_position(
        self,
        boundary: int,
        structure_start: int,
        structure_end: int,
        heading_positions: set
    ) -> int:
        """
        Choose the best position to move a boundary that falls within a structure.
        
        Prefers:
        1. Heading positions near the structure boundaries
        2. Position before the structure if boundary is closer to start
        3. Position after the structure if boundary is closer to end
        
        Args:
            boundary: Original boundary position
            structure_start: Start position of the structural element
            structure_end: End position of the structural element
            heading_positions: Set of heading positions
        
        Returns:
            Best position to move the boundary
        """
        # Check for headings near the structure boundaries
        for heading_pos in heading_positions:
            # Heading just before structure (within 20 chars)
            if structure_start - 20 <= heading_pos < structure_start:
                return heading_pos
            # Heading just after structure (within 20 chars)
            if structure_end < heading_pos <= structure_end + 20:
                return heading_pos
        
        # No nearby heading, choose based on which end is closer
        distance_to_start = boundary - structure_start
        distance_to_end = structure_end - boundary
        
        if distance_to_start < distance_to_end:
            # Closer to start, move before structure
            return structure_start
        else:
            # Closer to end, move after structure
            return structure_end
    
    def _find_nearby_heading(
        self,
        position: int,
        heading_positions: set,
        max_distance: int = 100
    ) -> Optional[int]:
        """
        Find a heading position near the given position.
        
        Args:
            position: Position to search near
            heading_positions: Set of heading positions
            max_distance: Maximum distance to search (default: 100 chars)
        
        Returns:
            Heading position if found within max_distance, None otherwise
        """
        closest_heading = None
        closest_distance = max_distance + 1
        
        for heading_pos in heading_positions:
            distance = abs(heading_pos - position)
            if distance < closest_distance and distance <= max_distance:
                closest_distance = distance
                closest_heading = heading_pos
        
        return closest_heading
    
    def _sanitize_content(self, content: str) -> str:
        """
        Sanitize content before sending to AI service.
        
        Removes potentially problematic characters that could cause issues
        with AI processing:
        - Null bytes (\\x00)
        - Control characters (except newlines, tabs, carriage returns)
        - Excessive whitespace
        
        Args:
            content: Raw content string
            
        Returns:
            Sanitized content string safe for AI processing
            
        Note:
            - VALIDATION: Removes control characters (Requirements 9.3)
            - Preserves newlines, tabs, and carriage returns for structure
            - Normalizes excessive whitespace
        """
        import re
        
        # Remove null bytes
        sanitized = content.replace('\x00', '')
        
        # Remove control characters except newline, tab, carriage return
        # Control characters are in range 0x00-0x1F and 0x7F-0x9F
        # Keep: \n (0x0A), \r (0x0D), \t (0x09)
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', sanitized)
        
        # Normalize excessive whitespace (more than 3 consecutive spaces)
        sanitized = re.sub(r' {4,}', '   ', sanitized)
        
        # Normalize excessive newlines (more than 3 consecutive newlines)
        sanitized = re.sub(r'\n{4,}', '\n\n\n', sanitized)
        
        return sanitized
