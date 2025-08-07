"""
Document ingestion pipeline for processing and storing documents.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import time

from .loaders import DocumentLoader
from ..models.schemas import (
    DocumentSchema,
    ChunkSchema,
    DocumentStatus,
    DocumentMetadata,
    IngestionRequest,
    IngestionResponse
)
from ..core.embeddings import get_embedding_manager
from ..core.vector_store import get_vector_store_manager
from ..utils.text_processing import TextProcessor
from ..utils.metrics import MetricsCollector
from ..core.config import get_settings

logger = logging.getLogger(__name__)


class DocumentIngestionPipeline:
    """Production-ready document ingestion pipeline."""
    
    def __init__(self):
        self.settings = get_settings()
        self.loader = DocumentLoader()
        self.text_processor = TextProcessor(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap
        )
        self.embedding_manager = None
        self.vector_store = None
        self.metrics = MetricsCollector()
        self.initialized = False
    
    async def initialize(self) -> None:
        """Initialize the ingestion pipeline."""
        if self.initialized:
            return
        
        try:
            logger.info("Initializing document ingestion pipeline...")
            
            # Initialize components
            self.embedding_manager = await get_embedding_manager()
            self.vector_store = await get_vector_store_manager()
            
            self.initialized = True
            logger.info("Document ingestion pipeline initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ingestion pipeline: {e}")
            raise
    
    async def ingest_document(
        self,
        request: IngestionRequest
    ) -> IngestionResponse:
        """
        Ingest a single document through the complete pipeline.
        
        Args:
            request: Document ingestion request
            
        Returns:
            Ingestion response with results
        """
        if not self.initialized:
            await self.initialize()
        
        start_time = time.time()
        document_id = str(uuid.uuid4())
        
        try:
            logger.info(f"Starting ingestion for document: {request.metadata.filename}")
            
            # Step 1: Load document content
            if request.file_url:
                # Load from URL (implement URL loading if needed)
                raise NotImplementedError("URL loading not yet implemented")
            elif request.file_content:
                # Load from provided content
                document_data = await self.loader.load_from_content(
                    content=request.file_content,
                    file_type=request.metadata.file_type,
                    metadata=request.metadata
                )
            else:
                raise ValueError("Either file_url or file_content must be provided")
            
            # Step 2: Create document schema
            document = DocumentSchema(
                id=document_id,
                content=document_data["content"],
                metadata=request.metadata,
                status=DocumentStatus.PROCESSING
            )
            
            # Step 3: Process and chunk the document
            chunks_data = self.text_processor.chunk_document(
                content=document.content,
                document_metadata=document.metadata.dict()
            )
            
            logger.info(f"Created {len(chunks_data)} chunks for document {document_id}")
            
            # Step 4: Create chunk schemas
            chunks = []
            for i, chunk_data in enumerate(chunks_data):
                chunk = ChunkSchema(
                    id=f"{document_id}_chunk_{i}",
                    document_id=document_id,
                    content=chunk_data["content"],
                    chunk_index=i,
                    metadata=chunk_data["metadata"]
                )
                chunks.append(chunk)
            
            # Step 5: Generate embeddings
            chunk_texts = [chunk.content for chunk in chunks]
            embeddings = await self.embedding_manager.encode_texts(chunk_texts)
            
            # Assign embeddings to chunks
            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding
            
            logger.info(f"Generated embeddings for {len(chunks)} chunks")
            
            # Step 6: Store in vector database
            if request.process_immediately:
                inserted_ids = await self.vector_store.insert_chunks(chunks)
                logger.info(f"Stored {len(inserted_ids)} chunks in vector database")
                
                # Update document status
                document.status = DocumentStatus.COMPLETED
                document.chunks = [chunk.id for chunk in chunks]
            else:
                # Just prepare chunks without storing
                document.status = DocumentStatus.PENDING
                document.chunks = []
            
            # Calculate processing time
            processing_time = int((time.time() - start_time) * 1000)
            
            # Record metrics
            self.metrics.record_query(
                processing_time=processing_time,
                num_sources=len(chunks),
                confidence_score=1.0,  # Successful ingestion
                cached=False
            )
            
            response = IngestionResponse(
                document_id=document_id,
                status=document.status,
                message=f"Successfully processed document with {len(chunks)} chunks",
                chunks_created=len(chunks),
                processing_time_ms=processing_time
            )
            
            logger.info(f"Document ingestion completed in {processing_time}ms")
            return response
            
        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            error_msg = f"Failed to ingest document: {str(e)}"
            logger.error(error_msg)
            
            # Record error metrics
            self.metrics.record_error("ingestion_error")
            
            return IngestionResponse(
                document_id=document_id,
                status=DocumentStatus.FAILED,
                message=error_msg,
                chunks_created=0,
                processing_time_ms=processing_time
            )
    
    async def ingest_file(
        self,
        file_path: str,
        metadata: Optional[DocumentMetadata] = None
    ) -> IngestionResponse:
        """
        Ingest a document from file path.
        
        Args:
            file_path: Path to the document file
            metadata: Optional metadata (will be auto-generated if not provided)
            
        Returns:
            Ingestion response
        """
        try:
            # Load document
            document_data = await self.loader.load_from_file(file_path, metadata)
            
            # Create ingestion request
            request = IngestionRequest(
                file_content=document_data["content"],
                metadata=document_data["metadata"],
                process_immediately=True
            )
            
            return await self.ingest_document(request)
            
        except Exception as e:
            logger.error(f"Failed to ingest file {file_path}: {e}")
            return IngestionResponse(
                document_id="",
                status=DocumentStatus.FAILED,
                message=str(e),
                chunks_created=0,
                processing_time_ms=0
            )
    
    async def batch_ingest_files(
        self,
        file_paths: List[str],
        max_concurrent: int = 5
    ) -> List[IngestionResponse]:
        """
        Ingest multiple files concurrently.
        
        Args:
            file_paths: List of file paths to ingest
            max_concurrent: Maximum concurrent ingestions
            
        Returns:
            List of ingestion responses
        """
        if not self.initialized:
            await self.initialize()
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def ingest_with_semaphore(file_path: str) -> IngestionResponse:
            async with semaphore:
                return await self.ingest_file(file_path)
        
        # Create tasks for all files
        tasks = [ingest_with_semaphore(file_path) for file_path in file_paths]
        
        # Execute with progress logging
        results = []
        completed = 0
        total = len(tasks)
        
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            completed += 1
            
            if completed % 10 == 0 or completed == total:
                logger.info(f"Batch ingestion progress: {completed}/{total}")
        
        # Log summary
        successful = sum(1 for r in results if r.status == DocumentStatus.COMPLETED)
        failed = total - successful
        total_chunks = sum(r.chunks_created for r in results)
        
        logger.info(
            f"Batch ingestion completed: {successful} successful, "
            f"{failed} failed, {total_chunks} total chunks created"
        )
        
        return results
    
    async def reingest_document(self, document_id: str) -> IngestionResponse:
        """
        Re-ingest a document (useful for updates or reprocessing).
        
        Args:
            document_id: ID of document to re-ingest
            
        Returns:
            Ingestion response
        """
        try:
            # First, delete existing chunks
            deleted_count = await self.vector_store.delete_by_document_id(document_id)
            logger.info(f"Deleted {deleted_count} existing chunks for document {document_id}")
            
            # Note: In a full implementation, you would need to store original
            # document content/metadata to enable re-ingestion
            # For now, return an error message
            return IngestionResponse(
                document_id=document_id,
                status=DocumentStatus.FAILED,
                message="Re-ingestion requires original document content storage (not implemented)",
                chunks_created=0,
                processing_time_ms=0
            )
            
        except Exception as e:
            logger.error(f"Failed to re-ingest document {document_id}: {e}")
            return IngestionResponse(
                document_id=document_id,
                status=DocumentStatus.FAILED,
                message=str(e),
                chunks_created=0,
                processing_time_ms=0
            )
    
    async def delete_document(self, document_id: str) -> Dict[str, Any]:
        """
        Delete a document and all its chunks.
        
        Args:
            document_id: ID of document to delete
            
        Returns:
            Deletion result
        """
        if not self.initialized:
            await self.initialize()
        
        try:
            deleted_count = await self.vector_store.delete_by_document_id(document_id)
            
            return {
                "status": "success",
                "document_id": document_id,
                "chunks_deleted": deleted_count,
                "message": f"Successfully deleted document and {deleted_count} chunks"
            }
            
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return {
                "status": "error",
                "document_id": document_id,
                "chunks_deleted": 0,
                "message": str(e)
            }
    
    async def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get ingestion pipeline statistics."""
        try:
            # Get vector store stats
            vector_stats = await self.vector_store.get_collection_stats()
            
            # Get metrics
            metrics = self.metrics.get_metrics()
            
            return {
                "vector_store": vector_stats,
                "processing_metrics": metrics,
                "pipeline_status": "healthy" if self.initialized else "not_initialized",
                "supported_formats": self.loader.get_supported_formats()
            }
            
        except Exception as e:
            logger.error(f"Failed to get ingestion stats: {e}")
            return {
                "error": str(e),
                "pipeline_status": "error"
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on ingestion pipeline."""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow(),
            "components": {}
        }
        
        try:
            # Check document loader
            health_status["components"]["document_loader"] = "healthy"
            
            # Check text processor
            test_text = "This is a test document for health checking."
            test_chunks = self.text_processor.chunk_text(test_text)
            if test_chunks:
                health_status["components"]["text_processor"] = "healthy"
            else:
                health_status["components"]["text_processor"] = "error"
            
            # Check embedding manager
            if self.embedding_manager:
                embedding_health = await self.embedding_manager.health_check()
                health_status["components"]["embedding_manager"] = embedding_health["status"]
            else:
                health_status["components"]["embedding_manager"] = "not_initialized"
            
            # Check vector store
            if self.vector_store:
                vector_health = await self.vector_store.health_check()
                health_status["components"]["vector_store"] = vector_health["status"]
            else:
                health_status["components"]["vector_store"] = "not_initialized"
            
            # Overall status
            if any(status != "healthy" for status in health_status["components"].values()):
                health_status["status"] = "degraded"
            
        except Exception as e:
            logger.error(f"Ingestion pipeline health check error: {e}")
            health_status["status"] = "error"
            health_status["error"] = str(e)
        
        return health_status


# Global ingestion pipeline instance
_ingestion_pipeline: Optional[DocumentIngestionPipeline] = None


async def get_ingestion_pipeline() -> DocumentIngestionPipeline:
    """Get or create the global ingestion pipeline instance."""
    global _ingestion_pipeline
    
    if _ingestion_pipeline is None:
        _ingestion_pipeline = DocumentIngestionPipeline()
        await _ingestion_pipeline.initialize()
    
    return _ingestion_pipeline
