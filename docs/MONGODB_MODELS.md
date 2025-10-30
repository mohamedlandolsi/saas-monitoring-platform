# MongoDB Models Documentation

## Overview

The SaaS Monitoring Platform uses MongoDB models to manage file metadata and search history. Two main model classes provide abstraction for database operations.

## Models

### 1. File Model (`app/models/file.py`)

Manages uploaded file metadata in MongoDB.

#### Initialization

```python
from models.file import File

file_model = File(mongo_client)
```

#### Methods

##### `create(filename, saved_as, file_type, file_size, log_count=0, status='pending', metadata=None)`

Create a new file document.

**Parameters:**
- `filename` (str): Original filename
- `saved_as` (str): Unique filename saved on disk
- `file_type` (str): File type (csv, json)
- `file_size` (int): Size in bytes
- `log_count` (int): Number of logs in file (default: 0)
- `status` (str): Upload status - pending, processing, completed, error (default: 'pending')
- `metadata` (dict): Additional metadata (optional)

**Returns:** `str` - MongoDB document ID

**Example:**
```python
file_id = file_model.create(
    filename='logs.csv',
    saved_as='20251030_120000_logs.csv',
    file_type='csv',
    file_size=1024,
    log_count=100,
    status='completed'
)
```

##### `get_all(sort_by='upload_date', ascending=False)`

Get all files sorted by specified field.

**Parameters:**
- `sort_by` (str): Field to sort by (default: 'upload_date')
- `ascending` (bool): Sort direction (default: False for descending)

**Returns:** `List[Dict]` - List of file documents

**Example:**
```python
files = file_model.get_all()
# Returns: [{'_id': '...', 'filename': '...', ...}, ...]
```

##### `get_by_id(file_id)`

Get a single file by ID.

**Parameters:**
- `file_id` (str): MongoDB ObjectId as string

**Returns:** `Dict` or `None` - File document or None if not found

**Example:**
```python
file = file_model.get_by_id('6903769e89e1374b4852a435')
# Returns: {'_id': '...', 'filename': '...', ...}
```

##### `delete(file_id)`

Delete a file document from MongoDB.

**Parameters:**
- `file_id` (str): MongoDB ObjectId as string

**Returns:** `bool` - True if deleted, False otherwise

**Example:**
```python
success = file_model.delete('6903769e89e1374b4852a435')
```

##### `update_status(file_id, status, log_count=None)`

Update file status and optionally log count.

**Parameters:**
- `file_id` (str): MongoDB ObjectId as string
- `status` (str): New status (pending, processing, completed, error)
- `log_count` (int): Optional log count to update

**Returns:** `bool` - True if updated, False otherwise

**Example:**
```python
success = file_model.update_status(
    file_id='6903769e89e1374b4852a435',
    status='completed',
    log_count=150
)
```

##### `get_statistics()`

Get file statistics.

**Returns:** `Dict` - Statistics including total files, logs, and size

**Example:**
```python
stats = file_model.get_statistics()
# Returns: {'total_files': 5, 'total_logs': 1000, 'total_size': 50000}
```

##### `get_by_status(status)`

Get files filtered by status.

**Parameters:**
- `status` (str): File status to filter by

**Returns:** `List[Dict]` - List of matching file documents

**Example:**
```python
completed_files = file_model.get_by_status('completed')
```

##### `count()`

Get total count of files.

**Returns:** `int` - Total number of files

**Example:**
```python
total = file_model.count()
```

---

### 2. SearchHistory Model (`app/models/search_history.py`)

Tracks search queries and provides analytics.

#### Initialization

```python
from models.search_history import SearchHistory

search_history_model = SearchHistory(mongo_client)
```

The model automatically creates indexes on `timestamp` and `(user, timestamp)` for performance.

#### Methods

##### `save(query, filters, user=None, results_count=0, execution_time_ms=None)`

Save a search query to history.

**Parameters:**
- `query` (str): Search query text
- `filters` (dict): Applied filters (level, status_code, server, etc.)
- `user` (str): User identifier (optional, defaults to 'anonymous')
- `results_count` (int): Number of results returned (default: 0)
- `execution_time_ms` (float): Query execution time in milliseconds (optional)

**Returns:** `str` - MongoDB document ID or None on error

**Example:**
```python
search_id = search_history_model.save(
    query='error database',
    filters={'level': 'ERROR', 'status_code': '5XX'},
    user='192.168.1.1',
    results_count=1428,
    execution_time_ms=289.27
)
```

##### `get_recent(limit=10, user=None)`

Get recent search queries.

**Parameters:**
- `limit` (int): Maximum number of results to return (default: 10)
- `user` (str): Optional user filter

**Returns:** `List[Dict]` - List of search history documents

**Example:**
```python
recent_searches = search_history_model.get_recent(limit=20)
# Returns: [{'_id': '...', 'query': '...', 'filters': {...}, ...}, ...]
```

##### `get_by_user(user, limit=50)`

Get search history for a specific user.

**Parameters:**
- `user` (str): User identifier
- `limit` (int): Maximum number of results (default: 50)

**Returns:** `List[Dict]` - List of search history documents

**Example:**
```python
user_searches = search_history_model.get_by_user('192.168.1.1', limit=100)
```

##### `get_popular_queries(limit=10, days=7)`

Get most popular search queries.

**Parameters:**
- `limit` (int): Maximum number of results (default: 10)
- `days` (int): Number of days to look back (default: 7)

**Returns:** `List[Dict]` - List of popular queries with counts

**Example:**
```python
popular = search_history_model.get_popular_queries(limit=5, days=30)
# Returns: [
#   {'_id': 'error', 'count': 45, 'avg_results': 520, 'last_used': '...'},
#   ...
# ]
```

##### `get_statistics(days=30)`

Get search statistics.

**Parameters:**
- `days` (int): Number of days to analyze (default: 30)

**Returns:** `Dict` - Statistics including total searches, unique users, etc.

**Example:**
```python
stats = search_history_model.get_statistics(days=7)
# Returns: {
#   'total_searches': 150,
#   'unique_users': 5,
#   'avg_results': 450.5,
#   'avg_execution_time_ms': 320.5,
#   'period_days': 7
# }
```

##### `delete_old_searches(days=90)`

Delete old search history entries.

**Parameters:**
- `days` (int): Delete entries older than this many days (default: 90)

**Returns:** `int` - Number of deleted documents

**Example:**
```python
deleted_count = search_history_model.delete_old_searches(days=180)
```

##### `get_by_date_range(start_date, end_date, user=None)`

Get searches within a date range.

**Parameters:**
- `start_date` (str): Start date (ISO format)
- `end_date` (str): End date (ISO format)
- `user` (str): Optional user filter

**Returns:** `List[Dict]` - List of search history documents

**Example:**
```python
searches = search_history_model.get_by_date_range(
    start_date='2025-10-01T00:00:00',
    end_date='2025-10-31T23:59:59',
    user='192.168.1.1'
)
```

---

## API Endpoints

### File Management Endpoints

#### GET /api/files

Get all uploaded files with statistics.

**Response:**
```json
{
  "success": true,
  "files": [
    {
      "_id": "6903769e89e1374b4852a435",
      "filename": "logs.json",
      "saved_as": "20251030_143054_logs.json",
      "file_type": "json",
      "file_size": 173,
      "upload_date": "2025-10-30T14:30:54.200028",
      "status": "completed",
      "log_count": 2
    }
  ],
  "stats": {
    "total_files": 6,
    "total_logs": 13,
    "total_size": 1241
  }
}
```

#### POST /api/upload

Upload a file (uses File model internally).

**Response:**
```json
{
  "success": true,
  "file_id": "6903769e89e1374b4852a435",
  "message": "File uploaded successfully: logs.json",
  "details": {
    "filename": "logs.json",
    "saved_as": "20251030_143054_logs.json",
    "file_size": 173,
    "log_count": 2,
    "upload_date": "2025-10-30T14:30:54.200028"
  }
}
```

#### DELETE /api/files/<file_id>

Delete a file (uses File model internally).

**Response:**
```json
{
  "success": true,
  "message": "File logs.json deleted successfully"
}
```

### Search History Endpoints

#### GET /api/search/history

Get recent search queries.

**Query Parameters:**
- `limit` (int): Maximum results (default: 10, max: 100)
- `user` (str): Filter by user (optional)

**Example:**
```bash
curl "http://localhost:5000/api/search/history?limit=5&user=192.168.1.1"
```

**Response:**
```json
{
  "success": true,
  "count": 2,
  "searches": [
    {
      "_id": "690375e189e1374b4852a433",
      "query": "database",
      "filters": {
        "page": 1,
        "per_page": 10,
        "status_code": "5XX"
      },
      "user": "172.20.0.1",
      "results_count": 1428,
      "execution_time_ms": 289.27,
      "timestamp": "2025-10-30T14:27:45.200669",
      "date": "2025-10-30"
    }
  ]
}
```

#### GET /api/search/history/popular

Get most popular search queries.

**Query Parameters:**
- `limit` (int): Maximum results (default: 10, max: 50)
- `days` (int): Days to look back (default: 7, max: 90)

**Example:**
```bash
curl "http://localhost:5000/api/search/history/popular?limit=5&days=30"
```

**Response:**
```json
{
  "success": true,
  "count": 2,
  "popular_queries": [
    {
      "_id": "error",
      "count": 1,
      "avg_results": 518.0,
      "last_used": "2025-10-30T14:25:16.780998"
    }
  ]
}
```

#### GET /api/search/history/stats

Get search statistics.

**Query Parameters:**
- `days` (int): Days to analyze (default: 30, max: 365)

**Example:**
```bash
curl "http://localhost:5000/api/search/history/stats?days=7"
```

**Response:**
```json
{
  "success": true,
  "statistics": {
    "total_searches": 2,
    "unique_users": 1,
    "avg_results": 973.0,
    "avg_execution_time_ms": 313.87,
    "period_days": 7
  }
}
```

---

## Database Schema

### Files Collection (`saas_monitoring.files`)

```javascript
{
  "_id": ObjectId,
  "filename": String,           // Original filename
  "saved_as": String,           // Unique filename on disk
  "file_type": String,          // "csv" or "json"
  "file_size": Number,          // Size in bytes
  "log_count": Number,          // Number of logs processed
  "status": String,             // "pending", "processing", "completed", "error"
  "upload_date": String,        // ISO 8601 timestamp
  "updated_at": String,         // ISO 8601 timestamp
  "metadata": Object            // Additional metadata
}
```

### Search History Collection (`saas_monitoring.search_history`)

```javascript
{
  "_id": ObjectId,
  "query": String,              // Search query text
  "filters": Object,            // Applied filters
  "user": String,               // User identifier
  "results_count": Number,      // Number of results
  "execution_time_ms": Number,  // Query execution time
  "timestamp": String,          // ISO 8601 timestamp
  "date": String                // Date only (YYYY-MM-DD)
}
```

**Indexes:**
- `timestamp`: Descending index for recent queries
- `user, timestamp`: Compound index for user-specific queries

---

## Integration Examples

### Upload Flow with File Model

```python
# In upload endpoint
file_id = file_model.create(
    filename=original_filename,
    saved_as=unique_filename,
    file_type=file_extension,
    file_size=file_size,
    log_count=log_count,
    status='completed'
)
```

### Search Flow with SearchHistory Model

```python
# In search endpoint
start_time = time.time()
response = es_client.search(index='saas-logs-*', body=search_body)
execution_time_ms = (time.time() - start_time) * 1000

# Save search history
search_history_model.save(
    query=q,
    filters={'level': level, 'status_code': status_code, ...},
    user=request.remote_addr,
    results_count=total,
    execution_time_ms=execution_time_ms
)
```

---

## Best Practices

### File Model

1. **Always set status**: Start with 'pending', update to 'processing', then 'completed' or 'error'
2. **Update log count**: After processing, update with actual count using `update_status()`
3. **Clean up on error**: If upload fails, delete both file and database record
4. **Use transactions**: For critical operations, consider MongoDB transactions

### SearchHistory Model

1. **Clean old data**: Periodically run `delete_old_searches()` to remove old entries
2. **Anonymous users**: Default to 'anonymous' or IP address for unauthenticated users
3. **Performance**: Use indexed fields (timestamp, user) in queries
4. **Analytics**: Combine with date range queries for detailed analysis

---

## Testing

### Test File Model

```bash
# Get all files
curl http://localhost:5000/api/files

# Upload file
curl -X POST http://localhost:5000/api/upload -F "file=@test.json"

# Delete file
curl -X DELETE http://localhost:5000/api/files/<file_id>
```

### Test SearchHistory Model

```bash
# Perform search (automatically saves history)
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"q": "error", "level": "ERROR"}'

# Get search history
curl "http://localhost:5000/api/search/history?limit=10"

# Get popular queries
curl "http://localhost:5000/api/search/history/popular?days=7"

# Get statistics
curl "http://localhost:5000/api/search/history/stats?days=30"
```

---

## Troubleshooting

### Model Not Initialized

**Error:** `File model not available` or `Search history not available`

**Solution:**
1. Check MongoDB connection: `docker-compose logs mongodb`
2. Verify models initialization in logs: Look for "✓ Models initialized successfully"
3. Restart webapp: `docker-compose restart webapp`

### Slow Queries

**Problem:** Search history queries are slow

**Solution:**
1. Check indexes exist: Run SearchHistory `__init__` to create indexes
2. Limit result sets: Use `limit` parameter in queries
3. Add date filters: Use `get_by_date_range()` instead of `get_recent()` for large datasets

### Missing Data

**Problem:** Search history not saving

**Solution:**
1. Check SearchHistory model initialization
2. Verify search endpoint is being called
3. Check for exceptions in logs
4. Ensure MongoDB write permissions

---

## Future Enhancements

1. **File Model:**
   - Add file validation before upload
   - Implement file versioning
   - Add file tagging/categorization
   - Track download history

2. **SearchHistory Model:**
   - Add user authentication integration
   - Implement search query suggestions
   - Add search result relevance tracking
   - Create search performance dashboards
