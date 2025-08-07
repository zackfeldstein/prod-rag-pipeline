"""
Pydantic schemas for the RAG pipeline.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentType(str, Enum):
    """Supported document types."""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"
    HTML = "html"
    CSV = "csv"
    XLSX = "xlsx"


class DocumentMetadata(BaseModel):
    """Document metadata schema."""
    filename: str
    file_size: int
    file_type: DocumentType
    upload_date: datetime
    source_url: Optional[str] = None
    author: Optional[str] = None
    title: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentSchema(BaseModel):
    """Document schema for ingestion."""
    id: Optional[str] = None
    content: str
    metadata: DocumentMetadata
    status: DocumentStatus = DocumentStatus.PENDING
    embedding: Optional[List[float]] = None
    chunks: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


class ChunkSchema(BaseModel):
    """Document chunk schema."""
    id: str
    document_id: str
    content: str
    chunk_index: int
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class QuerySchema(BaseModel):
    """Query schema for RAG requests."""
    query: str = Field(..., min_length=1, max_length=1000)
    max_results: int = Field(default=5, ge=1, le=20)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    include_metadata: bool = Field(default=True)
    filters: Optional[Dict[str, Any]] = None
    rerank: bool = Field(default=True)
    
    @validator("query")
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


class SearchResult(BaseModel):
    """Search result schema."""
    id: str
    content: str
    score: float
    metadata: Dict[str, Any]
    document_id: str
    chunk_index: int


class ResponseSchema(BaseModel):
    """RAG response schema."""
    query: str
    answer: str
    sources: List[SearchResult]
    confidence_score: float
    processing_time_ms: int
    model_info: Dict[str, str]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class HealthCheckSchema(BaseModel):
    """Health check response schema."""
    status: str
    timestamp: datetime
    services: Dict[str, str]
    version: str


class ErrorSchema(BaseModel):
    """Error response schema."""
    error: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None


class IngestionRequest(BaseModel):
    """Document ingestion request schema."""
    file_url: Optional[str] = None
    file_content: Optional[str] = None
    metadata: DocumentMetadata
    process_immediately: bool = Field(default=True)
    
    @validator("file_url", "file_content", pre=True, always=True)
    def validate_input(cls, v, values, field):
        file_url = values.get("file_url")
        file_content = values.get("file_content")
        
        if not file_url and not file_content:
            raise ValueError("Either file_url or file_content must be provided")
        
        if file_url and file_content:
            raise ValueError("Only one of file_url or file_content should be provided")
        
        return v


class IngestionResponse(BaseModel):
    """Document ingestion response schema."""
    document_id: str
    status: DocumentStatus
    message: str
    chunks_created: int
    processing_time_ms: int


class MetricsSchema(BaseModel):
    """Metrics response schema."""
    total_documents: int
    total_chunks: int
    total_queries: int
    average_response_time_ms: float
    cache_hit_rate: float
    active_connections: int
    system_health: Dict[str, Any]


class ConfigSchema(BaseModel):
    """Configuration schema for dynamic updates."""
    chunk_size: Optional[int] = Field(None, ge=100, le=2000)
    chunk_overlap: Optional[int] = Field(None, ge=0, le=500)
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_results: Optional[int] = Field(None, ge=1, le=50)
    cache_ttl: Optional[int] = Field(None, ge=0, le=86400)
    
    @validator("chunk_overlap")
    def validate_overlap(cls, v, values):
        chunk_size = values.get("chunk_size")
        if chunk_size and v and v >= chunk_size:
            raise ValueError("Chunk overlap must be less than chunk size")
        return v
