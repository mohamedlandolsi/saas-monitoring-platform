# Redis Caching Implementation

## Overview

The SaaS Monitoring Platform implements Redis-based caching to improve performance and reduce database/Elasticsearch query load. The caching system uses a decorator pattern for easy integration and automatic cache invalidation.

## Architecture

### Components

1. **CacheManager** (`app/utils/cache.py`): Core caching functionality
2. **cache_result** decorator: Automatic caching for Flask routes
3. **invalidate_cache** function: Manual cache invalidation
4. **Cache statistics**: Real-time monitoring of cache performance

## Cache Manager

### Initialization

```python
from utils.cache import CacheManager

cache_manager = CacheManager(redis_client)
app.cache_manager = cache_manager  # Attach to Flask app
```

### Methods

#### `get(key)`
Retrieve value from cache.

**Returns:** Cached value (dict) or None

#### `set(key, value, timeout)`
Store value in cache with TTL.

**Parameters:**
- `key` (str): Cache key
- `value` (any): Value to cache (JSON serializable)
- `timeout` (int): TTL in seconds

**Returns:** bool

#### `delete(key)`
Delete specific key from cache.

**Returns:** bool

#### `clear_pattern(pattern)`
Clear all keys matching pattern (e.g., "search:*").

**Returns:** int (number of keys deleted)

#### `get_stats()`
Get cache hit/miss statistics.

**Returns:** dict with hits, misses, total_requests, hit_rate_percent

#### `reset_stats()`
Reset cache statistics counters.

---

## cache_result Decorator

Automatic caching decorator for Flask routes.

### Usage

```python
from utils.cache import cache_result

@app.route('/api/stats')
@cache_result(timeout=60, key_prefix="stats")
def get_stats():
    return jsonify({'total': 100})
```

### Parameters

- `timeout` (int): Cache TTL in seconds (default: 300)
- `key_prefix` (str): Cache key prefix (default: "cache")

### How It Works

1. Generates unique cache key from:
   - Function name
   - Request method and path
   - Query parameters
   - Request body (JSON)
   - Function arguments

2. Checks cache for existing value
3. On cache HIT: Returns cached data
4. On cache MISS: Executes function, caches result, returns data

### Key Generation

Cache keys are generated as: `{prefix}:{func_name}:{hash}`

Example: `stats:get_stats:5d8782ea43cb739f357f783bf8902624`

The hash includes:
- Function name
- HTTP method and path
- Query parameters
- Request body
- Function arguments

---

## Cached Endpoints

### GET /api/stats

**Cache Duration:** 60 seconds  
**Cache Key Prefix:** `stats`

Statistics are expensive to compute (multiple Elasticsearch aggregations), so we cache for 1 minute.

```python
@app.route('/api/stats')
@cache_result(timeout=60, key_prefix="stats")
def get_stats():
    # Expensive Elasticsearch queries
    return jsonify(stats)
```

**Cache Behavior:**
- First request: Queries Elasticsearch (~2-3 seconds)
- Subsequent requests within 60s: Instant response from cache
- Auto-refresh after 60 seconds

### POST /api/search

**Cache Duration:** 300 seconds (5 minutes)  
**Cache Key Prefix:** `search`

Search queries are cached based on query parameters including text, filters, and pagination.

```python
@app.route('/api/search', methods=['POST'])
@cache_result(timeout=300, key_prefix="search")
def search_logs():
    # Search Elasticsearch
    return jsonify(results)
```

**Cache Behavior:**
- Same query + filters = cached result
- Different query parameters = new cache entry
- Pagination is part of cache key
- Cache expires after 5 minutes

**Example:**
```bash
# First request - MISS (takes ~300ms)
curl -X POST /api/search -d '{"q": "error", "level": "ERROR"}'

# Second request - HIT (takes ~5ms)
curl -X POST /api/search -d '{"q": "error", "level": "ERROR"}'
```

### GET /api/files

**Cache Duration:** 600 seconds (10 minutes)  
**Cache Key Prefix:** `files`

File list is relatively static and expensive to compute statistics.

```python
@app.route('/api/files', methods=['GET'])
@cache_result(timeout=600, key_prefix="files")
def get_files():
    files = file_model.get_all()
    stats = file_model.get_statistics()
    return jsonify({'files': files, 'stats': stats})
```

**Cache Invalidation:**
- Automatically invalidated after file upload
- Automatically invalidated after file deletion

---

## Cache Invalidation

### Automatic Invalidation

The files cache is automatically invalidated on changes:

```python
# In upload endpoint
invalidate_cache("files")

# In delete endpoint
invalidate_cache("files")
```

### Manual Invalidation

```python
from utils.cache import invalidate_cache

# Clear all files cache
invalidate_cache("files")  # Deletes all "files:*" keys

# Clear all search cache
invalidate_cache("search")  # Deletes all "search:*" keys

# Clear all stats cache
invalidate_cache("stats")   # Deletes all "stats:*" keys
```

### Implementation

```python
def invalidate_cache(key_prefix: str):
    """Clear all cache keys with given prefix"""
    pattern = f"{key_prefix}:*"
    deleted = cache_manager.clear_pattern(pattern)
    print(f"Invalidated {deleted} cache keys with pattern: {pattern}")
    return deleted
```

---

## Cache Statistics

### GET /api/cache/stats

Retrieve cache performance metrics.

**Response:**
```json
{
  "success": true,
  "cache_stats": {
    "hits": 8,
    "misses": 8,
    "total_requests": 16,
    "hit_rate_percent": 50.0
  },
  "redis_info": {
    "total_connections_received": 123,
    "total_commands_processed": 418,
    "keyspace_hits": 8,
    "keyspace_misses": 14,
    "redis_hit_rate_percent": 36.36,
    "used_memory_human": "1.09M"
  }
}
```

### Metrics

**Application-level Stats (cache_stats):**
- `hits`: Number of cache hits
- `misses`: Number of cache misses
- `total_requests`: Total cached requests
- `hit_rate_percent`: Cache hit rate percentage

**Redis-level Stats (redis_info):**
- `keyspace_hits`: Redis keyspace hits
- `keyspace_misses`: Redis keyspace misses
- `redis_hit_rate_percent`: Overall Redis hit rate
- `total_commands_processed`: Total Redis commands
- `total_connections_received`: Total Redis connections
- `used_memory_human`: Redis memory usage

### Example Usage

```bash
curl http://localhost:5000/api/cache/stats
```

---

## Performance Impact

### Before Caching

| Endpoint | Average Response Time |
|----------|----------------------|
| GET /api/stats | ~2500ms |
| POST /api/search | ~300ms |
| GET /api/files | ~150ms |

### After Caching (Cache HIT)

| Endpoint | Average Response Time | Improvement |
|----------|----------------------|-------------|
| GET /api/stats | ~5ms | **500x faster** |
| POST /api/search | ~5ms | **60x faster** |
| GET /api/files | ~5ms | **30x faster** |

### Cache Hit Rates (Expected)

- `/api/stats`: ~90% (refreshed every 60s, but requested frequently)
- `/api/search`: ~70% (common queries cached, but many unique queries)
- `/api/files`: ~95% (rarely changes, long TTL)

---

## Best Practices

### 1. Choose Appropriate TTL

```python
# Frequently changing data - short TTL
@cache_result(timeout=30, key_prefix="live_data")

# Relatively static data - medium TTL
@cache_result(timeout=300, key_prefix="search")

# Rarely changing data - long TTL
@cache_result(timeout=3600, key_prefix="config")
```

### 2. Invalidate on Mutations

Always invalidate cache when data changes:

```python
@app.route('/api/items', methods=['POST'])
def create_item():
    # Create item
    item_id = create_new_item()
    
    # Invalidate cache
    invalidate_cache("items")
    
    return jsonify({'id': item_id})
```

### 3. Use Descriptive Key Prefixes

```python
# Good - clear what's cached
@cache_result(key_prefix="user_profile")
@cache_result(key_prefix="product_list")

# Bad - unclear
@cache_result(key_prefix="data1")
@cache_result(key_prefix="cache")
```

### 4. Monitor Cache Performance

Regularly check `/api/cache/stats` to:
- Verify high hit rates
- Identify cold cache issues
- Adjust TTL values
- Detect memory issues

### 5. Handle Cache Failures Gracefully

The cache decorator automatically falls back to executing the function if Redis is unavailable:

```python
if not cache_manager:
    # Redis unavailable - execute function directly
    return func(*args, **kwargs)
```

---

## Testing

### Test Cache HITs and MISSes

```bash
# First request - MISS
curl http://localhost:5000/api/stats

# Check logs
docker-compose logs webapp --tail 5 | grep Cache
# Output: Cache MISS: stats:get_stats:...

# Second request - HIT
curl http://localhost:5000/api/stats

# Check logs
# Output: Cache HIT: stats:get_stats:...
```

### Test Cache Invalidation

```bash
# Request files (MISS)
curl http://localhost:5000/api/files

# Request again (HIT)
curl http://localhost:5000/api/files

# Upload new file (invalidates cache)
curl -X POST /api/upload -F "file=@test.json"

# Check logs
# Output: Invalidated 1 cache keys with pattern: files:*

# Request files again (MISS - cache was invalidated)
curl http://localhost:5000/api/files
```

### Test Different Query Parameters

```bash
# First search
curl -X POST /api/search -d '{"q": "error"}'
# Cache MISS

# Same search
curl -X POST /api/search -d '{"q": "error"}'
# Cache HIT

# Different search
curl -X POST /api/search -d '{"q": "warning"}'
# Cache MISS (different query)
```

---

## Troubleshooting

### Cache Not Working

**Problem:** No cache hits, all requests are misses

**Solutions:**
1. Check Redis connection:
   ```bash
   docker-compose logs redis
   docker-compose logs webapp | grep "Connected to Redis"
   ```

2. Verify cache manager initialization:
   ```bash
   docker-compose logs webapp | grep "Cache manager initialized"
   ```

3. Check decorator is applied:
   ```python
   @app.route('/api/endpoint')
   @cache_result(timeout=60, key_prefix="endpoint")  # Must be here
   def my_endpoint():
       pass
   ```

### Low Hit Rate

**Problem:** Hit rate < 30%

**Causes:**
- TTL too short (cache expires before reuse)
- Too many unique queries (search with many variations)
- High traffic with cold cache

**Solutions:**
1. Increase TTL for stable data
2. Warm up cache on startup
3. Add cache preloading for common queries

### Memory Issues

**Problem:** Redis using too much memory

**Solutions:**
1. Reduce TTL values
2. Limit cache size:
   ```python
   # Redis configuration
   maxmemory 256mb
   maxmemory-policy allkeys-lru
   ```

3. Clear old cache entries:
   ```python
   invalidate_cache("search")  # Clear all search cache
   ```

### Cache Stampede

**Problem:** Many requests hit at once when cache expires

**Solution:** Implement cache warming or use probabilistic early expiration:
```python
# Add jitter to TTL
import random
timeout = 300 + random.randint(-30, 30)
@cache_result(timeout=timeout, key_prefix="stats")
```

---

## Advanced Usage

### Custom Cache Keys

For more control over cache keys, use the CacheManager directly:

```python
@app.route('/api/custom')
def custom_endpoint():
    user_id = request.args.get('user_id')
    cache_key = f"custom:user:{user_id}"
    
    # Try cache
    cached = cache_manager.get(cache_key)
    if cached:
        return jsonify(cached)
    
    # Compute result
    result = expensive_computation(user_id)
    
    # Store in cache
    cache_manager.set(cache_key, result, timeout=600)
    
    return jsonify(result)
```

### Conditional Caching

Cache only for specific conditions:

```python
@app.route('/api/data')
def get_data():
    cache_enabled = request.args.get('cache', 'true') == 'true'
    
    if cache_enabled:
        @cache_result(timeout=300, key_prefix="data")
        def get_cached_data():
            return fetch_data()
        return get_cached_data()
    else:
        return jsonify(fetch_data())
```

---

## Future Enhancements

1. **Cache Warming**: Preload common queries on startup
2. **Smart Invalidation**: Selective invalidation instead of clearing all keys
3. **Cache Compression**: Compress large cached values
4. **Distributed Caching**: Multiple Redis instances with sharding
5. **Cache Analytics**: Detailed metrics per endpoint
6. **Automatic TTL Adjustment**: ML-based optimal TTL calculation
7. **Cache Versioning**: Handle cache format changes gracefully
