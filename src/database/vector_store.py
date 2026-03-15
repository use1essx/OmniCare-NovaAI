"""
Vector Store Integration

Provides interface to vector database for semantic search and retrieval.
Supports ChromaDB for local development and easy migration to Pinecone for production.
"""

import os
import hashlib
from typing import List, Dict, Any, Optional

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("Warning: chromadb not installed. Run: pip install chromadb")

from src.core.logging import get_logger

logger = get_logger(__name__)


class VectorStore:
    """
    Vector store interface for semantic search.
    Uses ChromaDB by default, can be extended for Pinecone/Weaviate.
    """
    
    def __init__(
        self,
        collection_name: str = "healthcare_knowledge",
        persist_directory: str = "./data/vector_store",
        embedding_function: Optional[Any] = None
    ):
        """
        Initialize vector store.
        
        Args:
            collection_name: Name of the collection
            persist_directory: Directory to persist data
            embedding_function: Custom embedding function (optional)
        """
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        
        if not CHROMA_AVAILABLE:
            raise ImportError("chromadb is required. Install with: pip install chromadb")
        
        # Create persist directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        try:
            self.collection = self.client.get_collection(
                name=collection_name,
                embedding_function=embedding_function
            )
            logger.info(f"Loaded existing collection: {collection_name}")
        except Exception:
            self.collection = self.client.create_collection(
                name=collection_name,
                embedding_function=embedding_function,
                metadata={"description": "Healthcare AI knowledge base"}
            )
            logger.info(f"Created new collection: {collection_name}")
    
    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
        embeddings: Optional[List[List[float]]] = None
    ) -> List[str]:
        """
        Add documents to the vector store.
        
        Args:
            documents: List of text documents
            metadatas: List of metadata dicts for each document
            ids: Optional list of IDs (will be generated if not provided)
            embeddings: Optional pre-computed embeddings
            
        Returns:
            List of document IDs
        """
        if not documents:
            return []
        
        # Generate IDs if not provided
        if ids is None:
            ids = [self._generate_id(doc, meta) for doc, meta in zip(documents, metadatas)]
        
        try:
            if embeddings is not None:
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids,
                    embeddings=embeddings
                )
            else:
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
            
            logger.info(f"Added {len(documents)} documents to vector store")
            return ids
            
        except Exception as e:
            logger.error(f"Error adding documents to vector store: {e}")
            raise
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Search for similar documents.
        
        Args:
            query: Search query text
            n_results: Number of results to return
            where: Metadata filters
            where_document: Document content filters
            
        Returns:
            Dict with 'ids', 'documents', 'metadatas', 'distances'
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
                where_document=where_document
            )
            
            # Flatten results (query returns nested lists)
            return {
                'ids': results['ids'][0] if results['ids'] else [],
                'documents': results['documents'][0] if results['documents'] else [],
                'metadatas': results['metadatas'][0] if results['metadatas'] else [],
                'distances': results['distances'][0] if results['distances'] else []
            }
            
        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            raise
    
    def search_with_embeddings(
        self,
        query_embeddings: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Search using pre-computed embeddings.
        
        Args:
            query_embeddings: Query embedding vector
            n_results: Number of results to return
            where: Metadata filters
            
        Returns:
            Dict with search results
        """
        try:
            results = self.collection.query(
                query_embeddings=[query_embeddings],
                n_results=n_results,
                where=where
            )
            
            return {
                'ids': results['ids'][0] if results['ids'] else [],
                'documents': results['documents'][0] if results['documents'] else [],
                'metadatas': results['metadatas'][0] if results['metadatas'] else [],
                'distances': results['distances'][0] if results['distances'] else []
            }
            
        except Exception as e:
            logger.error(f"Error searching with embeddings: {e}")
            raise
    
    def get_by_ids(self, ids: List[str]) -> Dict[str, Any]:
        """
        Retrieve documents by their IDs.
        
        Args:
            ids: List of document IDs
            
        Returns:
            Dict with documents and metadata
        """
        try:
            results = self.collection.get(ids=ids)
            return results
        except Exception as e:
            logger.error(f"Error retrieving documents by IDs: {e}")
            raise
    
    def update_documents(
        self,
        ids: List[str],
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        embeddings: Optional[List[List[float]]] = None
    ) -> None:
        """
        Update existing documents.
        
        Args:
            ids: List of document IDs to update
            documents: Updated document texts
            metadatas: Updated metadata
            embeddings: Updated embeddings
        """
        try:
            self.collection.update(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings
            )
            logger.info(f"Updated {len(ids)} documents")
        except Exception as e:
            logger.error(f"Error updating documents: {e}")
            raise
    
    def delete_documents(self, ids: List[str]) -> None:
        """
        Delete documents by IDs.
        
        Args:
            ids: List of document IDs to delete
        """
        try:
            self.collection.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} documents")
        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            raise
    
    def delete_by_metadata(self, where: Dict[str, Any]) -> None:
        """
        Delete documents matching metadata filter.
        
        Args:
            where: Metadata filter
        """
        try:
            self.collection.delete(where=where)
            logger.info(f"Deleted documents matching filter: {where}")
        except Exception as e:
            logger.error(f"Error deleting documents by metadata: {e}")
            raise
    
    def count(self) -> int:
        """Get total number of documents in collection."""
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"Error counting documents: {e}")
            return 0
    
    def reset(self) -> None:
        """Reset the collection (delete all documents)."""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Healthcare AI knowledge base"}
            )
            logger.warning(f"Reset collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Error resetting collection: {e}")
            raise
    
    def _generate_id(self, document: str, metadata: Dict[str, Any]) -> str:
        """
        Generate a unique ID for a document.
        
        Args:
            document: Document text
            metadata: Document metadata
            
        Returns:
            Unique ID string
        """
        # Use document_id and chunk_index from metadata if available
        if 'document_id' in metadata and 'chunk_index' in metadata:
            return f"doc_{metadata['document_id']}_chunk_{metadata['chunk_index']}"
        
        # Otherwise, generate hash-based ID
        content = f"{document}_{metadata.get('document_id', '')}_{metadata.get('chunk_index', '')}"
        hash_obj = hashlib.md5(content.encode())
        return f"chunk_{hash_obj.hexdigest()}"
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics.
        
        Returns:
            Dict with collection stats
        """
        try:
            count = self.count()
            
            # Sample some documents to get metadata stats
            sample_size = min(100, count)
            if sample_size > 0:
                sample = self.collection.peek(limit=sample_size)
                
                # Count categories
                categories = {}
                languages = {}
                for meta in sample.get('metadatas', []):
                    cat = meta.get('category', 'unknown')
                    lang = meta.get('language', 'unknown')
                    categories[cat] = categories.get(cat, 0) + 1
                    languages[lang] = languages.get(lang, 0) + 1
                
                return {
                    'total_documents': count,
                    'categories': categories,
                    'languages': languages,
                    'collection_name': self.collection_name
                }
            
            return {
                'total_documents': count,
                'collection_name': self.collection_name
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {'error': str(e)}


# Singleton instance
_vector_store_instance = None


def get_vector_store(
    collection_name: str = "healthcare_knowledge",
    persist_directory: str = "./data/vector_store"
) -> VectorStore:
    """
    Get or create vector store singleton instance.
    
    Args:
        collection_name: Name of the collection
        persist_directory: Directory to persist data
        
    Returns:
        VectorStore instance
    """
    global _vector_store_instance
    
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore(
            collection_name=collection_name,
            persist_directory=persist_directory
        )
    
    return _vector_store_instance
