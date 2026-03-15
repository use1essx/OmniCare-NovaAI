"""
Citation Tracker for RAG System

Tracks document citations in AI responses for:
- Analytics and usage tracking
- Source attribution
- Quality improvement
- Audit trails
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ..database.connection import get_async_db

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """Represents a single citation in a response"""
    document_id: int
    chunk_id: str
    excerpt: str
    relevance_score: float
    context: Optional[str] = None
    category: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'document_id': self.document_id,
            'chunk_id': self.chunk_id,
            'excerpt': self.excerpt,
            'relevance_score': self.relevance_score,
            'context': self.context,
            'category': self.category,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class CitationTracker:
    """
    Tracks and stores citations from RAG responses.
    
    Features:
    - Store citations for audit trail
    - Track document usage analytics
    - Support feedback collection
    - Query citation history
    """
    
    def __init__(self):
        """Initialize citation tracker"""
        self._pending_citations: List[Dict] = []
    
    async def track_citation(
        self,
        session_id: str,
        document_id: int,
        chunk_id: str,
        citation_text: str,
        citation_context: str,
        relevance_score: float,
        message_id: Optional[int] = None,
        query_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Track a single citation.
        
        Args:
            session_id: Chat session ID
            document_id: Source document ID
            chunk_id: Source chunk ID  
            citation_text: The cited text
            citation_context: How it was used in response
            relevance_score: Relevance score
            message_id: Associated message ID (optional)
            query_id: Associated RAG query ID (optional)
            
        Returns:
            Citation ID if successful, None otherwise
        """
        try:
            sql = text("""
                INSERT INTO rag_citations (
                    session_id, message_id, query_id,
                    document_id, chunk_id,
                    citation_text, citation_context, relevance_score,
                    cited_at
                ) VALUES (
                    :session_id, :message_id, :query_id,
                    :document_id, :chunk_id,
                    :citation_text, :citation_context, :relevance_score,
                    NOW()
                )
                RETURNING id
            """)
            
            async for session in get_async_db():
                result = await session.execute(sql, {
                    'session_id': session_id,
                    'message_id': message_id,
                    'query_id': query_id,
                    'document_id': document_id,
                    'chunk_id': chunk_id,
                    'citation_text': citation_text[:500] if citation_text else None,
                    'citation_context': citation_context[:500] if citation_context else None,
                    'relevance_score': relevance_score
                })
                await session.commit()
                
                row = result.fetchone()
                citation_id = row[0] if row else None
                
                # Update document citation count
                await self._increment_document_citations(document_id)
                
                logger.debug(f"Tracked citation {citation_id} for document {document_id}")
                return citation_id
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to track citation: {e}")
            return None
    
    async def track_multiple_citations(
        self,
        session_id: str,
        citations: List[Citation],
        message_id: Optional[int] = None,
        query_id: Optional[int] = None
    ) -> List[int]:
        """
        Track multiple citations at once.
        
        Args:
            session_id: Chat session ID
            citations: List of Citation objects
            message_id: Associated message ID
            query_id: Associated query ID
            
        Returns:
            List of citation IDs
        """
        citation_ids = []
        
        for citation in citations:
            cid = await self.track_citation(
                session_id=session_id,
                document_id=citation.document_id,
                chunk_id=citation.chunk_id,
                citation_text=citation.excerpt,
                citation_context=citation.context or '',
                relevance_score=citation.relevance_score,
                message_id=message_id,
                query_id=query_id
            )
            if cid:
                citation_ids.append(cid)
        
        return citation_ids
    
    async def get_session_citations(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get all citations for a session.
        
        Args:
            session_id: Chat session ID
            limit: Max citations to return
            
        Returns:
            List of citation dictionaries
        """
        try:
            sql = text("""
                SELECT 
                    rc.id, rc.document_id, rc.chunk_id,
                    rc.citation_text, rc.citation_context,
                    rc.relevance_score, rc.cited_at,
                    kd.title as document_title,
                    kd.category as document_category
                FROM rag_citations rc
                LEFT JOIN knowledge_documents kd ON rc.document_id = kd.id
                WHERE rc.session_id = :session_id
                ORDER BY rc.cited_at DESC
                LIMIT :limit
            """)
            
            async for session in get_async_db():
                result = await session.execute(sql, {
                    'session_id': session_id,
                    'limit': limit
                })
                rows = result.fetchall()
                
                return [
                    {
                        'id': row.id,
                        'document_id': row.document_id,
                        'chunk_id': row.chunk_id,
                        'citation_text': row.citation_text,
                        'citation_context': row.citation_context,
                        'relevance_score': row.relevance_score,
                        'cited_at': row.cited_at.isoformat() if row.cited_at else None,
                        'document_title': row.document_title,
                        'document_category': row.document_category
                    }
                    for row in rows
                ]
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get session citations: {e}")
            return []
    
    async def get_document_usage(
        self,
        document_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get usage statistics for a document.
        
        Args:
            document_id: Document ID
            days: Number of days to look back
            
        Returns:
            Usage statistics dictionary
        """
        try:
            sql = text("""
                SELECT 
                    COUNT(*) as total_citations,
                    COUNT(DISTINCT session_id) as unique_sessions,
                    AVG(relevance_score) as avg_relevance,
                    MIN(cited_at) as first_cited,
                    MAX(cited_at) as last_cited
                FROM rag_citations
                WHERE document_id = :document_id
                AND cited_at >= NOW() - INTERVAL ':days days'
            """.replace(':days', str(days)))
            
            async for session in get_async_db():
                result = await session.execute(sql, {
                    'document_id': document_id
                })
                row = result.fetchone()
                
                if row:
                    return {
                        'document_id': document_id,
                        'total_citations': row.total_citations or 0,
                        'unique_sessions': row.unique_sessions or 0,
                        'avg_relevance': float(row.avg_relevance) if row.avg_relevance else 0,
                        'first_cited': row.first_cited.isoformat() if row.first_cited else None,
                        'last_cited': row.last_cited.isoformat() if row.last_cited else None,
                        'period_days': days
                    }
            
            return {'document_id': document_id, 'total_citations': 0}
            
        except Exception as e:
            logger.error(f"Failed to get document usage: {e}")
            return {'document_id': document_id, 'error': str(e)}
    
    async def get_top_cited_documents(
        self,
        limit: int = 10,
        days: int = 30,
        category: Optional[str] = None
    ) -> List[Dict]:
        """
        Get most frequently cited documents.
        
        Args:
            limit: Max documents to return
            days: Number of days to look back
            category: Filter by category (optional)
            
        Returns:
            List of document usage dictionaries
        """
        try:
            category_clause = ""
            if category:
                category_clause = "AND kd.category = :category"
            
            sql = text(f"""
                SELECT 
                    kd.id, kd.title, kd.category,
                    COUNT(rc.id) as citation_count,
                    COUNT(DISTINCT rc.session_id) as unique_sessions,
                    AVG(rc.relevance_score) as avg_relevance
                FROM knowledge_documents kd
                JOIN rag_citations rc ON kd.id = rc.document_id
                WHERE rc.cited_at >= NOW() - INTERVAL '{days} days'
                {category_clause}
                GROUP BY kd.id, kd.title, kd.category
                ORDER BY citation_count DESC
                LIMIT :limit
            """)
            
            params = {'limit': limit}
            if category:
                params['category'] = category
            
            async for session in get_async_db():
                result = await session.execute(sql, params)
                rows = result.fetchall()
                
                return [
                    {
                        'document_id': row.id,
                        'title': row.title,
                        'category': row.category,
                        'citation_count': row.citation_count,
                        'unique_sessions': row.unique_sessions,
                        'avg_relevance': float(row.avg_relevance) if row.avg_relevance else 0
                    }
                    for row in rows
                ]
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get top cited documents: {e}")
            return []
    
    async def record_citation_feedback(
        self,
        citation_id: int,
        was_helpful: bool,
        feedback_text: Optional[str] = None
    ) -> bool:
        """
        Record user feedback for a citation.
        
        Args:
            citation_id: Citation ID
            was_helpful: Whether citation was helpful
            feedback_text: Optional feedback text
            
        Returns:
            True if successful
        """
        try:
            sql = text("""
                UPDATE rag_citations
                SET 
                    was_helpful = :was_helpful,
                    user_feedback = :feedback_text
                WHERE id = :citation_id
            """)
            
            async for session in get_async_db():
                await session.execute(sql, {
                    'citation_id': citation_id,
                    'was_helpful': was_helpful,
                    'feedback_text': feedback_text
                })
                await session.commit()
                
                logger.debug(f"Recorded feedback for citation {citation_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to record citation feedback: {e}")
            return False
    
    async def _increment_document_citations(self, document_id: int) -> None:
        """
        Increment citation count for a document.
        
        Args:
            document_id: Document ID
        """
        try:
            sql = text("""
                UPDATE knowledge_documents
                SET 
                    citation_count = citation_count + 1,
                    last_accessed_at = NOW()
                WHERE id = :document_id
            """)
            
            async for session in get_async_db():
                await session.execute(sql, {'document_id': document_id})
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to increment document citations: {e}")
    
    async def log_rag_query(
        self,
        query_text: str,
        session_id: str,
        agent_type: Optional[str] = None,
        skill_used: Optional[str] = None,
        retrieved_doc_ids: Optional[List[int]] = None,
        retrieved_chunk_ids: Optional[List[str]] = None,
        top_scores: Optional[List[float]] = None,
        retrieval_time_ms: Optional[int] = None
    ) -> Optional[int]:
        """
        Log a RAG query for analytics.
        
        Args:
            query_text: The search query
            session_id: Chat session ID
            agent_type: Type of agent making query
            skill_used: Skill that triggered query
            retrieved_doc_ids: IDs of retrieved documents
            retrieved_chunk_ids: IDs of retrieved chunks
            top_scores: Scores of top results
            retrieval_time_ms: Query time in milliseconds
            
        Returns:
            Query ID if successful
        """
        try:
            sql = text("""
                INSERT INTO rag_queries (
                    query_text, session_id, agent_type, skill_used,
                    retrieved_doc_ids, retrieved_chunk_ids, top_scores,
                    retrieval_time_ms, total_results, queried_at
                ) VALUES (
                    :query_text, :session_id, :agent_type, :skill_used,
                    :retrieved_doc_ids, :retrieved_chunk_ids, :top_scores,
                    :retrieval_time_ms, :total_results, NOW()
                )
                RETURNING id
            """)
            
            async for session in get_async_db():
                result = await session.execute(sql, {
                    'query_text': query_text[:1000] if query_text else None,
                    'session_id': session_id,
                    'agent_type': agent_type,
                    'skill_used': skill_used,
                    'retrieved_doc_ids': retrieved_doc_ids,
                    'retrieved_chunk_ids': retrieved_chunk_ids,
                    'top_scores': top_scores,
                    'retrieval_time_ms': retrieval_time_ms,
                    'total_results': len(retrieved_doc_ids) if retrieved_doc_ids else 0
                })
                await session.commit()
                
                row = result.fetchone()
                return row[0] if row else None
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to log RAG query: {e}")
            return None


# =========================================================================
# SINGLETON
# =========================================================================

_tracker_instance: Optional[CitationTracker] = None


def get_citation_tracker() -> CitationTracker:
    """Get or create citation tracker singleton"""
    global _tracker_instance
    
    if _tracker_instance is None:
        _tracker_instance = CitationTracker()
    
    return _tracker_instance

