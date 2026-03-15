"""
Fallback Handler for AI-Enhanced Semantic Chunking

This module provides graceful degradation to simple paragraph-based chunking
when AI semantic chunking fails. It ensures document ingestion always succeeds
even when AI services are unavailable or encounter errors.

The FallbackHandler:
- Logs errors without exposing document content (privacy protection)
- Falls back to simple paragraph-based chunking
- Marks chunks with "simple_fallback" method for monitoring
- Maintains backward compatibility with existing chunk schema
- Detects AI service unavailability within 5 seconds
- Handles timeout, connection, rate limit, and parsing errors
"""

import asyncio
import re
from typing import List, Callable, Awaitable

from src.core.logging import get_logger

logger = get_logger(__name__)


# Error types that trigger fallback
FALLBACK_ERROR_TYPES = (
    asyncio.TimeoutError,
    ConnectionError,
    ConnectionRefusedError,
    ConnectionResetError,
    TimeoutError,
    OSError,
    Exception,  # Catch-all for unexpected errors
)


class FallbackHandler:
    """
    Handles graceful fallback to simple chunking when AI chunking fails.
    
    This class provides a reliable fallback mechanism that ensures document
    ingestion continues successfully even when AI services are unavailable,
    timeout, or encounter errors. It uses simple paragraph-based chunking
    as a fallback strategy.
    
    Attributes:
        chunk_size: Target chunk size in characters (default: 800)
        chunk_overlap: Overlap between chunks in characters (default: 200)
        min_chunk_size: Minimum chunk size in characters (default: 200)
        detection_timeout: Timeout for detecting AI unavailability (default: 5 seconds)
    
    Example:
        >>> handler = FallbackHandler()
        >>> chunks = handler.handle_fallback(
        ...     document_id=123,
        ...     content="Document text...",
        ...     error=TimeoutError("AI service timeout")
        ... )
    """
    
    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 200,
        min_chunk_size: int = 200,
        detection_timeout: int = 5
    ):
        """
        Initialize FallbackHandler with chunking configuration.
        
        Args:
            chunk_size: Target chunk size in characters (default: 800)
            chunk_overlap: Overlap between chunks in characters (default: 200)
            min_chunk_size: Minimum chunk size in characters (default: 200)
            detection_timeout: Timeout for detecting AI unavailability in seconds (default: 5)
        
        Note:
            Default values are optimized for fallback scenarios to balance
            chunk quality with processing speed.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.detection_timeout = detection_timeout
        
        logger.info(
            "FallbackHandler initialized",
            extra={
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap,
                "min_chunk_size": self.min_chunk_size,
                "detection_timeout": self.detection_timeout,
            }
        )
    
    def categorize_error(self, error: Exception) -> str:
        """
        Categorize error type for logging and monitoring.
        
        Args:
            error: The exception that occurred
            
        Returns:
            String category: "timeout", "connection", "rate_limit", "parsing", 
            "unavailable", or "unknown"
            
        Example:
            >>> handler = FallbackHandler()
            >>> category = handler.categorize_error(asyncio.TimeoutError())
            >>> category
            'timeout'
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()
        
        # Timeout errors
        if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
            return "timeout"
        
        # Connection errors
        if isinstance(error, (ConnectionError, ConnectionRefusedError, ConnectionResetError, OSError)):
            return "connection"
        
        # Rate limit errors (check error message)
        if "rate limit" in error_msg or "429" in error_msg or "too many requests" in error_msg:
            return "rate_limit"
        
        # Parsing errors (JSON, response format)
        if "json" in error_msg or "parse" in error_msg or "invalid response" in error_msg:
            return "parsing"
        
        # Service unavailable
        if "503" in error_msg or "unavailable" in error_msg or "service" in error_msg:
            return "unavailable"
        
        return "unknown"
    
    def should_trigger_fallback(self, error: Exception) -> bool:
        """
        Determine if error should trigger fallback to simple chunking.
        
        All errors trigger fallback to ensure document ingestion always succeeds.
        This method exists for future extensibility if certain errors should be
        handled differently.
        
        Args:
            error: The exception that occurred
            
        Returns:
            bool: True if fallback should be triggered (always True currently)
            
        Example:
            >>> handler = FallbackHandler()
            >>> handler.should_trigger_fallback(TimeoutError())
            True
        """
        # Currently all errors trigger fallback
        # Future: Could add logic to retry certain errors before fallback
        return True
    
    async def detect_ai_unavailability(
        self,
        ai_check_func: Callable[[], Awaitable[bool]],
        timeout: int = None
    ) -> bool:
        """
        Detect if AI service is unavailable within detection timeout.
        
        Attempts to call a simple AI check function with a short timeout
        to quickly determine if the AI service is available before attempting
        full semantic chunking.
        
        Args:
            ai_check_func: Async function that makes a simple AI call
            timeout: Timeout in seconds (default: self.detection_timeout)
            
        Returns:
            bool: True if AI is unavailable, False if available
            
        Example:
            >>> handler = FallbackHandler()
            >>> async def check_ai():
            ...     return await ai_service.simple_call()
            >>> is_unavailable = await handler.detect_ai_unavailability(check_ai)
            
        Note:
            - VALIDATION: Uses short timeout (5 seconds) for quick detection
            - Returns True on any error (timeout, connection, etc.)
        """
        if timeout is None:
            timeout = self.detection_timeout
        
        try:
            # Try to call AI check function with timeout
            await asyncio.wait_for(ai_check_func(), timeout=timeout)
            return False  # AI is available
            
        except asyncio.TimeoutError:
            logger.warning(
                f"AI service unavailability detected: timeout after {timeout}s",
                extra={"timeout_seconds": timeout, "error_category": "timeout"}
            )
            return True  # AI is unavailable
            
        except Exception as e:
            error_category = self.categorize_error(e)
            logger.warning(
                f"AI service unavailability detected: {error_category} error",
                extra={
                    "error_type": type(e).__name__,
                    "error_category": error_category,
                    "error_message": str(e)
                }
            )
            return True  # AI is unavailable
    
    def handle_fallback(
        self,
        document_id: int,
        content: str,
        error: Exception
    ) -> List:
        """
        Handle fallback to simple chunking when AI chunking fails.
        
        This method:
        1. Logs the error with document_id only (no content for privacy)
        2. Performs simple paragraph-based chunking
        3. Marks all chunks with chunking_method="simple_fallback"
        4. Returns chunks in the same format as semantic chunking
        
        Args:
            document_id: ID of the document being processed
            content: Full document text content
            error: The exception that triggered the fallback
            
        Returns:
            List of DocumentChunk objects with chunking_method="simple_fallback"
            
        Example:
            >>> handler = FallbackHandler()
            >>> chunks = handler.handle_fallback(
            ...     document_id=123,
            ...     content="Long document text...",
            ...     error=TimeoutError("AI timeout")
            ... )
            >>> chunks[0].chunking_method
            'simple_fallback'
        
        Note:
            - PRIVACY: Logs only document_id and error type, never content
            - VALIDATION: Handles empty content gracefully
            - All chunks marked with "simple_fallback" for monitoring
        """
        # Import here to avoid circular dependency
        from src.knowledge_base.document_ingestion import DocumentChunk
        
        # Categorize error for better monitoring
        error_category = self.categorize_error(error)
        
        # DIAGNOSTIC: Enhanced fallback logging with detailed context
        # PRIVACY: Log error with document_id only, no content
        logger.warning(
            f"AI semantic chunking failed for document {document_id}: "
            f"{error_category} error ({type(error).__name__}). "
            f"Falling back to simple chunking.",
            extra={
                "document_id": document_id,
                "error_type": type(error).__name__,
                "error_category": error_category,
                "error_message": str(error),
                "fallback_method": "simple_paragraph",
                "pipeline_point": "semantic_chunking",
                "content_length": len(content)
            }
        )
        
        # DIAGNOSTIC: Log specific error details based on category
        if error_category == "timeout":
            logger.error(
                f"Timeout during semantic chunking for document {document_id}",
                extra={
                    "document_id": document_id,
                    "error_category": "timeout",
                    "likely_cause": "AI service slow response or network latency"
                }
            )
        elif error_category == "connection":
            logger.error(
                f"Connection error during semantic chunking for document {document_id}",
                extra={
                    "document_id": document_id,
                    "error_category": "connection",
                    "likely_cause": "AI service unavailable or network issue"
                }
            )
        elif error_category == "rate_limit":
            logger.error(
                f"Rate limit exceeded during semantic chunking for document {document_id}",
                extra={
                    "document_id": document_id,
                    "error_category": "rate_limit",
                    "likely_cause": "Too many concurrent AI requests"
                }
            )
        
        # VALIDATION: Handle empty content
        if not content or not content.strip():
            logger.warning(
                f"Empty content for document {document_id}, returning empty chunk list",
                extra={"document_id": document_id}
            )
            return []
        
        # Perform simple paragraph-based chunking
        chunks = self._chunk_document_simple(content)
        
        # PRIVACY: Log summary without content
        logger.info(
            f"Fallback chunking completed for document {document_id}",
            extra={
                "document_id": document_id,
                "chunk_count": len(chunks),
                "avg_chunk_size": sum(len(c.text) for c in chunks) // len(chunks) if chunks else 0,
                "chunking_method": "simple_fallback"
            }
        )
        
        return chunks
    
    def _chunk_document_simple(self, content: str) -> List:
        """
        Split document into overlapping chunks using paragraph boundaries.
        
        This implements simple paragraph-aware chunking as a fallback strategy.
        It splits content by paragraphs and creates chunks with overlap to
        maintain context across boundaries.
        
        Args:
            content: Full document text content
            
        Returns:
            List of DocumentChunk objects with chunking_method="simple_fallback"
            
        Note:
            - Splits by double newlines (paragraph boundaries)
            - Maintains chunk_overlap for context preservation
            - Enforces min_chunk_size to avoid tiny chunks
            - All chunks marked with chunking_method="simple_fallback"
        """
        # Import here to avoid circular dependency
        from src.knowledge_base.document_ingestion import DocumentChunk
        
        chunks = []
        
        # Split by paragraphs first
        paragraphs = re.split(r'\n\n+', content)
        
        current_chunk = ""
        current_start = 0
        chunk_index = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # If adding this paragraph exceeds chunk size
            if len(current_chunk) + len(para) + 2 > self.chunk_size:
                # Save current chunk if it meets minimum size
                if len(current_chunk) >= self.min_chunk_size:
                    chunks.append(DocumentChunk(
                        text=current_chunk.strip(),
                        index=chunk_index,
                        start_char=current_start,
                        end_char=current_start + len(current_chunk),
                        chunk_type="content",
                        chunking_method="simple_fallback"  # Mark as fallback
                    ))
                    chunk_index += 1
                
                # Start new chunk with overlap
                if len(current_chunk) > self.chunk_overlap:
                    overlap_text = current_chunk[-self.chunk_overlap:]
                    current_chunk = overlap_text + "\n\n" + para
                    current_start = current_start + len(current_chunk) - self.chunk_overlap - len(para) - 2
                else:
                    current_chunk = para
                    current_start = current_start + len(current_chunk)
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
        
        # Don't forget the last chunk
        if len(current_chunk) >= self.min_chunk_size:
            chunks.append(DocumentChunk(
                text=current_chunk.strip(),
                index=chunk_index,
                start_char=current_start,
                end_char=current_start + len(current_chunk),
                chunk_type="content",
                chunking_method="simple_fallback"  # Mark as fallback
            ))
        
        return chunks
