"""
Main FastAPI application setup and configuration.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import structlog

from .endpoints import router
from ..core.config import get_settings
from ..utils.metrics import MetricsCollector

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# Global metrics collector
metrics_collector = MetricsCollector()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("Starting Production RAG Pipeline API")
    
    # Start Prometheus metrics server
    settings = get_settings()
    try:
        metrics_collector.start_prometheus_server(port=8001)
        logger.info("Prometheus metrics server started on port 8001")
    except Exception as e:
        logger.warning(f"Failed to start Prometheus metrics server: {e}")
    
    # Pre-initialize core components
    try:
        from ..core.rag_engine import get_rag_engine
        from ..data.ingestion import get_ingestion_pipeline
        
        logger.info("Initializing RAG engine...")
        await get_rag_engine()
        
        logger.info("Initializing ingestion pipeline...")
        await get_ingestion_pipeline()
        
        logger.info("All components initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        # Continue startup but log the error
    
    yield
    
    # Shutdown
    logger.info("Shutting down Production RAG Pipeline API")
    
    # Cleanup resources
    try:
        from ..core.rag_engine import get_rag_engine
        rag_engine = await get_rag_engine()
        await rag_engine.close()
        logger.info("RAG engine closed")
    except Exception as e:
        logger.error(f"Error closing RAG engine: {e}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="Production RAG Pipeline",
        description="""
        A production-ready Retrieval Augmented Generation (RAG) pipeline built with:
        - LangChain for RAG orchestration
        - Milvus for vector storage
        - FastAPI for scalable API endpoints
        - Redis for caching
        - Prometheus for monitoring
        
        Features:
        - Document ingestion with multiple format support
        - Semantic search and retrieval
        - Real-time question answering
        - Comprehensive monitoring and metrics
        - Horizontal scaling capabilities
        """,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Add custom middleware for metrics and logging
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        """Middleware to collect metrics and log requests."""
        start_time = time.time()
        
        # Extract request info
        method = request.method
        path = request.url.path
        
        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            
            # Record metrics
            REQUEST_COUNT.labels(
                method=method,
                endpoint=path,
                status=status_code
            ).inc()
            
            duration = time.time() - start_time
            REQUEST_DURATION.labels(
                method=method,
                endpoint=path
            ).observe(duration)
            
            # Log request
            logger.info(
                "HTTP request completed",
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=round(duration * 1000, 2),
                user_agent=request.headers.get("user-agent", ""),
                remote_addr=request.client.host if request.client else ""
            )
            
            return response
            
        except Exception as e:
            # Record error metrics
            REQUEST_COUNT.labels(
                method=method,
                endpoint=path,
                status=500
            ).inc()
            
            duration = time.time() - start_time
            
            # Log error
            logger.error(
                "HTTP request failed",
                method=method,
                path=path,
                duration_ms=round(duration * 1000, 2),
                error=str(e),
                exc_info=True
            )
            
            raise
    
    # Add rate limiting middleware (simple implementation)
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        """Simple rate limiting middleware."""
        # In production, use a proper rate limiting solution like slowapi
        # This is a simplified example
        
        client_ip = request.client.host if request.client else "unknown"
        
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/metrics", "/status"]:
            return await call_next(request)
        
        # TODO: Implement proper rate limiting with Redis
        # For now, just pass through
        return await call_next(request)
    
    # Exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions with proper logging."""
        logger.warning(
            "HTTP exception",
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.url.path,
            method=request.method
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP Error",
                "detail": exc.detail,
                "status_code": exc.status_code,
                "timestamp": time.time()
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle general exceptions."""
        logger.error(
            "Unhandled exception",
            error=str(exc),
            path=request.url.path,
            method=request.method,
            exc_info=True
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "detail": "An unexpected error occurred",
                "timestamp": time.time()
            }
        )
    
    # Include API routes
    app.include_router(router, prefix="/api/v1")
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "Production RAG Pipeline",
            "version": "1.0.0",
            "status": "running",
            "docs_url": "/docs",
            "health_check": "/api/v1/health",
            "metrics": "/api/v1/metrics",
            "timestamp": time.time()
        }
    
    # Prometheus metrics endpoint
    @app.get("/prometheus-metrics")
    async def prometheus_metrics():
        """Expose Prometheus metrics."""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
    
    # Add startup event to log successful startup
    @app.on_event("startup")
    async def startup_event():
        """Log successful startup."""
        logger.info(
            "FastAPI application started",
            host=settings.api_host,
            port=settings.api_port,
            workers=settings.api_workers,
            reload=settings.api_reload
        )
    
    return app


# Create app instance
app = create_app()
