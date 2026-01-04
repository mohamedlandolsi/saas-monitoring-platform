# Search Functionality - Quick Reference

## 🎯 What's Implemented

### Backend (app.py)
✅ **GET /search** - Renders search page  
✅ **POST /api/search** - Search endpoint with comprehensive filtering

### Frontend (templates/search.html)
✅ Large search input with icon  
✅ Collapsible advanced filters section  
✅ Bootstrap 5 responsive table  
✅ Smart pagination (7-page window with ellipsis)  
✅ CSV export functionality  
✅ Loading overlay with spinner  
✅ Color-coded results (levels, status codes, response times)  
✅ No results message  
✅ Reset filters button  

## 🔍 Search Filters

| Filter | Options | Query Type |
|--------|---------|------------|
| Text Search | Free text | Match query with fuzzy matching |
| Log Level | ALL, DEBUG, INFO, WARNING, ERROR, CRITICAL | Term query |
| Status Code | ALL, 2XX, 4XX, 5XX, specific codes | Range/Term query |
| Server | ALL, server-01 to server-05 | Term query |
| Endpoint | Free text (exact match) | Term query |
| Date Range | From/To datetime | Range query |
| Pagination | Page number, per_page (1-100) | from/size |

## 📊 Results Display

**Table Columns:**
1. Timestamp (formatted, sortable)
2. Level (color badge)
3. Endpoint (code formatted)
4. Status (color coded: green 2xx, yellow 4xx, red 5xx)
5. Response Time (color coded: green <500ms, yellow 500-1000ms, red >1000ms)
6. Message (truncated to 100 chars, full text on hover)

**Pagination:**
- 50 results per page (default)
- Smart page numbers with ellipsis
- Previous/Next navigation
- Scroll to top on page change

## 🚀 Quick Test

```bash
# 1. Basic search
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"q": "error", "per_page": 5}' | python3 -m json.tool

# 2. Filter by level and status
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"level": "ERROR", "status_code": "5XX"}' | python3 -m json.tool

# 3. Access frontend
# Open browser: http://localhost:5000/search
```

## 📝 API Response Example

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

## 🎨 Color Coding

**Log Levels:**
- DEBUG → Gray
- INFO → Cyan
- WARNING → Yellow
- ERROR → Red
- CRITICAL → Dark Red

**Status Codes:**
- 2xx → Green (Success)
- 4xx → Yellow (Client Error)
- 5xx → Red (Server Error)

**Response Times:**
- < 500ms → Green (Fast)
- 500-1000ms → Yellow (Medium)
- > 1000ms → Red (Slow)

## 📥 CSV Export

Click "Export CSV" button to download current page results with:
- Timestamp
- Level
- Endpoint
- Status Code
- Response Time (ms)
- Server
- Message

Filename format: `saas_logs_export_2025-10-30T12-30-45.csv`

## 🔗 Navigation

- Dashboard: http://localhost:5000/
- Search: http://localhost:5000/search
- Upload: http://localhost:5000/upload
- Kibana: http://localhost:5601

## 📚 Full Documentation

See [SEARCH_FUNCTIONALITY.md](docs/SEARCH_FUNCTIONALITY.md) for:
- Detailed API reference
- Elasticsearch query examples
- Performance optimization
- Security considerations
- Future enhancements
- Troubleshooting guide
