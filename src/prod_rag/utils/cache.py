"""
Redis-based caching for the RAG pipeline.
"""

import json
import logging
from typing import Any, Dict, Optional
import redis.asyncio as redis
import hashlib

from ..core.config import Settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis-based cache manager for RAG responses."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.redis_client: Optional[redis.Redis] = None
        self.connected = False
    
    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            self.redis_client = redis.from_url(
                self.settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Test connection
            await self.redis_client.ping()
            self.connected = True
            logger.info("Connected to Redis cache")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connected = False
            raise
    
    def _get_cache_key(self, query: str) -> str:
        """Generate cache key from query."""
        # Create hash of query for consistent key
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return f"rag_query:{query_hash}"
    
    async def get(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Get cached response for a query.
        
        Args:
            query: Query string
            
        Returns:
            Cached response or None if not found
        """
        if not self.connected:
            await self.connect()
        
        try:
            cache_key = self._get_cache_key(query)
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached data: {e}")
            return None
    
    async def set(
        self, 
        query: str, 
        response: Dict[str, Any], 
        ttl: int = 3600
    ) -> bool:
        """
        Cache a response for a query.
        
        Args:
            query: Query string
            response: Response data to cache
            ttl: Time to live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            await self.connect()
        
        try:
            cache_key = self._get_cache_key(query)
            cached_data = json.dumps(response, default=str)
            
            await self.redis_client.setex(
                cache_key, 
                ttl, 
                cached_data
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error caching data: {e}")
            return False
    
    async def delete(self, query: str) -> bool:
        """
        Delete cached response for a query.
        
        Args:
            query: Query string
            
        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            await self.connect()
        
        try:
            cache_key = self._get_cache_key(query)
            result = await self.redis_client.delete(cache_key)
            return result > 0
            
        except Exception as e:
            logger.error(f"Error deleting cached data: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """
        Clear cache entries matching a pattern.
        
        Args:
            pattern: Pattern to match (e.g., "user:*")
            
        Returns:
            Number of deleted keys
        """
        if not self.connected:
            await self.connect()
        
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                return await self.redis_client.delete(*keys)
            return 0
            
        except Exception as e:
            logger.error(f"Error clearing cache pattern: {e}")
            return 0
    
    async def clear_all(self) -> bool:
        """
        Clear all cache entries.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            await self.connect()
        
        try:
            await self.redis_client.flushdb()
            return True
            
        except Exception as e:
            logger.error(f"Error clearing all cache: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.connected:
            await self.connect()
        
        try:
            info = await self.redis_client.info()
            
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on cache."""
        try:
            if not self.connected:
                await self.connect()
            
            # Test basic operation
            test_key = "health_check"
            await self.redis_client.setex(test_key, 10, "test")
            result = await self.redis_client.get(test_key)
            await self.redis_client.delete(test_key)
            
            if result == "test":
                stats = await self.get_stats()
                return {
                    "status": "healthy",
                    "stats": stats
                }
            else:
                return {"status": "error", "message": "Test operation failed"}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def close(self) -> None:
        """Close Redis connection."""
        try:
            if self.redis_client:
                await self.redis_client.close()
            self.connected = False
            logger.info("Closed Redis connection")
            
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
