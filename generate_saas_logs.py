"""
SaaS Web Application Log Generator
Generates realistic log data for testing the ELK Stack monitoring platform.

Usage:
    python generate_saas_logs.py --count 50000 --days 60 --format csv
    python generate_saas_logs.py --count 10000 --format both --output ./data
    python generate_saas_logs.py --help
"""

import csv
import json
import random
import argparse
import os
from datetime import datetime, timedelta
from faker import Faker
from collections import defaultdict

# Initialize Faker
fake = Faker()

# Log types
LOG_TYPES = ['web_request', 'database_query']
LOG_TYPE_WEIGHTS = [90, 10]  # 90% web requests, 10% database queries

# Log levels with exact distribution
LOG_LEVELS = ['INFO', 'WARNING', 'ERROR', 'CRITICAL']
LOG_LEVEL_WEIGHTS = [70, 15, 10, 5]

# HTTP Methods
HTTP_METHODS = ['GET', 'POST', 'PUT', 'DELETE']
HTTP_METHOD_WEIGHTS = [60, 25, 10, 5]

# API Endpoints with associated SQL queries
ENDPOINT_SQL_MAPPING = {
    '/api/auth/login': [
        'SELECT * FROM users WHERE email = ? AND active = true',
        'UPDATE users SET last_login = ?, login_count = login_count + 1 WHERE id = ?',
        'INSERT INTO sessions (user_id, token, created_at) VALUES (?, ?, ?)',
    ],
    '/api/users': [
        'SELECT * FROM users WHERE id = ? AND active = true',
        'SELECT * FROM users WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 50',
        'UPDATE users SET updated_at = ? WHERE id = ?',
        'INSERT INTO users (email, password_hash, tenant_id, created_at) VALUES (?, ?, ?, ?)',
    ],
    '/api/orders': [
        'SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 10',
        'SELECT o.*, u.email FROM orders o JOIN users u ON o.user_id = u.id WHERE o.status = ?',
        'INSERT INTO orders (user_id, total_amount, status, created_at) VALUES (?, ?, ?, ?)',
        'UPDATE orders SET status = ?, updated_at = ? WHERE id = ?',
    ],
    '/api/products': [
        'SELECT * FROM products WHERE category = ? AND in_stock = true',
        'SELECT COUNT(*) FROM products WHERE category = ? AND in_stock = true',
        'UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ? AND stock_quantity >= ?',
        'SELECT * FROM products WHERE id = ?',
    ],
    '/api/analytics/dashboard': [
        'SELECT * FROM analytics_events WHERE tenant_id = ? AND created_at > ? ORDER BY created_at DESC',
        'SELECT COUNT(*), AVG(value) FROM analytics_events WHERE tenant_id = ? AND event_type = ?',
        'SELECT DATE(created_at) as date, COUNT(*) as count FROM analytics_events WHERE tenant_id = ? GROUP BY DATE(created_at)',
    ],
    '/api/settings': [
        'SELECT * FROM settings WHERE tenant_id = ? AND key = ?',
        'UPDATE settings SET value = ?, updated_at = ? WHERE tenant_id = ? AND key = ?',
        'INSERT INTO audit_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)',
    ],
    '/api/integrations': [
        'SELECT * FROM integrations WHERE tenant_id = ? AND active = true',
        'UPDATE integrations SET config = ?, updated_at = ? WHERE id = ?',
        'SELECT * FROM integration_logs WHERE integration_id = ? ORDER BY created_at DESC LIMIT 100',
    ],
    '/api/webhooks': [
        'INSERT INTO webhooks_queue (tenant_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)',
        'SELECT * FROM webhooks WHERE tenant_id = ? AND active = true',
        'UPDATE webhooks SET last_triggered = ? WHERE id = ?',
    ],
    '/api/reports': [
        'SELECT * FROM reports WHERE tenant_id = ? AND created_at > ?',
        'INSERT INTO reports (tenant_id, type, data, created_at) VALUES (?, ?, ?, ?)',
    ],
    '/api/billing': [
        'SELECT * FROM invoices WHERE tenant_id = ? ORDER BY created_at DESC',
        'SELECT SUM(amount) FROM invoices WHERE tenant_id = ? AND status = ?',
        'UPDATE invoices SET status = ?, paid_at = ? WHERE id = ?',
    ],
}

ENDPOINTS = list(ENDPOINT_SQL_MAPPING.keys())

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

# Servers
SERVERS = ['server-01', 'server-02', 'server-03', 'server-04', 'server-05']

# Tenants
TENANTS = [f'tenant_{i}' for i in range(1, 51)]

# Global state for realistic patterns
user_sessions = {}  # Track active user sessions
error_burst_probability = 0.0  # Probability of error burst
last_error_burst_time = None


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Generate realistic SaaS application logs for testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s --count 50000 --days 60 --format csv
  %(prog)s --count 10000 --format both --output ./data
  %(prog)s --count 5000 --days 7 --format json --output ./logs
        '''
    )
    
    parser.add_argument(
        '--count',
        type=int,
        default=10000,
        help='Number of log entries to generate (default: 10000)'
    )
    
    parser.add_argument(
        '--format',
        type=str,
        choices=['csv', 'json', 'both'],
        default='both',
        help='Output format: csv, json, or both (default: both)'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Date range in days (default: 30)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='uploads',
        help='Output directory (default: uploads)'
    )
    
    return parser.parse_args()


def is_peak_hour(hour):
    """Check if hour is within peak hours (9 AM - 5 PM)."""
    return 9 <= hour <= 17


def should_create_error_burst():
    """Decide if we should create an error burst (5% chance)."""
    return random.random() < 0.05


def generate_timestamp(days_range, base_time=None):
    """
    Generate a random timestamp within the specified date range.
    Favors peak hours (9 AM - 5 PM) for more realistic distribution.
    """
    if base_time:
        # Generate timestamp close to base_time for session continuity
        seconds_offset = random.randint(-300, 300)  # Within 5 minutes
        return base_time + timedelta(seconds=seconds_offset)
    
    now = datetime.now()
    days_ago = random.randint(0, days_range)
    
    # Peak hours have 3x more traffic
    if random.random() < 0.75:  # 75% during peak hours
        hour = random.randint(9, 17)
    else:  # 25% during off-peak
        hour = random.choice(list(range(0, 9)) + list(range(18, 24)))
    
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    microsecond = random.randint(0, 999999)
    
    timestamp = now - timedelta(days=days_ago)
    timestamp = timestamp.replace(hour=hour, minute=minute, second=second, microsecond=microsecond)
    
    return timestamp


def generate_response_time(endpoint, status_code, has_sql=False, query_duration=0):
    """
    Generate response time correlated with query duration and endpoint complexity.
    - Errors (5xx) are faster (system fails fast)
    - Successful requests vary by endpoint
    - Response time >= query duration
    """
    base_time = 0
    
    # Base time by endpoint complexity
    if endpoint in ['/api/analytics/dashboard', '/api/reports']:
        base_time = random.randint(200, 800)  # Complex analytics
    elif endpoint in ['/api/orders', '/api/products']:
        base_time = random.randint(50, 300)  # Medium complexity
    else:
        base_time = random.randint(10, 150)  # Simple requests
    
    # Adjust for SQL query
    if has_sql and query_duration:
        base_time = max(base_time, query_duration + random.randint(10, 50))
    
    # Adjust for status code
    if status_code >= 500:
        # Errors often fail fast
        base_time = int(base_time * 0.3)
    elif status_code >= 400:
        # Client errors are typically fast
        base_time = int(base_time * 0.5)
    
    # Add some variability
    variance = int(base_time * 0.3)
    response_time = base_time + random.randint(-variance, variance)
    
    # Occasional slow outliers (5%)
    if random.random() < 0.05:
        response_time += random.randint(1000, 3000)
    
    return max(response_time, 1)  # Minimum 1ms


def get_active_user():
    """Get an active user from session or create new session."""
    global user_sessions
    
    # 60% chance to use existing session
    if user_sessions and random.random() < 0.6:
        user_id = random.choice(list(user_sessions.keys()))
        session = user_sessions[user_id]
        
        # Check if session is still valid (within 30 minutes)
        if (datetime.now() - session['last_activity']).seconds < 1800:
            session['last_activity'] = datetime.now()
            session['request_count'] += 1
            return user_id
        else:
            # Session expired, remove it
            del user_sessions[user_id]
    
    # Create new session (40% of time, or when needed)
    user_id = f'user_{random.randint(1, 500)}'
    user_sessions[user_id] = {
        'last_activity': datetime.now(),
        'request_count': 1,
        'tenant_id': random.choice(TENANTS)
    }
    
    return user_id


def generate_log_entry(timestamp=None, days_range=30, force_error=False):
    """Generate a single log entry with all required fields and realistic patterns."""
    global error_burst_probability, last_error_burst_time
    
    # Check if we're in an error burst
    if force_error or (error_burst_probability > 0 and random.random() < error_burst_probability):
        # Error burst mode - increase error likelihood
        level_weights = [30, 20, 35, 15]  # More errors and warnings
        status_weights = [30, 2, 20, 15, 20, 8, 5]  # More failures
    else:
        level_weights = LOG_LEVEL_WEIGHTS
        status_weights = STATUS_CODE_WEIGHTS
    
    # Timestamp
    if timestamp is None:
        timestamp = generate_timestamp(days_range)
    
    # Log type
    log_type = random.choices(LOG_TYPES, weights=LOG_TYPE_WEIGHTS)[0]
    
    # Log level
    level = random.choices(LOG_LEVELS, weights=level_weights)[0]
    
    # Client IP
    client_ip = fake.ipv4()
    
    # User ID - favor active sessions (90% authenticated during peak hours)
    hour = timestamp.hour
    if is_peak_hour(hour) and random.random() < 0.9:
        user_id = get_active_user()
    elif random.random() < 0.8:  # 80% authenticated off-peak
        user_id = get_active_user()
    else:
        user_id = ''  # Anonymous
    
    # Get tenant from user session if available
    if user_id and user_id in user_sessions:
        tenant_id = user_sessions[user_id]['tenant_id']
    else:
        tenant_id = random.choice(TENANTS)
    
    # HTTP Method
    method = random.choices(HTTP_METHODS, weights=HTTP_METHOD_WEIGHTS)[0]
    
    # Endpoint
    endpoint = random.choice(ENDPOINTS)
    
    # Status code
    status_code = random.choices(STATUS_CODES, weights=status_weights)[0]
    
    # SQL query correlated with endpoint (30% of logs have SQL query)
    sql_query = ''
    query_duration_ms = 0
    if random.random() < 0.30:
        sql_query = random.choice(ENDPOINT_SQL_MAPPING[endpoint])
        
        # Query duration correlated with complexity
        if 'SELECT' in sql_query and 'JOIN' in sql_query:
            query_duration_ms = random.randint(50, 500)  # Complex queries
        elif 'SELECT' in sql_query:
            query_duration_ms = random.randint(10, 200)  # Simple selects
        elif 'INSERT' in sql_query or 'UPDATE' in sql_query:
            query_duration_ms = random.randint(20, 150)  # Writes
        else:
            query_duration_ms = random.randint(5, 100)  # Other
        
        # Slow query outliers (3%)
        if random.random() < 0.03:
            query_duration_ms += random.randint(1000, 3000)
    
    # Response time correlated with query duration
    response_time_ms = generate_response_time(endpoint, status_code, bool(sql_query), query_duration_ms)
    
    # User agent
    user_agent = fake.user_agent()
    
    # Message based on status code
    message = random.choice(STATUS_MESSAGES[status_code])
    
    # Server
    server = random.choice(SERVERS)
    
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
        'query_duration_ms': query_duration_ms if sql_query else '',
        'server': server,
        'tenant_id': tenant_id,
    }


def generate_logs(num_logs, days_range):
    """Generate multiple log entries with realistic patterns."""
    global error_burst_probability, last_error_burst_time
    
    print(f'🚀 Generating {num_logs:,} SaaS log entries over {days_range} days...\n')
    logs = []
    
    for i in range(num_logs):
        # Occasionally create error bursts (multiple errors in short time)
        if should_create_error_burst() and error_burst_probability == 0:
            error_burst_probability = 0.7  # 70% errors during burst
            last_error_burst_time = datetime.now()
            burst_size = random.randint(5, 15)
            burst_timestamp = generate_timestamp(days_range)
            
            print(f'   ⚠️  Simulating error burst at {burst_timestamp.strftime("%Y-%m-%d %H:%M:%S")} ({burst_size} errors)')
            
            for _ in range(burst_size):
                log = generate_log_entry(timestamp=burst_timestamp, days_range=days_range, force_error=True)
                logs.append(log)
                # Advance time by a few seconds
                burst_timestamp += timedelta(seconds=random.randint(1, 5))
                i += 1
                if i >= num_logs:
                    break
            
            error_burst_probability = 0  # End burst
        else:
            log = generate_log_entry(days_range=days_range)
            logs.append(log)
        
        if (i + 1) % 5000 == 0:
            print(f'   ✓ Generated {i + 1:,} logs...')
    
    print(f'\n✅ Successfully generated {len(logs):,} logs!')
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
    
    file_size = os.path.getsize(filename)
    print(f'   ✓ Saved {len(logs):,} logs to {filename}')
    print(f'   📦 File size: {file_size / (1024 * 1024):.2f} MB')


def save_to_json(logs, filename):
    """Save logs to JSON file (JSONL format - one JSON object per line)."""
    print(f'\n📄 Saving logs to {filename}...')
    
    with open(filename, 'w', encoding='utf-8') as f:
        for log in logs:
            json.dump(log, f)
            f.write('\n')
    
    file_size = os.path.getsize(filename)
    print(f'   ✓ Saved {len(logs):,} logs to {filename}')
    print(f'   📦 File size: {file_size / (1024 * 1024):.2f} MB')


def print_statistics(logs, days_range):
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
    print(f'   Duration: {(latest - earliest).days + 1} days (requested: {days_range} days)')
    
    # Status code distribution
    print(f'\n🔢 Status Code Distribution:')
    status_counts = defaultdict(int)
    for log in logs:
        status_counts[log['status_code']] += 1
    
    for status in sorted(status_counts.keys()):
        count = status_counts[status]
        percentage = (count / len(logs)) * 100
        bar = '█' * int(percentage / 2)
        print(f'   {status}: {count:>6,} ({percentage:>5.1f}%) {bar}')
    
    # Log level distribution
    print(f'\n📊 Log Level Distribution:')
    level_counts = defaultdict(int)
    for log in logs:
        level_counts[log['level']] += 1
    
    for level in LOG_LEVELS:
        count = level_counts.get(level, 0)
        percentage = (count / len(logs)) * 100
        bar = '█' * int(percentage / 2)
        print(f'   {level:<10}: {count:>6,} ({percentage:>5.1f}%) {bar}')
    
    # HTTP Method distribution
    print(f'\n🌐 HTTP Method Distribution:')
    method_counts = defaultdict(int)
    for log in logs:
        method_counts[log['method']] += 1
    
    for method in HTTP_METHODS:
        count = method_counts.get(method, 0)
        percentage = (count / len(logs)) * 100
        print(f'   {method:<8}: {count:>6,} ({percentage:>5.1f}%)')
    
    # Log type distribution
    print(f'\n📦 Log Type Distribution:')
    type_counts = defaultdict(int)
    for log in logs:
        type_counts[log['log_type']] += 1
    
    for log_type, count in sorted(type_counts.items()):
        percentage = (count / len(logs)) * 100
        print(f'   {log_type:<20}: {count:>6,} ({percentage:>5.1f}%)')
    
    # Response time statistics by endpoint
    print(f'\n⚡ Average Response Time by Endpoint:')
    endpoint_times = defaultdict(list)
    for log in logs:
        endpoint_times[log['endpoint']].append(log['response_time_ms'])
    
    endpoint_stats = []
    for endpoint, times in endpoint_times.items():
        avg_time = sum(times) / len(times)
        endpoint_stats.append((endpoint, avg_time, len(times)))
    
    endpoint_stats.sort(key=lambda x: x[1], reverse=True)
    for endpoint, avg_time, count in endpoint_stats[:10]:
        print(f'   {endpoint:<30}: {avg_time:>7.2f} ms (n={count:,})')
    
    # Overall response time statistics
    response_times = [log['response_time_ms'] for log in logs]
    avg_response = sum(response_times) / len(response_times)
    min_response = min(response_times)
    max_response = max(response_times)
    
    # Calculate percentiles
    sorted_times = sorted(response_times)
    p50 = sorted_times[len(sorted_times) // 2]
    p95 = sorted_times[int(len(sorted_times) * 0.95)]
    p99 = sorted_times[int(len(sorted_times) * 0.99)]
    
    print(f'\n⚡ Overall Response Time Statistics:')
    print(f'   Average: {avg_response:.2f} ms')
    print(f'   Minimum: {min_response} ms')
    print(f'   Maximum: {max_response} ms')
    print(f'   P50 (median): {p50} ms')
    print(f'   P95: {p95} ms')
    print(f'   P99: {p99} ms')
    
    # SQL queries
    sql_count = sum(1 for log in logs if log['sql_query'])
    sql_percentage = (sql_count / len(logs)) * 100
    print(f'\n🗄️  Database Query Statistics:')
    print(f'   Logs with SQL: {sql_count:,} ({sql_percentage:.1f}%)')
    
    if sql_count > 0:
        query_times = [log['query_duration_ms'] for log in logs if log['query_duration_ms']]
        avg_query_time = sum(query_times) / len(query_times)
        max_query_time = max(query_times)
        min_query_time = min(query_times)
        print(f'   Avg Query Time: {avg_query_time:.2f} ms')
        print(f'   Min Query Time: {min_query_time} ms')
        print(f'   Max Query Time: {max_query_time} ms')
    
    # Peak hour analysis
    peak_hour_logs = sum(1 for log in logs if is_peak_hour(datetime.strptime(log['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ').hour))
    peak_percentage = (peak_hour_logs / len(logs)) * 100
    print(f'\n⏰ Peak Hours Analysis (9 AM - 5 PM):')
    print(f'   Peak hour logs: {peak_hour_logs:,} ({peak_percentage:.1f}%)')
    print(f'   Off-peak logs: {len(logs) - peak_hour_logs:,} ({100 - peak_percentage:.1f}%)')
    
    # User session analysis
    unique_users = len(set(log['user_id'] for log in logs if log['user_id']))
    anonymous = sum(1 for log in logs if not log['user_id'])
    authenticated = len(logs) - anonymous
    print(f'\n👤 User Session Statistics:')
    print(f'   Unique users: {unique_users:,}')
    print(f'   Authenticated requests: {authenticated:,} ({(authenticated/len(logs))*100:.1f}%)')
    print(f'   Anonymous requests: {anonymous:,} ({(anonymous/len(logs))*100:.1f}%)')
    print(f'   Avg requests per user: {len(logs) / max(unique_users, 1):.2f}')
    
    # Error analysis
    error_logs = sum(1 for log in logs if log['level'] in ['ERROR', 'CRITICAL'])
    error_percentage = (error_logs / len(logs)) * 100
    status_5xx = sum(1 for log in logs if log['status_code'] >= 500)
    status_4xx = sum(1 for log in logs if 400 <= log['status_code'] < 500)
    
    print(f'\n🚨 Error Analysis:')
    print(f'   Error/Critical logs: {error_logs:,} ({error_percentage:.1f}%)')
    print(f'   5xx status codes: {status_5xx:,} ({(status_5xx/len(logs))*100:.1f}%)')
    print(f'   4xx status codes: {status_4xx:,} ({(status_4xx/len(logs))*100:.1f}%)')
    
    # Top endpoints
    print(f'\n🔝 Top 10 Endpoints by Request Count:')
    endpoint_counts = defaultdict(int)
    for log in logs:
        endpoint_counts[log['endpoint']] += 1
    
    top_endpoints = sorted(endpoint_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for endpoint, count in top_endpoints:
        percentage = (count / len(logs)) * 100
        print(f'   {endpoint:<30}: {count:>5,} ({percentage:>5.1f}%)')
    
    # Server distribution
    print(f'\n🖥️  Server Distribution:')
    server_counts = defaultdict(int)
    for log in logs:
        server_counts[log['server']] += 1
    
    for server in sorted(server_counts.keys()):
        count = server_counts[server]
        percentage = (count / len(logs)) * 100
        print(f'   {server}: {count:>5,} ({percentage:>5.1f}%)')
    
    # Tenant distribution (top 10)
    print(f'\n🏢 Top 10 Tenants by Request Count:')
    tenant_counts = defaultdict(int)
    for log in logs:
        tenant_counts[log['tenant_id']] += 1
    
    top_tenants = sorted(tenant_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for tenant, count in top_tenants:
        percentage = (count / len(logs)) * 100
        print(f'   {tenant}: {count:>5,} ({percentage:>5.1f}%)')
    
    print('\n' + '=' * 70)


def main():
    """Main function to generate and save logs."""
    # Parse command-line arguments
    args = parse_arguments()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)
    
    # Determine output files
    output_csv = os.path.join(args.output, 'saas_logs.csv')
    output_json = os.path.join(args.output, 'saas_logs.json')
    
    print('=' * 70)
    print('🎯 SaaS WEB APPLICATION LOG GENERATOR')
    print('=' * 70)
    print(f'Configuration:')
    print(f'  • Log entries: {args.count:,}')
    print(f'  • Date range: {args.days} days')
    print(f'  • Output format: {args.format}')
    print(f'  • Output directory: {args.output}')
    if args.format in ['csv', 'both']:
        print(f'  • CSV file: {output_csv}')
    if args.format in ['json', 'both']:
        print(f'  • JSON file: {output_json}')
    print('=' * 70 + '\n')
    
    # Generate logs
    logs = generate_logs(args.count, args.days)
    
    # Sort logs by timestamp for realistic ordering
    logs.sort(key=lambda x: x['timestamp'])
    
    # Save to files based on format
    if args.format in ['csv', 'both']:
        save_to_csv(logs, output_csv)
    
    if args.format in ['json', 'both']:
        save_to_json(logs, output_json)
    
    # Print statistics
    print_statistics(logs, args.days)
    
    print('\n✅ Log generation completed successfully!')
    print('\n📋 Next Steps:')
    print(f'   1. Check the generated files in: {args.output}')
    if args.format in ['csv', 'both']:
        print(f'      • {output_csv}')
    if args.format in ['json', 'both']:
        print(f'      • {output_json}')
    print(f'   2. Upload via web interface: http://localhost:5000/upload')
    print(f'   3. Or copy to uploads/ directory for Logstash processing')
    print(f'   4. View logs in Kibana: http://localhost:5601')
    print(f'   5. Search logs in web app: http://localhost:5000/search')
    print('\n' + '=' * 70)


if __name__ == '__main__':
    main()