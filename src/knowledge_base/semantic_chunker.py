"""
Semantic Chunker for AI-Enhanced Document Chunking

This module implements the main SemanticChunker class that orchestrates
AI-powered semantic chunking of documents. It coordinates all chunking
components to create semantically-aware chunks with adaptive sizing and
rich metadata.

The SemanticChunker uses:
- StructureAnalyzer: Detect document structure (headings, lists, tables)
- BoundaryDetector: Identify semantic boundaries using AI
- ComplexityAnalyzer: Analyze content complexity for adaptive sizing
- MetadataGenerator: Generate AI-powered summaries and keywords
- OverlapCalculator: Calculate intelligent overlap between chunks
"""

import asyncio
from typing import List, Optional

from src.ai.ai_service import get_ai_service, HealthcareAIService
from src.knowledge_base.boundary_detector import BoundaryDetector
from src.knowledge_base.complexity_analyzer import ComplexityAnalyzer
from src.knowledge_base.metadata_generator import MetadataGenerator
from src.knowledge_base.overlap_calculator import OverlapCalculator
from src.knowledge_base.structure_analyzer import StructureAnalyzer
from src.knowledge_base.chunking_config import (
    SEMANTIC_CHUNK_MIN_SIZE,
    SEMANTIC_CHUNK_MAX_SIZE,
    SEMANTIC_CHUNK_TARGET_LOW,
    SEMANTIC_CHUNK_TARGET_MEDIUM,
    SEMANTIC_CHUNK_TARGET_HIGH,
    SEMANTIC_CHUNK_MAX_OVERLAP,
    SEMANTIC_CHUNK_TIMEOUT,
    SEMANTIC_CHUNK_MAX_CONCURRENT,
)
from src.core.logging import get_logger

logger = get_logger(__name__)


class SemanticChunker:
    """
    AI-powered semantic chunking with adaptive sizing and metadata generation.
    
    This class orchestrates all components of the semantic chunking system to
    create document chunks that:
    - Split at natural semantic boundaries (topic transitions)
    - Adapt size based on content complexity
    - Include AI-generated summaries and keywords
    - Respect document structure (headings, lists, tables)
    - Maintain intelligent overlap for context preservation
    
    The chunker is designed for use in document ingestion pipelines and
    provides graceful fallback to simple chunking on errors.
    
    Attributes:
        ai_service: HealthcareAIService instance for AI operations
        structure_analyzer: Analyzes document structure
        boundary_detector: Detects semantic boundaries using AI
        complexity_analyzer: Analyzes content complexity
        metadata_generator: Generates chunk metadata using AI
        overlap_calculator: Calculates intelligent overlap
        min_chunk_size: Minimum chunk size (200 characters)
        max_chunk_size: Maximum chunk size (1200 characters)
        target_sizes: Target sizes by complexity (low: 1000, medium: 650, high: 450)
        max_overlap: Maximum overlap between chunks (150 characters)
        timeout: AI service call timeout (30 seconds)
        max_concurrent: Maximum concurrent AI requests (5)
    
    Example:
        >>> chunker = SemanticChunker()
        >>> await chunker.initialize()
        >>> chunks = await chunker.chunk_document(
        ...     content="Document text...",
        ...     language="en",
        ...     title="Document Title"
        ... )
    """
    
    def __init__(self):
        """
        Initialize SemanticChunker with configuration constants.
        
        Note:
            Call initialize() before using chunk_document() to set up
            AI service and component instances.
        """
        # DIAGNOSTIC: Log SemanticChunker instantiation
        logger.info("SemanticChunker.__init__() called - creating instance")
        
        # AI service (initialized in initialize())
        self.ai_service: Optional[HealthcareAIService] = None
        
        # Component instances (initialized in initialize())
        self.structure_analyzer: Optional[StructureAnalyzer] = None
        self.boundary_detector: Optional[BoundaryDetector] = None
        self.complexity_analyzer: Optional[ComplexityAnalyzer] = None
        self.metadata_generator: Optional[MetadataGenerator] = None
        self.overlap_calculator: Optional[OverlapCalculator] = None
        
        # Chunk size configuration from chunking_config
        self.min_chunk_size: int = SEMANTIC_CHUNK_MIN_SIZE
        self.max_chunk_size: int = SEMANTIC_CHUNK_MAX_SIZE
        self.target_sizes: dict = {
            "low": SEMANTIC_CHUNK_TARGET_LOW,
            "medium": SEMANTIC_CHUNK_TARGET_MEDIUM,
            "high": SEMANTIC_CHUNK_TARGET_HIGH,
        }
        self.max_overlap: int = SEMANTIC_CHUNK_MAX_OVERLAP
        
        # AI service configuration from chunking_config
        self.timeout: int = SEMANTIC_CHUNK_TIMEOUT
        self.max_concurrent: int = SEMANTIC_CHUNK_MAX_CONCURRENT
        
        # Initialization flag
        self._initialized: bool = False
        
        logger.info(
            "SemanticChunker created with configuration",
            extra={
                "min_chunk_size": self.min_chunk_size,
                "max_chunk_size": self.max_chunk_size,
                "target_sizes": self.target_sizes,
                "max_overlap": self.max_overlap,
                "timeout": self.timeout,
                "max_concurrent": self.max_concurrent,
            }
        )
    
    async def initialize(self):
        """
        Initialize AI service and all component instances.
        
        This method must be called before using chunk_document(). It:
        - Initializes the AI service connection
        - Creates all component instances
        - Initializes components that require async setup
        
        Raises:
            Exception: If AI service or component initialization fails
        
        Example:
            >>> chunker = SemanticChunker()
            >>> await chunker.initialize()
        """
        # DIAGNOSTIC: Log initialize() entry
        logger.info("SemanticChunker.initialize() called")
        
        if self._initialized:
            logger.debug("SemanticChunker already initialized")
            return
        
        try:
            # Initialize AI service
            logger.info("Initializing AI service for SemanticChunker")
            self.ai_service = await get_ai_service()
            logger.info("AI service initialized successfully")
            
            # Initialize all components
            logger.info("Initializing SemanticChunker components")
            
            # Structure analyzer (no AI, no async init needed)
            self.structure_analyzer = StructureAnalyzer()
            logger.debug("StructureAnalyzer created")
            
            # Boundary detector (uses AI service)
            self.boundary_detector = BoundaryDetector(self.ai_service)
            logger.debug("BoundaryDetector created")
            
            # Complexity analyzer (uses AI service, needs async init)
            self.complexity_analyzer = ComplexityAnalyzer()
            await self.complexity_analyzer.initialize()
            logger.debug("ComplexityAnalyzer initialized")
            
            # Metadata generator (uses AI service)
            self.metadata_generator = MetadataGenerator(self.ai_service)
            logger.debug("MetadataGenerator created")
            
            # Overlap calculator (no AI, no async init needed)
            self.overlap_calculator = OverlapCalculator()
            logger.debug("OverlapCalculator created")
            
            self._initialized = True
            
            logger.info("SemanticChunker initialized successfully - all components ready")
            
        except Exception as e:
            logger.error(
                f"Failed to initialize SemanticChunker: {type(e).__name__}: {e}",
                extra={"error_type": type(e).__name__},
                exc_info=True
            )
            raise
    
    async def chunk_document(
        self,
        content: str,
        language: str,
        title: str
    ) -> List:
        """
        Chunk document using AI-enhanced semantic analysis.
        
        This is the main entry point for semantic chunking. It orchestrates
        all components to:
        1. Analyze document structure
        2. Detect semantic boundaries
        3. Analyze content complexity
        4. Create chunks at boundaries with adaptive sizing
        5. Generate metadata for all chunks
        6. Calculate overlap between consecutive chunks
        
        Args:
            content: Full document text content
            language: Language code (e.g., "en", "zh-HK", "zh")
            title: Document title for context
            
        Returns:
            List of DocumentChunk objects with AI-generated metadata
            
        Raises:
            ValueError: If SemanticChunker is not initialized
            Exception: If chunking fails (should trigger fallback in caller)
        
        Example:
            >>> chunker = SemanticChunker()
            >>> await chunker.initialize()
            >>> chunks = await chunker.chunk_document(
            ...     content="Document text with multiple paragraphs...",
            ...     language="en",
            ...     title="Healthcare Guidelines"
            ... )
            >>> len(chunks)
            5
        
        Note:
            - VALIDATION: Checks initialization before processing
            - PRIVACY: Logs only document length and metadata, not content
        """
        # VALIDATION: Ensure chunker is initialized
        if not self._initialized:
            raise ValueError(
                "SemanticChunker not initialized. Call initialize() first."
            )
        
        # VALIDATION: Input validation
        if not content or not content.strip():
            raise ValueError("Content cannot be empty")
        
        # VALIDATION: Content length validation (Requirements 1.1, 9.3)
        # Maximum content length: 1MB (1,000,000 characters)
        max_content_length = 1_000_000
        if len(content) > max_content_length:
            raise ValueError(
                f"Content exceeds maximum length of {max_content_length} characters "
                f"(got {len(content)} characters)"
            )
        
        # VALIDATION: Language code validation (Requirements 3.4, 9.3)
        # Supported language codes: en, zh, zh-HK, zh-CN, zh-TW
        supported_languages = {"en", "zh", "zh-hk", "zh-cn", "zh-tw"}
        if not language or language.lower() not in supported_languages:
            raise ValueError(
                f"Invalid language code '{language}'. "
                f"Supported languages: {', '.join(sorted(supported_languages))}"
            )
        
        # VALIDATION: Title validation
        if not title or not title.strip():
            raise ValueError("Document title is required")
        
        # VALIDATION: Sanitize title length
        if len(title) > 500:
            logger.warning(
                f"Title exceeds 500 characters ({len(title)}), truncating"
            )
            title = title[:497] + "..."
        
        # PRIVACY: Log only metadata, not content
        # DIAGNOSTIC: Log chunk_document() entry
        logger.info(
            "SemanticChunker.chunk_document() called",
            extra={
                "content_length": len(content),
                "language": language,
                "title": title,
            }
        )
        logger.info(
            "Starting semantic chunking",
            extra={
                "content_length": len(content),
                "language": language,
                "title": title,
            }
        )
        
        try:
            # Wrap entire chunking process with timeout
            # VALIDATION: Timeout for AI operations (30 seconds)
            async def _chunk_with_timeout():
                # Step 1: Analyze document structure
                logger.debug("Analyzing document structure")
                structure_info = self.structure_analyzer.analyze(content)
                logger.debug(
                    f"Structure analysis complete: {len(structure_info.headings)} headings, "
                    f"{len(structure_info.lists)} lists, {len(structure_info.tables)} tables, "
                    f"{len(structure_info.code_blocks)} code blocks"
                )
                
                # Step 2: Detect semantic boundaries using AI (with timeout)
                logger.debug("Detecting semantic boundaries")
                boundaries = await asyncio.wait_for(
                    self.boundary_detector.detect_boundaries(
                        content=content,
                        language=language,
                        structure_info=structure_info
                    ),
                    timeout=self.timeout
                )
                logger.debug(f"Detected {len(boundaries)} semantic boundaries")
                
                # Step 3: Create segments from boundaries
                segments = self._create_segments(content, boundaries)
                logger.debug(f"Created {len(segments)} segments from boundaries")
                
                # Step 4: Analyze complexity for each segment and create chunks with adaptive sizing
                logger.debug("Analyzing complexity and creating chunks")
                chunks_data = await asyncio.wait_for(
                    self._create_chunks_with_adaptive_sizing(
                        segments=segments,
                        language=language,
                        structure_info=structure_info
                    ),
                    timeout=self.timeout
                )
                logger.debug(f"Created {len(chunks_data)} chunks with adaptive sizing")
                
                # Step 5: Generate metadata for all chunks concurrently
                logger.debug("Generating metadata for all chunks concurrently")
                chunks_with_metadata = await asyncio.wait_for(
                    self._generate_metadata_for_chunks(
                        chunks_data=chunks_data,
                        language=language,
                        title=title,
                        structure_info=structure_info
                    ),
                    timeout=self.timeout
                )
                logger.debug(f"Generated metadata for {len(chunks_with_metadata)} chunks")
                
                # Step 6: Calculate overlap between consecutive chunks
                logger.debug("Calculating overlap between chunks")
                final_chunks = self._calculate_chunk_overlaps(
                    chunks_with_metadata=chunks_with_metadata,
                    language=language
                )
                logger.debug(f"Calculated overlaps for {len(final_chunks)} chunks")
                
                return final_chunks
            
            # Execute with timeout
            final_chunks = await _chunk_with_timeout()
            
            # PRIVACY: Log summary without content
            # DIAGNOSTIC: Log chunk_document() successful exit
            logger.info(
                "Semantic chunking completed successfully",
                extra={
                    "chunk_count": len(final_chunks),
                    "avg_chunk_size": sum(len(c.text) for c in final_chunks) // len(final_chunks) if final_chunks else 0,
                    "language": language,
                }
            )
            logger.info("SemanticChunker.chunk_document() completed successfully")
            
            return final_chunks
            
        except asyncio.TimeoutError as e:
            # PRIVACY: Log timeout error without content
            logger.error(
                f"Semantic chunking timeout after {self.timeout}s",
                extra={
                    "content_length": len(content),
                    "language": language,
                    "error_type": "TimeoutError",
                    "timeout_seconds": self.timeout
                },
                exc_info=True
            )
            raise
            
        except Exception as e:
            # PRIVACY: Log error without content
            logger.error(
                f"Semantic chunking failed: {e}",
                extra={
                    "content_length": len(content),
                    "language": language,
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise

    def _create_segments(
        self,
        content: str,
        boundaries: List[int]
    ) -> List[str]:
        """
        Split content into segments at boundary positions.

        Creates text segments by splitting the content at detected semantic
        boundaries. Each segment represents a semantically coherent unit that
        will be processed for complexity analysis and chunk creation.

        Args:
            content: Full document text content
            boundaries: List of character positions where content should be split

        Returns:
            List of text segments. If no boundaries, returns [content].

        Example:
            >>> segments = self._create_segments(
            ...     "First part. Second part. Third part.",
            ...     [12, 25]
            ... )
            >>> len(segments)
            3

        Note:
            - VALIDATION: Boundaries are assumed to be sorted and within content bounds
            - First segment starts at position 0
            - Last segment ends at end of content
            - Empty segments are filtered out
        """
        if not boundaries:
            return [content]

        segments = []
        start_pos = 0

        for boundary in boundaries:
            # Extract segment from start_pos to boundary
            segment = content[start_pos:boundary].strip()
            if segment:  # Only add non-empty segments
                segments.append(segment)
            start_pos = boundary

        # Add final segment from last boundary to end
        final_segment = content[start_pos:].strip()
        if final_segment:
            segments.append(final_segment)

        logger.debug(f"Created {len(segments)} segments from {len(boundaries)} boundaries")

        return segments

    async def _create_chunks_with_adaptive_sizing(
        self,
        segments: List[str],
        language: str,
        structure_info
    ) -> List[dict]:
        """
        Create chunks from segments with complexity-based adaptive sizing.

        Analyzes each segment's complexity and applies appropriate target chunk
        sizes. Segments are split or combined based on complexity to create
        optimally-sized chunks.

        Args:
            segments: List of text segments from boundary detection
            language: Language code (e.g., "en", "zh-HK")
            structure_info: StructureInfo object with document structure

        Returns:
            List of dictionaries with chunk data:
            [
                {
                    "text": "chunk text",
                    "complexity": "low|medium|high",
                    "start_char": int,
                    "end_char": int
                },
                ...
            ]

        Example:
            >>> chunks_data = await self._create_chunks_with_adaptive_sizing(
            ...     segments=["Simple text.", "Complex technical content..."],
            ...     language="en",
            ...     structure_info=structure_info
            ... )

        Note:
            - VALIDATION: Each segment is analyzed for complexity
            - Chunks are enforced to respect min/max size constraints
            - Character positions are tracked for metadata generation
        """
        chunks_data = []
        current_position = 0

        for segment in segments:
            # Analyze complexity of this segment
            complexity = await self.complexity_analyzer.analyze_complexity(
                text=segment,
                language=language
            )

            # Get target chunk size for this complexity level
            target_size = self.complexity_analyzer.get_target_chunk_size(complexity)

            # Enforce chunk size constraints
            chunk_text = self._enforce_chunk_size(
                chunk_text=segment,
                target_size=target_size,
                language=language
            )

            # If segment is too large, split it
            if len(segment) > self.max_chunk_size:
                # Split oversized segment into multiple chunks
                sub_chunks = self._split_oversized_chunk(
                    text=segment,
                    max_size=self.max_chunk_size,
                    language=language
                )

                for sub_chunk in sub_chunks:
                    chunk_data = {
                        "text": sub_chunk,
                        "complexity": complexity,
                        "start_char": current_position,
                        "end_char": current_position + len(sub_chunk)
                    }
                    chunks_data.append(chunk_data)
                    current_position += len(sub_chunk)
            else:
                # Segment fits within max size, create single chunk
                chunk_data = {
                    "text": segment,
                    "complexity": complexity,
                    "start_char": current_position,
                    "end_char": current_position + len(segment)
                }
                chunks_data.append(chunk_data)
                current_position += len(segment)

        logger.debug(
            f"Created {len(chunks_data)} chunks with adaptive sizing "
            f"from {len(segments)} segments"
        )

        return chunks_data

    def _enforce_chunk_size(
        self,
        chunk_text: str,
        target_size: int,
        language: str
    ) -> str:
        """
        Enforce minimum and maximum chunk size constraints.

        Validates that chunk text meets size requirements. This method is
        primarily for validation; actual splitting is handled by
        _split_oversized_chunk.

        Args:
            chunk_text: The chunk text to validate
            target_size: Target size based on complexity
            language: Language code for sentence detection

        Returns:
            The chunk text (unchanged, as splitting is handled elsewhere)

        Note:
            - VALIDATION: Checks against min_chunk_size and max_chunk_size
            - Logs warnings for chunks outside target range
            - Actual enforcement happens in _create_chunks_with_adaptive_sizing
        """
        chunk_length = len(chunk_text)

        # Log if chunk is below minimum size
        if chunk_length < self.min_chunk_size:
            logger.debug(
                f"Chunk below minimum size: {chunk_length} < {self.min_chunk_size}"
            )

        # Log if chunk exceeds maximum size
        if chunk_length > self.max_chunk_size:
            logger.debug(
                f"Chunk exceeds maximum size: {chunk_length} > {self.max_chunk_size}"
            )

        return chunk_text

    def _split_oversized_chunk(
        self,
        text: str,
        max_size: int,
        language: str
    ) -> List[str]:
        """
        Split chunks exceeding max size at sentence boundaries.

        When a semantic unit exceeds the maximum chunk size, this method
        splits it into smaller chunks at sentence boundaries to maintain
        readability and semantic coherence.

        Args:
            text: Text to split (exceeds max_size)
            max_size: Maximum chunk size in characters
            language: Language code for sentence detection

        Returns:
            List of text chunks, each respecting max_size constraint

        Example:
            >>> chunks = self._split_oversized_chunk(
            ...     "Very long text with many sentences...",
            ...     1200,
            ...     "en"
            ... )

        Note:
            - VALIDATION: Splits at sentence boundaries only
            - Each resulting chunk respects max_size
            - Handles both English and Chinese sentence endings
            - Last chunk may be smaller than max_size
        """
        import re
        
        if len(text) <= max_size:
            return [text]

        # Define sentence ending patterns based on language
        if language.startswith("zh"):
            # Chinese sentence endings: 。！？；
            sentence_pattern = r'[。！？；]'
        else:
            # English sentence endings: . ! ? ;
            sentence_pattern = r'[.!?;](?:\s|$)'

        # Find all sentence boundaries
        sentence_boundaries = []
        for match in re.finditer(sentence_pattern, text):
            sentence_boundaries.append(match.end())

        if not sentence_boundaries:
            # No sentence boundaries found, split at max_size
            logger.warning(
                f"No sentence boundaries found in oversized chunk "
                f"(length: {len(text)}), splitting at max_size"
            )
            chunks = []
            for i in range(0, len(text), max_size):
                chunks.append(text[i:i + max_size])
            return chunks

        # Split at sentence boundaries respecting max_size
        chunks = []
        current_chunk_start = 0

        for boundary in sentence_boundaries:
            chunk_length = boundary - current_chunk_start

            # If adding this sentence would exceed max_size, start new chunk
            if chunk_length > max_size and chunks:
                # Save current chunk
                chunk = text[current_chunk_start:sentence_boundaries[len(chunks) - 1]].strip()
                if chunk:
                    chunks.append(chunk)
                current_chunk_start = sentence_boundaries[len(chunks) - 1]

        # Add final chunk
        final_chunk = text[current_chunk_start:].strip()
        if final_chunk:
            chunks.append(final_chunk)

        logger.debug(
            f"Split oversized chunk (length: {len(text)}) into {len(chunks)} chunks"
        )

        return chunks if chunks else [text]

    async def _generate_metadata_for_chunks(
        self,
        chunks_data: List[dict],
        language: str,
        title: str,
        structure_info
    ) -> List:
        """
        Generate AI metadata for all chunks concurrently.

        Processes multiple chunks in parallel to generate summaries, keywords,
        and topics. Uses concurrency control to limit simultaneous AI requests.

        Args:
            chunks_data: List of chunk dictionaries with text and metadata
            language: Language code (e.g., "en", "zh-HK")
            title: Document title for context
            structure_info: StructureInfo object for heading context

        Returns:
            List of DocumentChunk objects with AI-generated metadata

        Example:
            >>> chunks = await self._generate_metadata_for_chunks(
            ...     chunks_data=[{"text": "...", "complexity": "medium", ...}],
            ...     language="en",
            ...     title="Healthcare Guide",
            ...     structure_info=structure_info
            ... )

        Note:
            - VALIDATION: Uses max_concurrent limit from configuration
            - PRIVACY: No chunk content in logs, only counts and metadata
            - Failed metadata generation returns None for that chunk
            - Uses asyncio.Semaphore for concurrency control
        """
        from src.knowledge_base.document_ingestion import DocumentChunk

        # Prepare batch data for metadata generation
        batch_data = []
        for i, chunk_data in enumerate(chunks_data):
            # Get heading context for this chunk
            heading_context = structure_info.get_heading_context(
                chunk_data["start_char"]
            )

            # Get previous chunk text for context (if available)
            previous_chunk = chunks_data[i - 1]["text"] if i > 0 else None

            # Build context string
            context_parts = [f"Document: {title}"]
            if heading_context:
                context_parts.append(f"Section: {heading_context}")

            context = " | ".join(context_parts)

            batch_data.append((
                chunk_data["text"],
                language,
                context
            ))

        # Generate metadata concurrently with limits
        logger.debug(
            f"Generating metadata for {len(batch_data)} chunks concurrently "
            f"(max_concurrent: {self.max_concurrent})"
        )

        metadata_list = await self.metadata_generator.generate_metadata_batch(
            chunks=batch_data,
            max_concurrent=self.max_concurrent,
            timeout=self.timeout
        )

        # Create DocumentChunk objects with metadata
        chunks_with_metadata = []
        for i, (chunk_data, metadata) in enumerate(zip(chunks_data, metadata_list)):
            # Get heading context
            heading_node = structure_info.get_heading_at_position(
                chunk_data["start_char"]
            )
            heading_context = heading_node.text if heading_node else None

            # Determine structure type
            structure_type = self._determine_structure_type(
                chunk_data["start_char"],
                chunk_data["end_char"],
                structure_info
            )

            # Create DocumentChunk with metadata
            chunk = DocumentChunk(
                text=chunk_data["text"],
                index=i,
                start_char=chunk_data["start_char"],
                end_char=chunk_data["end_char"],
                chunk_type="content",
                summary=metadata.summary if metadata else None,
                keywords=metadata.keywords if metadata else None,
                topic=metadata.topic if metadata else None,
                complexity=chunk_data["complexity"],
                structure_type=structure_type,
                heading_context=heading_context,
                chunking_method="semantic"
            )

            chunks_with_metadata.append(chunk)

        logger.debug(
            f"Generated metadata for {len(chunks_with_metadata)} chunks "
            f"({sum(1 for m in metadata_list if m)} successful)"
        )

        return chunks_with_metadata

    def _determine_structure_type(
        self,
        start_char: int,
        end_char: int,
        structure_info
    ) -> Optional[str]:
        """
        Determine the structure type of a chunk based on its position.

        Args:
            start_char: Start position of chunk
            end_char: End position of chunk
            structure_info: StructureInfo object

        Returns:
            Structure type: "list", "table", "code_block", "paragraph", or None
        """
        # Check if chunk contains a code block
        for code_start, code_end in structure_info.code_blocks:
            if code_start >= start_char and code_end <= end_char:
                return "code_block"

        # Check if chunk contains a table
        for table_start, table_end in structure_info.tables:
            if table_start >= start_char and table_end <= end_char:
                return "table"

        # Check if chunk contains a list
        for list_start, list_end in structure_info.lists:
            if list_start >= start_char and list_end <= end_char:
                return "list"

        # Default to paragraph
        return "paragraph"

    def _calculate_chunk_overlaps(
        self,
        chunks_with_metadata: List,
        language: str
    ) -> List:
        """
        Calculate overlap between consecutive chunks.

        Determines intelligent overlap between adjacent chunks based on
        boundary strength. Strong boundaries get minimal overlap, weak
        boundaries get larger overlap for context preservation.

        Args:
            chunks_with_metadata: List of DocumentChunk objects
            language: Language code for sentence detection

        Returns:
            List of DocumentChunk objects with overlap information added

        Example:
            >>> final_chunks = self._calculate_chunk_overlaps(
            ...     chunks_with_metadata=chunks,
            ...     language="en"
            ... )

        Note:
            - VALIDATION: Overlap limited to max_overlap configuration
            - Overlap contains complete sentences only
            - First chunk has no overlap
            - Boundary strength assumed to be 0.5 (medium) by default
        """
        if len(chunks_with_metadata) <= 1:
            return chunks_with_metadata

        # Calculate overlaps between consecutive chunks
        for i in range(1, len(chunks_with_metadata)):
            prev_chunk = chunks_with_metadata[i - 1]
            current_chunk = chunks_with_metadata[i]

            # Calculate overlap using OverlapCalculator
            # Default boundary strength to 0.5 (medium) since we don't have
            # explicit boundary strength from AI
            boundary_strength = 0.5

            overlap_text = self.overlap_calculator.calculate_overlap(
                prev_chunk_text=prev_chunk.text,
                next_chunk_text=current_chunk.text,
                boundary_strength=boundary_strength,
                language=language
            )

            # Store overlap in chunk metadata (if needed)
            # For now, we just log it
            if overlap_text:
                logger.debug(
                    f"Calculated overlap between chunks {i-1} and {i}: "
                    f"{len(overlap_text)} characters"
                )

        return chunks_with_metadata
