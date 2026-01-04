# Log Generator Enhancements

## Overview
Enhanced `generate_saas_logs.py` with command-line arguments, realistic data patterns, and comprehensive statistics for better testing and monitoring.

## Key Features

### 1. Command-Line Arguments
```bash
# Generate 50,000 logs over 60 days in CSV format
python3 generate_saas_logs.py --count 50000 --days 60 --format csv

# Generate logs with default settings (10,000 logs, 30 days, both formats)
python3 generate_saas_logs.py

# Generate JSON only in custom directory
python3 generate_saas_logs.py --count 20000 --format json --output ./custom_logs

# Show help
python3 generate_saas_logs.py --help
```

#### Available Arguments:
- `--count`: Number of log entries to generate (default: 10,000)
- `--format`: Output format: `csv`, `json`, or `both` (default: both)
- `--days`: Date range in days (default: 30)
- `--output`: Output directory (default: uploads)

### 2. Realistic Data Patterns

#### Peak Hour Simulation
- **75% of traffic** occurs during business hours (9 AM - 5 PM)
- **25% of traffic** occurs off-peak hours
- Reflects typical SaaS usage patterns

#### User Session Tracking
- **60% chance** to reuse an existing active user (within 30 minutes)
- **40% chance** to create a new user session
- Average **28-144 requests per user** depending on dataset size
- Simulates realistic multi-request user journeys

#### Error Burst Simulation
- **5% chance** of triggering an error burst
- Burst generates **5-15 consecutive errors** within seconds
- **70% error rate** during burst vs **15% normal**
- Simulates cascading failures and outages

#### SQL Query Correlation
- **30% of logs** include SQL queries
- Queries mapped to relevant endpoints:
  * `/api/users` → User table queries (SELECT, INSERT, UPDATE)
  * `/api/orders` → Order queries with JOINs
  * `/api/analytics/dashboard` → Complex aggregation queries
  * `/api/reports` → Reporting queries with JOINs
- Realistic query durations:
  * Simple SELECT: 10-200ms
  * SELECT with JOIN: 50-500ms
  * INSERT/UPDATE: 20-150ms
  * **3% slow queries**: +1000-3000ms penalty

#### Response Time Correlation
Response times reflect endpoint complexity and SQL query durations:

**Endpoint-Based:**
- Analytics endpoints: 200-800ms
- Order/product endpoints: 50-300ms
- Auth endpoints: 10-150ms

**SQL Query Correlation:**
- Response time >= Query duration + 10-50ms overhead
- Ensures realistic database latency

**Status Code Impact:**
- 5xx errors: 30% of normal time (fail fast)
- 4xx errors: 50% of normal time (quick validation)
- **5% outliers**: +1000-3000ms spike

### 3. Enhanced Statistics Output

The script now provides comprehensive statistics:

#### Log Overview
- Total logs generated
- Date range with duration
- File sizes in MB

#### Distribution Analysis
- Status code distribution with percentage bars
- Log level breakdown (INFO, WARNING, ERROR, CRITICAL)
- HTTP method distribution
- Log type distribution

#### Performance Metrics
- **Average response time by endpoint** (top 10)
- Overall response time statistics:
  * Average, Min, Max
  * **P50 (median), P95, P99 percentiles**
- Database query statistics:
  * Percentage of logs with SQL
  * Avg/Min/Max query duration

#### Traffic Analysis
- **Peak hour distribution** (9 AM - 5 PM vs off-peak)
- User session statistics:
  * Unique users
  * Authenticated vs anonymous requests
  * Average requests per user

#### Error Analysis
- Error/Critical log count and percentage
- 5xx status code breakdown
- 4xx status code breakdown

#### Usage Statistics
- Top 10 endpoints by request count
- Server distribution across 5 servers
- Top 10 tenants by request count

### 4. Performance

#### Generation Speed
- **50,000 logs**: ~2 seconds
- **10,000 logs**: <1 second
- Efficient in-memory processing

#### File Sizes
| Log Count | CSV Size | JSON Size |
|-----------|----------|-----------|
| 10,000    | 3.6 MB   | 6.8 MB    |
| 50,000    | 18.1 MB  | 33.9 MB   |
| 100,000   | 36.2 MB  | 67.8 MB   |

## Example Output

```bash
$ python3 generate_saas_logs.py --count 50000 --days 60 --format csv

======================================================================
🎯 SaaS WEB APPLICATION LOG GENERATOR
======================================================================
Configuration:
  • Log entries: 50,000
  • Date range: 60 days
  • Output format: csv
  • Output directory: ./test_output
  • CSV file: ./test_output/saas_logs.csv
======================================================================

🚀 Generating 50,000 SaaS log entries over 60 days...

   ⚠️  Simulating error burst at 2025-10-11 09:03:27 (8 errors)
   ⚠️  Simulating error burst at 2025-10-16 10:08:32 (7 errors)
   ...
   ✓ Generated 50,000 logs...

✅ Successfully generated 71,967 logs!

📄 Saving logs to ./test_output/saas_logs.csv...
   ✓ Saved 71,967 logs to ./test_output/saas_logs.csv
   📦 File size: 18.07 MB

======================================================================
📊 LOG GENERATION STATISTICS
======================================================================

📝 Total Logs Generated: 71,967
📅 Date Range: 2025-08-31 00:00:06 to 2025-10-30 23:59:21
   Duration: 61 days (requested: 60 days)

🔢 Status Code Distribution:
   200: 40,688 ( 56.5%) ████████████████████████████
   201:  2,805 (  3.9%) █
   400:  9,606 ( 13.3%) ██████
   401:  3,538 (  4.9%) ██
   404:  6,045 (  8.4%) ████
   500:  6,363 (  8.8%) ████
   503:  2,922 (  4.1%) ██

⚡ Average Response Time by Endpoint:
   /api/reports                  :  497.96 ms (n=7,209)
   /api/analytics/dashboard      :  494.49 ms (n=7,218)
   /api/orders                   :  261.31 ms (n=7,174)
   /api/products                 :  251.96 ms (n=7,082)
   /api/settings                 :  204.49 ms (n=7,393)
   ...

⏰ Peak Hours Analysis (9 AM - 5 PM):
   Peak hour logs: 53,985 (75.0%)
   Off-peak logs: 17,982 (25.0%)

👤 User Session Statistics:
   Unique users: 500
   Authenticated requests: 67,299 (93.5%)
   Anonymous requests: 4,668 (6.5%)
   Avg requests per user: 143.93

🚨 Error Analysis:
   Error/Critical logs: 19,312 (26.8%)
   5xx status codes: 9,285 (12.9%)
   4xx status codes: 19,189 (26.7%)

======================================================================
```

## Use Cases

### 1. Testing Dashboard Charts
Generate realistic data to test Chart.js visualizations:
```bash
python3 generate_saas_logs.py --count 100000 --days 90 --format json
```

### 2. Load Testing Elasticsearch
Generate large datasets for performance testing:
```bash
python3 generate_saas_logs.py --count 1000000 --days 180 --format both
```

### 3. Demo Data Generation
Create representative sample data:
```bash
python3 generate_saas_logs.py --count 5000 --days 7 --format csv --output ./demo_data
```

### 4. Error Pattern Analysis
Generate data to test error detection and alerting:
```bash
# Script automatically includes error bursts for testing
python3 generate_saas_logs.py --count 50000 --days 30
```

## Technical Implementation

### Data Structures
- **user_sessions**: Dict tracking active user sessions with last_activity
- **ENDPOINT_SQL_MAPPING**: Maps endpoints to relevant SQL queries
- **Global state**: Tracks error burst probability and timing

### Key Functions
- `parse_arguments()`: Argparse CLI argument handling
- `is_peak_hour(hour)`: Checks if hour falls in 9-5 range
- `should_create_error_burst()`: 5% chance of triggering burst
- `generate_timestamp()`: Weighted peak hour timestamp generation
- `generate_response_time()`: Correlated with endpoint/SQL/status
- `get_active_user()`: Session continuity with 60% reuse rate
- `generate_log_entry()`: Core realistic log generation
- `generate_logs()`: Batch generation with error burst injection
- `print_statistics()`: Comprehensive metrics reporting

### Dependencies
- `argparse`: Command-line argument parsing
- `Faker`: Realistic fake data generation
- `collections.defaultdict`: Efficient data aggregation
- Standard library: `datetime`, `random`, `csv`, `json`, `os`

## Future Enhancements

### Potential Additions
1. **Custom error burst configuration**: `--burst-rate`, `--burst-size`
2. **Multiple tenant focus**: `--tenant-id` to generate data for specific tenants
3. **Traffic pattern profiles**: `--profile` (normal, high-load, error-prone)
4. **Real-time streaming**: Generate logs continuously for live testing
5. **Custom endpoint lists**: `--endpoints-file` for specific API patterns
6. **Geographic distribution**: Add region/datacenter correlation
7. **Time-based anomalies**: Simulate maintenance windows, deployments
8. **Custom SQL query templates**: User-defined query patterns

### Performance Optimizations
1. Multi-threading for >1M log generation
2. Chunked writing for very large files
3. Memory-efficient generators for streaming

## Version History

### v2.0.0 (Current)
- Added command-line arguments
- Implemented realistic patterns (peak hours, sessions, bursts)
- Enhanced statistics with percentiles and detailed breakdowns
- Added file size reporting
- Improved documentation

### v1.0.0 (Original)
- Basic log generation
- Fixed 10,000 logs
- Simple statistics
- No CLI arguments

## Credits
Enhanced as part of the SaaS Monitoring Platform project to provide realistic test data for Chart.js dashboards, Elasticsearch ingestion, and Kibana visualization testing.
