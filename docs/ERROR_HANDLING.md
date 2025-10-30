# Error Handling Documentation

## Overview

The SaaS Monitoring Platform implements comprehensive error handling with custom exceptions, structured error responses, detailed logging, and user-friendly error pages.

## Architecture

### Components

1. **Custom Exception Classes** (`app/utils/errors.py`): Specialized exceptions for different error types
2. **Error Handlers** (`app/app.py`): Flask error handlers for custom and HTTP errors
3. **Logging System**: File and console logging with rotation
4. **Error Pages**: HTML templates for 404 and 500 errors

---

## Custom Exception Classes

Located in `app/utils/errors.py`

### Base Exception: AppError

All custom exceptions inherit from `AppError`:

```python
class AppError(Exception):
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict] = None)
```

**Methods:**
- `to_dict()`: Convert exception to dictionary for JSON response
- `to_response()`: Convert exception to Flask response with status code

### Available Exception Classes

#### 1. ValidationError

**Status Code:** 400  
**Use Case:** Input validation failures

```python
raise ValidationError(
    'Invalid file type',
    field='file',
    details={'allowed_extensions': ['json', 'csv']}
)
```

**Response:**
```json
{
    "success": false,
    "error": "Invalid file type",
    "code": 400,
    "type": "ValidationError",
    "details": {
        "field": "file",
        "allowed_extensions": ["json", "csv"]
    }
}
```

#### 2. DatabaseError

**Status Code:** 500  
**Use Case:** MongoDB operation failures

```python
raise DatabaseError(
    'Failed to save file metadata',
    operation='insert',
    details={'error': str(e)}
)
```

#### 3. CacheError

**Status Code:** 500  
**Use Case:** Redis cache operation failures

```python
raise CacheError(
    'Failed to retrieve cached data',
    operation='get',
    details={'key': cache_key}
)
```

#### 4. ElasticsearchError

**Status Code:** 500  
**Use Case:** Elasticsearch query/index failures

```python
raise ElasticsearchError(
    'Search query failed',
    operation='search',
    details={'query': query_body}
)
```

#### 5. FileProcessingError

**Status Code:** 400  
**Use Case:** File upload/processing failures

```python
raise FileProcessingError(
    'Invalid JSON format',
    filename='data.json',
    details={'line': 42}
)
```

#### 6. NotFoundError

**Status Code:** 404  
**Use Case:** Resource not found

```python
raise NotFoundError(
    'File not found',
    resource_type='file',
    resource_id='123abc'
)
```

#### 7. UnauthorizedError

**Status Code:** 401  
**Use Case:** Authentication/authorization failures

```python
raise UnauthorizedError(
    'Invalid API key',
    details={'api_key': 'xxx***'}
)
```

---

## Error Response Format

All errors return a consistent JSON structure:

### Success Response
```json
{
    "success": true,
    "code": 200,
    "message": "Operation completed successfully",
    "data": { ... }
}
```

### Error Response
```json
{
    "success": false,
    "error": "Human-readable error message",
    "code": 400,
    "type": "ValidationError",
    "details": {
        "field": "page",
        "additional_info": "..."
    }
}
```

---

## Flask Error Handlers

### Custom Exception Handlers

```python
@app.errorhandler(ValidationError)
def handle_validation_error(error):
    app.logger.warning(f"Validation error: {error.message}")
    return error.to_response()
```

Handlers registered for:
- `ValidationError`
- `DatabaseError`
- `CacheError`
- `ElasticsearchError`
- `FileProcessingError`
- `NotFoundError`

### HTTP Error Handlers

#### 404 Not Found

**API Requests** (`/api/*`):
```json
{
    "success": false,
    "error": "Endpoint not found",
    "code": 404
}
```

**Regular Requests**: Renders `templates/404.html`

#### 500 Internal Server Error

**API Requests** (`/api/*`):
```json
{
    "success": false,
    "error": "Internal server error",
    "code": 500
}
```

**Regular Requests**: Renders `templates/500.html`

#### Generic Exception Handler

Catches all unhandled exceptions:

```python
@app.errorhandler(Exception)
def handle_generic_error(error):
    app.logger.error(f"Unhandled exception: {str(error)}", exc_info=True)
    # Returns JSON for API, HTML for regular requests
```

---

## Logging System

### Configuration

**Location:** `logs/app.log`  
**Max Size:** 10 MB per file  
**Backup Count:** 10 rotating files  
**Format:**
```
2025-10-30 15:11:35,820 - app - INFO - [app.py:62] - Message here
```

### Log Levels

#### INFO
Successful operations and important events:
```python
app.logger.info(f"File upload completed: {filename} ({log_count} logs)")
app.logger.info("✓ Connected to MongoDB")
```

#### WARNING
Validation failures and recoverable errors:
```python
app.logger.warning(f"Upload failed: Invalid file type - {filename}")
app.logger.warning(f"404 Not Found: {request.url}")
```

#### ERROR
Exceptions and critical failures:
```python
app.logger.error(f"Database error: {str(e)}")
app.logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
```

### Log Rotation

Automatic rotation when file reaches 10 MB:
- `logs/app.log` (current)
- `logs/app.log.1` (most recent backup)
- `logs/app.log.2`
- ...
- `logs/app.log.10` (oldest backup)

---

## Usage Examples

### Example 1: Route with Error Handling

```python
@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        app.logger.info(f"File upload request from {request.remote_addr}")
        
        # Validate file presence
        if 'file' not in request.files:
            app.logger.warning("Upload failed: No file part in request")
            raise ValidationError('No file part in request', field='file')
        
        file = request.files['file']
        
        # Validate file type
        if not allowed_file(file.filename):
            raise ValidationError(
                'Invalid file type',
                field='file',
                details={'filename': file.filename}
            )
        
        # Process file...
        app.logger.info(f"File uploaded successfully: {filename}")
        
        return jsonify({'success': True, 'file_id': file_id}), 200
        
    except (ValidationError, DatabaseError):
        # Re-raise custom exceptions (handled by error handlers)
        raise
    except Exception as e:
        app.logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise FileProcessingError('Upload failed', details={'error': str(e)})
```

### Example 2: Validation Helper Usage

```python
from utils.errors import validate_required_fields, validate_pagination

@app.route('/api/search', methods=['POST'])
def search():
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        validate_required_fields(data, ['query'])
        
        # Validate pagination
        page, per_page = validate_pagination(
            data.get('page'), 
            data.get('per_page'),
            max_per_page=100
        )
        
        # Perform search...
        
    except ValidationError:
        raise  # Will be handled by @app.errorhandler(ValidationError)
```

### Example 3: Database Error Handling

```python
@app.route('/api/files/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    try:
        if not file_model:
            raise DatabaseError('Database not available')
        
        result = file_model.delete(file_id)
        
        if not result:
            raise NotFoundError('File not found', resource_id=file_id)
        
        app.logger.info(f"File deleted: {file_id}")
        return jsonify({'success': True}), 200
        
    except (DatabaseError, NotFoundError):
        raise
    except Exception as e:
        app.logger.error(f"Delete failed: {str(e)}", exc_info=True)
        raise DatabaseError('Failed to delete file', operation='delete')
```

---

## Error Pages

### 404 Page (`templates/404.html`)

**Features:**
- Purple gradient background
- Animated search icon
- "Go to Homepage" button
- Helpful suggestions
- Links to main sections

**Displayed when:**
- User navigates to non-existent page
- Route not defined
- Static file not found

### 500 Page (`templates/500.html`)

**Features:**
- Red gradient background
- Animated warning icon
- "Go to Homepage" and "Try Again" buttons
- Error explanation
- Troubleshooting suggestions
- Timestamp of error

**Displayed when:**
- Unhandled exception occurs
- Server error (500 status)
- Critical failure

---

## Testing Error Handling

### Test Validation Errors

```bash
# Missing file
curl -X POST http://localhost:5000/api/upload -d '{}'

# Invalid pagination
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"q":"test","page":-1}'
```

**Expected Response:**
```json
{
    "success": false,
    "error": "Page number must be greater than 0",
    "code": 400,
    "type": "ValidationError",
    "details": {"field": "page"}
}
```

### Test 404 Errors

```bash
# API endpoint
curl http://localhost:5000/api/nonexistent

# HTML page
curl http://localhost:5000/nonexistent-page
```

### Test Logging

```bash
# View logs
docker-compose exec webapp cat logs/app.log | tail -50

# Follow logs in real-time
docker-compose logs -f webapp | grep -E "(INFO|WARNING|ERROR)"
```

---

## Best Practices

### 1. Always Use Custom Exceptions

❌ **Bad:**
```python
return jsonify({'error': 'Invalid input'}), 400
```

✅ **Good:**
```python
raise ValidationError('Invalid input', field='username')
```

### 2. Include Context in Error Details

❌ **Bad:**
```python
raise ValidationError('Invalid file')
```

✅ **Good:**
```python
raise ValidationError(
    'Invalid file type',
    field='file',
    details={
        'filename': file.filename,
        'extension': extension,
        'allowed_extensions': ALLOWED_EXTENSIONS
    }
)
```

### 3. Log Before Raising Exceptions

```python
app.logger.warning(f"Upload failed: Invalid file type - {filename}")
raise ValidationError('Invalid file type', field='file')
```

### 4. Use Appropriate Log Levels

- **INFO**: Successful operations, connections, important events
- **WARNING**: Validation failures, 404s, recoverable errors
- **ERROR**: Exceptions, database errors, critical failures

### 5. Re-raise Custom Exceptions

```python
try:
    # Operation
except ValidationError:
    raise  # Let error handler deal with it
except Exception as e:
    app.logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    raise AppError('Something went wrong')
```

### 6. Provide User-Friendly Messages

❌ **Bad:**
```python
raise ValidationError('field_required')
```

✅ **Good:**
```python
raise ValidationError('File is required for upload', field='file')
```

---

## Monitoring and Debugging

### View Logs

```bash
# Last 50 lines
docker-compose exec webapp tail -50 logs/app.log

# Follow logs
docker-compose exec webapp tail -f logs/app.log

# Search for errors
docker-compose exec webapp grep "ERROR" logs/app.log

# Filter by date
docker-compose exec webapp grep "2025-10-30" logs/app.log
```

### Log Analysis

```bash
# Count errors by type
docker-compose exec webapp grep "ERROR" logs/app.log | wc -l

# Most common errors
docker-compose exec webapp grep "ERROR" logs/app.log | sort | uniq -c | sort -rn

# Errors in last hour
docker-compose exec webapp grep "$(date -u '+%Y-%m-%d %H')" logs/app.log | grep "ERROR"
```

### Debug Mode

For development, enable traceback in error responses:

```python
# In handle_generic_exception
error_response = handle_generic_exception(error, include_traceback=True)
```

---

## Troubleshooting

### Logs Not Being Written

**Problem:** No log file created

**Solution:**
```bash
# Create logs directory
mkdir -p logs

# Check permissions
chmod 755 logs

# Restart webapp
docker-compose restart webapp
```

### Too Many Log Files

**Problem:** Log rotation not working

**Solution:**
Check `RotatingFileHandler` configuration:
```python
file_handler = RotatingFileHandler(
    'logs/app.log',
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=10
)
```

### Error Pages Not Displaying

**Problem:** Getting JSON instead of HTML

**Solution:**
Error handlers check request path:
```python
if request.path.startswith('/api/'):
    return jsonify(error)  # JSON for API
else:
    return render_template('404.html')  # HTML for pages
```

---

## Future Enhancements

1. **Error Monitoring**: Integrate with Sentry or similar service
2. **Error Metrics**: Track error rates in Elasticsearch
3. **Alert System**: Send notifications for critical errors
4. **Error Recovery**: Automatic retry logic for transient failures
5. **User Feedback**: Allow users to report errors
6. **Error Dashboard**: Visualize error trends and patterns
