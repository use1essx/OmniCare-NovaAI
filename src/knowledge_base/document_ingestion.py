"""
Document Ingestion Service

Processes and indexes documents for the knowledge base.
Users add documents via admin interface or API - this service handles:
- Text extraction
- Chunking
- Embedding generation
- Storage in vector store and PostgreSQL
"""

import hashlib
import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ..database.connection import get_async_db
from ..database.vector_store import get_vector_store
from ..services.embedding_service import get_embedding_service
from .chunking_config import is_semantic_chunking_enabled
from .semantic_chunker import SemanticChunker
from .fallback_handler import FallbackHandler

logger = logging.getLogger(__name__)


def _normalize_age_group(value: str) -> Optional[str]:
    if not value:
        return None
    v = value.strip().lower()
    mapping = {
        "kid": "child",
        "kids": "child",
        "child": "child",
        "children": "child",
        "toddler": "child",
        "teen": "teen",
        "teenager": "teen",
        "adolescent": "teen",
        "youth": "teen",
        "adult": "adult",
        "成年人": "adult",
        "elderly": "elderly",
        "senior": "elderly",
        "old": "elderly",
        "older": "elderly",
        "長者": "elderly",
        "老人": "elderly",
        "兒童": "child",
        "小朋友": "child",
        "幼兒": "child",
        "青少年": "teen",
        "少年": "teen",
    }
    if v in mapping:
        return mapping[v]
    # Handle Chinese keywords embedded in a longer string
    if "兒童" in v or "小朋友" in v or "幼兒" in v:
        return "child"
    if "青少年" in v or "少年" in v:
        return "teen"
    if "長者" in v or "老人" in v:
        return "elderly"
    if "成人" in v:
        return "adult"
    return v or None


def _looks_garbled(value: str) -> bool:
    if not value:
        return False
    if "\ufffd" in value:
        return True
    control = sum(1 for c in value if unicodedata.category(c) == "Cc" and c not in ("\n", "\t", " "))
    if control:
        return True
    latin1 = sum(1 for c in value if 0x00C0 <= ord(c) <= 0x00FF)
    extended = sum(1 for c in value if 0x0080 <= ord(c) <= 0x00FF)
    cjk = sum(1 for c in value if 0x4E00 <= ord(c) <= 0x9FFF)
    ascii_letters = sum(1 for c in value if ("a" <= c.lower() <= "z"))
    mojibake_markers = ("Ã", "Â", "å", "ç", "œ", "™", "ï»¿")
    if any(m in value for m in mojibake_markers) and cjk == 0:
        return True
    if latin1 >= 2 and cjk == 0 and ascii_letters == 0:
        return True
    if extended >= 2 and cjk == 0:
        return True
    return False


def _normalize_topic(value: str) -> Optional[str]:
    if not value:
        return None
    v = value.strip()
    if _looks_garbled(v):
        return None
    v = v.lower()
    v = re.sub(r"\s+", "-", v)
    v = re.sub(r"[^a-z0-9\u4e00-\u9fff\-]+", "", v)
    return v or None


def _dedupe_list(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _coerce_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        parts = re.split(r"[,\n;/]+", value)
        return [p.strip() for p in parts if p.strip()]
    return [str(value).strip()] if str(value).strip() else []


def _extract_json_block(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{[\s\S]+\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


@dataclass
class DocumentChunk:
    """Represents a chunk of a document with optional AI-generated metadata"""
    text: str
    index: int
    start_char: int
    end_char: int
    chunk_type: str = "content"
    page: Optional[int] = None
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None
    
    # AI-generated metadata (optional, backward compatible)
    summary: Optional[str] = None  # AI-generated summary (max 150 chars)
    keywords: Optional[List[str]] = None  # AI-generated keywords (3-7)
    topic: Optional[str] = None  # Primary topic
    complexity: Optional[str] = None  # "low", "medium", "high"
    structure_type: Optional[str] = None  # "list", "table", "paragraph", etc.
    heading_context: Optional[str] = None  # Relevant heading
    boundary_strength: Optional[float] = None  # Strength of semantic boundary (0.0-1.0)
    chunking_method: str = "simple"  # "simple", "semantic", "simple_fallback"


@dataclass
class IngestedDocument:
    """Result of document ingestion"""
    document_id: int
    title: str
    chunk_count: int
    status: str
    error: Optional[str] = None


class DocumentIngestionService:
    """
    Service for ingesting documents into the knowledge base.
    
    This handles:
    1. Creating document record in PostgreSQL
    2. Chunking content for embedding
    3. Storing chunks in vector store
    4. Updating document status
    """
    
    # Chunking settings
    CHUNK_SIZE = 500  # characters
    CHUNK_OVERLAP = 100  # characters
    MIN_CHUNK_SIZE = 100
    
    def __init__(self):
        """Initialize ingestion service"""
        self.vector_store = get_vector_store()

    def _categorize_fallback_reason(self, error: Exception) -> str:
        """
        Categorize the reason for fallback to simple chunking.
        
        Args:
            error: The exception that caused the fallback
            
        Returns:
            Category string for logging and monitoring
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()
        
        # Timeout errors
        if "timeout" in error_type.lower() or "timeout" in error_msg:
            return "timeout"
        
        # AI service unavailable
        if "connection" in error_msg or "unavailable" in error_msg or "503" in error_msg:
            return "service_unavailable"
        
        # Rate limiting
        if "rate" in error_msg or "429" in error_msg or "quota" in error_msg:
            return "rate_limit"
        
        # Parsing errors
        if "json" in error_msg or "parse" in error_msg or "invalid" in error_msg:
            return "parsing_error"
        
        # Authentication/authorization
        if "auth" in error_msg or "401" in error_msg or "403" in error_msg:
            return "auth_error"
        
        # Generic AI service error
        if "ai" in error_msg or "model" in error_msg:
            return "ai_service_error"
        
        # Unknown error
        return "unknown_error"

    async def _auto_tag_and_summarize(
        self,
        title: str,
        content: str,
        language: str
    ) -> Dict[str, Any]:
        """Generate summary + tags using AI (best-effort)."""
        try:
            from src.ai.ai_service import get_ai_service
            from src.core.language_manager import get_language_manager

            lm = get_language_manager()
            doc_language = language if language in ["en", "zh-HK"] else lm.detect_language(content)
            excerpt = content[:4000]
            prompt = (
                "You are a knowledge base curator. Read the document excerpt and return JSON only "
                "with these keys:\n"
                "summary: 3-5 concise sentences in the same language as the document.\n"
                "topics: array of 2-8 concise topic tags in the same language as the document (short, lowercase when possible).\n"
                "topics_en: if the document is not English, translate topics into English; otherwise copy topics.\n"
                "topics_zh: if the document is not Chinese, translate topics into Chinese (Cantonese/Traditional); otherwise copy topics.\n"
                "age_groups: array of any of [child, teen, adult, elderly] if clearly relevant; otherwise empty.\n"
                "category: one short category label (1-3 words). If unsure, use \"general\".\n\n"
                f"Document title: {title}\n"
                f"Document language: {doc_language}\n"
                "Document excerpt:\n"
                f"{excerpt}"
            )

            ai = await get_ai_service()
            res = await ai.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.2,
            )
            data = _extract_json_block(res.get("content", "") or "")
            if not isinstance(data, dict):
                return {}

            summary = str(data.get("summary", "") or "").strip()
            topics = _coerce_list(data.get("topics"))
            topics_en = _coerce_list(data.get("topics_en"))
            topics_zh = _coerce_list(data.get("topics_zh"))
            age_groups = _coerce_list(data.get("age_groups"))
            category = str(data.get("category", "") or "").strip()
            return {
                "summary": summary,
                "topics": topics,
                "topics_en": topics_en,
                "topics_zh": topics_zh,
                "age_groups": age_groups,
                "category": category
            }
        except Exception as e:
            logger.warning(f"Auto-tag/summary failed: {e}")
            return {}
    
    async def ingest_document(
        self,
        title: str,
        content: str,
        category: str,
        category_id: Optional[int] = None,  # NEW: Accept category ID
        language: str = "en",
        tags: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        age_groups: Optional[List[str]] = None,
        auto_tag: bool = False,
        auto_summary: bool = False,
        source: Optional[str] = None,
        author: Optional[str] = None,
        metadata: Optional[Dict] = None,
        organization_id: Optional[int] = None,
        visibility: str = "org",
        file_hash: Optional[str] = None,
        force_reindex: bool = False,
        source_type: str = "text",
        chunks_override: Optional[List[DocumentChunk]] = None,
        use_semantic_chunking: Optional[bool] = None  # NEW: Override feature flag
    ) -> IngestedDocument:
        """
        Ingest a single document into the knowledge base.
        
        Args:
            title: Document title
            content: Document text content
            category: Category (psychoeducation, crisis_protocol, etc.)
            category_id: Optional category ID from kb_categories table
            language: Language code (en, zh-HK)
            tags: Optional tags
            source: Source reference
            author: Author name
            metadata: Additional metadata
            use_semantic_chunking: Optional override for AI semantic chunking feature flag.
                If None, uses AI_SEMANTIC_CHUNKING_ENABLED from config.
                If True, forces AI semantic chunking (with fallback on errors).
                If False, uses simple paragraph-based chunking.
            
        Returns:
            IngestedDocument with results
            
        Note:
            When AI semantic chunking is enabled, the system will:
            - Use AI to detect semantic boundaries
            - Adapt chunk sizes based on content complexity
            - Generate AI-powered summaries and keywords
            - Fall back to simple chunking if AI services fail
        """
        try:
            auto_result: Dict[str, Any] = {}
            if auto_tag or auto_summary:
                auto_result = await self._auto_tag_and_summarize(title, content, language)

            ai_summary = auto_result.get("summary") if auto_summary else None
            ai_topics = auto_result.get("topics") if auto_tag else None
            ai_topics_en = auto_result.get("topics_en") if auto_tag else None
            ai_topics_zh = auto_result.get("topics_zh") if auto_tag else None
            ai_ages = auto_result.get("age_groups") if auto_tag else None
            ai_category = auto_result.get("category") if auto_tag else None

            if (not category) or category.strip().lower() == "auto":
                if ai_category:
                    category = ai_category
                else:
                    category = "general"

            # Normalize topics/age groups and merge into tags + metadata
            meta = metadata or {}
            if isinstance(topics, str):
                topics = [t.strip() for t in topics.split(",") if t.strip()]
            if isinstance(age_groups, str):
                age_groups = [a.strip() for a in age_groups.split(",") if a.strip()]

            combined_topics = _coerce_list(topics or meta.get("topics", []))
            combined_topics_en = _coerce_list(meta.get("topics_en", []))
            combined_topics_zh = _coerce_list(meta.get("topics_zh", []))
            combined_ages = _coerce_list(age_groups or meta.get("age_groups", []))
            if ai_topics:
                combined_topics.extend(_coerce_list(ai_topics))
            if ai_topics_en:
                combined_topics_en.extend(_coerce_list(ai_topics_en))
            if ai_topics_zh:
                combined_topics_zh.extend(_coerce_list(ai_topics_zh))
            if ai_ages:
                combined_ages.extend(_coerce_list(ai_ages))

            normalized_topics = _dedupe_list([_normalize_topic(t) for t in combined_topics])
            normalized_topics_en = _dedupe_list([_normalize_topic(t) for t in combined_topics_en])
            normalized_topics_zh = _dedupe_list([_normalize_topic(t) for t in combined_topics_zh])
            normalized_ages = _dedupe_list([_normalize_age_group(a) for a in combined_ages])
            all_topics = _dedupe_list(normalized_topics + normalized_topics_en + normalized_topics_zh)

            if normalized_topics:
                meta["topics"] = normalized_topics
            if normalized_topics_en:
                meta["topics_en"] = normalized_topics_en
            if normalized_topics_zh:
                meta["topics_zh"] = normalized_topics_zh
            if all_topics:
                meta["topics_all"] = all_topics
            if normalized_ages:
                meta["age_groups"] = normalized_ages
            if ai_summary:
                meta["summary"] = ai_summary
            if ai_category:
                meta["ai_category"] = ai_category

            tag_list = list(tags or [])
            tag_list.extend([f"topic:{t}" for t in all_topics])
            tag_list.extend([f"age:{a}" for a in normalized_ages])
            tag_list = _dedupe_list(tag_list)

            # Generate hashes for deduplication
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            file_hash_value = file_hash or content_hash
            
            if not force_reindex:
                # Check for duplicate by file_hash first, then content_hash
                existing = await self._check_duplicate(file_hash_value, content_hash)
                if existing:
                    logger.info(f"Document already exists with ID {existing}")
                    return IngestedDocument(
                        document_id=existing,
                        title=title,
                        chunk_count=0,
                        status="duplicate",
                        error="Document with same content already exists"
                    )
            
            # Create document record
            document_id = await self._create_document_record(
                title=title,
                content=content,
                content_hash=content_hash,
                category=category,
                category_id=category_id,  # NEW: Pass category_id
                language=language,
                tags=tag_list,
                source=source,
                author=author,
                metadata=meta,
                organization_id=organization_id,
                visibility=visibility,
                file_hash=file_hash_value,
                source_type=source_type
            )
            
            if not document_id:
                return IngestedDocument(
                    document_id=0,
                    title=title,
                    chunk_count=0,
                    status="error",
                    error="Failed to create document record"
                )
            
            # Chunk the document (or use provided pre-chunked list)
            if chunks_override:
                chunks = chunks_override
            else:
                # FEATURE FLAG: Check if AI semantic chunking is enabled
                # use_semantic_chunking parameter can override the feature flag
                use_ai_chunking = (
                    use_semantic_chunking 
                    if use_semantic_chunking is not None 
                    else is_semantic_chunking_enabled()
                )
                
                if use_ai_chunking:
                    # VALIDATION: Use AI-enhanced semantic chunking with fallback
                    # PRIVACY: Log only metadata, not content
                    logger.info(
                        "Starting AI semantic chunking",
                        extra={
                            "document_id": document_id,
                            "content_length": len(content),
                            "language": language,
                            "chunking_method": "semantic"
                        }
                    )
                    
                    # Track AI service call duration
                    start_time = time.time()
                    
                    try:
                        # Initialize and use SemanticChunker
                        semantic_chunker = SemanticChunker()
                        await semantic_chunker.initialize()
                        
                        chunks = await semantic_chunker.chunk_document(
                            content=content,
                            language=language,
                            title=title
                        )
                        
                        # Calculate metrics
                        duration = time.time() - start_time
                        chunk_sizes = [len(c.text) for c in chunks]
                        avg_chunk_size = sum(chunk_sizes) // len(chunks) if chunks else 0
                        min_chunk_size = min(chunk_sizes) if chunk_sizes else 0
                        max_chunk_size = max(chunk_sizes) if chunk_sizes else 0
                        
                        # PRIVACY: Log success metrics without content
                        logger.info(
                            "AI semantic chunking succeeded",
                            extra={
                                "document_id": document_id,
                                "chunk_count": len(chunks),
                                "avg_chunk_size": avg_chunk_size,
                                "min_chunk_size": min_chunk_size,
                                "max_chunk_size": max_chunk_size,
                                "ai_service_duration_seconds": round(duration, 2),
                                "chunking_method": "semantic",
                                "success": True
                            }
                        )
                        
                    except Exception as e:
                        # Calculate duration even on failure
                        duration = time.time() - start_time
                        
                        # Categorize fallback reason
                        fallback_reason = self._categorize_fallback_reason(e)
                        
                        # VALIDATION: Graceful fallback to simple chunking on any error
                        # PRIVACY: Log error without content
                        logger.warning(
                            f"AI semantic chunking failed, falling back to simple chunking",
                            extra={
                                "document_id": document_id,
                                "error_type": type(e).__name__,
                                "error_message": str(e),
                                "fallback_reason": fallback_reason,
                                "ai_service_duration_seconds": round(duration, 2),
                                "chunking_method": "simple_fallback",
                                "success": False
                            }
                        )
                        
                        # Use FallbackHandler for graceful degradation
                        fallback_handler = FallbackHandler()
                        chunks = fallback_handler.handle_fallback(
                            document_id=document_id,
                            content=content,
                            error=e
                        )
                        
                        # Log fallback chunk statistics
                        if chunks:
                            chunk_sizes = [len(c.text) for c in chunks]
                            avg_chunk_size = sum(chunk_sizes) // len(chunks) if chunks else 0
                            logger.info(
                                "Fallback chunking completed",
                                extra={
                                    "document_id": document_id,
                                    "chunk_count": len(chunks),
                                    "avg_chunk_size": avg_chunk_size,
                                    "chunking_method": "simple_fallback"
                                }
                            )
                else:
                    # Use existing simple paragraph-based chunking
                    logger.info(
                        "Using simple paragraph-based chunking",
                        extra={
                            "document_id": document_id,
                            "content_length": len(content),
                            "chunking_method": "simple"
                        }
                    )
                    chunks = self._chunk_document(content)
                    
                    # Log simple chunking statistics
                    if chunks:
                        chunk_sizes = [len(c.text) for c in chunks]
                        avg_chunk_size = sum(chunk_sizes) // len(chunks) if chunks else 0
                        logger.info(
                            "Simple chunking completed",
                            extra={
                                "document_id": document_id,
                                "chunk_count": len(chunks),
                                "avg_chunk_size": avg_chunk_size,
                                "chunking_method": "simple"
                            }
                        )
                
                # Add AI summary as first chunk if available
                if ai_summary:
                    summary_chunk = DocumentChunk(
                        text=ai_summary,
                        index=0,
                        start_char=0,
                        end_char=len(ai_summary),
                        chunk_type="summary"
                    )
                    if chunks:
                        for i, chunk in enumerate(chunks, start=1):
                            chunk.index = i
                    chunks = [summary_chunk] + chunks
            
            # Store chunks in PostgreSQL and vector store
            chunk_count = await self._store_chunks(
                document_id,
                chunks,
                category,
                language,
                organization_id,
                source_type,
                title=title,
                tags=tag_list,
                topics=all_topics,
                age_groups=normalized_ages,
                visibility=visibility,
                doc_metadata=meta
            )
            
            # Update document status
            await self._update_document_status(document_id, "indexed", chunk_count)
            
            logger.info(f"Ingested document '{title}' with {chunk_count} chunks")
            
            return IngestedDocument(
                document_id=document_id,
                title=title,
                chunk_count=chunk_count,
                status="indexed"
            )
            
        except Exception as e:
            logger.error(f"Failed to ingest document '{title}': {e}", exc_info=True)
            return IngestedDocument(
                document_id=0,
                title=title,
                chunk_count=0,
                status="error",
                error=str(e)
            )
    
    async def ingest_batch(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[IngestedDocument]:
        """
        Ingest multiple documents.
        
        Args:
            documents: List of document dicts with title, content, category, etc.
            
        Returns:
            List of IngestedDocument results
        """
        results = []
        for doc in documents:
            result = await self.ingest_document(
                title=doc.get('title', 'Untitled'),
                content=doc.get('content', ''),
                category=doc.get('category', 'psychoeducation'),
                language=doc.get('language', 'en'),
                tags=doc.get('tags'),
                topics=doc.get('topics'),
                age_groups=doc.get('age_groups'),
                source=doc.get('source'),
                author=doc.get('author'),
                metadata=doc.get('metadata'),
                organization_id=doc.get("organization_id"),
                visibility=doc.get("visibility", "org"),
                file_hash=doc.get("file_hash"),
                force_reindex=doc.get("force_reindex", False),
                source_type=doc.get("source_type", "text")
            )
            results.append(result)
        
        return results
    
    def _chunk_document(self, content: str) -> List[DocumentChunk]:
        """
        Split document into overlapping chunks.
        
        Uses paragraph-aware chunking to maintain context.
        """
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
            if len(current_chunk) + len(para) + 2 > self.CHUNK_SIZE:
                # Save current chunk if it meets minimum size
                if len(current_chunk) >= self.MIN_CHUNK_SIZE:
                    chunks.append(DocumentChunk(
                        text=current_chunk.strip(),
                        index=chunk_index,
                        start_char=current_start,
                        end_char=current_start + len(current_chunk),
                        chunk_type="content"
                    ))
                    chunk_index += 1
                
                # Start new chunk with overlap
                if len(current_chunk) > self.CHUNK_OVERLAP:
                    overlap_text = current_chunk[-self.CHUNK_OVERLAP:]
                    current_chunk = overlap_text + "\n\n" + para
                    current_start = current_start + len(current_chunk) - self.CHUNK_OVERLAP - len(para) - 2
                else:
                    current_chunk = para
                    current_start = current_start + len(current_chunk)
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
        
        # Don't forget the last chunk
        if len(current_chunk) >= self.MIN_CHUNK_SIZE:
            chunks.append(DocumentChunk(
                text=current_chunk.strip(),
                index=chunk_index,
                start_char=current_start,
                end_char=current_start + len(current_chunk),
                chunk_type="content"
            ))
        
        return chunks
    
    async def _check_duplicate(self, file_hash: str, content_hash: str) -> Optional[int]:
        """
        Check if document with same content or file hash exists.
        
        PRIVACY: No PII in logs - only document IDs
        """
        try:
            # Check in uploaded_documents table (knowledge_documents doesn't exist)
            sql = text("""
                SELECT id FROM uploaded_documents 
                WHERE file_hash = :file_hash
                LIMIT 1
            """)
            
            async for session in get_async_db():
                result = await session.execute(
                    sql, {"file_hash": file_hash}
                )
                row = result.fetchone()
                return row.id if row else None
            
            return None
        except Exception as e:
            logger.error(f"Error checking duplicate: {e}")
            return None
    
    async def _create_document_record(
        self,
        title: str,
        content: str,
        content_hash: str,
        category: str,
        category_id: Optional[int],  # NEW: Add category_id parameter
        language: str,
        tags: List[str],
        source: Optional[str],
        author: Optional[str],
        metadata: Dict,
        organization_id: Optional[int],
        visibility: str,
        file_hash: str,
        source_type: str
    ) -> Optional[int]:
        """Create document record in PostgreSQL (inserts into uploaded_documents table)"""
        try:
            # Map visibility to access_level for uploaded_documents table
            # uploaded_documents uses: public, internal, restricted, confidential
            # knowledge API uses: public, org, private
            access_level_map = {
                "public": "public",
                "org": "internal",  # Map org to internal
                "private": "restricted"  # Map private to restricted
            }
            access_level = access_level_map.get(visibility, "internal")
            
            # Insert into uploaded_documents table (not the view)
            sql = text("""
                INSERT INTO uploaded_documents (
                    title, extracted_text, file_hash, category,
                    language, tags, document_metadata,
                    processing_status, uploaded_by, access_level,
                    original_filename, stored_filename, file_path,
                    file_size, file_type, mime_type, document_type,
                    is_active, is_searchable
                ) VALUES (
                    :title, :content, :file_hash, :category,
                    :language, :tags, :metadata,
                    'processing', :uploaded_by, :access_level,
                    :original_filename, :stored_filename, :file_path,
                    :file_size, :file_type, :mime_type, :document_type,
                    TRUE, TRUE
                )
                RETURNING id
            """)
            
            metadata_json = metadata if isinstance(metadata, str) else json.dumps(metadata or {})
            
            # Extract file info from metadata if available
            file_path = metadata.get("file_path", "") if isinstance(metadata, dict) else ""
            # Calculate file_size from metadata or content length
            file_size = metadata.get("file_size", 0) if isinstance(metadata, dict) else 0
            if file_size == 0 and content:
                # Use content length as file size (in bytes, UTF-8 encoded)
                file_size = len(content.encode('utf-8'))
            content_type = metadata.get("content_type", "text/plain") if isinstance(metadata, dict) else "text/plain"
            filename = metadata.get("filename", "document.txt") if isinstance(metadata, dict) else "document.txt"
            
            async for session in get_async_db():
                result = await session.execute(sql, {
                    "title": title,
                    "content": content,
                    "file_hash": file_hash,
                    "category": category,
                    "language": language,
                    "tags": tags,
                    "metadata": metadata_json,
                    "uploaded_by": organization_id or 1,
                    "access_level": access_level,
                    "original_filename": filename,
                    "stored_filename": filename,
                    "file_path": file_path or f"/tmp/{file_hash}",
                    "file_size": file_size,
                    "file_type": source_type,
                    "mime_type": content_type,
                    "document_type": "training_material"  # Use training_material for KB documents
                })
                await session.commit()
                
                row = result.fetchone()
                doc_id = row[0] if row else None
                
                # If category_id is provided, create the association in document_category_tags
                if doc_id and category_id:
                    try:
                        tag_sql = text("""
                            INSERT INTO document_category_tags (document_id, category_id)
                            VALUES (:doc_id, :category_id)
                            ON CONFLICT DO NOTHING
                        """)
                        await session.execute(tag_sql, {
                            "doc_id": doc_id,
                            "category_id": category_id
                        })
                        await session.commit()
                    except Exception as tag_error:
                        logger.warning(f"Failed to create category tag: {tag_error}")
                
                return doc_id
            
            return None
        except Exception as e:
            logger.error(f"Error creating document record: {e}", exc_info=True)
            return None
    
    async def _store_chunks(
        self,
        document_id: int,
        chunks: List[DocumentChunk],
        category: str,
        language: str,
        organization_id: Optional[int],
        source_type: str,
        title: str,
        tags: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        age_groups: Optional[List[str]] = None,
        visibility: Optional[str] = None,
        doc_metadata: Optional[Dict] = None
    ) -> int:
        """
        Store chunks in vector store only (document_chunks table doesn't exist).
        
        PRIVACY: No PII in logs - only document IDs
        VALIDATION: Generate embeddings before storing to ensure correct dimensions
        """
        stored_count = 0
        
        # Extract form metadata from document metadata (Requirements 2.4, 3.1)
        is_form = False
        form_type = None
        if doc_metadata:
            is_form = doc_metadata.get("is_form", False)
            form_type = doc_metadata.get("form_type")
        
        # BUGFIX: Generate embeddings in batch before storing
        # This ensures we use AWS Titan embeddings (1536 dims) instead of ChromaDB default (384 dims)
        try:
            # Extract chunk texts
            chunk_texts = [chunk.text for chunk in chunks]
            
            # Generate embeddings using EmbeddingService
            embedding_service = get_embedding_service()
            logger.info(f"Generating embeddings for {len(chunk_texts)} chunks from document {document_id}")
            embeddings = await embedding_service.embed_batch(chunk_texts, batch_size=100)
            
            if len(embeddings) != len(chunks):
                logger.error(f"Embedding count mismatch: {len(embeddings)} embeddings for {len(chunks)} chunks")
                return 0
            
            logger.info(f"Successfully generated {len(embeddings)} embeddings (dimension: {len(embeddings[0]) if embeddings else 0})")
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings for document {document_id}: {e}")
            return 0
        
        # Store chunks with pre-computed embeddings
        for chunk, embedding in zip(chunks, embeddings):
            try:
                # Store in vector store with chunk metadata
                # Note: document_chunks table doesn't exist, so we store only in vector store
                chunk_id = f"doc_{document_id}_chunk_{chunk.index}"
                meta_source_type = "summary" if chunk.chunk_type == "summary" else source_type
                
                self.vector_store.add_documents(
                    documents=[chunk.text],
                    embeddings=[embedding],  # BUGFIX: Pass pre-computed embeddings
                    metadatas=[{
                        "document_id": document_id,
                        "chunk_id": chunk_id,
                        "chunk_index": chunk.index,
                        "chunk_type": chunk.chunk_type,
                        "category": category,
                        "language": language,
                        "organization_id": organization_id or 0,
                        "visibility": visibility or "org",
                        "source_type": meta_source_type,
                        "title": title,
                        # ChromaDB doesn't allow empty lists - only include if non-empty
                        **({} if not tags else {"tags": tags}),
                        **({} if not topics else {"topics": topics}),
                        **({} if not age_groups else {"age_groups": age_groups}),
                        **({} if not getattr(chunk, "page", None) else {"page": chunk.page}),
                        **({} if not getattr(chunk, "timestamp_start", None) else {"timestamp_start": chunk.timestamp_start}),
                        **({} if not getattr(chunk, "timestamp_end", None) else {"timestamp_end": chunk.timestamp_end}),
                        # AI-generated metadata fields (optional, backward compatible)
                        **({} if not getattr(chunk, "summary", None) else {"chunk_summary": chunk.summary}),
                        **({} if not getattr(chunk, "keywords", None) else {"chunk_keywords": chunk.keywords}),
                        **({} if not getattr(chunk, "topic", None) else {"chunk_topic": chunk.topic}),
                        **({} if not getattr(chunk, "complexity", None) else {"complexity": chunk.complexity}),
                        **({} if not getattr(chunk, "structure_type", None) else {"structure_type": chunk.structure_type}),
                        **({} if not getattr(chunk, "heading_context", None) else {"heading_context": chunk.heading_context}),
                        # Always include chunking_method (defaults to "simple" in DocumentChunk)
                        "chunking_method": getattr(chunk, "chunking_method", "simple"),
                        # Form metadata fields (Requirements 2.4, 3.1)
                        "is_form": is_form,
                        **({} if not form_type else {"form_type": form_type})
                    }],
                    ids=[chunk_id]
                )
                stored_count += 1
                logger.debug(f"Stored chunk {chunk.index} for document {document_id} in vector store")
                    
            except Exception as e:
                logger.error(f"Error storing chunk {chunk.index} for document {document_id}: {e}")
        
        return stored_count
    
    async def _update_document_status(
        self,
        document_id: int,
        status: str,
        chunk_count: int
    ) -> None:
        """Update document status after processing (updates uploaded_documents table)"""
        try:
            # Map status to processing_status for uploaded_documents table
            status_map = {
                "indexed": "processed",  # Fixed: use 'processed' not 'completed'
                "processing": "processing",
                "error": "failed",
                "pending": "uploaded"  # Fixed: use 'uploaded' not 'pending'
            }
            processing_status = status_map.get(status, "processing")
            
            sql = text("""
                UPDATE uploaded_documents
                SET 
                    processing_status = :status,
                    processing_completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = :doc_id
            """)
            
            async for session in get_async_db():
                await session.execute(sql, {
                    "doc_id": document_id,
                    "status": processing_status
                })
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error updating document status: {e}")

    async def _reset_document_record(
        self,
        document_id: int,
        category: str,
        language: str,
        tags: List[str],
        metadata: Dict[str, Any]
    ) -> None:
        """Reset document metadata before reindexing (updates uploaded_documents table)."""
        try:
            sql = text("""
                UPDATE uploaded_documents
                SET
                    category = :category,
                    language = :language,
                    tags = :tags,
                    document_metadata = :metadata,
                    processing_status = 'processing',
                    processing_error = NULL,
                    processing_completed_at = NULL,
                    updated_at = NOW()
                WHERE id = :doc_id
            """)
            metadata_json = metadata if isinstance(metadata, str) else json.dumps(metadata or {})
            async for session in get_async_db():
                await session.execute(sql, {
                    "doc_id": document_id,
                    "category": category,
                    "language": language,
                    "tags": tags,
                    "metadata": metadata_json
                })
                await session.commit()
        except Exception as e:
            logger.error(f"Error resetting document record: {e}")

    async def _delete_chunks(self, document_id: int) -> None:
        """
        Delete existing chunks for a document from vector store.
        Note: document_chunks table doesn't exist, so we only delete from vector store.
        
        PRIVACY: No PII in logs - only document IDs
        """
        try:
            # Delete from vector store only (document_chunks table doesn't exist)
            if self.vector_store is None:
                self.vector_store = get_vector_store()
            self.vector_store.delete_by_metadata({"document_id": document_id})
            logger.debug(f"Deleted chunks for document {document_id} from vector store")
        except Exception as e:
            logger.error(f"Error deleting chunks for doc {document_id}: {e}")

    async def reindex_document(
        self,
        document_id: int,
        category: Optional[str] = None,
        language: Optional[str] = None,
        tags: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        age_groups: Optional[List[str]] = None,
        auto_tag: bool = False,
        auto_summary: bool = False,
    ) -> IngestedDocument:
        """Re-index an existing document with optional auto-tag/summary."""
        try:
            # Read from uploaded_documents table directly instead of view
            sql = text("""
                SELECT id, title, extracted_text as content, category, language, 
                       document_metadata as metadata, uploaded_by as organization_id,
                       CASE 
                           WHEN access_level = 'public' THEN 'public'
                           WHEN access_level = 'organization' THEN 'org'
                           ELSE 'private'
                       END as visibility
                FROM uploaded_documents
                WHERE id = :doc_id AND is_active = TRUE
            """)
            async for session in get_async_db():
                result = await session.execute(sql, {"doc_id": document_id})
                row = result.fetchone()
                if not row:
                    return IngestedDocument(
                        document_id=0,
                        title="",
                        chunk_count=0,
                        status="error",
                        error="Document not found"
                    )

            title = row.title or "Untitled"
            content = row.content or ""
            if not content.strip():
                return IngestedDocument(
                    document_id=document_id,
                    title=title,
                    chunk_count=0,
                    status="error",
                    error="Document content is empty"
                )

            doc_category = category or row.category or "general"
            doc_language = language or row.language or "en"
            tag_list = list(tags) if tags is not None else []  # No tags column in uploaded_documents

            meta = row.metadata
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            if not isinstance(meta, dict):
                meta = {}

            auto_result: Dict[str, Any] = {}
            if auto_tag or auto_summary:
                auto_result = await self._auto_tag_and_summarize(title, content, doc_language)

            ai_summary = auto_result.get("summary") if auto_summary else None
            ai_topics = auto_result.get("topics") if auto_tag else None
            ai_topics_en = auto_result.get("topics_en") if auto_tag else None
            ai_topics_zh = auto_result.get("topics_zh") if auto_tag else None
            ai_ages = auto_result.get("age_groups") if auto_tag else None
            ai_category = auto_result.get("category") if auto_tag else None

            if (not doc_category) or str(doc_category).strip().lower() == "auto":
                doc_category = ai_category or "general"

            combined_topics = _coerce_list(topics if topics is not None else meta.get("topics", []))
            combined_topics_en = _coerce_list(meta.get("topics_en", []))
            combined_topics_zh = _coerce_list(meta.get("topics_zh", []))
            combined_ages = _coerce_list(age_groups if age_groups is not None else meta.get("age_groups", []))
            if ai_topics:
                combined_topics.extend(_coerce_list(ai_topics))
            if ai_topics_en:
                combined_topics_en.extend(_coerce_list(ai_topics_en))
            if ai_topics_zh:
                combined_topics_zh.extend(_coerce_list(ai_topics_zh))
            if ai_ages:
                combined_ages.extend(_coerce_list(ai_ages))

            normalized_topics = _dedupe_list([_normalize_topic(t) for t in combined_topics])
            normalized_topics_en = _dedupe_list([_normalize_topic(t) for t in combined_topics_en])
            normalized_topics_zh = _dedupe_list([_normalize_topic(t) for t in combined_topics_zh])
            normalized_ages = _dedupe_list([_normalize_age_group(a) for a in combined_ages])
            all_topics = _dedupe_list(normalized_topics + normalized_topics_en + normalized_topics_zh)

            if normalized_topics:
                meta["topics"] = normalized_topics
            else:
                meta.pop("topics", None)
            if normalized_topics_en:
                meta["topics_en"] = normalized_topics_en
            else:
                meta.pop("topics_en", None)
            if normalized_topics_zh:
                meta["topics_zh"] = normalized_topics_zh
            else:
                meta.pop("topics_zh", None)
            if all_topics:
                meta["topics_all"] = all_topics
            else:
                meta.pop("topics_all", None)
            if normalized_ages:
                meta["age_groups"] = normalized_ages
            else:
                meta.pop("age_groups", None)

            summary_text = ai_summary or (meta.get("summary") if isinstance(meta, dict) else None)
            if summary_text:
                meta["summary"] = summary_text
            if ai_category:
                meta["ai_category"] = ai_category

            tag_list.extend([f"topic:{t}" for t in all_topics])
            tag_list.extend([f"age:{a}" for a in normalized_ages])
            tag_list = _dedupe_list(tag_list)

            # Clear old chunks in vector store and postgres
            try:
                if self.vector_store is None:
                    self.vector_store = get_vector_store()
                self.vector_store.delete_by_metadata({"document_id": document_id})
            except Exception:
                pass
            await self._delete_chunks(document_id)

            # Reset document record metadata
            await self._reset_document_record(
                document_id=document_id,
                category=doc_category,
                language=doc_language,
                tags=tag_list,
                metadata=meta
            )

            chunks = self._chunk_document(content)
            if summary_text:
                summary_chunk = DocumentChunk(
                    text=summary_text,
                    index=0,
                    start_char=0,
                    end_char=len(summary_text),
                    chunk_type="summary"
                )
                if chunks:
                    for i, chunk in enumerate(chunks, start=1):
                        chunk.index = i
                chunks = [summary_chunk] + chunks

            chunk_count = await self._store_chunks(
                document_id,
                chunks,
                doc_category,
                doc_language,
                row.organization_id,
                meta.get("source_type", "text"),
                title=title,
                tags=tag_list,
                topics=all_topics,
                age_groups=normalized_ages,
                visibility=row.visibility,
                doc_metadata=meta
            )
            await self._update_document_status(document_id, "indexed", chunk_count)

            return IngestedDocument(
                document_id=document_id,
                title=title,
                chunk_count=chunk_count,
                status="indexed"
            )
        except Exception as e:
            logger.error(f"Failed to reindex document {document_id}: {e}", exc_info=True)
            return IngestedDocument(
                document_id=document_id,
                title="",
                chunk_count=0,
                status="error",
                error=str(e)
            )
    
    async def delete_document(self, document_id: int) -> bool:
        """
        Delete a document and its chunks.
        
        Args:
            document_id: Document ID to delete
            
        Returns:
            True if successful
            
        PRIVACY: No PII in logs - only document IDs
        AUDIT: Document deletion should be logged by caller
        """
        try:
            # Delete from vector store
            try:
                self.vector_store.delete_by_metadata({"document_id": document_id})
            except Exception:
                pass  # May not exist in vector store
            
            # Delete from PostgreSQL (use uploaded_documents table)
            sql = text("""
                DELETE FROM uploaded_documents WHERE id = :doc_id
            """)
            
            async for session in get_async_db():
                await session.execute(sql, {"doc_id": document_id})
                await session.commit()
            
            logger.info(f"Deleted document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return False


# Singleton
_ingestion_service: Optional[DocumentIngestionService] = None


def get_ingestion_service() -> DocumentIngestionService:
    """Get or create ingestion service singleton"""
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = DocumentIngestionService()
    return _ingestion_service

