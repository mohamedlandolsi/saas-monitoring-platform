# Search Functionality Documentation

## Overview
Comprehensive search functionality for querying and filtering SaaS application logs stored in Elasticsearch.

## Features

### 1. Full-Text Search
- Search across log messages with fuzzy matching
- Auto-complete and intelligent query parsing
- Real-time search results

### 2. Advanced Filters

#### Log Level Filter
- ALL (default)
- DEBUG
- INFO
- WARNING
- ERROR
- CRITICAL

#### Status Code Filter
- ALL (default)
- 2xx (Success): HTTP 200-299
- 4xx (Client Error): HTTP 400-499
- 5xx (Server Error): HTTP 500-599
- Specific codes: 200, 404, 500, etc.

#### Server Filter
- ALL (default)
- server-01
- server-02
- server-03
- server-04
- server-05

#### Endpoint Filter
- Free text input for exact endpoint matching
- Example: `/api/users`, `/api/products`

#### Date Range Filter
- Date From: Start date/time (ISO 8601)
- Date To: End date/time (ISO 8601)

### 3. Results Display

#### Results Table Columns
1. **Timestamp**: Formatted date/time (locale-aware)
2. **Level**: Color-coded badge
   - DEBUG: Gray
   - INFO: Cyan
   - WARNING: Yellow
   - ERROR: Red
   - CRITICAL: Dark Red
3. **Endpoint**: Code-formatted API path
4. **Status**: Color-coded HTTP status
   - 2xx: Green
   - 4xx: Yellow
   - 5xx: Red
5. **Response Time**: Color-coded performance
   - < 500ms: Green (Fast)
   - 500-1000ms: Yellow (Medium)
   - > 1000ms: Red (Slow)
6. **Message**: Truncated to 100 characters (full text on hover)

#### Pagination
- 50 results per page (configurable)
- Smart pagination with ellipsis
- Previous/Next buttons
- Direct page number navigation
- Scroll to top on page change

### 4. Export Functionality
- Export current page results to CSV
- Includes all fields: Timestamp, Level, Endpoint, Status, Response Time, Server, Message
- Auto-generated filename with timestamp: `saas_logs_export_2025-10-30T12-30-45.csv`

## API Endpoint

### POST /api/search

**Request Body:**
```json
{
  "q": "search text",
  "level": "ERROR",
  "date_from": "2025-10-29T00:00:00Z",
  "date_to": "2025-10-30T23:59:59Z",
  "endpoint": "/api/users",
  "status_code": "5XX",
  "server": "server-01",
  "page": 1,
  "per_page": 50
}
```

**Parameters:**
- `q` (string, optional): Search text for message field
- `level` (string, optional): Log level filter (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `date_from` (string, optional): ISO 8601 start date
- `date_to` (string, optional): ISO 8601 end date
- `endpoint` (string, optional): Exact endpoint path
- `status_code` (string, optional): Status code or range (2XX, 4XX, 5XX, 200, 404, 500)
- `server` (string, optional): Server name
- `page` (integer, default: 1): Page number
- `per_page` (integer, default: 50, max: 100): Results per page

**Response:**
```json
{
  "results": [
    {
      "timestamp": "2025-10-30T09:22:10.087Z",
      "level": "ERROR",
      "endpoint": "/api/users",
      "status_code": 500,
      "response_time_ms": 1250,
      "message": "Database connection timeout",
      "server": "server-01",
      "user_id": "user_123",
      "client_ip": "192.168.1.100"
    }
  ],
  "total": 1234,
  "page": 1,
  "per_page": 50,
  "total_pages": 25
}
```

## Elasticsearch Query DSL

The search endpoint builds complex Elasticsearch queries with:

### Bool Query with Must Clauses
- All filters are combined with AND logic
- Only documents matching ALL criteria are returned

### Query Types
1. **Match Query**: Text search on `message` field with fuzzy matching
2. **Term Query**: Exact matches for `level`, `endpoint`, `server`
3. **Range Query**: Date ranges and status code ranges
4. **Sort**: Results sorted by `@timestamp` descending (newest first)

### Example Query Structure
```json
{
  "query": {
    "bool": {
      "must": [
        {
          "match": {
            "message": {
              "query": "error",
              "operator": "and",
              "fuzziness": "AUTO"
            }
          }
        },
        {
          "term": {
            "level.keyword": "ERROR"
          }
        },
        {
          "range": {
            "status_code": {
              "gte": 500,
              "lt": 600
            }
          }
        },
        {
          "range": {
            "@timestamp": {
              "gte": "2025-10-29T00:00:00Z",
              "lte": "2025-10-30T23:59:59Z"
            }
          }
        }
      ]
    }
  },
  "sort": [
    {
      "@timestamp": {
        "order": "desc"
      }
    }
  ],
  "from": 0,
  "size": 50
}
```

## Usage Examples

### 1. Basic Text Search
Search for "timeout" in messages:
```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"q": "timeout", "per_page": 10}'
```

### 2. Filter by Error Level
Get all ERROR logs:
```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"level": "ERROR", "per_page": 20}'
```

### 3. Filter by Status Code Range
Get all 5xx server errors:
```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"status_code": "5XX", "per_page": 50}'
```

### 4. Combined Filters
Search for errors on specific endpoint:
```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "q": "database",
    "level": "ERROR",
    "endpoint": "/api/users",
    "server": "server-01",
    "per_page": 25
  }'
```

### 5. Date Range Query
Get logs from last 24 hours:
```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "date_from": "2025-10-29T10:00:00Z",
    "date_to": "2025-10-30T10:00:00Z",
    "per_page": 50
  }'
```

### 6. Pagination
Navigate to page 3:
```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "q": "error",
    "page": 3,
    "per_page": 50
  }'
```

## Frontend Features

### User Interface
- **Large Search Bar**: Prominent search input with icon
- **Advanced Filters Toggle**: Collapsible filter section
- **Loading Overlay**: Full-screen spinner during search
- **Results Count**: "Showing 1-50 of 1234 results"
- **Responsive Table**: Scrollable with sticky header
- **No Results Message**: Friendly empty state
- **Export Button**: Download results as CSV

### JavaScript Functions
- `performSearch(page)`: Execute search via AJAX
- `displayResults(data)`: Render results table
- `updatePagination(page, totalPages)`: Build pagination UI
- `formatTimestamp(timestamp)`: Format dates
- `formatLevelBadge(level)`: Create colored badges
- `formatResponseTime(ms)`: Color-code performance
- `exportCsvBtn`: Generate and download CSV

### Keyboard Shortcuts
- **Enter**: Submit search form
- **Escape**: Clear search input (custom implementation possible)

## Performance Considerations

### Elasticsearch Optimization
- Index pattern: `saas-logs-*` (multi-index search)
- Query timeout: 30 seconds
- Max results per page: 100 (configurable)
- Fuzzy matching: AUTO (balance accuracy vs performance)

### Frontend Optimization
- AJAX requests: No page reload
- Results caching: Store current results in memory
- Lazy loading: Consider for very large result sets
- Debouncing: Could implement for search-as-you-type

### Caching Strategy (Future Enhancement)
```python
# Redis caching for frequent queries
cache_key = f"search:{hash(json.dumps(searchParams))}"
cached_results = redis_client.get(cache_key)
if cached_results:
    return json.loads(cached_results)
```

## Error Handling

### API Error Responses
```json
{
  "error": "Elasticsearch client not initialized"
}
```

Status codes:
- `200`: Success
- `400`: Bad request (invalid parameters)
- `500`: Server error (Elasticsearch connection issue)
- `503`: Service unavailable

### Frontend Error Handling
- Network errors: Alert user with error message
- Empty results: Show "No Results Found" message
- Elasticsearch timeout: Display timeout message
- Malformed queries: Validate before sending

## Security Considerations

### Input Validation
- XSS protection: `escapeHtml()` function for user-generated content
- SQL injection: N/A (NoSQL Elasticsearch)
- Parameter validation: Type checking on backend

### Query Restrictions
- Max per_page: 100 (prevent resource exhaustion)
- Timeout: 30 seconds (prevent long-running queries)
- Authentication: TODO - Add JWT/session-based auth

## Future Enhancements

### 1. Saved Searches
- Save frequently used search queries
- Quick access dropdown
- Share searches with team

### 2. Search History
- Recent searches dropdown
- Clear history option

### 3. Advanced Query Builder
- Visual query builder UI
- Boolean operators (AND, OR, NOT)
- Nested conditions

### 4. Real-time Search
- Search-as-you-type with debouncing
- Auto-complete suggestions
- Query suggestions based on history

### 5. Export Enhancements
- Export all results (not just current page)
- Export to JSON format
- Schedule periodic exports

### 6. Visualization
- Search result charts (trends, distributions)
- Timeline view
- Heatmap of errors by time/server

### 7. Alerting
- Create alerts from search queries
- Email/Slack notifications
- Threshold-based triggers

## Testing

### API Testing
```bash
# Test basic search
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"q": "test", "per_page": 5}' | jq

# Test filters
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"level": "ERROR", "status_code": "5XX"}' | jq

# Test pagination
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"page": 2, "per_page": 10}' | jq
```

### Frontend Testing
1. Open http://localhost:5000/search
2. Enter search query
3. Toggle advanced filters
4. Apply multiple filters
5. Navigate pagination
6. Export results to CSV
7. Reset filters

## Troubleshooting

### No Results Found
- Check Elasticsearch connection: http://localhost:9200
- Verify index exists: `curl http://localhost:9200/_cat/indices`
- Check query syntax in browser console
- Ensure filters are not too restrictive

### Slow Search Performance
- Add Elasticsearch indices
- Reduce per_page value
- Implement caching layer
- Optimize query structure

### CSV Export Issues
- Check browser download settings
- Verify results array is populated
- Test in different browsers
- Check for special characters in messages

## Related Documentation
- [Kibana Setup Guide](KIBANA_SETUP.md)
- [Elasticsearch API Reference](https://www.elastic.co/guide/en/elasticsearch/reference/8.11/index.html)
- [Bootstrap 5 Documentation](https://getbootstrap.com/docs/5.3/)

## Support
For issues or questions:
1. Check application logs: `docker-compose logs webapp`
2. Check Elasticsearch logs: `docker-compose logs elasticsearch`
3. Review this documentation
4. Open GitHub issue with reproduction steps

## CSV Export Feature

### Overview
The CSV export functionality allows you to download ALL matching search results (up to 10,000 logs) as a CSV file, not just the current page.

### API Endpoint: POST /api/export

**Request:**
```json
POST /api/export
Content-Type: application/json

{
  "q": "error",
  "level": "ERROR",
  "status_code": "5XX",
  "server": "server-01",
  "endpoint": "/api/users",
  "date_from": "2025-10-29T00:00:00Z",
  "date_to": "2025-10-30T23:59:59Z"
}
```

**Response:**
```
Content-Type: text/csv
Content-Disposition: attachment; filename=logs_export_20251030_123045.csv

timestamp,level,endpoint,status_code,response_time_ms,message,client_ip,user_id,server
2025-10-30T09:22:10.087Z,ERROR,/api/users,500,1250,Database connection timeout,192.168.1.100,user_123,server-01
...
```

### CSV Format

**Columns (9 total):**
1. `timestamp` - ISO 8601 format (e.g., 2025-10-30T09:22:10.087Z)
2. `level` - Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
3. `endpoint` - API endpoint path (e.g., /api/users)
4. `status_code` - HTTP status code (e.g., 200, 404, 500)
5. `response_time_ms` - Response time in milliseconds
6. `message` - Log message (newlines replaced with spaces)
7. `client_ip` - Client IP address
8. `user_id` - User identifier
9. `server` - Server name (e.g., server-01)

**Special Handling:**
- Newlines in messages are replaced with spaces
- Empty values rendered as empty strings
- Header row always included
- UTF-8 encoding

### Frontend Usage

**Button Location:**
The "Export CSV" button is located in the top-right of the results section, next to the results count.

**Button States:**
1. **Normal**: `<i class="bi bi-file-earmark-spreadsheet"></i> Export CSV`
2. **Loading**: `<spinner> Exporting...` (button disabled)
3. **Success**: Shows green alert for 3 seconds

**User Flow:**
1. Enter search criteria and filters
2. Click "Search" to execute search
3. Review results in table
4. Click "Export CSV" button
5. Browser downloads file automatically
6. Success message appears briefly
7. File saved to default downloads folder

**Filename Format:**
`logs_export_YYYYMMDD_HHMMSS.csv`

Example: `logs_export_20251030_123045.csv`

### Export Behavior

**Key Differences from Search:**
| Feature | Search (/api/search) | Export (/api/export) |
|---------|---------------------|---------------------|
| Pagination | Yes (50 per page) | No (all results) |
| Max Results | Unlimited (paginated) | 10,000 max |
| Response Format | JSON | CSV file download |
| Use Case | Interactive browsing | Data analysis/backup |

**Filters Applied:**
- All search filters are applied to export
- No pagination parameters needed
- Results sorted by timestamp (desc)
- Same Elasticsearch query as search

### Export Limits

**Maximum Results:** 10,000 logs per export

**Why 10,000?**
This is Elasticsearch's default `max_result_window` setting. To export more:

1. **Option 1: Use Multiple Exports**
   - Apply more specific filters
   - Export in date ranges
   - Export by server or endpoint

2. **Option 2: Increase Elasticsearch Limit** (Advanced)
   ```bash
   curl -X PUT "localhost:9200/saas-logs-*/_settings" \
     -H 'Content-Type: application/json' \
     -d '{"index.max_result_window": 50000}'
   ```

3. **Option 3: Use Scroll API** (For Production)
   - Implement async export job
   - Use Elasticsearch scroll API
   - Generate download link when complete

### Usage Examples

#### 1. Export All Errors
```bash
curl -X POST http://localhost:5000/api/export \
  -H "Content-Type: application/json" \
  -d '{"level": "ERROR"}' \
  --output errors.csv
```

#### 2. Export Server Errors (5XX)
```bash
curl -X POST http://localhost:5000/api/export \
  -H "Content-Type: application/json" \
  -d '{"status_code": "5XX"}' \
  --output server_errors.csv
```

#### 3. Export by Date Range
```bash
curl -X POST http://localhost:5000/api/export \
  -H "Content-Type: application/json" \
  -d '{
    "date_from": "2025-10-29T00:00:00Z",
    "date_to": "2025-10-30T00:00:00Z"
  }' \
  --output logs_24h.csv
```

#### 4. Export Specific Server
```bash
curl -X POST http://localhost:5000/api/export \
  -H "Content-Type: application/json" \
  -d '{"server": "server-01", "level": "CRITICAL"}' \
  --output server01_critical.csv
```

#### 5. Combined Filters
```bash
curl -X POST http://localhost:5000/api/export \
  -H "Content-Type: application/json" \
  -d '{
    "q": "database",
    "level": "ERROR",
    "endpoint": "/api/users",
    "server": "server-01",
    "date_from": "2025-10-29T00:00:00Z"
  }' \
  --output database_errors_filtered.csv
```

### Error Handling

**Possible Errors:**

1. **Elasticsearch Connection Error**
   ```json
   {"error": "Elasticsearch client not initialized"}
   ```
   Status: 500

2. **Query Error**
   ```json
   {"error": "Search error: <error message>"}
   ```
   Status: 500

3. **No Results**
   Returns CSV with header only (1 row)

### Performance Considerations

**Export Time Estimates:**
- 100 rows: < 1 second
- 1,000 rows: 1-2 seconds
- 10,000 rows: 5-10 seconds

**Optimization Tips:**
1. Use specific filters to reduce result size
2. Export during off-peak hours for large datasets
3. Consider implementing caching for frequent exports
4. Use date ranges to limit results

**Browser Considerations:**
- Large files (>5MB) may take time to download
- Browser may show "Save As" dialog
- Progress not shown during download
- Cancel may not work mid-download

### Security Considerations

**Current Implementation:**
- ⚠️ No authentication required
- ⚠️ No rate limiting
- ⚠️ No audit logging
- ⚠️ All users can export all data

**Recommended Production Enhancements:**
1. Add JWT/session authentication
2. Implement role-based access control
3. Add rate limiting (e.g., 10 exports per hour)
4. Log all export requests (who, when, filters)
5. Add field-level permissions
6. Implement export quotas per user
7. Add data masking for sensitive fields

### Testing Export

**Test Different Scenarios:**

```bash
# Test 1: Small export
curl -X POST http://localhost:5000/api/export \
  -H "Content-Type: application/json" \
  -d '{"level": "CRITICAL"}' \
  --output test1.csv

# Test 2: No results
curl -X POST http://localhost:5000/api/export \
  -H "Content-Type: application/json" \
  -d '{"q": "nonexistentterm"}' \
  --output test2.csv

# Test 3: Large export
curl -X POST http://localhost:5000/api/export \
  -H "Content-Type: application/json" \
  -d '{"level": "INFO"}' \
  --output test3.csv

# Verify results
wc -l test*.csv
head -5 test1.csv
```

### Troubleshooting

**Problem: Export button does nothing**
- Check browser console for errors
- Verify /api/export endpoint is accessible
- Check network tab for failed requests

**Problem: CSV file is empty or has only headers**
- Search returned no results
- Check filters are correct
- Try broader search criteria

**Problem: Export takes too long**
- Reduce result size with filters
- Check Elasticsearch performance
- Consider implementing async export

**Problem: CSV format issues in Excel**
- Newlines in messages may cause issues
- Use "Import Data" wizard in Excel
- Specify UTF-8 encoding when opening

### Future Enhancements

1. **Async Export**
   - Queue export jobs
   - Email download link when ready
   - Progress bar during export

2. **Export All Pages**
   - Remove 10,000 limit using scroll API
   - Background processing for large exports
   - Chunked download for very large files

3. **Multiple Format Support**
   - JSON export
   - Excel (XLSX) format
   - PDF report generation

4. **Scheduled Exports**
   - Daily/weekly automated exports
   - Email delivery
   - S3/cloud storage integration

5. **Export Templates**
   - Save filter combinations
   - Named export presets
   - Quick export buttons

