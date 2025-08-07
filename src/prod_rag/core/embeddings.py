"""
Embedding management for the RAG pipeline.
"""

import asyncio
from typing import List, Optional
import logging
import torch
from sentence_transformers import SentenceTransformer
import numpy as np
from functools import lru_cache

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """Manages embedding generation with caching and batch processing."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.model: Optional[SentenceTransformer] = None
        self.device = self._determine_device()
        
    def _determine_device(self) -> str:
        """Determine the best available device for embeddings."""
        if self.settings.embedding_device == "cuda" and torch.cuda.is_available():
            return "cuda"
        elif self.settings.embedding_device == "mps" and torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"
    
    async def initialize(self) -> None:
        """Initialize the embedding model asynchronously."""
        try:
            logger.info(f"Loading embedding model: {self.settings.embedding_model}")
            
            # Load model in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None, 
                self._load_model
            )
            
            logger.info(f"Embedding model loaded successfully on device: {self.device}")
            
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {e}")
            raise
    
    def _load_model(self) -> SentenceTransformer:
        """Load the sentence transformer model."""
        model = SentenceTransformer(self.settings.embedding_model)
        model.to(self.device)
        return model
    
    async def encode_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Encode a list of texts into embeddings.
        
        Args:
            texts: List of text strings to encode
            
        Returns:
            List of embedding vectors
        """
        if not self.model:
            await self.initialize()
        
        if not texts:
            return []
        
        try:
            # Process in batches to manage memory
            embeddings = []
            batch_size = self.settings.embedding_batch_size
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                # Run encoding in thread pool
                loop = asyncio.get_event_loop()
                batch_embeddings = await loop.run_in_executor(
                    None,
                    self._encode_batch,
                    batch
                )
                
                embeddings.extend(batch_embeddings)
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to encode texts: {e}")
            raise
    
    def _encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encode a batch of texts synchronously."""
        embeddings = self.model.encode(
            texts,
            device=self.device,
            show_progress_bar=False,
            convert_to_tensor=False,
            normalize_embeddings=True
        )
        
        # Ensure numpy array and convert to list
        if isinstance(embeddings, torch.Tensor):
            embeddings = embeddings.cpu().numpy()
        
        return embeddings.tolist()
    
    async def encode_single(self, text: str) -> List[float]:
        """
        Encode a single text into an embedding.
        
        Args:
            text: Text string to encode
            
        Returns:
            Embedding vector
        """
        embeddings = await self.encode_texts([text])
        return embeddings[0] if embeddings else []
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of the embedding vectors."""
        return self.settings.embedding_dimension
    
    async def similarity_search(
        self, 
        query_embedding: List[float], 
        candidate_embeddings: List[List[float]],
        top_k: int = 5
    ) -> List[tuple]:
        """
        Perform similarity search between query and candidate embeddings.
        
        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: List of candidate embedding vectors
            top_k: Number of top results to return
            
        Returns:
            List of (index, score) tuples sorted by similarity score
        """
        if not candidate_embeddings:
            return []
        
        try:
            # Convert to numpy arrays for efficient computation
            query_vec = np.array(query_embedding)
            candidate_vecs = np.array(candidate_embeddings)
            
            # Compute cosine similarity
            similarities = np.dot(candidate_vecs, query_vec) / (
                np.linalg.norm(candidate_vecs, axis=1) * np.linalg.norm(query_vec)
            )
            
            # Get top-k indices
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            # Return (index, score) pairs
            results = [(int(idx), float(similarities[idx])) for idx in top_indices]
            return results
            
        except Exception as e:
            logger.error(f"Failed to perform similarity search: {e}")
            raise
    
    @lru_cache(maxsize=1000)
    def _cached_encode(self, text: str) -> tuple:
        """Cache frequently encoded texts."""
        if not self.model:
            raise RuntimeError("Model not initialized")
        
        embedding = self.model.encode([text], device=self.device)[0]
        return tuple(embedding.tolist())
    
    async def health_check(self) -> dict:
        """Perform health check on the embedding service."""
        try:
            if not self.model:
                return {"status": "error", "message": "Model not loaded"}
            
            # Test encoding a simple text
            test_text = "This is a test sentence."
            embedding = await self.encode_single(test_text)
            
            if len(embedding) == self.get_embedding_dimension():
                return {
                    "status": "healthy",
                    "model": self.settings.embedding_model,
                    "device": self.device,
                    "dimension": len(embedding)
                }
            else:
                return {
                    "status": "error", 
                    "message": f"Unexpected embedding dimension: {len(embedding)}"
                }
                
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Global embedding manager instance
_embedding_manager: Optional[EmbeddingManager] = None


async def get_embedding_manager() -> EmbeddingManager:
    """Get or create the global embedding manager instance."""
    global _embedding_manager
    
    if _embedding_manager is None:
        _embedding_manager = EmbeddingManager()
        await _embedding_manager.initialize()
    
    return _embedding_manager
