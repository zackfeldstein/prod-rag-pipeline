"""
Vector store management using Milvus.
"""

import logging
from typing import Dict, List, Optional, Any
import asyncio
from pymilvus import (
    connections, 
    Collection, 
    CollectionSchema, 
    FieldSchema, 
    DataType,
    utility
)
from pymilvus.exceptions import MilvusException

from .config import Settings, get_settings
from ..models.schemas import ChunkSchema, SearchResult

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Manages Milvus vector store operations."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.collection_name = self.settings.milvus_collection_name
        self.collection: Optional[Collection] = None
        self.connected = False
        
    async def connect(self) -> None:
        """Establish connection to Milvus."""
        try:
            logger.info(f"Connecting to Milvus at {self.settings.milvus_host}:{self.settings.milvus_port}")
            
            # Run connection in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._connect_sync)
            
            self.connected = True
            logger.info("Successfully connected to Milvus")
            
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise
    
    def _connect_sync(self) -> None:
        """Synchronous connection to Milvus."""
        connections.connect(
            alias="default",
            host=self.settings.milvus_host,
            port=self.settings.milvus_port,
            user=self.settings.milvus_user,
            password=self.settings.milvus_password,
            secure=self.settings.milvus_secure
        )
    
    async def create_collection(self) -> None:
        """Create the documents collection if it doesn't exist."""
        try:
            loop = asyncio.get_event_loop()
            exists = await loop.run_in_executor(
                None, 
                utility.has_collection, 
                self.collection_name
            )
            
            if exists:
                logger.info(f"Collection '{self.collection_name}' already exists")
                self.collection = Collection(self.collection_name)
                return
            
            # Define collection schema
            fields = [
                FieldSchema(
                    name="id", 
                    dtype=DataType.VARCHAR, 
                    is_primary=True, 
                    auto_id=False,
                    max_length=100
                ),
                FieldSchema(
                    name="document_id", 
                    dtype=DataType.VARCHAR, 
                    max_length=100
                ),
                FieldSchema(
                    name="chunk_index", 
                    dtype=DataType.INT64
                ),
                FieldSchema(
                    name="content", 
                    dtype=DataType.VARCHAR, 
                    max_length=65535
                ),
                FieldSchema(
                    name="embedding", 
                    dtype=DataType.FLOAT_VECTOR, 
                    dim=self.settings.embedding_dimension
                ),
                FieldSchema(
                    name="metadata", 
                    dtype=DataType.JSON
                )
            ]
            
            schema = CollectionSchema(
                fields=fields,
                description="RAG document chunks collection"
            )
            
            # Create collection
            await loop.run_in_executor(
                None,
                self._create_collection_sync,
                schema
            )
            
            logger.info(f"Created collection '{self.collection_name}'")
            
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise
    
    def _create_collection_sync(self, schema: CollectionSchema) -> None:
        """Synchronously create collection."""
        self.collection = Collection(
            name=self.collection_name,
            schema=schema
        )
        
        # Create index for vector field
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        
        self.collection.create_index(
            field_name="embedding",
            index_params=index_params
        )
        
        # Load collection into memory
        self.collection.load()
    
    async def insert_chunks(self, chunks: List[ChunkSchema]) -> List[str]:
        """
        Insert document chunks into the vector store.
        
        Args:
            chunks: List of document chunks to insert
            
        Returns:
            List of inserted chunk IDs
        """
        if not self.collection:
            await self.create_collection()
        
        if not chunks:
            return []
        
        try:
            # Prepare data for insertion
            data = [
                [chunk.id for chunk in chunks],  # id
                [chunk.document_id for chunk in chunks],  # document_id
                [chunk.chunk_index for chunk in chunks],  # chunk_index
                [chunk.content for chunk in chunks],  # content
                [chunk.embedding for chunk in chunks],  # embedding
                [chunk.metadata for chunk in chunks]  # metadata
            ]
            
            # Insert data
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.collection.insert,
                data
            )
            
            # Flush to ensure data is persisted
            await loop.run_in_executor(None, self.collection.flush)
            
            logger.info(f"Inserted {len(chunks)} chunks into vector store")
            return result.primary_keys
            
        except Exception as e:
            logger.error(f"Failed to insert chunks: {e}")
            raise
    
    async def search(
        self,
        query_embedding: List[float],
        limit: int = 5,
        filters: Optional[str] = None,
        similarity_threshold: float = 0.0
    ) -> List[SearchResult]:
        """
        Search for similar chunks in the vector store.
        
        Args:
            query_embedding: Query embedding vector
            limit: Maximum number of results
            filters: Optional filter expression
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of search results
        """
        if not self.collection:
            await self.create_collection()
        
        try:
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            
            output_fields = ["id", "document_id", "chunk_index", "content", "metadata"]
            
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                self._search_sync,
                query_embedding,
                limit,
                search_params,
                output_fields,
                filters
            )
            
            # Convert to SearchResult objects
            search_results = []
            for hit in results[0]:  # results is a list with one element
                if hit.score >= similarity_threshold:
                    result = SearchResult(
                        id=hit.entity.get("id"),
                        content=hit.entity.get("content"),
                        score=float(hit.score),
                        metadata=hit.entity.get("metadata", {}),
                        document_id=hit.entity.get("document_id"),
                        chunk_index=hit.entity.get("chunk_index")
                    )
                    search_results.append(result)
            
            logger.info(f"Found {len(search_results)} similar chunks")
            return search_results
            
        except Exception as e:
            logger.error(f"Failed to search vector store: {e}")
            raise
    
    def _search_sync(
        self,
        query_embedding: List[float],
        limit: int,
        search_params: dict,
        output_fields: List[str],
        filters: Optional[str]
    ):
        """Synchronous search operation."""
        return self.collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=limit,
            output_fields=output_fields,
            expr=filters
        )
    
    async def delete_by_document_id(self, document_id: str) -> int:
        """
        Delete all chunks for a specific document.
        
        Args:
            document_id: Document ID to delete
            
        Returns:
            Number of deleted chunks
        """
        if not self.collection:
            return 0
        
        try:
            expr = f'document_id == "{document_id}"'
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.collection.delete,
                expr
            )
            
            await loop.run_in_executor(None, self.collection.flush)
            
            logger.info(f"Deleted chunks for document: {document_id}")
            return result.delete_count
            
        except Exception as e:
            logger.error(f"Failed to delete chunks for document {document_id}: {e}")
            raise
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        if not self.collection:
            return {}
        
        try:
            loop = asyncio.get_event_loop()
            stats = await loop.run_in_executor(
                None,
                self.collection.get_stats
            )
            
            return {
                "total_entities": stats["row_count"],
                "total_size_bytes": stats.get("data_size", 0),
                "index_size_bytes": stats.get("index_size", 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on vector store."""
        try:
            if not self.connected:
                return {"status": "error", "message": "Not connected to Milvus"}
            
            if not self.collection:
                await self.create_collection()
            
            # Test basic operations
            loop = asyncio.get_event_loop()
            is_loaded = await loop.run_in_executor(
                None,
                lambda: utility.get_query_segment_info(self.collection_name)
            )
            
            stats = await self.get_collection_stats()
            
            return {
                "status": "healthy",
                "collection_name": self.collection_name,
                "loaded": len(is_loaded) > 0,
                "stats": stats
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def close(self) -> None:
        """Close the connection to Milvus."""
        try:
            if self.collection:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.collection.release)
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                connections.disconnect,
                "default"
            )
            
            self.connected = False
            logger.info("Disconnected from Milvus")
            
        except Exception as e:
            logger.error(f"Error closing Milvus connection: {e}")


# Global vector store manager instance
_vector_store_manager: Optional[VectorStoreManager] = None


async def get_vector_store_manager() -> VectorStoreManager:
    """Get or create the global vector store manager instance."""
    global _vector_store_manager
    
    if _vector_store_manager is None:
        _vector_store_manager = VectorStoreManager()
        await _vector_store_manager.connect()
        await _vector_store_manager.create_collection()
    
    return _vector_store_manager
