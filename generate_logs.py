"""
SaaS Log Generator
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
OUTPUT_CSV = 'uploads/saas_logs_sample.csv'
OUTPUT_JSON = 'uploads/saas_logs_sample.json'

# Log types and endpoints
LOG_TYPES = ['api', 'web', 'database', 'auth', 'payment', 'notification']

ENDPOINTS = [
    '/api/users',
    '/api/users/{id}',
    '/api/auth/login',
    '/api/auth/logout',
    '/api/auth/register',
    '/api/products',
    '/api/products/{id}',
    '/api/orders',
    '/api/orders/{id}',
    '/api/payments',
    '/api/payments/process',
    '/api/analytics',
    '/api/settings',
    '/api/notifications',
    '/api/dashboard',
    '/health',
    '/metrics',
    '/api/reports',
    '/api/exports',
    '/api/webhooks',
]

HTTP_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']

# Status code distribution (weighted for realism)
STATUS_CODES = {
    200: 60,  # 60% success
    201: 10,  # 10% created
    204: 5,   # 5% no content
    400: 8,   # 8% bad request
    401: 5,   # 5% unauthorized
    403: 3,   # 3% forbidden
    404: 5,   # 5% not found
    500: 2,   # 2% server error
    502: 1,   # 1% bad gateway
    503: 1,   # 1% service unavailable
}

# Log levels based on status code
LOG_LEVELS = {
    200: 'info',
    201: 'info',
    204: 'info',
    400: 'warning',
    401: 'warning',
    403: 'error',
    404: 'warning',
    500: 'error',
    502: 'error',
    503: 'error',
}

# Sample SQL queries for database logs
SQL_QUERIES = [
    'SELECT * FROM users WHERE id = ?',
    'SELECT * FROM products WHERE category = ?',
    'INSERT INTO orders (user_id, product_id, quantity) VALUES (?, ?, ?)',
    'UPDATE users SET last_login = ? WHERE id = ?',
    'DELETE FROM sessions WHERE expired_at < ?',
    'SELECT COUNT(*) FROM orders WHERE created_at > ?',
    'SELECT * FROM products JOIN categories ON products.category_id = categories.id',
    'UPDATE products SET stock = stock - ? WHERE id = ?',
    'SELECT * FROM users WHERE email = ? AND active = true',
    'INSERT INTO audit_logs (user_id, action, timestamp) VALUES (?, ?, ?)',
]

# Sample messages
MESSAGES = {
    200: [
        'Request processed successfully',
        'Data retrieved successfully',
        'Operation completed',
        'Resource fetched successfully',
    ],
    201: [
        'Resource created successfully',
        'New record added',
        'Entity created',
    ],
    204: [
        'Resource deleted successfully',
        'Operation completed, no content to return',
    ],
    400: [
        'Invalid request parameters',
        'Missing required fields',
        'Validation failed',
        'Bad request format',
    ],
    401: [
        'Authentication required',
        'Invalid credentials',
        'Token expired',
        'Unauthorized access attempt',
    ],
    403: [
        'Access denied',
        'Insufficient permissions',
        'Forbidden resource',
    ],
    404: [
        'Resource not found',
        'Endpoint does not exist',
        'Record not found in database',
    ],
    500: [
        'Internal server error',
        'Database connection failed',
        'Unhandled exception occurred',
        'Service error',
    ],
    502: [
        'Bad gateway',
        'Upstream service unavailable',
    ],
    503: [
        'Service temporarily unavailable',
        'System overloaded',
    ],
}

# Server names
SERVERS = ['app-server-01', 'app-server-02', 'app-server-03', 'app-server-04', 'app-server-05']

# Tenant IDs for multi-tenant SaaS
TENANT_IDS = [f'tenant_{i:04d}' for i in range(1, 51)]


def weighted_choice(choices_dict):
    """Select a random choice based on weights."""
    choices = list(choices_dict.keys())
    weights = list(choices_dict.values())
    return random.choices(choices, weights=weights)[0]


def generate_log_entry(index):
    """Generate a single log entry."""
    # Generate timestamp within last 30 days
    days_ago = random.randint(0, 30)
    hours_ago = random.randint(0, 23)
    minutes_ago = random.randint(0, 59)
    seconds_ago = random.randint(0, 59)
    
    timestamp = datetime.now() - timedelta(
        days=days_ago,
        hours=hours_ago,
        minutes=minutes_ago,
        seconds=seconds_ago
    )
    
    # Select random endpoint and method
    endpoint = random.choice(ENDPOINTS)
    method = random.choice(HTTP_METHODS)
    
    # Replace {id} with actual ID if present
    if '{id}' in endpoint:
        endpoint = endpoint.replace('{id}', str(random.randint(1, 1000)))
    
    # Weighted status code selection
    status_code = weighted_choice(STATUS_CODES)
    
    # Response time based on status code (errors tend to be slower)
    if status_code >= 500:
        response_time_ms = random.randint(1000, 5000)
    elif status_code >= 400:
        response_time_ms = random.randint(100, 1000)
    else:
        response_time_ms = random.randint(10, 500)
    
    # Log level based on status code
    level = LOG_LEVELS.get(status_code, 'info')
    
    # Determine log type
    if 'auth' in endpoint:
        log_type = 'auth'
    elif 'payment' in endpoint:
        log_type = 'payment'
    elif 'database' in endpoint or status_code == 500:
        log_type = 'database'
    else:
        log_type = random.choice(['api', 'web'])
    
    # Generate user agent
    user_agent = fake.user_agent()
    
    # Generate client IP
    client_ip = fake.ipv4()
    
    # Generate user ID (80% of requests are authenticated)
    user_id = f'user_{random.randint(1, 500):05d}' if random.random() > 0.2 else ''
    
    # Generate message
    message = random.choice(MESSAGES.get(status_code, ['Log entry']))
    
    # Generate SQL query for database logs (30% chance)
    sql_query = ''
    query_duration_ms = ''
    if log_type == 'database' or random.random() < 0.3:
        sql_query = random.choice(SQL_QUERIES)
        query_duration_ms = random.randint(5, 500)
    
    # Select server
    server = random.choice(SERVERS)
    
    # Select tenant
    tenant_id = random.choice(TENANT_IDS)
    
    return {
        'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
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
    print(f'Generating {num_logs:,} log entries...')
    logs = []
    
    for i in range(num_logs):
        log = generate_log_entry(i)
        logs.append(log)
        
        if (i + 1) % 1000 == 0:
            print(f'  Generated {i + 1:,} logs...')
    
    print(f'✓ Generated {num_logs:,} logs successfully')
    return logs


def save_to_csv(logs, filename):
    """Save logs to CSV file."""
    print(f'\nSaving logs to {filename}...')
    
    # CSV headers
    headers = [
        'timestamp', 'log_type', 'level', 'client_ip', 'user_id',
        'method', 'endpoint', 'status_code', 'response_time_ms',
        'user_agent', 'message', 'sql_query', 'query_duration_ms',
        'server', 'tenant_id'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(logs)
    
    print(f'✓ Saved {len(logs):,} logs to {filename}')


def save_to_json(logs, filename):
    """Save logs to JSON file (JSONL format - one JSON per line)."""
    print(f'\nSaving logs to {filename}...')
    
    with open(filename, 'w', encoding='utf-8') as f:
        for log in logs:
            # Convert timestamp to ISO format for JSON
            log_copy = log.copy()
            dt = datetime.strptime(log_copy['timestamp'], '%Y-%m-%d %H:%M:%S')
            log_copy['timestamp'] = dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            
            json.dump(log_copy, f)
            f.write('\n')
    
    print(f'✓ Saved {len(logs):,} logs to {filename}')


def print_statistics(logs):
    """Print statistics about generated logs."""
    print('\n' + '=' * 60)
    print('LOG STATISTICS')
    print('=' * 60)
    
    # Count by status code
    status_counts = {}
    for log in logs:
        status = log['status_code']
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print('\nStatus Code Distribution:')
    for status, count in sorted(status_counts.items()):
        percentage = (count / len(logs)) * 100
        print(f'  {status}: {count:>6,} ({percentage:>5.1f}%)')
    
    # Count by log level
    level_counts = {}
    for log in logs:
        level = log['level']
        level_counts[level] = level_counts.get(level, 0) + 1
    
    print('\nLog Level Distribution:')
    for level, count in sorted(level_counts.items()):
        percentage = (count / len(logs)) * 100
        print(f'  {level.upper():<8}: {count:>6,} ({percentage:>5.1f}%)')
    
    # Count by log type
    type_counts = {}
    for log in logs:
        log_type = log['log_type']
        type_counts[log_type] = type_counts.get(log_type, 0) + 1
    
    print('\nLog Type Distribution:')
    for log_type, count in sorted(type_counts.items()):
        percentage = (count / len(logs)) * 100
        print(f'  {log_type:<12}: {count:>6,} ({percentage:>5.1f}%)')
    
    # Average response time
    avg_response_time = sum(log['response_time_ms'] for log in logs) / len(logs)
    print(f'\nAverage Response Time: {avg_response_time:.2f} ms')
    
    # Count authenticated vs unauthenticated
    authenticated = sum(1 for log in logs if log['user_id'])
    print(f'\nAuthenticated Requests: {authenticated:,} ({(authenticated/len(logs))*100:.1f}%)')
    print(f'Unauthenticated Requests: {len(logs) - authenticated:,} ({((len(logs) - authenticated)/len(logs))*100:.1f}%)')
    
    print('\n' + '=' * 60)


def main():
    """Main function."""
    print('=' * 60)
    print('SaaS LOG GENERATOR')
    print('=' * 60)
    print(f'Target: {NUM_LOGS:,} log entries')
    print(f'Output: {OUTPUT_CSV}, {OUTPUT_JSON}')
    print('=' * 60 + '\n')
    
    # Generate logs
    logs = generate_logs(NUM_LOGS)
    
    # Save to files
    save_to_csv(logs, OUTPUT_CSV)
    save_to_json(logs, OUTPUT_JSON)
    
    # Print statistics
    print_statistics(logs)
    
    print('\n✓ Log generation completed successfully!')
    print(f'\nNext steps:')
    print(f'  1. Check the files: {OUTPUT_CSV} and {OUTPUT_JSON}')
    print(f'  2. Logstash will automatically process these files')
    print(f'  3. View logs in Kibana at http://localhost:5601')
    print(f'  4. Or search them at http://localhost:5000/search')


if __name__ == '__main__':
    main()
