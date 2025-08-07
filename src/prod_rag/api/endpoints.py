"""
FastAPI endpoints for the RAG pipeline.
"""

import logging
import time
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
import tempfile
import os
import uuid

from ..models.schemas import (
    QuerySchema,
    ResponseSchema,
    IngestionRequest,
    IngestionResponse,
    DocumentMetadata,
    DocumentType,
    HealthCheckSchema,
    MetricsSchema,
    ErrorSchema
)
from ..core.rag_engine import get_rag_engine
from ..data.ingestion import get_ingestion_pipeline
from ..core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Dependency to get settings
def get_current_settings():
    return get_settings()


@router.post("/query", response_model=ResponseSchema)
async def query_rag(
    query: QuerySchema,
    settings = Depends(get_current_settings)
) -> ResponseSchema:
    """
    Query the RAG system for information.
    
    Args:
        query: Query parameters including question and filters
        
    Returns:
        RAG response with answer and sources
    """
    try:
        logger.info(f"Received query: {query.query}")
        
        rag_engine = await get_rag_engine()
        response = await rag_engine.query(query)
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/documents/upload", response_model=IngestionResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    source_url: Optional[str] = Form(None),
    process_immediately: bool = Form(True)
) -> IngestionResponse:
    """
    Upload and process a document.
    
    Args:
        file: Document file to upload
        title: Document title
        author: Document author
        tags: Comma-separated tags
        source_url: Source URL if applicable
        process_immediately: Whether to process immediately or queue
        
    Returns:
        Ingestion response with processing status
    """
    try:
        # Validate file size
        settings = get_settings()
        max_size = settings.max_file_size_mb * 1024 * 1024
        
        # Read file content
        content = await file.read()
        if len(content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {settings.max_file_size_mb}MB"
            )
        
        # Determine file type
        filename = file.filename or "unknown"
        file_extension = os.path.splitext(filename)[1].lower()
        
        type_mapping = {
            '.pdf': DocumentType.PDF,
            '.docx': DocumentType.DOCX,
            '.txt': DocumentType.TXT,
            '.md': DocumentType.MD,
            '.html': DocumentType.HTML,
            '.csv': DocumentType.CSV,
            '.xlsx': DocumentType.XLSX
        }
        
        file_type = type_mapping.get(file_extension, DocumentType.TXT)
        
        # Create metadata
        metadata = DocumentMetadata(
            filename=filename,
            file_size=len(content),
            file_type=file_type,
            title=title,
            author=author,
            source_url=source_url,
            tags=tags.split(',') if tags else []
        )
        
        # Create ingestion request
        request = IngestionRequest(
            file_content=content.decode('utf-8', errors='ignore'),
            metadata=metadata,
            process_immediately=process_immediately
        )
        
        # Get ingestion pipeline
        pipeline = await get_ingestion_pipeline()
        
        if process_immediately:
            # Process synchronously
            response = await pipeline.ingest_document(request)
        else:
            # Process in background
            background_tasks.add_task(pipeline.ingest_document, request)
            response = IngestionResponse(
                document_id=str(uuid.uuid4()),
                status="pending",
                message="Document queued for processing",
                chunks_created=0,
                processing_time_ms=0
            )
        
        logger.info(f"Document upload completed: {filename}")
        return response
        
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Unable to decode file content. Please ensure the file is text-based."
        )
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {str(e)}"
        )


@router.post("/documents/ingest", response_model=IngestionResponse)
async def ingest_document_content(
    request: IngestionRequest
) -> IngestionResponse:
    """
    Ingest document content directly.
    
    Args:
        request: Document ingestion request with content and metadata
        
    Returns:
        Ingestion response with processing status
    """
    try:
        pipeline = await get_ingestion_pipeline()
        response = await pipeline.ingest_document(request)
        
        return response
        
    except Exception as e:
        logger.error(f"Error ingesting document: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to ingest document: {str(e)}"
        )


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str) -> Dict[str, Any]:
    """
    Delete a document and all its chunks.
    
    Args:
        document_id: ID of document to delete
        
    Returns:
        Deletion result
    """
    try:
        rag_engine = await get_rag_engine()
        result = await rag_engine.delete_document(document_id)
        
        if result["status"] == "error":
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )


@router.post("/documents/batch-upload")
async def batch_upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    process_immediately: bool = Form(True)
) -> Dict[str, Any]:
    """
    Upload multiple documents for batch processing.
    
    Args:
        files: List of document files
        process_immediately: Whether to process immediately
        
    Returns:
        Batch processing status
    """
    try:
        if len(files) > 50:  # Limit batch size
            raise HTTPException(
                status_code=400,
                detail="Maximum 50 files per batch"
            )
        
        # Save files temporarily and create ingestion requests
        temp_files = []
        requests = []
        
        for file in files:
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_files.append(temp_file.name)
                
                # Create metadata
                metadata = DocumentMetadata(
                    filename=file.filename or "unknown",
                    file_size=len(content),
                    file_type=DocumentType.TXT  # Simplified for batch
                )
                
                # Create request
                request = IngestionRequest(
                    file_content=content.decode('utf-8', errors='ignore'),
                    metadata=metadata,
                    process_immediately=process_immediately
                )
                requests.append(request)
        
        # Process batch
        pipeline = await get_ingestion_pipeline()
        
        if process_immediately:
            # Process all files
            responses = []
            for request in requests:
                response = await pipeline.ingest_document(request)
                responses.append(response)
            
            # Clean up temp files
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass
            
            successful = sum(1 for r in responses if r.status == "completed")
            total_chunks = sum(r.chunks_created for r in responses)
            
            return {
                "status": "completed",
                "total_files": len(files),
                "successful": successful,
                "failed": len(files) - successful,
                "total_chunks": total_chunks,
                "responses": responses
            }
        else:
            # Queue for background processing
            for request in requests:
                background_tasks.add_task(pipeline.ingest_document, request)
            
            return {
                "status": "queued",
                "total_files": len(files),
                "message": "Files queued for background processing"
            }
        
    except Exception as e:
        # Clean up temp files on error
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except OSError:
                pass
        
        logger.error(f"Error in batch upload: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process batch upload: {str(e)}"
        )


@router.get("/health", response_model=HealthCheckSchema)
async def health_check() -> HealthCheckSchema:
    """
    Perform comprehensive health check.
    
    Returns:
        Health status of all components
    """
    try:
        # Check RAG engine
        rag_engine = await get_rag_engine()
        rag_health = await rag_engine.health_check()
        
        # Check ingestion pipeline
        pipeline = await get_ingestion_pipeline()
        ingestion_health = await pipeline.health_check()
        
        # Combine health statuses
        services = {
            "rag_engine": rag_health["status"],
            "ingestion_pipeline": ingestion_health["status"],
            **rag_health.get("services", {}),
            **ingestion_health.get("components", {})
        }
        
        # Determine overall status
        if all(status == "healthy" for status in services.values()):
            overall_status = "healthy"
        elif any(status == "error" for status in services.values()):
            overall_status = "error"
        else:
            overall_status = "degraded"
        
        return HealthCheckSchema(
            status=overall_status,
            timestamp=time.time(),
            services=services,
            version="1.0.0"
        )
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return HealthCheckSchema(
            status="error",
            timestamp=time.time(),
            services={"error": str(e)},
            version="1.0.0"
        )


@router.get("/metrics", response_model=Dict[str, Any])
async def get_metrics() -> Dict[str, Any]:
    """
    Get system metrics and statistics.
    
    Returns:
        Comprehensive metrics data
    """
    try:
        # Get RAG engine metrics
        rag_engine = await get_rag_engine()
        rag_metrics = await rag_engine.get_metrics()
        
        # Get ingestion pipeline stats
        pipeline = await get_ingestion_pipeline()
        ingestion_stats = await pipeline.get_ingestion_stats()
        
        return {
            "rag_engine": rag_metrics,
            "ingestion_pipeline": ingestion_stats,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get metrics: {str(e)}"
        )


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """
    Get simple status information.
    
    Returns:
        Basic status information
    """
    return {
        "status": "running",
        "version": "1.0.0",
        "timestamp": time.time(),
        "message": "Production RAG Pipeline is operational"
    }


@router.get("/documents/stats")
async def get_document_stats() -> Dict[str, Any]:
    """
    Get document and chunk statistics.
    
    Returns:
        Document statistics
    """
    try:
        pipeline = await get_ingestion_pipeline()
        stats = await pipeline.get_ingestion_stats()
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting document stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get document statistics: {str(e)}"
        )


@router.get("/supported-formats")
async def get_supported_formats() -> Dict[str, List[str]]:
    """
    Get list of supported document formats.
    
    Returns:
        List of supported file formats
    """
    try:
        pipeline = await get_ingestion_pipeline()
        formats = pipeline.loader.get_supported_formats()
        
        return {
            "supported_formats": formats,
            "total_formats": len(formats)
        }
        
    except Exception as e:
        logger.error(f"Error getting supported formats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get supported formats: {str(e)}"
        )
