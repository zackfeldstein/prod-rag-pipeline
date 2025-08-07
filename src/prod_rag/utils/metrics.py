"""
Metrics collection for monitoring RAG performance.
"""

import time
from collections import defaultdict, deque
from typing import Dict, Any, List
import threading
from datetime import datetime, timedelta

from prometheus_client import Counter, Histogram, Gauge, start_http_server
import logging

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and exposes metrics for the RAG pipeline."""
    
    def __init__(self):
        # Prometheus metrics
        self.query_counter = Counter(
            'rag_queries_total',
            'Total number of RAG queries processed'
        )
        
        self.query_duration = Histogram(
            'rag_query_duration_seconds',
            'Time spent processing RAG queries',
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        )
        
        self.cache_hits = Counter(
            'rag_cache_hits_total',
            'Total number of cache hits'
        )
        
        self.cache_misses = Counter(
            'rag_cache_misses_total', 
            'Total number of cache misses'
        )
        
        self.document_chunks = Gauge(
            'rag_document_chunks_total',
            'Total number of document chunks in vector store'
        )
        
        self.embedding_duration = Histogram(
            'rag_embedding_duration_seconds',
            'Time spent generating embeddings',
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
        )
        
        self.vector_search_duration = Histogram(
            'rag_vector_search_duration_seconds', 
            'Time spent on vector similarity search',
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
        )
        
        self.llm_generation_duration = Histogram(
            'rag_llm_generation_duration_seconds',
            'Time spent on LLM response generation',
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        )
        
        # Internal tracking
        self._lock = threading.Lock()
        self._recent_queries = deque(maxlen=1000)
        self._error_counts = defaultdict(int)
        self._start_time = time.time()
        
        # Quality metrics
        self._confidence_scores = deque(maxlen=1000)
        self._source_counts = deque(maxlen=1000)
        
    def record_query(
        self, 
        processing_time: int,
        num_sources: int = 0,
        confidence_score: float = 0.0,
        cached: bool = False
    ) -> None:
        """Record a query execution."""
        with self._lock:
            # Prometheus metrics
            self.query_counter.inc()
            self.query_duration.observe(processing_time / 1000.0)
            
            if cached:
                self.cache_hits.inc()
            else:
                self.cache_misses.inc()
            
            # Internal tracking
            query_data = {
                'timestamp': datetime.utcnow(),
                'processing_time_ms': processing_time,
                'num_sources': num_sources,
                'confidence_score': confidence_score,
                'cached': cached
            }
            self._recent_queries.append(query_data)
            
            # Quality tracking
            if confidence_score > 0:
                self._confidence_scores.append(confidence_score)
            if num_sources > 0:
                self._source_counts.append(num_sources)
    
    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        self.cache_hits.inc()
    
    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        self.cache_misses.inc()
    
    def record_embedding_time(self, duration_seconds: float) -> None:
        """Record embedding generation time."""
        self.embedding_duration.observe(duration_seconds)
    
    def record_vector_search_time(self, duration_seconds: float) -> None:
        """Record vector search time."""
        self.vector_search_duration.observe(duration_seconds)
    
    def record_llm_generation_time(self, duration_seconds: float) -> None:
        """Record LLM generation time."""
        self.llm_generation_duration.observe(duration_seconds)
    
    def record_error(self, error_type: str) -> None:
        """Record an error occurrence."""
        with self._lock:
            self._error_counts[error_type] += 1
    
    def update_chunk_count(self, count: int) -> None:
        """Update the total chunk count."""
        self.document_chunks.set(count)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        with self._lock:
            now = datetime.utcnow()
            
            # Calculate rates
            total_queries = len(self._recent_queries)
            if total_queries > 0:
                first_query_time = self._recent_queries[0]['timestamp']
                time_span = (now - first_query_time).total_seconds()
                query_rate = total_queries / max(time_span, 1.0)
            else:
                query_rate = 0.0
            
            # Cache hit rate
            cache_hits = sum(1 for q in self._recent_queries if q['cached'])
            cache_hit_rate = cache_hits / max(total_queries, 1) * 100
            
            # Average metrics
            if self._recent_queries:
                avg_processing_time = sum(
                    q['processing_time_ms'] for q in self._recent_queries
                ) / len(self._recent_queries)
                
                avg_sources = sum(
                    q['num_sources'] for q in self._recent_queries
                ) / len(self._recent_queries)
            else:
                avg_processing_time = 0.0
                avg_sources = 0.0
            
            # Confidence metrics
            if self._confidence_scores:
                avg_confidence = sum(self._confidence_scores) / len(self._confidence_scores)
                min_confidence = min(self._confidence_scores)
                max_confidence = max(self._confidence_scores)
            else:
                avg_confidence = min_confidence = max_confidence = 0.0
            
            return {
                'system': {
                    'uptime_seconds': time.time() - self._start_time,
                    'total_queries': total_queries,
                    'query_rate_per_second': round(query_rate, 2),
                    'error_counts': dict(self._error_counts)
                },
                'performance': {
                    'average_processing_time_ms': round(avg_processing_time, 2),
                    'cache_hit_rate_percent': round(cache_hit_rate, 2),
                    'average_sources_per_query': round(avg_sources, 2)
                },
                'quality': {
                    'average_confidence_score': round(avg_confidence, 3),
                    'min_confidence_score': round(min_confidence, 3),
                    'max_confidence_score': round(max_confidence, 3),
                    'total_confidence_samples': len(self._confidence_scores)
                },
                'recent_activity': self._get_recent_activity_stats(now)
            }
    
    def _get_recent_activity_stats(self, now: datetime) -> Dict[str, Any]:
        """Get statistics for recent activity."""
        # Last hour stats
        hour_ago = now - timedelta(hours=1)
        recent_queries = [
            q for q in self._recent_queries 
            if q['timestamp'] > hour_ago
        ]
        
        # Last minute stats
        minute_ago = now - timedelta(minutes=1)
        very_recent_queries = [
            q for q in self._recent_queries
            if q['timestamp'] > minute_ago
        ]
        
        return {
            'last_hour': {
                'query_count': len(recent_queries),
                'average_processing_time_ms': (
                    sum(q['processing_time_ms'] for q in recent_queries) / 
                    max(len(recent_queries), 1)
                )
            },
            'last_minute': {
                'query_count': len(very_recent_queries),
                'queries_per_second': len(very_recent_queries) / 60.0
            }
        }
    
    def get_health_metrics(self) -> Dict[str, Any]:
        """Get health-focused metrics."""
        with self._lock:
            total_errors = sum(self._error_counts.values())
            total_queries = len(self._recent_queries)
            error_rate = (total_errors / max(total_queries, 1)) * 100
            
            # Recent performance
            recent_queries = list(self._recent_queries)[-100:]  # Last 100 queries
            if recent_queries:
                recent_avg_time = sum(
                    q['processing_time_ms'] for q in recent_queries
                ) / len(recent_queries)
                
                # Check for performance degradation
                performance_threshold = 5000  # 5 seconds
                slow_queries = sum(
                    1 for q in recent_queries 
                    if q['processing_time_ms'] > performance_threshold
                )
                slow_query_rate = (slow_queries / len(recent_queries)) * 100
            else:
                recent_avg_time = 0.0
                slow_query_rate = 0.0
            
            # Determine health status
            if error_rate > 10:
                health_status = "critical"
            elif error_rate > 5 or slow_query_rate > 20:
                health_status = "warning"
            elif recent_avg_time > 3000:  # 3 seconds
                health_status = "degraded"
            else:
                health_status = "healthy"
            
            return {
                'status': health_status,
                'error_rate_percent': round(error_rate, 2),
                'recent_average_processing_time_ms': round(recent_avg_time, 2),
                'slow_query_rate_percent': round(slow_query_rate, 2),
                'total_errors': total_errors,
                'uptime_seconds': time.time() - self._start_time
            }
    
    def start_prometheus_server(self, port: int = 8001) -> None:
        """Start Prometheus metrics server."""
        try:
            start_http_server(port)
            logger.info(f"Prometheus metrics server started on port {port}")
        except Exception as e:
            logger.error(f"Failed to start Prometheus server: {e}")
    
    def reset_metrics(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._recent_queries.clear()
            self._error_counts.clear()
            self._confidence_scores.clear()
            self._source_counts.clear()
            self._start_time = time.time()
