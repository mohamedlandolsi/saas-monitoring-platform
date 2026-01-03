"""
Prometheus metrics for Flask application.
Exposes HTTP request metrics, latency histograms, and system metrics.
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from functools import wraps
import time
import psutil
import os

# ============================================================================
# HTTP Request Metrics
# ============================================================================

# Total HTTP requests counter
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

# HTTP request latency histogram with percentile buckets
http_request_latency_seconds = Histogram(
    'http_request_latency_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Response size histogram
http_response_size_bytes = Histogram(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint'],
    buckets=[100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]
)

# Active connections gauge
http_active_connections = Gauge(
    'http_active_connections',
    'Number of active HTTP connections'
)

# ============================================================================
# System Metrics
# ============================================================================

# CPU usage
system_cpu_usage_percent = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage'
)

# Memory usage
system_memory_usage_bytes = Gauge(
    'system_memory_usage_bytes',
    'System memory usage in bytes'
)

system_memory_usage_percent = Gauge(
    'system_memory_usage_percent',
    'System memory usage percentage'
)

# ============================================================================
# Application Metrics
# ============================================================================

# Elasticsearch query metrics
elasticsearch_queries_total = Counter(
    'elasticsearch_queries_total',
    'Total Elasticsearch queries',
    ['operation', 'status']
)

elasticsearch_query_latency_seconds = Histogram(
    'elasticsearch_query_latency_seconds',
    'Elasticsearch query latency in seconds',
    ['operation'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

# MongoDB query metrics
mongodb_queries_total = Counter(
    'mongodb_queries_total',
    'Total MongoDB queries',
    ['collection', 'operation', 'status']
)

mongodb_query_latency_seconds = Histogram(
    'mongodb_query_latency_seconds',
    'MongoDB query latency in seconds',
    ['collection', 'operation'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

# Redis operations metrics
redis_operations_total = Counter(
    'redis_operations_total',
    'Total Redis operations',
    ['operation', 'status']
)

# ============================================================================
# Business Metrics (SaaS)
# ============================================================================

# Active users
saas_active_users = Gauge(
    'saas_active_users',
    'Number of active users',
    ['period']  # 'daily', 'weekly', 'monthly'
)

# Log ingestion rate
saas_logs_ingested_total = Counter(
    'saas_logs_ingested_total',
    'Total logs ingested',
    ['source', 'level']
)

# Search operations
saas_searches_total = Counter(
    'saas_searches_total',
    'Total search operations',
    ['user_type']
)

# File uploads
saas_file_uploads_total = Counter(
    'saas_file_uploads_total',
    'Total file uploads',
    ['file_type', 'status']
)

# WebSocket connections
saas_websocket_connections = Gauge(
    'saas_websocket_connections',
    'Active WebSocket connections'
)

# ============================================================================
# Health Status Metrics
# ============================================================================

service_health_status = Gauge(
    'service_health_status',
    'Health status of services (1=healthy, 0=unhealthy)',
    ['service']
)

service_health_latency_seconds = Gauge(
    'service_health_latency_seconds',
    'Health check latency in seconds',
    ['service']
)


def update_system_metrics():
    """Update system resource metrics."""
    try:
        # CPU
        cpu_percent = psutil.cpu_percent(interval=None)
        system_cpu_usage_percent.set(cpu_percent)
        
        # Memory
        memory = psutil.virtual_memory()
        system_memory_usage_bytes.set(memory.used)
        system_memory_usage_percent.set(memory.percent)
    except Exception:
        pass


def get_metrics():
    """Generate Prometheus metrics output."""
    update_system_metrics()
    return generate_latest()


def get_content_type():
    """Get Prometheus content type."""
    return CONTENT_TYPE_LATEST
