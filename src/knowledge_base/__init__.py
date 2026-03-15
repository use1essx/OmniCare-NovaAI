"""
Knowledge Base Module for Healthcare AI

Provides hybrid search (BM25 + Vector + RRF) for RAG retrieval,
citation tracking, document ingestion, category management, and tree navigation.

Documents are added by users through the admin interface or API.
"""

from .hybrid_retriever import (
    HybridRetriever,
    SearchResult,
    RetrievalConfig,
    get_hybrid_retriever,
)
from .citation_tracker import (
    CitationTracker,
    Citation,
)
from .document_ingestion import (
    DocumentIngestionService,
    IngestedDocument,
    get_ingestion_service,
)
from .category_service import (
    CategoryService,
    get_category_service,
)

__all__ = [
    # Retrieval
    'HybridRetriever',
    'SearchResult',
    'RetrievalConfig',
    'get_hybrid_retriever',
    
    # Citations
    'CitationTracker',
    'Citation',
    
    # Document Ingestion
    'DocumentIngestionService',
    'IngestedDocument',
    'get_ingestion_service',
    
    # Category Management
    'CategoryService',
    'get_category_service',
]

