"""
Hybrid Retriever for RAG System

Combines BM25 (keyword search), Vector (semantic search), and RRF (Reciprocal Rank Fusion)
for high-accuracy document retrieval.

Features:
- BM25 full-text search via PostgreSQL
- Vector similarity search via ChromaDB
- RRF fusion for combining results
- Skill-aware filtering
- Citation tracking integration
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from sqlalchemy import text

from ..database.connection import get_async_db
from ..database.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)


@dataclass
class RetrievalConfig:
    """Configuration for hybrid retrieval"""
    bm25_weight: float = 0.3
    vector_weight: float = 0.7
    rrf_k: int = 60  # RRF constant
    top_k: int = 5
    min_score: float = 0.1
    include_metadata: bool = True
    skill_filter: Optional[List[str]] = None
    category_filter: Optional[List[str]] = None
    language_filter: Optional[str] = None
    organization_id: Optional[int] = None
    visibility: Optional[str] = None  # public|org|private
    recency_boost_days: int = 30
    summary_boost: float = 0.05
    single_doc_ratio: float = 0.8
    single_doc_score_margin: float = 1.1
    # BUGFIX: Form-only search boost multiplier
    # Controls how much to boost form documents from form-only search in RRF fusion
    # Higher values (e.g., 3.0) ensure forms rank in top 3 positions when form keywords detected
    # Lower values (e.g., 1.5) provide gentler boosting for edge cases
    # Set to 1.0 to disable form-only boosting (not recommended for form search fix)
    form_only_boost_multiplier: float = 3.0



@dataclass
class SearchResult:
    """Single search result with combined scoring"""
    chunk_id: str
    document_id: int
    content: str
    score: float
    bm25_score: float
    vector_score: float
    rank: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'chunk_id': self.chunk_id,
            'document_id': self.document_id,
            'content': self.content,
            'score': self.score,
            'bm25_score': self.bm25_score,
            'vector_score': self.vector_score,
            'rank': self.rank,
            'metadata': self.metadata
        }


class HybridRetriever:
    """
    Hybrid retriever combining BM25 and Vector search with RRF fusion.
    
    Architecture:
    1. Query arrives
    2. Parallel execution:
       - BM25 search via PostgreSQL full-text search
       - Vector search via ChromaDB
    3. RRF fusion combines results
    4. Final ranking and filtering
    5. Return top-k results with citations
    """
    
    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        config: Optional[RetrievalConfig] = None
    ):
        """
        Initialize hybrid retriever.
        
        Args:
            vector_store: ChromaDB vector store instance
            config: Retrieval configuration
        """
        # Lazy init to avoid model download when BM25-only
        self.vector_store = vector_store
        self.config = config or RetrievalConfig()
        self.embedding_service = None  # Lazy loaded
    
    async def hybrid_search(
        self,
        query: str,
        skills: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        category_id: Optional[int] = None,  # NEW: Category filtering
        include_subcategories: bool = True,  # NEW: Include child categories
        config_override: Optional[RetrievalConfig] = None,
        organization_id: Optional[int] = None,
        visibility: Optional[str] = None,
        debug: bool = False,
        use_vector: bool = True,
        document_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform hybrid search combining BM25 and vector search.
        
        Args:
            query: Search query text
            skills: Active skills for filtering (optional)
            top_k: Number of results to return
            category_id: Filter by category ID (optional)
            include_subcategories: Include documents from child categories
            config_override: Override default config
            
        Returns:
            Dict with results, citations, and metadata
        """
        config = config_override or self.config
        # override org/visibility if provided
        if organization_id is not None:
            config.organization_id = organization_id
        if visibility:
            config.visibility = visibility
        top_k = top_k or config.top_k
        
        start_time = datetime.utcnow()
        
        try:
            # Build category filter from skills
            category_filter = None
            if skills:
                category_filter = self._skills_to_categories(skills)
            
            # Get document IDs in category if category_id is provided
            category_doc_ids = None
            if category_id is not None:
                try:
                    from src.knowledge_base.category_service import get_category_service
                    async for db in get_async_db():
                        category_service = get_category_service()
                        category_doc_ids = await category_service.get_documents_in_category(
                            db, category_id, include_subcategories
                        )
                        logger.info(f"Category {category_id} has {len(category_doc_ids)} documents")
                        break
                except Exception as cat_error:
                    logger.warning(f"Failed to get category documents: {cat_error}")
            
            # Run BM25 (and optionally Vector) searches
            bm25_results = await self._bm25_search(
                query,
                top_k * 2,
                category_filter,
                organization_id=config.organization_id,
                visibility=config.visibility,
                document_id=document_id,
                category_doc_ids=category_doc_ids,  # NEW: Pass category document IDs
            )
            vector_results = []
            if use_vector:
                vector_results = await self._vector_search(
                    query,
                    top_k * 2,
                    category_filter,
                    organization_id=config.organization_id,
                    visibility=config.visibility,
                    document_id=document_id,
                    category_doc_ids=category_doc_ids,  # NEW: Pass category document IDs
                )
            
            # Use query terms to softly boost metadata overlap (no preset mapping)
            query_terms = self._extract_fallback_terms(query)[:12]
            
            # BUGFIX: Detect form keywords for smart boosting (hybrid approach)
            # Only boost forms when user explicitly asks for forms
            has_form_keywords = self._detect_form_keywords(query)
            form_only_results = []
            if has_form_keywords:
                logger.info(f"📋 Form keywords detected in query, triggering form-only search")
                # BUGFIX: Run form-only search to ensure form documents are included
                # This bypasses BM25 text-length bias that excludes forms with minimal content
                form_only_results = await self._form_only_search(
                    query=query,
                    top_k=top_k,
                    organization_id=config.organization_id,
                    visibility=config.visibility
                )
                logger.info(f"📋 Form-only search returned {len(form_only_results)} results")

            # BUGFIX: Adjust weights when one search method fails
            # If vector search failed but BM25 succeeded, use BM25-only mode
            # If BM25 failed but vector succeeded, use vector-only mode
            adjusted_bm25_weight = config.bm25_weight
            adjusted_vector_weight = config.vector_weight
            
            if not vector_results and bm25_results:
                # Vector search failed, use BM25 only
                logger.warning("Vector search returned no results, falling back to BM25-only mode")
                adjusted_bm25_weight = 1.0
                adjusted_vector_weight = 0.0
            elif not bm25_results and vector_results:
                # BM25 search failed, use vector only
                logger.warning("BM25 search returned no results, falling back to vector-only mode")
                adjusted_bm25_weight = 0.0
                adjusted_vector_weight = 1.0

            # Combine results using RRF
            combined_results = self._rrf_fusion(
                bm25_results=bm25_results,
                vector_results=vector_results,
                bm25_weight=adjusted_bm25_weight,
                vector_weight=adjusted_vector_weight,
                rrf_k=config.rrf_k,
                query_terms=query_terms,
                has_form_keywords=has_form_keywords,  # BUGFIX: Pass form keyword detection for smart boosting
                form_only_results=form_only_results  # BUGFIX: Pass form-only search results for merging
            )
            
            # Filter and limit results
            filtered_results = [
                r for r in combined_results
                if r.score >= config.min_score
            ][:top_k]
            # If we have candidates but all were below min_score, relax the threshold.
            if not filtered_results and combined_results:
                filtered_results = combined_results[:top_k]
                min_score_relaxed = True
            else:
                min_score_relaxed = False
            
            # BUGFIX: Precision filtering for specific form requests
            # Initialize precision filtering flags
            precision_filtered = False
            filtered_form_count = 0
            is_specific_request = False
            
            if has_form_keywords and filtered_results:
                # Check if this is a specific form request
                is_specific_request = self._is_specific_form_request(query)
                
                if is_specific_request:
                    # BUGFIX: Apply precision filtering for specific form requests
                    # Only keep the most relevant form
                    
                    # Separate form and non-form results
                    form_results = [r for r in filtered_results if r.metadata.get('is_form')]
                    non_form_results = [r for r in filtered_results if not r.metadata.get('is_form')]
                    
                    if len(form_results) > 1:
                        # Calculate precision scores
                        form_scores = []
                        for form_result in form_results:
                            precision_score = self._calculate_form_precision_score(query, form_result)
                            form_scores.append((form_result, precision_score))
                            # PRIVACY: Log document ID only, no content
                            logger.debug(f"Form precision score: doc_id={form_result.document_id}, "
                                       f"score={precision_score:.3f}")
                        
                        # Sort by precision score (descending)
                        form_scores.sort(key=lambda x: x[1], reverse=True)
                        
                        # Keep only the top form
                        top_form = form_scores[0][0]
                        filtered_form_count = len(form_results) - 1
                        
                        # PRIVACY: Log IDs only
                        logger.info(f"📋 Precision filtering: Specific form request detected, "
                                   f"keeping top form (doc_id={top_form.document_id}), "
                                   f"filtered out {filtered_form_count} forms")
                        
                        # Rebuild filtered_results with only top form + non-form results
                        filtered_results = [top_form] + non_form_results
                        precision_filtered = True
            
            # Multi-topic detection (for grounding + cohesion)
            topic_groups = self._split_multi_topic_query(query)
            is_multi_topic = len(topic_groups) >= 2

            # Prefer a single dominant document for single-topic queries
            if filtered_results and not is_multi_topic:
                doc_counts: Dict[int, int] = {}
                doc_scores: Dict[int, List[float]] = {}
                for r in filtered_results:
                    doc_counts[r.document_id] = doc_counts.get(r.document_id, 0) + 1
                    doc_scores.setdefault(r.document_id, []).append(r.score)
                if doc_counts:
                    sorted_docs = sorted(doc_counts.items(), key=lambda x: (-x[1], x[0]))
                    top_doc_id, top_count = sorted_docs[0]
                    second_doc_id = sorted_docs[1][0] if len(sorted_docs) > 1 else None
                    top_ratio = top_count / max(len(filtered_results), 1)
                    top_avg = sum(doc_scores.get(top_doc_id, [0])) / max(len(doc_scores.get(top_doc_id, [])), 1)
                    second_avg = 0.0
                    if second_doc_id is not None:
                        second_avg = sum(doc_scores.get(second_doc_id, [0])) / max(len(doc_scores.get(second_doc_id, [])), 1)
                    if top_ratio >= config.single_doc_ratio and (second_doc_id is None or top_avg >= (second_avg * config.single_doc_score_margin)):
                        filtered_results = [r for r in filtered_results if r.document_id == top_doc_id]

            # Build citations
            citations = self._build_citations(filtered_results)

            # Relevance check based on term overlap (strong terms required)
            terms = self._extract_fallback_terms(query)
            strong_terms = self._filter_strong_terms(terms)
            matched_terms = []
            matched_strong = []
            if filtered_results and terms:
                for term in terms:
                    for r in filtered_results:
                        if self._term_in_result(term, r):
                            matched_terms.append(term)
                            if term in strong_terms:
                                matched_strong.append(term)
                            break
                    if len(matched_terms) >= 6:
                        break
            if not filtered_results:
                low_relevance = True
            elif strong_terms:
                required = 2 if len(strong_terms) >= 4 else 1
                low_relevance = len(set(matched_strong)) < required
            else:
                low_relevance = len(matched_terms) < 1

            # Multi-topic grounding: require coverage for each group
            multi_topic_covered = []
            if topic_groups and filtered_results:
                for group_terms in topic_groups:
                    covered = False
                    for term in group_terms:
                        for r in filtered_results:
                            if self._term_in_result(term, r):
                                covered = True
                                break
                        if covered:
                            break
                    if covered:
                        multi_topic_covered.append(group_terms)
                if len(multi_topic_covered) < len(topic_groups):
                    low_relevance = True

            # Anchor checks for explicit chapter/section references
            anchor_terms = self._extract_anchor_terms(query)
            anchor_matched = True
            if anchor_terms and filtered_results:
                anchor_matched = False
                for term in anchor_terms:
                    for r in filtered_results:
                        content = r.content or ""
                        title = (r.metadata or {}).get("title") or ""
                        if term in content or term in title:
                            anchor_matched = True
                            break
                    if anchor_matched:
                        break
                if not anchor_matched:
                    low_relevance = True
            
            # Calculate retrieval time
            retrieval_time_ms = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )
            
            response = {
                'results': [r.to_dict() for r in filtered_results],
                'citations': citations,
                'query': query,
                'skills_used': skills,
                'total_results': len(filtered_results),
                'retrieval_time_ms': retrieval_time_ms,
                'config': {
                    'bm25_weight': config.bm25_weight,
                    'vector_weight': config.vector_weight,
                    'top_k': top_k,
                    'use_vector': use_vector,
                    'min_score_relaxed': min_score_relaxed
                },
                'matched_terms': matched_terms,
                'matched_strong_terms': list(dict.fromkeys(matched_strong)),
                'is_multi_topic': is_multi_topic,
                'multi_topic_groups': [[t for t in g] for g in topic_groups],
                'multi_topic_covered': len(multi_topic_covered),
                'anchor_terms': anchor_terms,
                'anchor_matched': anchor_matched,
                'low_relevance': low_relevance,
                # BUGFIX: Precision filtering metadata for debugging
                'precision_filtered': precision_filtered,
                'specific_form_request': is_specific_request,
                'filtered_form_count': filtered_form_count
            }
            if debug:
                response['debug'] = self._build_debug_trace(
                    query=query,
                    skills=skills,
                    category_filter=category_filter,
                    document_id=document_id,
                    bm25_results=bm25_results,
                    vector_results=vector_results,
                    fused_results=filtered_results,
                    config=config,
                    top_k=top_k,
                    retrieval_time_ms=retrieval_time_ms
                )
            return response
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}", exc_info=True)
            return {
                'results': [],
                'citations': [],
                'query': query,
                'error': str(e),
                'retrieval_time_ms': 0
            }

    def _build_debug_trace(
        self,
        query: str,
        skills: Optional[List[str]],
        category_filter: Optional[List[str]],
        document_id: Optional[int],
        bm25_results: List[Tuple[str, int, str, float, Dict]],
        vector_results: List[Tuple[str, int, str, float, Dict]],
        fused_results: List["SearchResult"],
        config: RetrievalConfig,
        top_k: int,
        retrieval_time_ms: int
    ) -> Dict[str, Any]:
        """Build a compact retrieval trace for debugging."""
        def _truncate(text: str, limit: int = 220) -> str:
            if not text:
                return ""
            return text if len(text) <= limit else text[:limit] + "..."

        def _pack_tuple(item: Tuple[str, int, str, float, Dict]) -> Dict[str, Any]:
            chunk_id, doc_id, content, score, meta = item
            meta = meta or {}
            return {
                "chunk_id": chunk_id,
                "document_id": doc_id,
                "score": score,
                "title": meta.get("title"),
                "page": meta.get("page"),
                "timestamp_start": meta.get("timestamp_start"),
                "timestamp_end": meta.get("timestamp_end"),
                "source_type": meta.get("source_type"),
                "snippet": _truncate(content)
            }

        return {
            "query": query,
            "skills": skills or [],
            "category_filter": category_filter or [],
            "document_id": document_id,
            "config": {
                "bm25_weight": config.bm25_weight,
                "vector_weight": config.vector_weight,
                "rrf_k": config.rrf_k,
                "top_k": top_k
            },
            "timing": {
                "retrieval_time_ms": retrieval_time_ms
            },
            "bm25_top": [_pack_tuple(x) for x in bm25_results[: top_k]],
            "vector_top": [_pack_tuple(x) for x in vector_results[: top_k]],
            "fused_top": [
                {
                    "chunk_id": r.chunk_id,
                    "document_id": r.document_id,
                    "score": r.score,
                    "bm25_score": r.bm25_score,
                    "vector_score": r.vector_score,
                    "rank": r.rank,
                    "title": (r.metadata or {}).get("title"),
                    "page": (r.metadata or {}).get("page"),
                    "timestamp_start": (r.metadata or {}).get("timestamp_start"),
                    "timestamp_end": (r.metadata or {}).get("timestamp_end"),
                    "source_type": (r.metadata or {}).get("source_type"),
                    "snippet": _truncate(r.content)
                }
                for r in fused_results[: top_k]
            ]
        }
    
    async def _bm25_search(
        self,
        query: str,
        limit: int,
        category_filter: Optional[List[str]] = None,
        organization_id: Optional[int] = None,
        visibility: Optional[str] = None,
        document_id: Optional[int] = None,
        category_doc_ids: Optional[List[int]] = None  # NEW: Category document IDs
    ) -> List[Tuple[str, int, str, float, Dict]]:
        """
        Perform BM25 full-text search via PostgreSQL.
        
        Args:
            query: Search query
            limit: Max results
            category_filter: Category filter
            category_doc_ids: Filter by category document IDs
            
        Returns:
            List of (chunk_id, document_id, content, score) tuples
        """
        logger.info(f"BM25 search called: query='{query[:50]}...', limit={limit}")
        try:
            # Build SQL query for full-text search
            # Uses ts_rank_cd for BM25-like scoring
            
            category_clause = ""
            if category_filter:
                categories_str = ", ".join(f"'{c}'" for c in category_filter)
                category_clause = f"AND kd.category IN ({categories_str})"
            
            # NEW: Category document IDs filter
            category_doc_clause = ""
            if category_doc_ids is not None and len(category_doc_ids) > 0:
                doc_ids_str = ", ".join(str(doc_id) for doc_id in category_doc_ids)
                category_doc_clause = f"AND kd.id IN ({doc_ids_str})"
            
            visibility_clause = ""
            if visibility:
                visibility_clause = "AND kd.visibility = :visibility"
            org_clause = ""
            if organization_id:
                org_clause = "AND (kd.organization_id = :org_id OR kd.visibility = 'public')"
            doc_clause = ""
            if document_id:
                doc_clause = "AND kd.id = :doc_id"
            
            sql = text(f"""
                SELECT 
                    dc.id::text as chunk_id,
                    dc.document_id,
                    dc.content as content,
                    1.0 as score,
                    kd.title,
                    kd.tags,
                    kd.doc_metadata as metadata,
                    kd.category
                FROM knowledge_chunks dc
                JOIN knowledge_documents kd ON dc.document_id = kd.id
                WHERE kd.status IN ('approved', 'indexed')
                AND (
                    dc.content ILIKE :pattern
                    OR kd.title ILIKE :pattern
                    OR CAST(kd.doc_metadata AS TEXT) ILIKE :pattern
                )
                {category_clause}
                {category_doc_clause}
                {visibility_clause}
                {org_clause}
                {doc_clause}
                ORDER BY score DESC
                LIMIT :limit
            """)
            
            try:
                from src.database.connection import get_async_session_context
                
                logger.info(f"🔍 BM25: Opening database session...")
                async with get_async_session_context() as session:
                    # Build search pattern
                    pattern = f"%{query}%"
                    
                    logger.info(f"🔍 BM25: Executing query with pattern={pattern[:50]}, limit={limit}")
                    
                    result = await session.execute(
                        sql, 
                        {
                            "pattern": pattern,
                            "limit": limit,
                            "visibility": visibility,
                            "org_id": organization_id,
                            "doc_id": document_id,
                        }
                    )
                    rows = result.fetchall()
                    logger.info(f"🔍 BM25: Query executed, found {len(rows)} rows")
                    if rows:
                        logger.info(f"BM25 search found {len(rows)} results")
                        return [
                        (
                            str(row.chunk_id),
                            row.document_id,
                            row.content,
                            float(row.score),
                            {
                                "title": row.title,
                                "tags": row.tags or [],
                                "topics": (row.metadata or {}).get("topics") if row.metadata else [],
                                "age_groups": (row.metadata or {}).get("age_groups") if row.metadata else [],
                                "category": row.category,
                                "is_form": (row.metadata or {}).get("is_form", False),
                                "form_type": (row.metadata or {}).get("form_type") if row.metadata else None,
                            },
                        )
                        for row in rows
                    ]

                    # Fallback for CJK or title-only matches: use ILIKE over chunk text or doc title.
                    logger.info("🔍 BM25: Primary search returned no results, trying fallback")
                    terms = self._extract_fallback_terms(query)
                    logger.info(f"🔍 BM25: Extracted {len(terms)} fallback terms: {terms[:5]}")
                    
                    # BUGFIX: For multilingual search, prioritize CJK terms over English terms
                    # If we have CJK terms, use only those (they're more specific for Chinese documents)
                    # Otherwise, use filtered English terms
                    cjk_terms = [t for t in terms if not t.isascii()]
                    if cjk_terms:
                        filtered_terms = cjk_terms
                        logger.info(f"🔍 BM25: Using {len(filtered_terms)} CJK terms: {filtered_terms[:5]}")
                    else:
                        # No CJK terms, filter English terms
                        filtered_terms = self._filter_strong_terms(terms)
                        logger.info(f"🔍 BM25: Using {len(filtered_terms)} filtered English terms: {filtered_terms[:5]}")
                    
                    if not filtered_terms:
                        logger.info("🔍 BM25: No strong fallback terms after filtering, returning empty")
                        return []
                    term_clauses = []
                    score_clauses = []
                    params = {
                        "limit": limit,
                        "visibility": visibility,
                        "org_id": organization_id,
                        "doc_id": document_id,
                    }
                    for idx, term in enumerate(filtered_terms[:8]):
                        key = f"pattern{idx}"
                        weight_key = f"weight{idx}"
                        params[key] = f"%{term}%"
                        params[weight_key] = max(1, min(len(term), 6))
                        clause = (
                            f"(dc.content ILIKE :{key} "
                            f"OR kd.title ILIKE :{key} "
                            f"OR CAST(kd.doc_metadata AS TEXT) ILIKE :{key} "
                            f"OR CAST(kd.tags AS TEXT) ILIKE :{key})"
                        )
                        term_clauses.append(clause)
                        score_clauses.append(f"(CASE WHEN {clause} THEN :{weight_key} ELSE 0 END)")
                    term_sql = " OR ".join(term_clauses)
                    score_sql = " + ".join(score_clauses) if score_clauses else "0"

                    fallback_sql = text(f"""
                        SELECT 
                            dc.id::text as chunk_id,
                            dc.document_id,
                            dc.content as content,
                            ({score_sql})::float as score,
                            kd.title,
                            kd.tags,
                            kd.doc_metadata as metadata,
                            kd.category
                        FROM knowledge_chunks dc
                        JOIN knowledge_documents kd ON dc.document_id = kd.id
                        WHERE kd.status IN ('approved', 'indexed')
                        {category_clause}
                        {category_doc_clause}
                        {visibility_clause}
                        {org_clause}
                        {doc_clause}
                        AND ({term_sql})
                        ORDER BY score DESC, dc.id DESC
                        LIMIT :limit
                    """)
                    
                    logger.info(f"🔍 BM25: Fallback SQL params: {params}")
                    logger.info(f"🔍 BM25: Fallback SQL query:\n{fallback_sql}")
                    fallback = await session.execute(
                        fallback_sql,
                        params
                    )
                    rows = fallback.fetchall()
                    logger.info(f"🔍 BM25: Fallback query executed, found {len(rows)} rows")
                    if not rows:
                        logger.debug("BM25 fallback search also returned no results")
                        return []
                    logger.info(f"BM25 fallback search found {len(rows)} results")
                    return [
                        (
                            str(row.chunk_id),
                            row.document_id,
                            row.content,
                            float(row.score),
                            {
                                "title": row.title,
                                "tags": row.tags or [],
                                "topics": (row.metadata or {}).get("topics") if row.metadata else [],
                                "age_groups": (row.metadata or {}).get("age_groups") if row.metadata else [],
                                "category": row.category,
                                "is_form": (row.metadata or {}).get("is_form", False),
                                "form_type": (row.metadata or {}).get("form_type") if row.metadata else None,
                            },
                        )
                        for row in rows
                    ]
            except Exception as db_error:
                logger.error(f"BM25 database query failed: {db_error}", exc_info=True)
                return []
            
            return []
            
        except Exception as e:
            logger.error(f"BM25 search failed: {e}", exc_info=True)
            return []
    
    async def _vector_search(
        self,
        query: str,
        limit: int,
        category_filter: Optional[List[str]] = None,
        organization_id: Optional[int] = None,
        visibility: Optional[str] = None,
        document_id: Optional[int] = None,
        category_doc_ids: Optional[List[int]] = None  # NEW: Category document IDs
    ) -> List[Tuple[str, int, str, float]]:
        """
        Perform vector similarity search via ChromaDB.
        
        Args:
            query: Search query
            limit: Max results
            category_filter: Category filter
            category_doc_ids: Filter by category document IDs
            
        Returns:
            List of (chunk_id, document_id, content, score) tuples
        """
        try:
            if self.vector_store is None:
                self.vector_store = get_vector_store()

            # Build metadata filter
            where_filter = None
            filters = {}
            if category_filter:
                filters["category"] = {"$in": category_filter}
            
            # NEW: Category document IDs filter
            if category_doc_ids is not None and len(category_doc_ids) > 0:
                filters["document_id"] = {"$in": category_doc_ids}
            
            # BUGFIX: Only add org/visibility filters if they have values
            # Forms don't have these fields, so we shouldn't filter by them
            # if organization_id:
            #     filters["organization_id"] = organization_id
            # if visibility:
            #     filters["visibility"] = visibility
            
            if document_id:
                filters["document_id"] = document_id
            where_filter = filters or None
            
            # Generate query embedding using our embedding service
            if self.embedding_service is None:
                from src.services.embedding_service import get_embedding_service
                self.embedding_service = get_embedding_service()
            
            query_embeddings = await self.embedding_service.embed_batch([query])
            query_embedding = query_embeddings[0]
            
            # Search vector store with pre-computed embeddings
            results = self.vector_store.search_with_embeddings(
                query_embeddings=query_embedding,
                n_results=limit,
                where=where_filter
            )
            
            # Convert distances to scores (1 - distance for cosine)
            search_results = []
            for i, (doc_id, doc, meta, dist) in enumerate(zip(
                results.get('ids', []),
                results.get('documents', []),
                results.get('metadatas', []),
                results.get('distances', [])
            )):
                # Convert distance to similarity score
                score = 1 - dist if dist < 1 else 0
                document_id = meta.get('document_id', 0) if meta else 0
                
                search_results.append((
                    str(doc_id),
                    int(document_id),
                    doc,
                    float(score),
                    meta or {}
                ))
            
            return search_results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    async def _form_only_search(
        self,
        query: str,
        top_k: int = 5,
        organization_id: Optional[int] = None,
        visibility: Optional[str] = None
    ) -> List[Tuple[str, int, str, float, Dict]]:
        """
        Search for form documents only, bypassing BM25 text-length bias.

        This method queries the knowledge_documents table directly with filter
        doc_metadata->>'is_form' = 'true' to find form documents, matching against
        document title and metadata fields using ILIKE for fuzzy matching.

        This bypasses the BM25 content scoring which favors text-rich documents,
        ensuring form documents (which have minimal text) can be found when users
        explicitly request forms.

        Args:
            query: Search query text
            top_k: Maximum number of results to return
            organization_id: Filter by organization ID (for multi-tenancy)
            visibility: Filter by visibility level (public/org/private)

        Returns:
            List of (chunk_id, document_id, content, score, metadata) tuples

        Security:
            - VALIDATION: Uses parameterized queries to prevent SQL injection
            - SECURITY: Organization isolation enforced via organization_id filter
            - PRIVACY: Logs document IDs only, no content or PII

        Bug Context:
            - Bug_Condition: Form documents excluded from top results due to BM25 bias
            - Expected_Behavior: Form documents appear in top 3 when form keywords detected
            - Preservation: Non-form queries unaffected (this method only called for form queries)
        """
        # PRIVACY: Log query length only, not content
        logger.info(f"Form-only search called: query_length={len(query)}, top_k={top_k}")

        try:
            # VALIDATION: Extract query terms safely (no SQL injection)
            query_terms = self._extract_fallback_terms(query)

            if not query_terms:
                logger.info("Form-only search: No valid query terms extracted")
                return []

            # PRIVACY: Log term count only, not actual terms
            logger.info(f"Form-only search: Extracted {len(query_terms)} query terms")

            # Build SQL query to find form documents
            # SECURITY: Organization isolation via WHERE clause
            visibility_clause = ""
            if visibility:
                visibility_clause = "AND kd.visibility = :visibility"

            org_clause = ""
            if organization_id:
                org_clause = "AND (kd.organization_id = :org_id OR kd.visibility = 'public')"

            # Build ILIKE clauses for each query term
            # Match against title, tags, and metadata fields
            term_clauses = []
            score_clauses = []
            params = {
                "top_k": top_k,
                "visibility": visibility,
                "org_id": organization_id,
            }

            # VALIDATION: Use parameterized queries for each term
            for idx, term in enumerate(query_terms[:8]):  # Limit to 8 terms for performance
                key = f"pattern{idx}"
                weight_key = f"weight{idx}"
                params[key] = f"%{term}%"
                # Weight longer terms higher (more specific)
                params[weight_key] = max(1, min(len(term), 6))

                # Match against title, tags, and metadata
                clause = (
                    f"(kd.title ILIKE :{key} "
                    f"OR CAST(kd.tags AS TEXT) ILIKE :{key} "
                    f"OR CAST(kd.doc_metadata AS TEXT) ILIKE :{key})"
                )
                term_clauses.append(clause)
                score_clauses.append(f"(CASE WHEN {clause} THEN :{weight_key} ELSE 0 END)")

            if not term_clauses:
                logger.info("Form-only search: No valid term clauses built")
                return []

            term_sql = " OR ".join(term_clauses)
            score_sql = " + ".join(score_clauses)

            # SQL: Query form documents with is_form=true filter
            sql = text(f"""
                SELECT
                    dc.id::text as chunk_id,
                    dc.document_id,
                    dc.content as content,
                    ({score_sql})::float as score,
                    kd.title,
                    kd.tags,
                    kd.doc_metadata as metadata,
                    kd.category
                FROM knowledge_chunks dc
                JOIN knowledge_documents kd ON dc.document_id = kd.id
                WHERE kd.status IN ('approved', 'indexed')
                AND kd.doc_metadata->>'is_form' = 'true'
                AND ({term_sql})
                {visibility_clause}
                {org_clause}
                ORDER BY score DESC, dc.id DESC
                LIMIT :top_k
            """)

            # Execute query with async database session
            from src.database.connection import get_async_session_context

            async with get_async_session_context() as session:
                result = await session.execute(sql, params)
                rows = result.fetchall()

                # PRIVACY: Log count only, not document details
                logger.info(f"Form-only search found {len(rows)} form documents")

                if not rows:
                    return []

                # Build result tuples
                results = []
                for row in rows:
                    chunk_id = str(row.chunk_id)
                    document_id = row.document_id
                    content = row.content
                    score = float(row.score)

                    # Extract metadata
                    metadata = {
                        "title": row.title,
                        "tags": row.tags or [],
                        "topics": (row.metadata or {}).get("topics", []) if row.metadata else [],
                        "age_groups": (row.metadata or {}).get("age_groups", []) if row.metadata else [],
                        "category": row.category,
                        "is_form": (row.metadata or {}).get("is_form", False),
                        "form_type": (row.metadata or {}).get("form_type") if row.metadata else None,
                    }

                    results.append((chunk_id, document_id, content, score, metadata))

                    # PRIVACY: Log document ID only, no content
                    logger.debug(f"Form-only search result: doc_id={document_id}, score={score:.2f}")

                return results

        except Exception as e:
            # PRIVACY: Log error without exposing query content
            logger.error(f"Form-only search failed: {type(e).__name__}", exc_info=True)
            return []

    
    def _rrf_fusion(
        self,
        bm25_results: List[Tuple[str, int, str, float]],
        vector_results: List[Tuple[str, int, str, float, Dict]],
        bm25_weight: float = 0.3,
        vector_weight: float = 0.7,
        rrf_k: int = 60,
        query_terms: Optional[List[str]] = None,
        has_form_keywords: bool = False,  # BUGFIX: Form keyword detection for smart boosting
        form_only_results: Optional[List[Tuple[str, int, str, float, Dict]]] = None  # BUGFIX: Form-only search results
    ) -> List[SearchResult]:
        """
        Combine results using Reciprocal Rank Fusion.
        
        RRF formula: score = sum(1 / (k + rank))
        
        Args:
            bm25_results: Results from BM25 search
            vector_results: Results from vector search
            bm25_weight: Weight for BM25 component
            vector_weight: Weight for vector component
            rrf_k: RRF constant (higher = more emphasis on top results)
            has_form_keywords: Whether query contains form-related keywords
            form_only_results: Results from form-only search (when form keywords detected)
            
        Returns:
            Combined and sorted SearchResult list
        """
        # Build lookup dictionaries
        bm25_lookup = {
            chunk_id: (doc_id, content, score, rank + 1, meta)
            for rank, (chunk_id, doc_id, content, score, meta)
            in enumerate(bm25_results)
        }
        
        vector_lookup = {}
        for rank, (chunk_id, doc_id, content, score, meta) in enumerate(vector_results):
            vector_lookup[chunk_id] = (doc_id, content, score, rank + 1, meta)
        
        # BUGFIX: Build form-only lookup dictionary
        # Form-only results get priority ranking to ensure they appear in top results
        form_only_lookup = {}
        if form_only_results:
            for rank, (chunk_id, doc_id, content, score, meta) in enumerate(form_only_results):
                form_only_lookup[chunk_id] = (doc_id, content, score, rank + 1, meta)
            logger.info(f"📋 Form-only fusion: Processing {len(form_only_results)} form documents")
        
        # Get all unique chunk IDs (including form-only results)
        all_chunks = set(bm25_lookup.keys()) | set(vector_lookup.keys()) | set(form_only_lookup.keys())
        
        # Calculate RRF scores
        combined_results = []
        for chunk_id in all_chunks:
            bm25_data = bm25_lookup.get(chunk_id)
            vector_data = vector_lookup.get(chunk_id)
            form_only_data = form_only_lookup.get(chunk_id)
            
            # RRF calculation
            bm25_rrf = 0
            vector_rrf = 0
            form_only_rrf = 0
            bm25_score = 0
            vector_score = 0
            form_only_score = 0
            
            if bm25_data:
                doc_id, content, bm25_score, bm25_rank, bm25_meta = bm25_data
                bm25_rrf = 1.0 / (rrf_k + bm25_rank)
            else:
                bm25_meta = {}
            
            if vector_data:
                doc_id, content, vector_score, vector_rank, meta = vector_data
                vector_rrf = 1.0 / (rrf_k + vector_rank)
            else:
                meta = {}
            
            # BUGFIX: Calculate form-only RRF score with high priority
            # Form-only results get configurable boost weight to ensure they rank in top 3
            if form_only_data:
                doc_id, content, form_only_score, form_only_rank, form_meta = form_only_data
                form_only_rrf = 1.0 / (rrf_k + form_only_rank)
                # Apply configurable boost to form-only RRF score
                form_only_rrf *= self.config.form_only_boost_multiplier
                logger.debug(
                    f"📋 Form-only RRF: doc_id={doc_id}, rank={form_only_rank}, "
                    f"rrf={form_only_rrf:.4f}, multiplier={self.config.form_only_boost_multiplier}x"
                )
                # Use form metadata if available
                if not meta:
                    meta = form_meta
            
            # Weighted combination (including form-only results)
            combined_score = (
                bm25_weight * bm25_rrf + 
                vector_weight * vector_rrf +
                form_only_rrf  # Form-only contribution (already weighted)
            )
            
            # Get document info (prefer vector data, then form-only, then BM25)
            if vector_data:
                doc_id, content = vector_data[0], vector_data[1]
            elif form_only_data:
                doc_id, content = form_only_data[0], form_only_data[1]
            else:
                doc_id, content = bm25_data[0], bm25_data[1]
            
            meta_for_scoring = meta or bm25_meta

            # Apply small boost for summary chunks
            if meta_for_scoring.get("source_type") == "summary":
                combined_score += 0.05

            # Soft boost for direct metadata overlap (no preset mapping)
            if query_terms:
                meta_terms = []
                meta_terms.extend([str(t) for t in (meta_for_scoring.get("tags") or [])])
                meta_terms.extend([str(t) for t in (meta_for_scoring.get("topics") or [])])
                meta_terms.extend([str(t) for t in (meta_for_scoring.get("topics_all") or [])])
                meta_terms.extend([str(t) for t in (meta_for_scoring.get("topics_en") or [])])
                meta_terms.extend([str(t) for t in (meta_for_scoring.get("topics_zh") or [])])
                meta_terms.extend([str(t) for t in (meta_for_scoring.get("age_groups") or [])])
                meta_terms = [t for t in meta_terms if t and not self._is_garbled_term(t)]
                if meta_terms:
                    matches = 0
                    for term in query_terms:
                        term_lower = term.lower()
                        for mt in meta_terms:
                            mt_lower = mt.lower()
                            if term_lower in mt_lower or mt_lower in term_lower:
                                matches += 1
                                break
                        if matches >= 5:
                            break
                    if matches:
                        combined_score += min(0.08, 0.02 * matches)
            
            # BUGFIX: Smart form boosting (hybrid approach)
            # Only boost forms when user explicitly asks for forms (has_form_keywords=True)
            # This ensures forms rank higher when requested, but don't pollute other queries
            # Configurable boost multiplier for future tuning
            if has_form_keywords and meta_for_scoring.get("is_form"):
                form_boost_multiplier = 2.5  # Configurable: 2.5x boost for forms when form keywords detected
                original_score = combined_score
                combined_score *= form_boost_multiplier
                logger.debug(
                    f"📋 Form boost applied: doc_id={doc_id}, "
                    f"original_score={original_score:.4f}, "
                    f"boosted_score={combined_score:.4f}, "
                    f"multiplier={form_boost_multiplier}x"
                )

            combined_results.append(SearchResult(
                chunk_id=chunk_id,
                document_id=doc_id,
                content=content,
                score=combined_score,
                bm25_score=bm25_score,
                vector_score=vector_score,
                rank=0,  # Will be set after sorting
                metadata=meta or bm25_meta
            ))
        
        # Sort by combined score
        combined_results.sort(key=lambda x: x.score, reverse=True)
        
        # BUGFIX: Ensure at least one form appears in top 3 positions if forms were found
        # This guarantees form documents are visible to users when they explicitly request forms
        if form_only_results and len(combined_results) >= 3:
            # Check if any form is already in top 3
            top_3_has_form = any(
                result.metadata.get("is_form") for result in combined_results[:3]
            )
            
            if not top_3_has_form:
                # Find the highest-ranked form document outside top 3
                form_result = None
                form_index = None
                for i, result in enumerate(combined_results[3:], start=3):
                    if result.metadata.get("is_form"):
                        form_result = result
                        form_index = i
                        break
                
                # Promote form to position 3 (index 2) if found
                if form_result is not None:
                    logger.info(
                        f"📋 Form promotion: Moving form doc_id={form_result.document_id} "
                        f"from position {form_index + 1} to position 3 to ensure visibility"
                    )
                    # Remove form from current position and insert at position 3
                    combined_results.pop(form_index)
                    combined_results.insert(2, form_result)
        
        # Assign final ranks
        for i, result in enumerate(combined_results):
            result.rank = i + 1
        
        # BUGFIX: Log final positions of all form documents for debugging
        if form_only_results:
            form_positions = [
                (i + 1, result.document_id) 
                for i, result in enumerate(combined_results) 
                if result.metadata.get("is_form")
            ]
            if form_positions:
                positions_str = ", ".join([f"doc_id={doc_id} at position {pos}" for pos, doc_id in form_positions])
                logger.info(f"📋 Final form positions: {positions_str}")
            else:
                logger.warning("📋 No form documents found in final results despite form-only search returning results")
        
        return combined_results
    
    def _skills_to_categories(self, skills: List[str]) -> List[str]:
        """
        Map skill names to document categories.
        
        Args:
            skills: List of active skill names
            
        Returns:
            List of relevant document categories
        """
        skill_category_map = {
            'mental_health': [
                'psychoeducation', 'therapy', 'coping_strategies',
                'child_mental_health', 'adolescent_mental_health'
            ],
            'physical_health': [
                'medication', 'hk_facilities', 'professional_guidelines'
            ],
            'safety_crisis': [
                'crisis_protocol', 'professional_guidelines'
            ],
            'wellness_coaching': [
                'coping_strategies', 'psychoeducation', 'parent_guide'
            ],
            'sleep_support': [
                'coping_strategies', 'psychoeducation'
            ],
            'social_support': [
                'family_support', 'parent_guide', 'psychoeducation'
            ]
        }
        
        categories = set()
        for skill in skills:
            if skill in skill_category_map:
                categories.update(skill_category_map[skill])
        
        # If no specific categories, include all
        if not categories:
            categories = {
                'psychoeducation', 'crisis_protocol', 'parent_guide',
                'hk_facilities', 'therapy', 'coping_strategies'
            }
        
        return list(categories)

    def _filter_strong_terms(self, terms: List[str]) -> List[str]:
        """Filter out weak/stop terms to reduce false grounding."""
        if not terms:
            return []
        stop_en = {
            "what", "how", "where", "when", "which", "who", "whom", "why",
            "is", "are", "was", "were", "the", "and", "or", "for", "from",
            "with", "about", "tell", "me", "please", "can", "could", "would",
            "should", "do", "does", "did", "a", "an", "to"
        }
        stop_cjk = {
            "請問", "唔該", "可以", "可唔可以", "麻煩", "點樣", "怎樣", "如何",
            "點", "咩", "乜嘢", "有冇", "有沒有", "關於", "有關", "請", "想問",
            "想知", "我想", "我想知", "我想問", "介紹", "有咩", "重點", "列出",
            "列三", "三點", "兩點", "幾點", "幾個", "幾多", "多少", "邊個",
            "邊一", "邊節", "邊段"
        }
        strong: List[str] = []
        for term in terms:
            if not term:
                continue
            if term.isascii():
                t = term.lower()
                if len(t) < 4:
                    continue
                if t.isnumeric() or t in stop_en:
                    continue
                strong.append(term)
            else:
                if len(term) < 2:
                    continue
                if term in stop_cjk:
                    continue
                strong.append(term)

        seen = set()
        out = []
        for t in strong:
            key = t.lower() if t.isascii() else t
            if key in seen:
                continue
            seen.add(key)
            out.append(t)
        return out

    def _is_garbled_term(self, value: str) -> bool:
        if not value:
            return False
        if "\ufffd" in value:
            return True
        latin1 = sum(1 for c in value if 0x00C0 <= ord(c) <= 0x00FF)
        cjk = sum(1 for c in value if 0x4E00 <= ord(c) <= 0x9FFF)
        ascii_letters = sum(1 for c in value if ("a" <= c.lower() <= "z"))
        mojibake_markers = ("Ã", "Â", "å", "ç", "œ", "™", "ï»¿")
        if any(m in value for m in mojibake_markers) and cjk == 0:
            return True
        if latin1 >= 2 and cjk == 0 and ascii_letters == 0:
            return True
        return False

    def _split_multi_topic_query(self, query: str) -> List[List[str]]:
        """Split query into topic groups for multi-topic coverage checks."""
        if not query:
            return []
        separators = r"\s+(?:and|&|with|plus|及|以及|和|與|跟|同|並)\s+|[、，,；;]|\/"
        parts = [p.strip() for p in re.split(separators, query) if p.strip()]
        # Avoid over-splitting: keep at most 3 meaningful parts
        if len(parts) <= 1:
            return []
        groups = []
        for part in parts[:3]:
            terms = self._extract_fallback_terms(part)
            strong = self._filter_strong_terms(terms)
            if strong:
                groups.append(strong[:6])
        return groups

    def _term_in_result(self, term: str, result: "SearchResult") -> bool:
        """Check if a term appears in content or metadata."""
        if not term or not result:
            return False
        term_lower = term.lower()
        content = result.content or ""
        hay = content.lower() if term.isascii() else content
        meta = result.metadata or {}
        meta_bits = []
        meta_bits.append(str(meta.get("title", "") or ""))
        meta_bits.extend([str(t) for t in (meta.get("tags") or [])])
        meta_bits.extend([str(t) for t in (meta.get("topics") or [])])
        meta_bits.extend([str(t) for t in (meta.get("topics_all") or [])])
        meta_bits.extend([str(t) for t in (meta.get("topics_en") or [])])
        meta_bits.extend([str(t) for t in (meta.get("topics_zh") or [])])
        meta_bits = [b for b in meta_bits if b and not self._is_garbled_term(b)]
        meta_hay = " ".join(meta_bits)
        meta_hay = meta_hay.lower() if term.isascii() else meta_hay
        return ((term_lower in hay) if term.isascii() else (term in hay)) or (
            (term_lower in meta_hay) if term.isascii() else (term in meta_hay)
        )

    def _extract_anchor_terms(self, query: str) -> List[str]:
        """Extract explicit chapter/section anchors to enforce grounding."""
        if not query:
            return []
        anchors: List[str] = []
        anchors.extend(re.findall(r"第[一二三四五六七八九十百零0-9]+章", query))
        anchors.extend(re.findall(r"第[一二三四五六七八九十百零0-9]+節", query))
        anchors.extend(re.findall(r"(?:chapter|section)\\s+\\d+", query, flags=re.I))
        anchors.extend(re.findall(r"(?:chapter|section)\\s+[ivx]+", query, flags=re.I))
        seen = set()
        out = []
        for term in anchors:
            if term in seen:
                continue
            seen.add(term)
            out.append(term)
        return out

    def _extract_fallback_terms(self, query: str) -> List[str]:
        """Extract simple tokens for ILIKE fallback (English words + CJK sequences)."""
        terms: List[str] = []
        terms.extend(re.findall(r"[A-Za-z0-9_]{2,}", query))
        cjk_sequences = re.findall(r"[\u4e00-\u9fff]{2,}", query)
        if cjk_sequences:
            polite_prefixes = [
                "我想知", "想知", "想了解", "請問", "唔該", "可以", "可唔可以", "麻煩",
                "我想", "想問", "想請教"
            ]
            for seq in cjk_sequences:
                cleaned = seq
                for prefix in polite_prefixes:
                    if cleaned.startswith(prefix) and len(cleaned) > len(prefix) + 1:
                        cleaned = cleaned[len(prefix):]
                        break
                if cleaned:
                    terms.append(cleaned)
                    # Add a few short n-grams for better CJK matching
                    max_terms = 6
                    if len(cleaned) >= 4:
                        for size in (2, 3):
                            for i in range(0, len(cleaned) - size + 1):
                                terms.append(cleaned[i:i + size])
                                if len(terms) >= 20:
                                    break
                            if len(terms) >= 20:
                                break
                else:
                    terms.append(seq)
        seen = set()
        deduped = []
        for term in terms:
            key = term.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(term)
        return deduped
    
    def _is_specific_form_request(self, query: str) -> bool:
        """
        Detect if query requests a specific single form vs. general query.
        
        This method distinguishes between:
        - Specific requests: "我需要綜援表格", "CSSA form", "給我樂悠咭申請表"
        - General queries: "有什麼表格？", "what forms are available?", "所有申請表"
        
        Args:
            query: User's search query
            
        Returns:
            bool: True if query requests a specific single form, False for general queries
            
        Security:
            - PRIVACY: No PII in logs, only boolean result
            
        Bug Context:
            - Bug_Condition: Detects when user requests ONE specific form
            - Expected_Behavior: Return True for specific requests, False for general queries
            - Preservation: General queries return False (no precision filtering applied)
        """
        if not query:
            return False
        
        query_lower = query.lower()
        
        # Check for plural/general indicators (Chinese)
        general_indicators_zh = [
            "有什麼", "有咩", "所有", "哪些", "多少", "幾個", "幾多",
            "什麼表格", "咩表格", "邊啲", "邊個", "列出", "全部"
        ]
        
        # Check for plural/general indicators (English)
        general_indicators_en = [
            "what", "all", "which", "how many", "list", "available",
            "what forms", "which forms", "any forms", "show me all"
        ]
        
        # If query contains plural/general indicators, it's a general query
        for indicator in general_indicators_zh + general_indicators_en:
            if indicator in query_lower:
                return False  # General query, not specific request
        
        # Check if query is too short/generic
        # For single-word queries: English <= 4 chars is too generic, CJK needs >= 3 chars
        query_stripped = query.strip()
        if ' ' not in query_stripped:  # Single word
            # Check if it's CJK (Chinese/Japanese/Korean)
            has_cjk = any('\u4e00' <= c <= '\u9fff' for c in query_stripped)
            if has_cjk:
                # CJK: Need 3+ characters to be specific (e.g., "表格" = 2 chars is generic, "綜援表格" = 4 chars is specific)
                if len(query_stripped) < 3:
                    return False  # Too short
            else:
                # English: <= 4 characters is too generic (e.g., "form" = 4 chars, generic)
                if len(query_stripped) <= 4:
                    return False  # Too generic
        
        # Check for form keywords using existing method
        has_form_keyword = self._detect_form_keywords(query)
        
        # If has form keyword and no general indicators, likely specific request
        # Examples: "綜援表格", "我需要CSSA form", "樂悠咭申請表"
        return has_form_keyword
    
    def _calculate_form_precision_score(self, query: str, result: SearchResult) -> float:
        """
        Calculate precision score for form result based on query-to-title similarity.
        
        Higher scores indicate better match to specific form request.
        
        Scoring factors:
        - Exact title match: +1.0
        - Substring match in title: +0.5 to +0.8 (based on coverage)
        - Form type alignment: +0.2
        - Query term coverage: +0.1 per term (max +0.5)
        
        Args:
            query: User's search query
            result: SearchResult to score
            
        Returns:
            float: Precision score (0.0 to 1.0)
            
        Security:
            - PRIVACY: No PII in logs, only scores and document IDs
            
        Bug Context:
            - Bug_Condition: Scores forms by relevance to specific request
            - Expected_Behavior: Higher scores for better matches
            - Preservation: Only called for specific form requests
        """
        score = 0.0
        query_lower = query.lower()
        title = result.metadata.get('title', '').lower()
        
        if not title:
            return 0.0
        
        # Extract key terms from query (remove common words)
        query_terms = self._extract_fallback_terms(query)
        query_terms = self._filter_strong_terms(query_terms)
        
        # Exact match: query appears in title or title appears in query
        # For CJK, also check if query characters appear in title (ignoring spaces)
        if query_lower in title or title in query_lower:
            score += 1.0
        elif query_terms:
            # Check if all query terms appear in title (more lenient for CJK)
            all_terms_found = all(term.lower() in title for term in query_terms if term)
            if all_terms_found and len(query_terms) >= 2:
                score += 0.9  # Almost as good as exact match
        
        # Substring matching: count how many query terms appear in title
        matched_terms = 0
        if query_terms:
            for term in query_terms:
                term_lower = term.lower()
                if term_lower in title:
                    matched_terms += 1
            
            # Calculate coverage (0.0 to 1.0)
            coverage = matched_terms / len(query_terms)
            # Add 0.5 to 0.8 based on coverage
            score += coverage * 0.8
        
        # Form type alignment: if query mentions specific form type
        form_type = result.metadata.get('form_type', '')
        if form_type and form_type.lower() in query_lower:
            score += 0.2
        
        # Query term coverage bonus: +0.1 per matched term (max +0.5)
        term_bonus = min(0.5, matched_terms * 0.1)
        score += term_bonus
        
        # Cap score at 1.0
        return min(score, 1.0)
    
    def _detect_form_keywords(self, query: str) -> bool:
        """
        Detect if query contains form-related keywords.
        
        This method checks for explicit form requests in both English and Chinese.
        Used for smart form boosting in the hybrid approach.
        
        Args:
            query: User's search query
            
        Returns:
            bool: True if form keywords detected, False otherwise
            
        Security:
            - PRIVACY: No PII in logs, only boolean result
        """
        query_lower = query.lower()
        
        # Form keywords in English
        form_keywords_en = [
            "form", "application", "registration", "申請表",
            "表格", "登記表", "報名表", "填表"
        ]
        
        # Check if any form keyword is in the query
        for keyword in form_keywords_en:
            if keyword in query_lower:
                return True
        
        return False
    
    def _build_citations(self, results: List[SearchResult]) -> List[Dict]:
        """
        Build citation information from search results.
        
        Args:
            results: Search results
            
        Returns:
            List of citation dictionaries
        """
        citations = []
        for result in results:
            citations.append({
                'chunk_id': result.chunk_id,
                'document_id': result.document_id,
                'excerpt': result.content[:200] + '...' if len(result.content) > 200 else result.content,
                'relevance_score': result.score,
                'source_type': result.metadata.get('source_type', result.metadata.get('category', 'unknown')),
                'page': result.metadata.get('page'),
                'timestamp_start': result.metadata.get('timestamp_start'),
                'timestamp_end': result.metadata.get('timestamp_end'),
                'title': result.metadata.get('title'),
                'organization_id': result.metadata.get('organization_id'),
            })
        
        return citations
    
    async def get_document_by_id(self, document_id: int) -> Optional[Dict]:
        """
        Get full document by ID.
        
        Args:
            document_id: Document ID
            
        Returns:
            Document dictionary or None
        """
        try:
            sql = text("""
                SELECT 
                    id, title, content, category, subcategory,
                    source, author, language, tags, metadata
                FROM knowledge_documents
                WHERE id = :doc_id
            """)
            
            async for session in get_async_db():
                result = await session.execute(sql, {"doc_id": document_id})
                row = result.fetchone()
                
                if row:
                    return {
                        'id': row.id,
                        'title': row.title,
                        'content': row.content,
                        'category': row.category,
                        'subcategory': row.subcategory,
                        'source': row.source,
                        'author': row.author,
                        'language': row.language,
                        'tags': row.tags,
                        'metadata': row.metadata
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get document: {e}")
            return None
    
    async def search_by_category(
        self,
        query: str,
        category: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Search within a specific category.
        
        Args:
            query: Search query
            category: Document category
            top_k: Number of results
            
        Returns:
            Search results
        """
        config = RetrievalConfig(
            category_filter=[category],
            top_k=top_k
        )
        
        return await self.hybrid_search(query, config_override=config)


# =========================================================================
# SINGLETON AND FACTORY
# =========================================================================

_retriever_instance: Optional[HybridRetriever] = None


def get_hybrid_retriever(
    config: Optional[RetrievalConfig] = None
) -> HybridRetriever:
    """
    Get or create hybrid retriever singleton.
    
    Args:
        config: Optional retrieval configuration
        
    Returns:
        HybridRetriever instance
    """
    global _retriever_instance
    
    if _retriever_instance is None:
        _retriever_instance = HybridRetriever(config=config)
    
    return _retriever_instance


def reset_hybrid_retriever() -> None:
    """Reset the singleton instance"""
    global _retriever_instance
    _retriever_instance = None

