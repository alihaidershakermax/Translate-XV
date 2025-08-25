"""
Advanced caching system for translation results.
Supports both Redis and in-memory caching with fallback.
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta
import redis.asyncio as redis
from functools import lru_cache
import pickle
import zlib

logger = logging.getLogger(__name__)

class CacheKey:
    """Helper class for generating consistent cache keys"""
    
    @staticmethod
    def translation_key(text: str, source_lang: str, target_lang: str, text_type: str = "general") -> str:
        """Generate cache key for translation results"""
        # Create a hash of the input to handle long texts
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        return f"translation:{source_lang}:{target_lang}:{text_type}:{text_hash}"
    
    @staticmethod
    def user_quota_key(user_id: int, date: str = None) -> str:
        """Generate cache key for user quotas"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        return f"quota:user:{user_id}:{date}"
    
    @staticmethod
    def file_processing_key(file_hash: str) -> str:
        """Generate cache key for file processing results"""
        return f"file:processed:{file_hash}"
    
    @staticmethod
    def api_rate_limit_key(api_service: str, key_id: str) -> str:
        """Generate cache key for API rate limiting"""
        return f"rate_limit:{api_service}:{key_id}"

class InMemoryCache:
    """In-memory cache fallback when Redis is not available"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.access_times: Dict[str, float] = {}
    
    def _is_expired(self, key: str) -> bool:
        """Check if cache entry is expired"""
        if key not in self.cache:
            return True
        
        entry = self.cache[key]
        if 'expires_at' in entry:
            return time.time() > entry['expires_at']
        return False
    
    def _cleanup_expired(self):
        """Remove expired entries"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if 'expires_at' in entry and current_time > entry['expires_at']
        ]
        
        for key in expired_keys:
            self.cache.pop(key, None)
            self.access_times.pop(key, None)
    
    def _evict_lru(self):
        """Evict least recently used items if cache is full"""
        if len(self.cache) <= self.max_size:
            return
        
        # Sort by access time and remove oldest
        sorted_keys = sorted(self.access_times.items(), key=lambda x: x[1])
        keys_to_remove = [key for key, _ in sorted_keys[:len(self.cache) - self.max_size]]
        
        for key in keys_to_remove:
            self.cache.pop(key, None)
            self.access_times.pop(key, None)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        self._cleanup_expired()
        
        if self._is_expired(key):
            return None
        
        self.access_times[key] = time.time()
        entry = self.cache.get(key)
        return entry['value'] if entry else None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        self._cleanup_expired()
        self._evict_lru()
        
        expires_at = None
        if ttl is not None:
            expires_at = time.time() + ttl
        elif self.default_ttl:
            expires_at = time.time() + self.default_ttl
        
        self.cache[key] = {
            'value': value,
            'created_at': time.time(),
            'expires_at': expires_at
        }
        self.access_times[key] = time.time()
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        deleted = key in self.cache
        self.cache.pop(key, None)
        self.access_times.pop(key, None)
        return deleted
    
    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired"""
        return not self._is_expired(key)
    
    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()
        self.access_times.clear()
    
    async def cleanup_expired(self):
        """Public method to clean up expired entries"""
        self._cleanup_expired()

class AdvancedCacheSystem:
    """Advanced caching system with Redis and in-memory fallback"""
    
    def __init__(self, redis_url: Optional[str] = None, max_memory_cache_size: int = 1000, default_ttl: int = 3600):
        self.redis_client: Optional[redis.Redis] = None
        self.memory_cache = InMemoryCache(max_memory_cache_size, default_ttl)
        self.default_ttl = default_ttl
        self.redis_available = False
        
        if redis_url:
            self._setup_redis(redis_url)
    
    def _setup_redis(self, redis_url: str):
        """Setup Redis connection"""
        try:
            self.redis_client = redis.from_url(
                redis_url,
                encoding='utf-8',
                decode_responses=True,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30
            )
            logger.info("Redis cache initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis cache: {e}")
            self.redis_client = None
    
    async def _test_redis_connection(self) -> bool:
        """Test Redis connection health"""
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis connection test failed: {e}")
            return False
    
    async def get(self, key: str, use_compression: bool = False) -> Optional[Any]:
        """Get value from cache (Redis first, then memory fallback)"""
        # Try Redis first
        if self.redis_client:
            try:
                value = await self.redis_client.get(key)
                if value is not None:
                    if use_compression:
                        try:
                            # Decompress and unpickle
                            compressed_data = value.encode('latin-1')
                            decompressed_data = zlib.decompress(compressed_data)
                            return pickle.loads(decompressed_data)
                        except Exception as e:
                            logger.error(f"Failed to decompress cached value: {e}")
                            return None
                    else:
                        try:
                            return json.loads(value)
                        except json.JSONDecodeError:
                            return value
                    
            except Exception as e:
                logger.warning(f"Redis get failed for key {key}: {e}")
        
        # Fallback to memory cache
        return await self.memory_cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, use_compression: bool = False) -> bool:
        """Set value in cache (both Redis and memory)"""
        if ttl is None:
            ttl = self.default_ttl
        
        success = False
        
        # Try Redis first
        if self.redis_client:
            try:
                if use_compression:
                    # Pickle and compress for large objects
                    pickled_data = pickle.dumps(value)
                    compressed_data = zlib.compress(pickled_data)
                    redis_value = compressed_data.decode('latin-1')
                else:
                    # JSON serialize for simple objects
                    try:
                        redis_value = json.dumps(value)
                    except (TypeError, ValueError):
                        redis_value = str(value)
                
                await self.redis_client.setex(key, ttl, redis_value)
                success = True
                
            except Exception as e:
                logger.warning(f"Redis set failed for key {key}: {e}")
        
        # Always store in memory cache as well
        await self.memory_cache.set(key, value, ttl)
        return success or True  # Always return True if memory cache succeeded
    
    async def delete(self, key: str) -> bool:
        """Delete key from both caches"""
        redis_success = False
        memory_success = await self.memory_cache.delete(key)
        
        if self.redis_client:
            try:
                redis_success = bool(await self.redis_client.delete(key))
            except Exception as e:
                logger.warning(f"Redis delete failed for key {key}: {e}")
        
        return redis_success or memory_success
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in either cache"""
        # Check Redis first
        if self.redis_client:
            try:
                if await self.redis_client.exists(key):
                    return True
            except Exception as e:
                logger.warning(f"Redis exists check failed for key {key}: {e}")
        
        # Check memory cache
        return await self.memory_cache.exists(key)
    
    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Increment a numeric value (for rate limiting)"""
        if self.redis_client:
            try:
                pipeline = self.redis_client.pipeline()
                pipeline.incr(key, amount)
                if ttl:
                    pipeline.expire(key, ttl)
                results = await pipeline.execute()
                return results[0]
            except Exception as e:
                logger.warning(f"Redis increment failed for key {key}: {e}")
        
        # Memory cache fallback (simplified)
        current_value = await self.memory_cache.get(key) or 0
        new_value = int(current_value) + amount
        await self.memory_cache.set(key, new_value, ttl)
        return new_value
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            'redis_available': bool(self.redis_client and await self._test_redis_connection()),
            'memory_cache_size': len(self.memory_cache.cache),
            'memory_cache_max_size': self.memory_cache.max_size
        }
        
        if self.redis_client and stats['redis_available']:
            try:
                info = await self.redis_client.info('memory')
                stats.update({
                    'redis_memory_used': info.get('used_memory_human', 'N/A'),
                    'redis_connected_clients': info.get('connected_clients', 0)
                })
            except Exception as e:
                logger.warning(f"Failed to get Redis stats: {e}")
        
        return stats
    
    def clear_memory_cache(self):
        """Clear memory cache"""
        self.memory_cache.clear()
    
    async def close(self):
        """Close Redis connection properly"""
        if self.redis_client:
            try:
                await self.redis_client.aclose()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")
    
    async def cleanup_expired(self):
        """Clean up expired entries from memory cache"""
        try:
            await self.memory_cache.cleanup_expired()
            logger.debug("Memory cache cleanup completed")
        except Exception as e:
            logger.warning(f"Memory cache cleanup failed: {e}")
        logger.info("Memory cache cleared")

# Cache decorators for common use cases
def cache_translation(ttl: int = 3600):
    """Decorator to cache translation results"""
    def decorator(func):
        async def wrapper(self, text: str, source_lang: str = "auto", target_lang: str = "ar", text_type: str = "general", *args, **kwargs):
            if not hasattr(self, 'cache_system'):
                return await func(self, text, source_lang, target_lang, text_type, *args, **kwargs)
            
            cache_key = CacheKey.translation_key(text, source_lang, target_lang, text_type)
            
            # Try to get from cache
            cached_result = await self.cache_system.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for translation: {cache_key[:50]}...")
                return cached_result
            
            # Execute function and cache result
            result = await func(self, text, source_lang, target_lang, text_type, *args, **kwargs)
            if result:
                await self.cache_system.set(cache_key, result, ttl)
                logger.debug(f"Cached translation result: {cache_key[:50]}...")
            
            return result
        return wrapper
    return decorator

@lru_cache(maxsize=128)
def get_file_hash(file_content: bytes) -> str:
    """Generate hash for file content (with LRU cache for performance)"""
    return hashlib.sha256(file_content).hexdigest()