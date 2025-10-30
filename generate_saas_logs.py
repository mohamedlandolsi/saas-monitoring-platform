"""
SaaS Web Application Log Generator
Generates realistic log data for testing the ELK Stack monitoring platform.
"""

import csv
import json
import random
from datetime import datetime, timedelta
from faker import Faker

# Initialize Faker
fake = Faker()

# Configuration
NUM_LOGS = 10000
OUTPUT_CSV = 'uploads/saas_logs.csv'
OUTPUT_JSON = 'uploads/saas_logs.json'

# Log types
LOG_TYPES = ['web_request', 'database_query']
LOG_TYPE_WEIGHTS = [90, 10]  # 90% web requests, 10% database queries

# Log levels with exact distribution
LOG_LEVELS = ['INFO', 'WARNING', 'ERROR', 'CRITICAL']
LOG_LEVEL_WEIGHTS = [70, 15, 10, 5]

# HTTP Methods
HTTP_METHODS = ['GET', 'POST', 'PUT', 'DELETE']
HTTP_METHOD_WEIGHTS = [60, 25, 10, 5]

# API Endpoints
ENDPOINTS = [
    '/api/auth/login',
    '/api/users',
    '/api/orders',
    '/api/products',
    '/api/analytics/dashboard',
    '/api/settings',
    '/api/integrations',
    '/api/webhooks',
    '/api/reports',
    '/api/billing',
]

# Status codes with exact distribution
STATUS_CODES = [200, 201, 400, 404, 500, 503, 401]
STATUS_CODE_WEIGHTS = [70, 5, 10, 5, 3, 2, 5]

# Messages based on status codes
STATUS_MESSAGES = {
    200: [
        'Request processed successfully',
        'Data retrieved successfully',
        'Operation completed successfully',
        'Resource fetched successfully',
        'Action executed successfully',
    ],
    201: [
        'Resource created successfully',
        'New record added to database',
        'Entity created successfully',
        'User registration completed',
    ],
    400: [
        'Bad request - invalid parameters',
        'Missing required fields in request',
        'Validation failed for input data',
        'Invalid JSON format in request body',
        'Request parameter validation error',
    ],
    404: [
        'Resource not found',
        'Requested endpoint does not exist',
        'User not found in database',
        'Record not found',
        'API endpoint not found',
    ],
    500: [
        'Internal server error occurred',
        'Database connection failed',
        'Unhandled exception in request handler',
        'Service error - unable to process request',
        'Critical error in application logic',
    ],
    503: [
        'Service temporarily unavailable',
        'Database connection pool exhausted',
        'System overloaded - retry later',
        'Upstream service unavailable',
    ],
    401: [
        'Authentication required',
        'Invalid authentication token',
        'Token expired - please login again',
        'Unauthorized access attempt',
        'Missing authentication credentials',
    ],
}

# SQL Queries for database logs
SQL_QUERIES = [
    'SELECT * FROM users WHERE id = ? AND active = true',
    'SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 10',
    'INSERT INTO audit_logs (user_id, action, timestamp) VALUES (?, ?, ?)',
    'UPDATE users SET last_login = ?, login_count = login_count + 1 WHERE id = ?',
    'SELECT COUNT(*) FROM products WHERE category = ? AND in_stock = true',
    'SELECT o.*, u.email FROM orders o JOIN users u ON o.user_id = u.id WHERE o.status = ?',
    'DELETE FROM sessions WHERE expired_at < ? AND user_id = ?',
    'UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ? AND stock_quantity >= ?',
    'SELECT * FROM analytics_events WHERE tenant_id = ? AND created_at > ? ORDER BY created_at DESC',
    'INSERT INTO webhooks_queue (tenant_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)',
]

# Servers
SERVERS = ['server-01', 'server-02', 'server-03', 'server-04', 'server-05']

# Tenants
TENANTS = [f'tenant_{i}' for i in range(1, 51)]


def generate_timestamp():
    """Generate a random timestamp within the last 30 days."""
    now = datetime.now()
    days_ago = random.randint(0, 30)
    hours_ago = random.randint(0, 23)
    minutes_ago = random.randint(0, 59)
    seconds_ago = random.randint(0, 59)
    
    timestamp = now - timedelta(
        days=days_ago,
        hours=hours_ago,
        minutes=minutes_ago,
        seconds=seconds_ago
    )
    
    return timestamp


def generate_response_time():
    """
    Generate response time with realistic distribution:
    - Mostly 10-500ms (85%)
    - Some outliers 500-3000ms (12%)
    - Few extreme 3000-5000ms (3%)
    """
    rand = random.random()
    
    if rand < 0.85:
        # Mostly fast responses
        return random.randint(10, 500)
    elif rand < 0.97:
        # Some slower responses
        return random.randint(500, 3000)
    else:
        # Few very slow responses
        return random.randint(3000, 5000)


def generate_log_entry():
    """Generate a single log entry with all required fields."""
    
    # Timestamp
    timestamp = generate_timestamp()
    
    # Log type
    log_type = random.choices(LOG_TYPES, weights=LOG_TYPE_WEIGHTS)[0]
    
    # Log level
    level = random.choices(LOG_LEVELS, weights=LOG_LEVEL_WEIGHTS)[0]
    
    # Client IP
    client_ip = fake.ipv4()
    
    # User ID (10% null for anonymous)
    user_id = '' if random.random() < 0.10 else f'user_{random.randint(1, 500)}'
    
    # HTTP Method
    method = random.choices(HTTP_METHODS, weights=HTTP_METHOD_WEIGHTS)[0]
    
    # Endpoint
    endpoint = random.choice(ENDPOINTS)
    
    # Status code
    status_code = random.choices(STATUS_CODES, weights=STATUS_CODE_WEIGHTS)[0]
    
    # Response time
    response_time_ms = generate_response_time()
    
    # User agent
    user_agent = fake.user_agent()
    
    # Message based on status code
    message = random.choice(STATUS_MESSAGES[status_code])
    
    # SQL query (10% of logs have SQL query)
    sql_query = ''
    query_duration_ms = ''
    if random.random() < 0.10:
        sql_query = random.choice(SQL_QUERIES)
        query_duration_ms = random.randint(5, 2000)
    
    # Server
    server = random.choice(SERVERS)
    
    # Tenant ID
    tenant_id = random.choice(TENANTS)
    
    return {
        'timestamp': timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',  # ISO8601 format
        'log_type': log_type,
        'level': level,
        'client_ip': client_ip,
        'user_id': user_id,
        'method': method,
        'endpoint': endpoint,
        'status_code': status_code,
        'response_time_ms': response_time_ms,
        'user_agent': user_agent,
        'message': message,
        'sql_query': sql_query,
        'query_duration_ms': query_duration_ms,
        'server': server,
        'tenant_id': tenant_id,
    }


def generate_logs(num_logs):
    """Generate multiple log entries."""
    print(f'🚀 Generating {num_logs:,} SaaS log entries...\n')
    logs = []
    
    for i in range(num_logs):
        log = generate_log_entry()
        logs.append(log)
        
        if (i + 1) % 1000 == 0:
            print(f'   ✓ Generated {i + 1:,} logs...')
    
    print(f'\n✅ Successfully generated {num_logs:,} logs!')
    return logs


def save_to_csv(logs, filename):
    """Save logs to CSV file with header row."""
    print(f'\n📄 Saving logs to {filename}...')
    
    # CSV headers (column names)
    headers = [
        'timestamp',
        'log_type',
        'level',
        'client_ip',
        'user_id',
        'method',
        'endpoint',
        'status_code',
        'response_time_ms',
        'user_agent',
        'message',
        'sql_query',
        'query_duration_ms',
        'server',
        'tenant_id',
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()  # Write header row
        writer.writerows(logs)
    
    print(f'   ✓ Saved {len(logs):,} logs to {filename}')


def save_to_json(logs, filename):
    """Save logs to JSON file (JSONL format - one JSON object per line)."""
    print(f'\n📄 Saving logs to {filename}...')
    
    with open(filename, 'w', encoding='utf-8') as f:
        for log in logs:
            json.dump(log, f)
            f.write('\n')
    
    print(f'   ✓ Saved {len(logs):,} logs to {filename}')


def print_statistics(logs):
    """Print comprehensive statistics about generated logs."""
    print('\n' + '=' * 70)
    print('📊 LOG GENERATION STATISTICS')
    print('=' * 70)
    
    # Total logs
    print(f'\n📝 Total Logs Generated: {len(logs):,}')
    
    # Date range
    timestamps = [datetime.strptime(log['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ') for log in logs]
    earliest = min(timestamps)
    latest = max(timestamps)
    print(f'📅 Date Range: {earliest.strftime("%Y-%m-%d %H:%M:%S")} to {latest.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'   Duration: {(latest - earliest).days} days')
    
    # Status code distribution
    print(f'\n🔢 Status Code Distribution:')
    status_counts = {}
    for log in logs:
        status = log['status_code']
        status_counts[status] = status_counts.get(status, 0) + 1
    
    for status in sorted(status_counts.keys()):
        count = status_counts[status]
        percentage = (count / len(logs)) * 100
        bar = '█' * int(percentage / 2)
        print(f'   {status}: {count:>6,} ({percentage:>5.1f}%) {bar}')
    
    # Log level distribution
    print(f'\n📊 Log Level Distribution:')
    level_counts = {}
    for log in logs:
        level = log['level']
        level_counts[level] = level_counts.get(level, 0) + 1
    
    for level in LOG_LEVELS:
        count = level_counts.get(level, 0)
        percentage = (count / len(logs)) * 100
        bar = '█' * int(percentage / 2)
        print(f'   {level:<10}: {count:>6,} ({percentage:>5.1f}%) {bar}')
    
    # HTTP Method distribution
    print(f'\n🌐 HTTP Method Distribution:')
    method_counts = {}
    for log in logs:
        method = log['method']
        method_counts[method] = method_counts.get(method, 0) + 1
    
    for method in HTTP_METHODS:
        count = method_counts.get(method, 0)
        percentage = (count / len(logs)) * 100
        print(f'   {method:<8}: {count:>6,} ({percentage:>5.1f}%)')
    
    # Log type distribution
    print(f'\n📦 Log Type Distribution:')
    type_counts = {}
    for log in logs:
        log_type = log['log_type']
        type_counts[log_type] = type_counts.get(log_type, 0) + 1
    
    for log_type, count in sorted(type_counts.items()):
        percentage = (count / len(logs)) * 100
        print(f'   {log_type:<20}: {count:>6,} ({percentage:>5.1f}%)')
    
    # Response time statistics
    response_times = [log['response_time_ms'] for log in logs]
    avg_response = sum(response_times) / len(response_times)
    min_response = min(response_times)
    max_response = max(response_times)
    
    print(f'\n⚡ Response Time Statistics:')
    print(f'   Average: {avg_response:.2f} ms')
    print(f'   Minimum: {min_response} ms')
    print(f'   Maximum: {max_response} ms')
    
    # SQL queries
    sql_count = sum(1 for log in logs if log['sql_query'])
    sql_percentage = (sql_count / len(logs)) * 100
    print(f'\n🗄️  Database Queries:')
    print(f'   Logs with SQL: {sql_count:,} ({sql_percentage:.1f}%)')
    
    if sql_count > 0:
        query_times = [log['query_duration_ms'] for log in logs if log['query_duration_ms']]
        avg_query_time = sum(query_times) / len(query_times)
        print(f'   Avg Query Time: {avg_query_time:.2f} ms')
    
    # Anonymous vs authenticated
    anonymous = sum(1 for log in logs if not log['user_id'])
    authenticated = len(logs) - anonymous
    print(f'\n👤 User Authentication:')
    print(f'   Authenticated: {authenticated:,} ({(authenticated/len(logs))*100:.1f}%)')
    print(f'   Anonymous: {anonymous:,} ({(anonymous/len(logs))*100:.1f}%)')
    
    # Top endpoints
    print(f'\n🔝 Top 5 Endpoints:')
    endpoint_counts = {}
    for log in logs:
        endpoint = log['endpoint']
        endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1
    
    top_endpoints = sorted(endpoint_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    for endpoint, count in top_endpoints:
        percentage = (count / len(logs)) * 100
        print(f'   {endpoint:<30}: {count:>5,} ({percentage:>5.1f}%)')
    
    # Server distribution
    print(f'\n🖥️  Server Distribution:')
    server_counts = {}
    for log in logs:
        server = log['server']
        server_counts[server] = server_counts.get(server, 0) + 1
    
    for server in sorted(server_counts.keys()):
        count = server_counts[server]
        percentage = (count / len(logs)) * 100
        print(f'   {server}: {count:>5,} ({percentage:>5.1f}%)')
    
    print('\n' + '=' * 70)


def main():
    """Main function to generate and save logs."""
    print('=' * 70)
    print('🎯 SaaS WEB APPLICATION LOG GENERATOR')
    print('=' * 70)
    print(f'Target: {NUM_LOGS:,} log entries')
    print(f'Output CSV: {OUTPUT_CSV}')
    print(f'Output JSON: {OUTPUT_JSON}')
    print('=' * 70 + '\n')
    
    # Generate logs
    logs = generate_logs(NUM_LOGS)
    
    # Save to files
    save_to_csv(logs, OUTPUT_CSV)
    save_to_json(logs, OUTPUT_JSON)
    
    # Print statistics
    print_statistics(logs)
    
    print('\n✅ Log generation completed successfully!')
    print('\n📋 Next Steps:')
    print(f'   1. Check the generated files:')
    print(f'      • {OUTPUT_CSV}')
    print(f'      • {OUTPUT_JSON}')
    print(f'   2. Logstash will automatically process these files')
    print(f'   3. View logs in Kibana: http://localhost:5601')
    print(f'   4. Search logs in web app: http://localhost:5000/search')
    print(f'   5. Upload more files via: http://localhost:5000/upload')
    print('\n' + '=' * 70)


if __name__ == '__main__':
    main()
