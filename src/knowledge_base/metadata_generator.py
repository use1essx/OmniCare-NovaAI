"""
Metadata Generator for AI-enhanced semantic chunking.

This module provides the MetadataGenerator class that uses AI to generate
rich metadata for document chunks, including summaries, keywords, and topics.
The metadata improves retrieval quality by providing additional semantic
information for matching user queries.
"""

import asyncio
import json
from typing import List, Optional, Tuple

from src.ai.ai_service import HealthcareAIService
from src.knowledge_base.semantic_types import ChunkMetadata
from src.core.logging import get_logger


logger = get_logger(__name__)


class MetadataGenerator:
    """
    Generates AI-powered metadata for document chunks.
    
    This class uses the AI service to analyze chunk content and generate:
    - Concise summaries (max 150 characters)
    - Relevant keywords (3-7 keywords)
    - Primary topic identification
    
    The generated metadata is language-aware, producing summaries and keywords
    in the same language as the source content (English or Chinese).
    
    Attributes:
        ai_service: HealthcareAIService instance for making AI calls
    
    Example:
        >>> generator = MetadataGenerator(ai_service)
        >>> metadata = await generator.generate_metadata(
        ...     chunk_text="Patient care guidelines...",
        ...     language="en",
        ...     context="Healthcare > Patient Care"
        ... )
        >>> print(metadata.summary)
        'Guidelines for providing quality patient care'
    """
    
    def __init__(self, ai_service: HealthcareAIService):
        """
        Initialize MetadataGenerator with AI service.
        
        Args:
            ai_service: HealthcareAIService instance for AI calls
        """
        self.ai_service = ai_service
    
    async def generate_metadata(
        self,
        chunk_text: str,
        language: str,
        context: Optional[str] = None,
        heading: Optional[str] = None,
        previous_chunk: Optional[str] = None
    ) -> ChunkMetadata:
        """
        Generate metadata for a document chunk using AI.
        
        This method analyzes the chunk content and generates:
        - A concise summary in the same language as the content (max 150 chars)
        - 3-7 relevant keywords in the same language
        - The primary topic of the chunk
        
        The AI considers the surrounding context (heading, previous chunk) to
        generate more accurate and contextually relevant metadata.
        
        Args:
            chunk_text: The text content of the chunk to analyze
            language: Language code (e.g., "en", "zh-HK", "zh")
            context: Optional context string (e.g., heading path)
            heading: Optional current heading for this chunk
            previous_chunk: Optional text from previous chunk for continuity
            
        Returns:
            ChunkMetadata object with summary, keywords, and topic
            
        Raises:
            Exception: If AI service call fails or response parsing fails
            
        Example:
            >>> metadata = await generator.generate_metadata(
            ...     chunk_text="Elderly patients require special care...",
            ...     language="en",
            ...     heading="Patient Care Guidelines"
            ... )
        """
        # VALIDATION: Input sanitization (Requirements 9.3)
        if not chunk_text or not chunk_text.strip():
            raise ValueError("Chunk text cannot be empty")
        
        if not language:
            raise ValueError("Language code is required")
        
        # VALIDATION: Sanitize chunk text before AI call
        sanitized_chunk_text = self._sanitize_text(chunk_text)
        
        # Build context information for AI
        context_parts = []
        if heading:
            context_parts.append(f"Current heading: {heading}")
        if context:
            context_parts.append(f"Document context: {context}")
        if previous_chunk:
            # Include only a snippet of previous chunk for context
            # VALIDATION: Sanitize previous chunk snippet
            sanitized_prev = self._sanitize_text(previous_chunk)
            prev_snippet = sanitized_prev[:200] + "..." if len(sanitized_prev) > 200 else sanitized_prev
            context_parts.append(f"Previous chunk: {prev_snippet}")
        
        context_info = "\n".join(context_parts) if context_parts else "No additional context"
        
        # Determine language name for prompt
        language_name = self._get_language_name(language)
        
        # Create AI prompt for metadata generation
        system_prompt = self._create_system_prompt(language_name)
        user_prompt = self._create_user_prompt(sanitized_chunk_text, context_info, language_name)
        
        try:
            # Make AI request with low temperature for consistent output
            response = await self.ai_service.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=300,
                temperature=0.2
            )
            
            # Parse AI response
            metadata = self._parse_ai_response(response["content"], language)
            
            # PRIVACY: Log success without content
            logger.info(
                "Metadata generated successfully",
                extra={
                    "language": language,
                    "has_context": bool(context),
                    "has_heading": bool(heading),
                    "chunk_length": len(chunk_text)
                }
            )
            
            return metadata
            
        except Exception as e:
            # PRIVACY: Log error without exposing chunk content
            logger.error(
                f"Failed to generate metadata: {e}",
                extra={
                    "language": language,
                    "chunk_length": len(chunk_text),
                    "error_type": type(e).__name__
                }
            )
            raise
    
    async def generate_metadata_batch(
        self,
        chunks: List[Tuple[str, str, Optional[str]]],
        max_concurrent: int = 5,
        timeout: int = 30
    ) -> List[Optional[ChunkMetadata]]:
        """
        Generate metadata for multiple chunks concurrently.
        
        This method processes multiple chunks in parallel with concurrency control
        and timeout handling. It's designed for efficient batch processing of
        document chunks during ingestion.
        
        Args:
            chunks: List of tuples (text, language, context) for each chunk
                - text: The chunk text content
                - language: Language code (e.g., "en", "zh-HK")
                - context: Optional context string (heading, previous chunk info)
            max_concurrent: Maximum number of concurrent AI requests (default: 5)
            timeout: Timeout in seconds for each chunk (default: 30)
            
        Returns:
            List of ChunkMetadata objects (or None for failed chunks) in the same
            order as the input chunks. Failed chunks return None and are logged.
            
        Example:
            >>> chunks = [
            ...     ("Patient care text...", "en", "Healthcare > Patient Care"),
            ...     ("Elderly services...", "en", "Healthcare > Elderly"),
            ...     ("醫療指南...", "zh-HK", "醫療 > 指南")
            ... ]
            >>> results = await generator.generate_metadata_batch(chunks)
            >>> # results[0] is ChunkMetadata or None
        
        Note:
            - Uses asyncio.Semaphore to limit concurrent requests
            - Each chunk has independent timeout handling
            - Errors are logged but don't stop processing of other chunks
            - Returns None for chunks that fail or timeout
        """
        # VALIDATION: Input validation
        if not chunks:
            logger.warning("Empty chunks list provided to generate_metadata_batch")
            return []
        
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")
        
        if timeout < 1:
            raise ValueError("timeout must be at least 1 second")
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_chunk_with_semaphore(
            index: int,
            chunk_data: Tuple[str, str, Optional[str]]
        ) -> Tuple[int, Optional[ChunkMetadata]]:
            """
            Process a single chunk with semaphore and timeout.
            
            Args:
                index: Index of the chunk in the original list
                chunk_data: Tuple of (text, language, context)
                
            Returns:
                Tuple of (index, metadata or None)
            """
            text, language, context = chunk_data
            
            async with semaphore:
                try:
                    # Apply timeout to the metadata generation
                    metadata = await asyncio.wait_for(
                        self.generate_metadata(
                            chunk_text=text,
                            language=language,
                            context=context
                        ),
                        timeout=timeout
                    )
                    return (index, metadata)
                    
                except asyncio.TimeoutError:
                    # PRIVACY: Log timeout without chunk content
                    logger.warning(
                        f"Metadata generation timed out after {timeout}s",
                        extra={
                            "chunk_index": index,
                            "language": language,
                            "chunk_length": len(text),
                            "timeout": timeout
                        }
                    )
                    return (index, None)
                    
                except Exception as e:
                    # PRIVACY: Log error without chunk content
                    logger.error(
                        f"Failed to generate metadata for chunk {index}: {e}",
                        extra={
                            "chunk_index": index,
                            "language": language,
                            "chunk_length": len(text),
                            "error_type": type(e).__name__
                        }
                    )
                    return (index, None)
        
        # Create tasks for all chunks
        tasks = [
            process_chunk_with_semaphore(i, chunk_data)
            for i, chunk_data in enumerate(chunks)
        ]
        
        # Execute all tasks concurrently
        logger.info(
            f"Starting concurrent metadata generation for {len(chunks)} chunks",
            extra={
                "chunk_count": len(chunks),
                "max_concurrent": max_concurrent,
                "timeout": timeout
            }
        )
        
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        # Sort results by index to maintain order
        sorted_results = sorted(results, key=lambda x: x[0])
        metadata_list = [metadata for _, metadata in sorted_results]
        
        # Log summary
        success_count = sum(1 for m in metadata_list if m is not None)
        failure_count = len(metadata_list) - success_count
        
        logger.info(
            f"Completed concurrent metadata generation",
            extra={
                "total_chunks": len(chunks),
                "successful": success_count,
                "failed": failure_count,
                "success_rate": f"{(success_count / len(chunks) * 100):.1f}%"
            }
        )
        
        return metadata_list
    
    def _get_language_name(self, language_code: str) -> str:
        """
        Convert language code to full language name.
        
        Args:
            language_code: Language code (e.g., "en", "zh-HK", "zh")
            
        Returns:
            Full language name (e.g., "English", "Chinese")
        """
        # Normalize to lowercase for comparison
        normalized_code = language_code.lower()
        
        language_mapping = {
            "en": "English",
            "zh": "Chinese",
            "zh-hk": "Chinese",
            "zh-cn": "Chinese",
            "zh-tw": "Chinese"
        }
        return language_mapping.get(normalized_code, "English")
    
    def _create_system_prompt(self, language_name: str) -> str:
        """
        Create system prompt for metadata generation.
        
        Args:
            language_name: Full language name (e.g., "English", "Chinese")
            
        Returns:
            System prompt string
        """
        return f"""You are a metadata generator for a healthcare knowledge base system.
Your task is to analyze document chunks and generate concise, accurate metadata.

Generate metadata in {language_name} that matches the language of the input text.

Requirements:
- Summary: Maximum 150 characters, concise and informative
- Keywords: Between 3 and 7 relevant keywords
- Topic: Single primary topic that best describes the content

Focus on healthcare-relevant information and maintain professional terminology."""
    
    def _create_user_prompt(
        self,
        chunk_text: str,
        context_info: str,
        language_name: str
    ) -> str:
        """
        Create user prompt for metadata generation.
        
        Args:
            chunk_text: The chunk text to analyze
            context_info: Context information string
            language_name: Full language name
            
        Returns:
            User prompt string
        """
        return f"""Analyze this document chunk and generate metadata in {language_name}.

Context:
{context_info}

Chunk text:
{chunk_text}

Generate metadata in JSON format:
{{
  "summary": "concise summary in {language_name} (max 150 chars)",
  "keywords": ["keyword1", "keyword2", "keyword3", ...],
  "topic": "primary topic"
}}

Ensure:
- Summary is under 150 characters
- 3-7 keywords that capture key concepts
- All text is in {language_name}
- Keywords and topic are relevant to healthcare context"""
    
    def _parse_ai_response(self, response_content: str, language: str) -> ChunkMetadata:
        """
        Parse AI response and extract metadata.
        
        This method extracts the JSON from the AI response and validates
        the metadata fields before creating a ChunkMetadata object.
        
        Args:
            response_content: Raw response content from AI
            language: Language code for validation
            
        Returns:
            ChunkMetadata object with validated fields
            
        Raises:
            ValueError: If response cannot be parsed or is invalid
            json.JSONDecodeError: If JSON parsing fails
        """
        try:
            # Try to extract JSON from response
            # AI might wrap JSON in markdown code blocks
            content = response_content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            
            if content.endswith("```"):
                content = content[:-3]
            
            content = content.strip()
            
            # Parse JSON
            data = json.loads(content)
            
            # Validate required fields
            if "summary" not in data:
                raise ValueError("Missing 'summary' field in AI response")
            if "keywords" not in data:
                raise ValueError("Missing 'keywords' field in AI response")
            if "topic" not in data:
                raise ValueError("Missing 'topic' field in AI response")
            
            # Extract and validate fields
            summary = str(data["summary"]).strip()
            keywords = data["keywords"]
            topic = str(data["topic"]).strip()
            
            # Ensure keywords is a list
            if not isinstance(keywords, list):
                raise ValueError("Keywords must be a list")
            
            # Convert keywords to strings and strip whitespace
            keywords = [str(k).strip() for k in keywords if k]
            
            # Truncate summary if too long
            if len(summary) > 150:
                logger.warning(
                    f"Summary exceeds 150 characters ({len(summary)}), truncating",
                    extra={"language": language}
                )
                summary = summary[:147] + "..."
            
            # Ensure keywords count is within range
            if len(keywords) < 3:
                logger.warning(
                    f"Only {len(keywords)} keywords generated, expected 3-7",
                    extra={"language": language}
                )
                # Pad with generic keywords if needed
                while len(keywords) < 3:
                    keywords.append("healthcare" if language.startswith("en") else "醫療")
            elif len(keywords) > 7:
                logger.warning(
                    f"Too many keywords ({len(keywords)}), keeping first 7",
                    extra={"language": language}
                )
                keywords = keywords[:7]
            
            # Create and return ChunkMetadata
            # The __post_init__ will validate the fields
            return ChunkMetadata(
                summary=summary,
                keywords=keywords,
                topic=topic
            )
            
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JSON from AI response: {e}",
                extra={"response_preview": response_content[:200]}
            )
            raise ValueError(f"Invalid JSON in AI response: {e}")
        
        except Exception as e:
            logger.error(
                f"Failed to parse AI response: {e}",
                extra={"error_type": type(e).__name__}
            )
            raise
    
    def _sanitize_text(self, text: str) -> str:
        """
        Sanitize text before sending to AI service.
        
        Removes potentially problematic characters that could cause issues
        with AI processing:
        - Null bytes (\\x00)
        - Control characters (except newlines, tabs, carriage returns)
        - Excessive whitespace
        
        Args:
            text: Raw text string
            
        Returns:
            Sanitized text string safe for AI processing
            
        Note:
            - VALIDATION: Removes control characters (Requirements 9.3)
            - Preserves newlines, tabs, and carriage returns for structure
            - Normalizes excessive whitespace
        """
        import re
        
        # Remove null bytes
        sanitized = text.replace('\x00', '')
        
        # Remove control characters except newline, tab, carriage return
        # Control characters are in range 0x00-0x1F and 0x7F-0x9F
        # Keep: \n (0x0A), \r (0x0D), \t (0x09)
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', sanitized)
        
        # Normalize excessive whitespace (more than 3 consecutive spaces)
        sanitized = re.sub(r' {4,}', '   ', sanitized)
        
        # Normalize excessive newlines (more than 3 consecutive newlines)
        sanitized = re.sub(r'\n{4,}', '\n\n\n', sanitized)
        
        return sanitized
