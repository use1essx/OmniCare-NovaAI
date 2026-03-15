"""
Embedding Service

Generates embeddings for text using AWS Titan Embeddings.
Uses AWS Bedrock for embedding generation (Nova doesn't support embeddings).
"""

import os
import json
from typing import List, Optional

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None
    ClientError = Exception

from src.core.logging import get_logger
from src.core.config import settings

logger = get_logger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using AWS Titan"""
    
    def __init__(
        self,
        model_name: str = "amazon.titan-embed-text-v1",
        region: str = "us-east-1"
    ):
        """
        Initialize embedding service with AWS Titan.
        
        Args:
            model_name: AWS Titan embedding model ID
            region: AWS region
        """
        self.model_name = model_name
        self.region = region
        self.client = None
        
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 package not installed. Run: pip install boto3")
        
        try:
            # Initialize AWS Bedrock Runtime client for embeddings
            self.client = boto3.client(
                'bedrock-runtime',
                region_name=region,
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
            logger.info(f"Using AWS Titan Embeddings (model: {model_name})")
        except Exception as e:
            logger.error(f"Failed to initialize AWS Bedrock client: {e}")
            raise
    
    async def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text using AWS Titan.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        embeddings = await self._embed_titan([text])
        return embeddings[0]
    
    async def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts using AWS Titan.
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for API calls (Titan processes one at a time)
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Filter out empty texts
        valid_texts = [t for t in texts if t and t.strip()]
        if len(valid_texts) != len(texts):
            logger.warning(f"Filtered out {len(texts) - len(valid_texts)} empty texts")
        
        if not valid_texts:
            return []
        
        # Process in batches
        all_embeddings = []
        
        for i in range(0, len(valid_texts), batch_size):
            batch = valid_texts[i:i + batch_size]
            embeddings = await self._embed_titan(batch)
            all_embeddings.extend(embeddings)
        
        return all_embeddings
    
    async def _embed_titan(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using AWS Titan Embeddings.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not self.client:
            raise RuntimeError("AWS Bedrock client not initialized. Check AWS credentials.")
        
        embeddings = []
        
        for text in texts:
            try:
                # Prepare request body for Titan
                body = json.dumps({
                    "inputText": text
                })
                
                # Call Bedrock Runtime API
                response = self.client.invoke_model(
                    modelId=self.model_name,
                    body=body,
                    contentType="application/json",
                    accept="application/json"
                )
                
                # Parse response
                response_body = json.loads(response['body'].read())
                embedding = response_body.get('embedding', [])
                
                if not embedding:
                    raise ValueError(f"No embedding returned for text: {text[:50]}...")
                
                embeddings.append(embedding)
                
            except ClientError as e:
                logger.error(f"AWS Bedrock API error: {e}")
                raise
            except Exception as e:
                logger.error(f"Error generating Titan embedding: {e}")
                raise
        
        logger.info(f"Generated {len(embeddings)} embeddings using AWS Titan")
        return embeddings
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this model."""
        if self.model_name == "amazon.titan-embed-text-v1":
            return 1536  # Titan Text Embeddings V1
        elif self.model_name == "amazon.titan-embed-text-v2:0":
            return 1024  # Titan Text Embeddings V2
        else:
            return 1536  # Default


# Singleton instance
_embedding_service_instance = None


def get_embedding_service(
    model_name: str = "amazon.titan-embed-text-v1",
    region: str = "us-east-1"
) -> EmbeddingService:
    """
    Get or create embedding service singleton.
    
    Args:
        model_name: AWS Titan embedding model ID
        region: AWS region
        
    Returns:
        EmbeddingService instance
    """
    global _embedding_service_instance
    
    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService(
            model_name=model_name,
            region=region
        )
    
    return _embedding_service_instance
