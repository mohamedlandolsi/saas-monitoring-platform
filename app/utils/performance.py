"""
Performance utilities for connection pooling, caching, and optimization.

This module provides:
- Connection pooling for Elasticsearch, MongoDB, and Redis
- Query result pagination
- Lazy loading for dashboard statistics
- Response compression utilities
- Query caching with TTL
"""

import time
import gzip
import json
import functools
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable
from flask import request, current_app
import redis
from pymongo import MongoClient
from elasticsearch import Elasticsearch


# Global connection pools
_es_pool = None
_mongo_pool = None
_redis_pool = None


class ConnectionPool:
    """Manages connection pools for external services."""
    
    def __init__(self):
        self.es_client = None
        self.mongo_client = None
        self.redis_client = None
        self._initialized = False
    
    def initialize(self, es_url: str, mongo_uri: str, redis_host: str, redis_port: int):
        """
        Initialize all connection pools.
        
        Args:
            es_url: Elasticsearch URL
            mongo_uri: MongoDB connection URI
            redis_host: Redis host
            redis_port: Redis port
        """
        if self._initialized:
            return
        
        # Elasticsearch with connection pooling
        self.es_client = Elasticsearch(
            [es_url],
            maxsize=25,  # Max connections in pool
            timeout=30,
            max_retries=3,
            retry_on_timeout=True
        )
        
        # MongoDB with connection pooling
        self.mongo_client = MongoClient(
            mongo_uri,
            maxPoolSize=50,  # Max connections
            minPoolSize=10,  # Min connections
            maxIdleTimeMS=60000,  # 60 seconds
            waitQueueTimeoutMS=5000,  # 5 seconds
            serverSelectionTimeoutMS=5000
        )
        
        # Redis connection pool
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True,
            max_connections=50,
            socket_timeout=5,
            socket_connect_timeout=5,
            health_check_interval=30
        )
        
        self._initialized = True
    
    def get_es_client(self) -> Elasticsearch:
        """Get Elasticsearch client from pool."""
        if not self._initialized:
            raise RuntimeError("Connection pool not initialized")
        return self.es_client
    
    def get_mongo_client(self) -> MongoClient:
        """Get MongoDB client from pool."""
        if not self._initialized:
            raise RuntimeError("Connection pool not initialized")
        return self.mongo_client
    
    def get_redis_client(self) -> redis.Redis:
        """Get Redis client from pool."""
        if not self._initialized:
            raise RuntimeError("Connection pool not initialized")
        return self.redis_client
    
    def close_all(self):
        """Close all connection pools."""
        if self.es_client:
            self.es_client.close()
        if self.mongo_client:
            self.mongo_client.close()
        if self.redis_client:
            self.redis_client.close()
        self._initialized = False


# Global connection pool instance
connection_pool = ConnectionPool()


def get_es_client() -> Elasticsearch:
    """Get Elasticsearch client from global pool."""
    return connection_pool.get_es_client()


def get_mongo_client() -> MongoClient:
    """Get MongoDB client from global pool."""
    return connection_pool.get_mongo_client()


def get_redis_client() -> redis.Redis:
    """Get Redis client from global pool."""
    return connection_pool.get_redis_client()


class QueryCache:
    """Cache for Elasticsearch query results with TTL."""
    
    def __init__(self, redis_client: redis.Redis, default_ttl: int = 300):
        """
        Initialize query cache.
        
        Args:
            redis_client: Redis client instance
            default_ttl: Default TTL in seconds (default: 5 minutes)
        """
        self.redis = redis_client
        self.default_ttl = default_ttl
        self.cache_prefix = "query_cache:"
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get cached query result.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        try:
            cached = self.redis.get(f"{self.cache_prefix}{key}")
            if cached:
                return json.loads(cached)
        except Exception as e:
            current_app.logger.error(f"Cache get error: {e}")
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Set cached query result.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses default if not provided)
        """
        try:
            ttl = ttl or self.default_ttl
            self.redis.setex(
                f"{self.cache_prefix}{key}",
                ttl,
                json.dumps(value, default=str)
            )
        except Exception as e:
            current_app.logger.error(f"Cache set error: {e}")
    
    def delete(self, key: str):
        """Delete cached query result."""
        try:
            self.redis.delete(f"{self.cache_prefix}{key}")
        except Exception as e:
            current_app.logger.error(f"Cache delete error: {e}")
    
    def clear_all(self):
        """Clear all cached queries."""
        try:
            keys = self.redis.keys(f"{self.cache_prefix}*")
            if keys:
                self.redis.delete(*keys)
        except Exception as e:
            current_app.logger.error(f"Cache clear error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            info = self.redis.info('stats')
            keys = len(self.redis.keys(f"{self.cache_prefix}*"))
            return {
                'total_keys': keys,
                'hits': info.get('keyspace_hits', 0),
                'misses': info.get('keyspace_misses', 0),
                'hit_rate': self._calculate_hit_rate(
                    info.get('keyspace_hits', 0),
                    info.get('keyspace_misses', 0)
                )
            }
        except Exception as e:
            current_app.logger.error(f"Cache stats error: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def _calculate_hit_rate(hits: int, misses: int) -> float:
        """Calculate cache hit rate percentage."""
        total = hits + misses
        return round((hits / total * 100) if total > 0 else 0, 2)


def cache_query(ttl: int = 300, key_func: Optional[Callable] = None):
    """
    Decorator to cache query results.
    
    Args:
        ttl: Cache TTL in seconds
        key_func: Function to generate cache key from args/kwargs
    
    Example:
        @cache_query(ttl=600)
        def get_logs(query, size):
            return es.search(...)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            redis_client = get_redis_client()
            cache = QueryCache(redis_client, ttl)
            cached_result = cache.get(cache_key)
            
            if cached_result is not None:
                current_app.logger.debug(f"Cache HIT: {cache_key}")
                return cached_result
            
            # Cache miss - execute function
            current_app.logger.debug(f"Cache MISS: {cache_key}")
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator


class Pagination:
    """Pagination helper for large result sets."""
    
    def __init__(self, page: int = 1, per_page: int = 50, max_per_page: int = 1000):
        """
        Initialize pagination.
        
        Args:
            page: Current page (1-indexed)
            per_page: Items per page
            max_per_page: Maximum allowed items per page
        """
        self.page = max(1, page)
        self.per_page = min(per_page, max_per_page)
        self.max_per_page = max_per_page
    
    @property
    def offset(self) -> int:
        """Get offset for query."""
        return (self.page - 1) * self.per_page
    
    @property
    def limit(self) -> int:
        """Get limit for query."""
        return self.per_page
    
    def paginate_es_query(self, query: Dict, total_hits: int) -> Dict:
        """
        Add pagination to Elasticsearch query.
        
        Args:
            query: Elasticsearch query dict
            total_hits: Total number of hits
            
        Returns:
            Pagination metadata
        """
        query['from'] = self.offset
        query['size'] = self.limit
        
        total_pages = (total_hits + self.per_page - 1) // self.per_page
        
        return {
            'page': self.page,
            'per_page': self.per_page,
            'total': total_hits,
            'total_pages': total_pages,
            'has_next': self.page < total_pages,
            'has_prev': self.page > 1
        }
    
    @staticmethod
    def from_request() -> 'Pagination':
        """Create pagination from Flask request args."""
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        return Pagination(page, per_page)


class ESQueryOptimizer:
    """Elasticsearch query optimization utilities."""
    
    @staticmethod
    def optimize_query(query: Dict, source_fields: Optional[List[str]] = None) -> Dict:
        """
        Optimize Elasticsearch query.
        
        Args:
            query: Original query dict
            source_fields: Fields to return (None = all fields)
            
        Returns:
            Optimized query dict
        """
        optimized = query.copy()
        
        # Add _source filtering
        if source_fields:
            optimized['_source'] = source_fields
        
        # Add track_total_hits for accurate counts
        if 'track_total_hits' not in optimized:
            optimized['track_total_hits'] = True
        
        return optimized
    
    @staticmethod
    def scroll_query(es_client: Elasticsearch, index: str, query: Dict, 
                     scroll: str = '2m', size: int = 1000) -> List[Dict]:
        """
        Use scroll API for large result sets.
        
        Args:
            es_client: Elasticsearch client
            index: Index name
            query: Query dict
            scroll: Scroll window (e.g., '2m')
            size: Batch size
            
        Returns:
            List of all documents
        """
        results = []
        
        # Initial search
        response = es_client.search(
            index=index,
            body=query,
            scroll=scroll,
            size=size
        )
        
        scroll_id = response['_scroll_id']
        hits = response['hits']['hits']
        results.extend(hits)
        
        # Scroll through results
        while hits:
            response = es_client.scroll(scroll_id=scroll_id, scroll=scroll)
            scroll_id = response['_scroll_id']
            hits = response['hits']['hits']
            results.extend(hits)
        
        # Clear scroll
        try:
            es_client.clear_scroll(scroll_id=scroll_id)
        except:
            pass
        
        return results


class LazyDashboardStats:
    """Lazy loading for dashboard statistics."""
    
    def __init__(self, es_client: Elasticsearch, index: str):
        """
        Initialize lazy stats loader.
        
        Args:
            es_client: Elasticsearch client
            index: Index name
        """
        self.es = es_client
        self.index = index
        self._cache = {}
    
    def get_stat(self, stat_name: str, query_func: Callable) -> Any:
        """
        Get statistic with lazy loading.
        
        Args:
            stat_name: Name of the statistic
            query_func: Function that executes the query
            
        Returns:
            Statistic value
        """
        if stat_name not in self._cache:
            self._cache[stat_name] = query_func()
        return self._cache[stat_name]
    
    def clear_cache(self):
        """Clear cached statistics."""
        self._cache.clear()


class ResponseCompression:
    """Response compression utilities."""
    
    @staticmethod
    def compress_json(data: Any, threshold: int = 1024) -> bytes:
        """
        Compress JSON data with gzip.
        
        Args:
            data: Data to compress
            threshold: Minimum size to compress (bytes)
            
        Returns:
            Compressed bytes or original JSON bytes
        """
        json_str = json.dumps(data, default=str)
        json_bytes = json_str.encode('utf-8')
        
        # Only compress if above threshold
        if len(json_bytes) < threshold:
            return json_bytes
        
        return gzip.compress(json_bytes, compresslevel=6)
    
    @staticmethod
    def should_compress(content_length: int, threshold: int = 1024) -> bool:
        """
        Check if response should be compressed.
        
        Args:
            content_length: Content length in bytes
            threshold: Minimum size to compress
            
        Returns:
            True if should compress
        """
        # Check Accept-Encoding header
        accept_encoding = request.headers.get('Accept-Encoding', '')
        supports_gzip = 'gzip' in accept_encoding.lower()
        
        return supports_gzip and content_length >= threshold


class PerformanceMonitor:
    """Monitor and track performance metrics."""
    
    def __init__(self, redis_client: redis.Redis):
        """
        Initialize performance monitor.
        
        Args:
            redis_client: Redis client for storing metrics
        """
        self.redis = redis_client
        self.metrics_prefix = "perf_metrics:"
        self.window_size = 3600  # 1 hour window
    
    def record_api_time(self, endpoint: str, duration: float):
        """Record API endpoint response time."""
        self._record_metric(f"api:{endpoint}", duration)
    
    def record_es_query_time(self, query_type: str, duration: float):
        """Record Elasticsearch query time."""
        self._record_metric(f"es:{query_type}", duration)
    
    def record_mongo_query_time(self, collection: str, duration: float):
        """Record MongoDB query time."""
        self._record_metric(f"mongo:{collection}", duration)
    
    def _record_metric(self, metric_key: str, value: float):
        """Record a metric value with timestamp."""
        try:
            key = f"{self.metrics_prefix}{metric_key}"
            timestamp = int(time.time())
            
            # Add to sorted set with timestamp as score
            self.redis.zadd(key, {f"{timestamp}:{value}": timestamp})
            
            # Remove old entries outside window
            min_timestamp = timestamp - self.window_size
            self.redis.zremrangebyscore(key, '-inf', min_timestamp)
            
            # Set expiry on the key
            self.redis.expire(key, self.window_size * 2)
        except Exception as e:
            current_app.logger.error(f"Error recording metric: {e}")
    
    def get_average_time(self, metric_prefix: str) -> Dict[str, float]:
        """
        Get average times for metrics matching prefix.
        
        Args:
            metric_prefix: Metric prefix (e.g., 'api:', 'es:', 'mongo:')
            
        Returns:
            Dict of metric names to average times
        """
        try:
            pattern = f"{self.metrics_prefix}{metric_prefix}*"
            keys = self.redis.keys(pattern)
            
            results = {}
            for key in keys:
                metric_name = key.replace(self.metrics_prefix, '')
                values = self.redis.zrange(key, 0, -1)
                
                if values:
                    times = [float(v.split(':')[1]) for v in values]
                    results[metric_name] = round(sum(times) / len(times), 2)
            
            return results
        except Exception as e:
            current_app.logger.error(f"Error getting average time: {e}")
            return {}
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all performance metrics."""
        return {
            'api_times': self.get_average_time('api:'),
            'es_query_times': self.get_average_time('es:'),
            'mongo_query_times': self.get_average_time('mongo:')
        }


def measure_time(metric_name: str, metric_type: str = 'api'):
    """
    Decorator to measure and record execution time.
    
    Args:
        metric_name: Name of the metric
        metric_type: Type of metric ('api', 'es', 'mongo')
    
    Example:
        @measure_time('search_logs', 'es')
        def search_logs():
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = (time.time() - start_time) * 1000  # Convert to ms
                
                # Record metric
                try:
                    redis_client = get_redis_client()
                    monitor = PerformanceMonitor(redis_client)
                    
                    if metric_type == 'api':
                        monitor.record_api_time(metric_name, duration)
                    elif metric_type == 'es':
                        monitor.record_es_query_time(metric_name, duration)
                    elif metric_type == 'mongo':
                        monitor.record_mongo_query_time(metric_name, duration)
                    
                    current_app.logger.info(
                        f"{metric_type.upper()} {metric_name}: {duration:.2f}ms"
                    )
                except Exception as e:
                    current_app.logger.error(f"Error recording time metric: {e}")
        
        return wrapper
    return decorator


# Export all public functions and classes
__all__ = [
    'ConnectionPool',
    'connection_pool',
    'get_es_client',
    'get_mongo_client',
    'get_redis_client',
    'QueryCache',
    'cache_query',
    'Pagination',
    'ESQueryOptimizer',
    'LazyDashboardStats',
    'ResponseCompression',
    'PerformanceMonitor',
    'measure_time'
]
