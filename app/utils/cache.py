"""
Redis caching utilities for the SaaS Monitoring Platform
"""
import json
import hashlib
import functools
from typing import Any, Optional, Callable
from flask import request


class CacheManager:
    """Manager for Redis caching operations"""
    
    def __init__(self, redis_client):
        """
        Initialize cache manager with Redis client
        
        Args:
            redis_client: Redis client instance
        """
        self.redis = redis_client
        self.stats = {
            'hits': 0,
            'misses': 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None if not found
        """
        if not self.redis:
            return None
        
        try:
            value = self.redis.get(key)
            if value:
                self.stats['hits'] += 1
                return json.loads(value)
            else:
                self.stats['misses'] += 1
                return None
        except Exception as e:
            print(f"Cache get error: {str(e)}")
            self.stats['misses'] += 1
            return None
    
    def set(self, key: str, value: Any, timeout: int = 300) -> bool:
        """
        Set value in cache with timeout
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            timeout: TTL in seconds (default: 300)
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.redis:
            return False
        
        try:
            serialized = json.dumps(value)
            self.redis.setex(key, timeout, serialized)
            return True
        except Exception as e:
            print(f"Cache set error: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete key from cache
        
        Args:
            key: Cache key to delete
        
        Returns:
            bool: True if deleted, False otherwise
        """
        if not self.redis:
            return False
        
        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            print(f"Cache delete error: {str(e)}")
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching pattern
        
        Args:
            pattern: Pattern to match (e.g., "search:*")
        
        Returns:
            int: Number of keys deleted
        """
        if not self.redis:
            return 0
        
        try:
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
                return len(keys)
            return 0
        except Exception as e:
            print(f"Cache clear pattern error: {str(e)}")
            return 0
    
    def get_stats(self) -> dict:
        """
        Get cache statistics
        
        Returns:
            dict: Statistics including hits, misses, and hit rate
        """
        total = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total * 100) if total > 0 else 0
        
        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'total_requests': total,
            'hit_rate_percent': round(hit_rate, 2)
        }
    
    def reset_stats(self):
        """Reset cache statistics"""
        self.stats = {
            'hits': 0,
            'misses': 0
        }


def cache_result(timeout: int = 300, key_prefix: str = "cache"):
    """
    Decorator to cache function results in Redis
    
    Args:
        timeout: TTL in seconds (default: 300)
        key_prefix: Prefix for cache key (default: "cache")
    
    Usage:
        @cache_result(timeout=60, key_prefix="stats")
        def get_statistics():
            return {'total': 100}
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get cache manager from app context
            from flask import current_app, jsonify
            cache_manager = getattr(current_app, 'cache_manager', None)
            
            if not cache_manager:
                # If cache not available, call function directly
                return func(*args, **kwargs)
            
            # Generate cache key based on function name and arguments
            cache_key = _generate_cache_key(key_prefix, func.__name__, args, kwargs)
            
            # Try to get from cache
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                print(f"Cache HIT: {cache_key}")
                # Return the cached data wrapped in jsonify
                return jsonify(cached_value)
            
            # Cache miss - call function
            print(f"Cache MISS: {cache_key}")
            result = func(*args, **kwargs)
            
            # Extract data from Flask Response if needed
            if hasattr(result, 'get_json'):
                # It's a Flask Response, extract the JSON data
                data_to_cache = result.get_json()
                cache_manager.set(cache_key, data_to_cache, timeout)
            elif isinstance(result, tuple):
                # Handle (response, status_code) tuples
                response_obj = result[0]
                if hasattr(response_obj, 'get_json'):
                    data_to_cache = response_obj.get_json()
                    cache_manager.set(cache_key, data_to_cache, timeout)
            else:
                # Try to cache as-is (should be a dict)
                try:
                    cache_manager.set(cache_key, result, timeout)
                except:
                    print(f"Warning: Could not cache result for {cache_key}")
            
            return result
        
        return wrapper
    return decorator


def _generate_cache_key(prefix: str, func_name: str, args: tuple, kwargs: dict) -> str:
    """
    Generate cache key from function name and arguments
    
    Args:
        prefix: Key prefix
        func_name: Function name
        args: Positional arguments
        kwargs: Keyword arguments
    
    Returns:
        str: Cache key
    """
    # Get request data if available (for Flask routes)
    try:
        if request:
            # Include request method and path
            request_data = {
                'method': request.method,
                'path': request.path,
                'args': request.args.to_dict(),
                'json': request.get_json(silent=True) or {}
            }
            key_data = {
                'func': func_name,
                'args': args,
                'kwargs': kwargs,
                'request': request_data
            }
        else:
            key_data = {
                'func': func_name,
                'args': args,
                'kwargs': kwargs
            }
    except:
        # If request context not available
        key_data = {
            'func': func_name,
            'args': args,
            'kwargs': kwargs
        }
    
    # Create hash of key data
    key_string = json.dumps(key_data, sort_keys=True, default=str)
    key_hash = hashlib.md5(key_string.encode()).hexdigest()
    
    return f"{prefix}:{func_name}:{key_hash}"


def invalidate_cache(key_prefix: str):
    """
    Invalidate all cache keys with given prefix
    
    Args:
        key_prefix: Prefix to match (e.g., "files")
    
    Usage:
        invalidate_cache("files")  # Clears all "files:*" keys
    """
    from flask import current_app
    cache_manager = getattr(current_app, 'cache_manager', None)
    
    if cache_manager:
        pattern = f"{key_prefix}:*"
        deleted = cache_manager.clear_pattern(pattern)
        print(f"Invalidated {deleted} cache keys with pattern: {pattern}")
        return deleted
    
    return 0
