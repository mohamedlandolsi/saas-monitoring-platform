# API Documentation

## Overview

Complete documentation for all API endpoints, functions, and utilities in the SaaS Monitoring Platform.

---

## Table of Contents

1. [Utility Functions](#utility-functions)
2. [Helper Functions](#helper-functions)
3. [API Endpoints](#api-endpoints)
4. [Models](#models)
5. [Error Handling](#error-handling)
6. [Caching](#caching)

---

## Utility Functions

### File Validation

#### `allowed_file(filename: str) -> bool`

Check if a file has an allowed extension.

**Parameters:**
- `filename` (str): Name of the file to check

**Returns:**
- `bool`: True if file extension is in ALLOWED_EXTENSIONS, False otherwise

**Allowed Extensions:**
- `.csv`
- `.json`

**Examples:**
```python
allowed_file('data.csv')  # Returns: True
allowed_file('script.py')  # Returns: False
```

---

### Client Initialization

#### `init_elasticsearch() -> Optional[Elasticsearch]`

Initialize and test Elasticsearch client connection.

**Returns:**
- `Optional[Elasticsearch]`: Elasticsearch client if successful, None otherwise

**Environment Variables:**
- `ELASTICSEARCH_HOST`: Elasticsearch server URL (default: http://localhost:9200)

**Example:**
```python
es_client = init_elasticsearch()
if es_client:
    print("Connected to Elasticsearch")
```

#### `init_mongodb() -> Optional[MongoClient]`

Initialize and test MongoDB client connection.

**Returns:**
- `Optional[MongoClient]`: MongoDB client if successful, None otherwise

**Environment Variables:**
- `MONGODB_URI`: MongoDB connection URI

#### `init_redis() -> Optional[Redis]`

Initialize and test Redis client connection.

**Returns:**
- `Optional[Redis]`: Redis client if successful, None otherwise

**Environment Variables:**
- `REDIS_HOST`: Redis server host (default: localhost)
- `REDIS_PORT`: Redis server port (default: 6379)

---

## Helper Functions

Located in `app/utils/helpers.py`

### File Formatting

#### `format_file_size(size_bytes: int) -> str`

Convert file size in bytes to human-readable format.

**Parameters:**
- `size_bytes` (int): File size in bytes

**Returns:**
- `str`: Formatted file size (e.g., "2.50 MB", "1.23 GB")

**Examples:**
```python
format_file_size(1024)      # Returns: "1.00 KB"
format_file_size(1048576)   # Returns: "1.00 MB"
format_file_size(1536)      # Returns: "1.50 KB"
```

---

### Timestamp Formatting

#### `format_timestamp(timestamp: Union[str, datetime], format_type: str = 'short') -> str`

Format ISO timestamp or datetime object to human-readable string.

**Parameters:**
- `timestamp` (Union[str, datetime]): ISO 8601 timestamp string or datetime object
- `format_type` (str): Output format type (default: 'short')

**Format Types:**
- `'short'`: "Oct 30, 10:00 AM"
- `'long'`: "October 30, 2025 at 10:00:00 AM"
- `'date'`: "Oct 30, 2025"
- `'time'`: "10:00 AM"
- `'iso'`: ISO 8601 format

**Returns:**
- `str`: Formatted timestamp string

**Examples:**
```python
format_timestamp("2025-10-30T10:00:00Z")
# Returns: "Oct 30, 10:00 AM"

format_timestamp("2025-10-30T10:00:00Z", format_type='date')
# Returns: "Oct 30, 2025"
```

---

### File Validation

#### `validate_file_type(filename: str, allowed_extensions: Optional[list] = None) -> bool`

Validate if a file has an allowed extension.

**Parameters:**
- `filename` (str): Name of the file to validate
- `allowed_extensions` (Optional[list]): List of allowed extensions (default: ['csv', 'json'])

**Returns:**
- `bool`: True if extension is allowed, False otherwise

**Examples:**
```python
validate_file_type('data.csv')              # Returns: True
validate_file_type('data.txt')              # Returns: False
validate_file_type('config.yaml', ['yaml', 'yml'])  # Returns: True
```

---

### Percentage Calculation

#### `calculate_percentage(part: Union[int, float], total: Union[int, float]) -> float`

Calculate percentage with safe division.

**Parameters:**
- `part` (Union[int, float]): The part value (numerator)
- `total` (Union[int, float]): The total value (denominator)

**Returns:**
- `float`: Percentage value (0.0 to 100.0), rounded to 2 decimal places

**Examples:**
```python
calculate_percentage(25, 100)   # Returns: 25.0
calculate_percentage(1, 3)      # Returns: 33.33
calculate_percentage(5, 0)      # Returns: 0.0
```

---

### Additional Helpers

#### `truncate_string(text: str, max_length: int = 50, suffix: str = '...') -> str`

Truncate string to maximum length with optional suffix.

#### `safe_divide(numerator: Union[int, float], denominator: Union[int, float], default: Union[int, float] = 0) -> float`

Perform division with safe handling of zero denominator.

#### `format_log_level(level: str) -> dict`

Get display properties for log level (color, icon, badge class).

#### `format_status_code(code: int) -> dict`

Get display properties for HTTP status code.

#### `sanitize_filename(filename: str) -> str`

Sanitize filename by removing/replacing unsafe characters.

#### `parse_date_range(date_from: Optional[str], date_to: Optional[str]) -> dict`

Parse and validate date range parameters.

#### `get_file_extension(filename: str) -> str`

Extract file extension from filename.

#### `format_duration(milliseconds: float) -> str`

Format duration in milliseconds to human-readable string.

---

## API Endpoints

### Health Check

#### `GET /api/health`

Health check endpoint to verify service dependencies.

**Response:**
```json
{
    "status": "healthy",
    "elasticsearch": true,
    "mongodb": true,
    "redis": true,
    "healthy": true
}
```

**Status Codes:**
- `200`: All services healthy
- `503`: One or more services unhealthy

---

### Statistics

#### `GET /api/stats`

Get comprehensive log statistics from Elasticsearch.

**Caching:**
- TTL: 60 seconds
- Cache key: `stats:get_stats:<hash>`

**Response:**
```json
{
    "total_logs": 150000,
    "total_logs_24h": 5000,
    "error_rate": 2.5,
    "avg_response_time_24h": 245.5,
    "top_slowest_endpoints": [
        {
            "endpoint": "/api/search",
            "avg_response_time": 1200.5,
            "count": 150
        }
    ],
    "unique_users_24h": 45,
    "latest_error": {
        "timestamp": "2025-10-30T10:00:00Z",
        "level": "ERROR",
        "message": "Database connection failed",
        "endpoint": "/api/upload",
        "status_code": 500
    },
    "system_status": {
        "elasticsearch": true,
        "mongodb": true,
        "redis": true
    },
    "cluster_status": "green",
    "indices": [
        {
            "name": "saas-logs-2025-10",
            "docs_count": 150000,
            "store_size": "250.5 MB"
        }
    ]
}
```

---

### Search Logs

#### `POST /api/search`

Search logs in Elasticsearch with advanced filters.

**Caching:**
- TTL: 300 seconds (5 minutes)
- Cache key: `search:search_logs:<hash>`

**Request Body:**
```json
{
    "q": "error message",
    "level": "ERROR",
    "date_from": "2025-10-01T00:00:00Z",
    "date_to": "2025-10-31T23:59:59Z",
    "endpoint": "/api/upload",
    "status_code": "500",
    "server": "server-01",
    "page": 1,
    "per_page": 50
}
```

**Parameters:**
- `q` (string, optional): Search query for message field
- `level` (string, optional): Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL, ALL)
- `date_from` (string, optional): Start date (ISO 8601)
- `date_to` (string, optional): End date (ISO 8601)
- `endpoint` (string, optional): Endpoint filter
- `status_code` (string, optional): Status code or range (2XX, 4XX, 5XX, or specific code)
- `server` (string, optional): Server name filter
- `page` (int, optional): Page number (default: 1)
- `per_page` (int, optional): Results per page (default: 50, max: 100)

**Response:**
```json
{
    "results": [
        {
            "timestamp": "2025-10-30T10:00:00Z",
            "level": "ERROR",
            "endpoint": "/api/upload",
            "status_code": 500,
            "response_time_ms": 1200,
            "message": "Database connection failed",
            "server": "server-01",
            "user_id": "user123",
            "client_ip": "192.168.1.1"
        }
    ],
    "total": 150,
    "page": 1,
    "per_page": 50,
    "total_pages": 3
}
```

**Error Responses:**
- `400`: Validation error (invalid parameters)
- `500`: Elasticsearch error

---

### File Upload

#### `POST /api/upload`

Upload CSV or JSON files with metadata storage.

**Request:**
- Content-Type: `multipart/form-data`
- Field: `file` (CSV or JSON file)

**Response:**
```json
{
    "success": true,
    "file_id": "507f1f77bcf86cd799439011",
    "message": "File uploaded successfully: data.csv",
    "details": {
        "filename": "data.csv",
        "saved_as": "20251030_100000_data.csv",
        "file_size": 1048576,
        "log_count": 1000,
        "upload_date": "2025-10-30T10:00:00Z"
    }
}
```

**Error Responses:**
- `400`: ValidationError - No file, invalid type, or file too large
- `500`: DatabaseError - Failed to save metadata

---

### File Management

#### `GET /api/files`

Get list of uploaded files with statistics.

**Caching:**
- TTL: 600 seconds (10 minutes)
- Cache key: `files:get_files:<hash>`
- Invalidated on: File upload, file delete

**Response:**
```json
{
    "success": true,
    "files": [
        {
            "id": "507f1f77bcf86cd799439011",
            "filename": "data.csv",
            "saved_as": "20251030_100000_data.csv",
            "file_type": "csv",
            "file_size": 1048576,
            "log_count": 1000,
            "status": "completed",
            "upload_date": "2025-10-30T10:00:00Z"
        }
    ],
    "stats": {
        "total_files": 10,
        "total_size": 10485760,
        "total_logs": 10000,
        "by_type": {
            "csv": 6,
            "json": 4
        },
        "by_status": {
            "completed": 10
        }
    }
}
```

#### `DELETE /api/files/<file_id>`

Delete a file by ID.

**Parameters:**
- `file_id` (string): MongoDB ObjectId of the file

**Response:**
```json
{
    "success": true,
    "message": "File deleted successfully"
}
```

**Error Responses:**
- `404`: NotFoundError - File not found
- `500`: DatabaseError - Delete operation failed

---

### Search History

#### `GET /api/search/history`

Get recent search history.

**Query Parameters:**
- `limit` (int, optional): Number of results (default: 10, max: 100)
- `user` (string, optional): Filter by user (IP address)

**Response:**
```json
{
    "success": true,
    "searches": [
        {
            "id": "507f1f77bcf86cd799439011",
            "query": "error",
            "filters": {
                "level": "ERROR",
                "date_from": "2025-10-01"
            },
            "user": "192.168.1.1",
            "results_count": 150,
            "execution_time_ms": 245.5,
            "timestamp": "2025-10-30T10:00:00Z"
        }
    ],
    "count": 10
}
```

#### `GET /api/search/history/popular`

Get most popular search queries.

**Query Parameters:**
- `limit` (int, optional): Number of results (default: 10)

**Response:**
```json
{
    "success": true,
    "popular_queries": [
        {
            "query": "error",
            "count": 50,
            "avg_results": 125.5,
            "avg_execution_time_ms": 200.3
        }
    ]
}
```

#### `GET /api/search/history/stats`

Get search history statistics.

**Response:**
```json
{
    "success": true,
    "stats": {
        "total_searches": 1000,
        "unique_users": 25,
        "avg_execution_time_ms": 250.5,
        "searches_24h": 150,
        "top_filters": {
            "level": ["ERROR", "WARNING"],
            "status_code": ["500", "404"]
        }
    }
}
```

---

### Cache Statistics

#### `GET /api/cache/stats`

Get cache performance metrics.

**Response:**
```json
{
    "success": true,
    "cache_stats": {
        "hits": 150,
        "misses": 50,
        "total_requests": 200,
        "hit_rate_percent": 75.0
    },
    "redis_info": {
        "total_connections_received": 500,
        "total_commands_processed": 2000,
        "keyspace_hits": 150,
        "keyspace_misses": 50,
        "redis_hit_rate_percent": 75.0,
        "used_memory_human": "2.5 MB"
    }
}
```

---

## Type Hints Reference

### Common Type Definitions

```python
from typing import Optional, Dict, Any, List, Tuple, Union

# Response types
Response = Tuple[Dict[str, Any], int]  # (JSON data, status code)

# Common parameter types
FileId = str  # MongoDB ObjectId as string
Timestamp = Union[str, datetime]  # ISO 8601 string or datetime object
LogLevel = str  # "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
```

---

## Usage Examples

### Python Client Example

```python
import requests

# Health check
response = requests.get('http://localhost:5000/api/health')
print(response.json())

# Get statistics
stats = requests.get('http://localhost:5000/api/stats')
print(f"Total logs: {stats.json()['total_logs']}")

# Search logs
search_params = {
    "q": "error",
    "level": "ERROR",
    "page": 1,
    "per_page": 50
}
results = requests.post('http://localhost:5000/api/search', json=search_params)
print(f"Found {results.json()['total']} errors")

# Upload file
with open('logs.csv', 'rb') as f:
    files = {'file': f}
    upload = requests.post('http://localhost:5000/api/upload', files=files)
    print(upload.json()['message'])
```

### JavaScript Client Example

```javascript
// Search logs
async function searchLogs(query, level) {
    const response = await fetch('/api/search', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            q: query,
            level: level,
            page: 1,
            per_page: 50
        })
    });
    
    const data = await response.json();
    console.log(`Found ${data.total} results`);
    return data.results;
}

// Upload file
async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData
    });
    
    const data = await response.json();
    return data;
}
```

---

## Testing

### Run Helper Function Tests

```bash
docker-compose exec webapp python3 -c "
from utils.helpers import *

# Test all helper functions
print('File Size:', format_file_size(1048576))
print('Timestamp:', format_timestamp('2025-10-30T10:00:00Z'))
print('Validate:', validate_file_type('data.csv'))
print('Percentage:', calculate_percentage(25, 100))
"
```

### Test API Endpoints

```bash
# Health check
curl http://localhost:5000/api/health

# Statistics
curl http://localhost:5000/api/stats

# Search
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"q":"error","level":"ERROR"}'

# Upload
curl -X POST http://localhost:5000/api/upload \
  -F "file=@logs.csv"
```

---

## Best Practices

### 1. Always Use Type Hints

```python
def process_data(items: List[Dict[str, Any]]) -> bool:
    """Process items with proper type hints."""
    pass
```

### 2. Write Comprehensive Docstrings

```python
def calculate_stats(data: List[int]) -> Dict[str, float]:
    """
    Calculate statistics for a list of integers.
    
    Args:
        data (List[int]): List of integers to analyze
    
    Returns:
        Dict[str, float]: Dictionary with mean, median, std_dev
    
    Raises:
        ValueError: If data list is empty
    """
    pass
```

### 3. Document Complex Logic

```python
# Calculate error rate as percentage
# Formula: (error_count / total_count) * 100
# Safe division: returns 0.0 if total is 0
error_rate = calculate_percentage(error_count, total_count)
```

---

## Contributing

When adding new functions:

1. Add comprehensive docstring
2. Include type hints for all parameters and return values
3. Provide usage examples in docstring
4. Add inline comments for complex logic
5. Update this API documentation
6. Write tests for the new functionality
