import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from elasticsearch import Elasticsearch
from pymongo import MongoClient
from redis import Redis
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import json
import time
from models.file import File
from models.search_history import SearchHistory
from utils.cache import CacheManager, cache_result, invalidate_cache
from utils.errors import (
    AppError, ValidationError, DatabaseError, CacheError, 
    ElasticsearchError, FileProcessingError, NotFoundError,
    format_error_response, handle_generic_exception
)

app = Flask(__name__)
CORS(app)

# ============================================================================
# Logging Configuration
# ============================================================================

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# File handler with rotation
file_handler = RotatingFileHandler(
    'logs/app.log',
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=10
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
))

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))

# Add handlers to app logger
app.logger.addHandler(file_handler)
app.logger.addHandler(console_handler)
app.logger.setLevel(logging.INFO)

app.logger.info("=" * 80)
app.logger.info("SaaS Monitoring Platform Starting...")
app.logger.info("=" * 80)

# Upload configuration
UPLOAD_FOLDER = '/app/uploads'
ALLOWED_EXTENSIONS = {'csv', 'json'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ============================================================================
# Initialize Clients
# ============================================================================

def init_elasticsearch():
    """Initialize Elasticsearch client"""
    es_host = os.getenv('ELASTICSEARCH_HOST', 'http://localhost:9200')
    try:
        es = Elasticsearch([es_host], verify_certs=False, request_timeout=30)
        if es.ping():
            app.logger.info(f"✓ Connected to Elasticsearch at {es_host}")
            return es
        else:
            app.logger.error(f"✗ Failed to ping Elasticsearch at {es_host}")
            return None
    except Exception as e:
        app.logger.error(f"✗ Elasticsearch connection error: {str(e)}")
        return None

def init_mongodb():
    """Initialize MongoDB client"""
    mongo_uri = os.getenv('MONGODB_URI', 'mongodb://admin:password123@localhost:27017/')
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        app.logger.info(f"✓ Connected to MongoDB")
        return client
    except Exception as e:
        app.logger.error(f"✗ MongoDB connection error: {str(e)}")
        return None

def init_redis():
    """Initialize Redis client"""
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    try:
        client = Redis(host=redis_host, port=redis_port, decode_responses=True, socket_connect_timeout=5)
        client.ping()
        app.logger.info(f"✓ Connected to Redis at {redis_host}:{redis_port}")
        return client
    except Exception as e:
        app.logger.error(f"✗ Redis connection error: {str(e)}")
        return None

# Initialize clients
es_client = init_elasticsearch()
mongo_client = init_mongodb()
redis_client = init_redis()

# Initialize models
file_model = None
search_history_model = None

if mongo_client:
    try:
        file_model = File(mongo_client)
        search_history_model = SearchHistory(mongo_client)
        app.logger.info("✓ Models initialized successfully")
    except Exception as e:
        app.logger.error(f"✗ Error initializing models: {str(e)}")

# Initialize cache manager
cache_manager = None
if redis_client:
    try:
        cache_manager = CacheManager(redis_client)
        app.cache_manager = cache_manager  # Attach to app context
        app.logger.info("✓ Cache manager initialized successfully")
    except Exception as e:
        app.logger.error(f"✗ Error initializing cache manager: {str(e)}")

# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(ValidationError)
def handle_validation_error(error):
    """Handle validation errors"""
    app.logger.warning(f"Validation error: {error.message} - Details: {error.details}")
    return error.to_response()

@app.errorhandler(DatabaseError)
def handle_database_error(error):
    """Handle database errors"""
    app.logger.error(f"Database error: {error.message} - Details: {error.details}")
    return error.to_response()

@app.errorhandler(CacheError)
def handle_cache_error(error):
    """Handle cache errors"""
    app.logger.error(f"Cache error: {error.message} - Details: {error.details}")
    return error.to_response()

@app.errorhandler(ElasticsearchError)
def handle_elasticsearch_error(error):
    """Handle Elasticsearch errors"""
    app.logger.error(f"Elasticsearch error: {error.message} - Details: {error.details}")
    return error.to_response()

@app.errorhandler(FileProcessingError)
def handle_file_processing_error(error):
    """Handle file processing errors"""
    app.logger.warning(f"File processing error: {error.message} - Details: {error.details}")
    return error.to_response()

@app.errorhandler(NotFoundError)
def handle_not_found_error(error):
    """Handle not found errors"""
    app.logger.warning(f"Not found: {error.message} - Details: {error.details}")
    return error.to_response()

@app.errorhandler(404)
def handle_404(error):
    """Handle 404 errors"""
    app.logger.warning(f"404 Not Found: {request.url}")
    
    # Return JSON for API requests
    if request.path.startswith('/api/'):
        return jsonify(format_error_response("Endpoint not found", 404)), 404
    
    # Return HTML page for regular requests
    return render_template('404.html'), 404

@app.errorhandler(500)
def handle_500(error):
    """Handle 500 errors"""
    app.logger.error(f"500 Internal Server Error: {str(error)}")
    
    # Return JSON for API requests
    if request.path.startswith('/api/'):
        return jsonify(format_error_response("Internal server error", 500)), 500
    
    # Return HTML page for regular requests
    return render_template('500.html'), 500

@app.errorhandler(Exception)
def handle_generic_error(error):
    """Handle all other exceptions"""
    app.logger.error(f"Unhandled exception: {str(error)}", exc_info=True)
    
    # Return JSON for API requests
    if request.path.startswith('/api/'):
        return jsonify(handle_generic_exception(error)), 500
    
    # Return HTML page for regular requests
    return render_template('500.html'), 500

# ============================================================================
# Routes
# ============================================================================

@app.route('/')
def index():
    """Render dashboard"""
    return render_template('index.html')

@app.route('/search')
def search():
    """Render search page"""
    return render_template('search.html')

@app.route('/upload')
def upload():
    """Render upload page"""
    return render_template('upload.html')

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    health_status = {
        'status': 'healthy',
        'elasticsearch': False,
        'mongodb': False,
        'redis': False,
        'healthy': False
    }
    
    # Check Elasticsearch
    if es_client:
        try:
            health_status['elasticsearch'] = es_client.ping()
        except:
            pass
    
    # Check MongoDB
    if mongo_client:
        try:
            mongo_client.admin.command('ping')
            health_status['mongodb'] = True
        except:
            pass
    
    # Check Redis
    if redis_client:
        try:
            redis_client.ping()
            health_status['redis'] = True
        except:
            pass
    
    # Overall health
    health_status['healthy'] = (
        health_status['elasticsearch'] and 
        health_status['mongodb'] and 
        health_status['redis']
    )
    
    if not health_status['healthy']:
        health_status['status'] = 'unhealthy'
    
    status_code = 200 if health_status['healthy'] else 503
    return jsonify(health_status), status_code

@app.route('/api/stats')
@cache_result(timeout=60, key_prefix="stats")
def get_stats():
    """Get comprehensive log statistics from Elasticsearch (cached for 60s)"""
    stats = {
        'total_logs': 0,
        'total_logs_24h': 0,
        'error_rate': 0,
        'avg_response_time_24h': 0,
        'top_slowest_endpoints': [],
        'unique_users_24h': 0,
        'latest_error': None,
        'system_status': {
            'elasticsearch': False,
            'mongodb': False,
            'redis': False
        },
        'cluster_status': 'unknown',
        'indices': [],
        'error': None
    }
    
    try:
        if not es_client:
            raise Exception("Elasticsearch client not initialized")
        
        # Check system health
        stats['system_status']['elasticsearch'] = es_client.ping()
        try:
            if mongo_client:
                mongo_client.admin.command('ping')
                stats['system_status']['mongodb'] = True
        except:
            pass
        try:
            if redis_client:
                redis_client.ping()
                stats['system_status']['redis'] = True
        except:
            pass
        
        # Get cluster health
        cluster_health = es_client.cluster.health()
        stats['cluster_status'] = cluster_health.get('status', 'unknown')
        
        # 1. Total logs (all time)
        count_result = es_client.count(index='saas-logs-*')
        stats['total_logs'] = count_result.get('count', 0)
        
        # 2. Total logs (last 24 hours)
        count_24h = es_client.count(
            index='saas-logs-*',
            body={
                'query': {
                    'range': {
                        '@timestamp': {
                            'gte': 'now-24h'
                        }
                    }
                }
            }
        )
        stats['total_logs_24h'] = count_24h.get('count', 0)
        
        # 3. Error rate (status_code >= 500)
        if stats['total_logs'] > 0:
            error_count = es_client.count(
                index='saas-logs-*',
                body={
                    'query': {
                        'range': {
                            'status_code': {
                                'gte': 500
                            }
                        }
                    }
                }
            )
            stats['error_rate'] = round((error_count.get('count', 0) / stats['total_logs']) * 100, 2)
        
        # 4. Average response time (last 24h)
        avg_response_time = es_client.search(
            index='saas-logs-*',
            body={
                'query': {
                    'range': {
                        '@timestamp': {
                            'gte': 'now-24h'
                        }
                    }
                },
                'size': 0,
                'aggs': {
                    'avg_response_time': {
                        'avg': {
                            'field': 'response_time_ms'
                        }
                    }
                }
            }
        )
        
        avg_value = avg_response_time.get('aggregations', {}).get('avg_response_time', {}).get('value')
        stats['avg_response_time_24h'] = round(avg_value, 2) if avg_value else 0
        
        # 5. Top 3 slowest endpoints (last 24h)
        slowest_endpoints = es_client.search(
            index='saas-logs-*',
            body={
                'query': {
                    'range': {
                        '@timestamp': {
                            'gte': 'now-24h'
                        }
                    }
                },
                'size': 0,
                'aggs': {
                    'endpoints': {
                        'terms': {
                            'field': 'endpoint.keyword',
                            'size': 3,
                            'order': {
                                'avg_response_time': 'desc'
                            }
                        },
                        'aggs': {
                            'avg_response_time': {
                                'avg': {
                                    'field': 'response_time_ms'
                                }
                            }
                        }
                    }
                }
            }
        )
        
        stats['top_slowest_endpoints'] = [
            {
                'endpoint': bucket['key'],
                'avg_response_time': round(bucket['avg_response_time']['value'], 2),
                'count': bucket['doc_count']
            }
            for bucket in slowest_endpoints.get('aggregations', {}).get('endpoints', {}).get('buckets', [])
        ]
        
        # 6. Unique users (last 24h)
        unique_users = es_client.search(
            index='saas-logs-*',
            body={
                'query': {
                    'range': {
                        '@timestamp': {
                            'gte': 'now-24h'
                        }
                    }
                },
                'size': 0,
                'aggs': {
                    'unique_users': {
                        'cardinality': {
                            'field': 'user_id.keyword'
                        }
                    }
                }
            }
        )
        stats['unique_users_24h'] = unique_users.get('aggregations', {}).get('unique_users', {}).get('value', 0)
        
        # 7. Latest error
        latest_error = es_client.search(
            index='saas-logs-*',
            body={
                'query': {
                    'terms': {
                        'level.keyword': ['ERROR', 'CRITICAL']
                    }
                },
                'size': 1,
                'sort': [
                    {'@timestamp': {'order': 'desc'}}
                ]
            }
        )
        
        if latest_error['hits']['total']['value'] > 0:
            error_hit = latest_error['hits']['hits'][0]['_source']
            stats['latest_error'] = {
                'timestamp': error_hit.get('@timestamp'),
                'level': error_hit.get('level'),
                'message': error_hit.get('message'),
                'endpoint': error_hit.get('endpoint'),
                'status_code': error_hit.get('status_code')
            }
        
        # Get list of indices
        indices = es_client.cat.indices(index='saas-logs-*', format='json')
        stats['indices'] = [
            {
                'name': idx['index'],
                'docs_count': int(idx.get('docs.count', 0)),
                'store_size': idx.get('store.size', 'N/A')
            }
            for idx in indices
        ]
        
    except Exception as e:
        stats['error'] = str(e)
        print(f"Error fetching stats: {str(e)}")
    
    return jsonify(stats)

@app.route('/api/search', methods=['POST'])
@cache_result(timeout=300, key_prefix="search")
def search_logs():
    """Search logs in Elasticsearch with advanced filters (cached for 5 min)"""
    if not es_client:
        app.logger.error("Search failed: Elasticsearch client not initialized")
        raise ElasticsearchError('Elasticsearch client not initialized', operation='search')
    
    try:
        data = request.get_json() or {}
        
        app.logger.info(f"Search request from {request.remote_addr}: query='{data.get('q', '')}', level={data.get('level', 'ALL')}")
        
        # Extract parameters
        q = data.get('q', '').strip()
        level = data.get('level', '').upper()
        date_from = data.get('date_from', '')
        date_to = data.get('date_to', '')
        endpoint = data.get('endpoint', '').strip()
        status_code = data.get('status_code', '')
        server = data.get('server', '').strip()
        
        # Validate pagination parameters
        try:
            page = int(data.get('page', 1))
            per_page = int(data.get('per_page', 50))
            
            if page < 1:
                raise ValidationError('Page number must be greater than 0', field='page')
            if per_page < 1:
                raise ValidationError('Items per page must be greater than 0', field='per_page')
            if per_page > 100:
                per_page = 100  # Cap at 100
        except (ValueError, TypeError) as e:
            raise ValidationError('Invalid pagination parameters', details={'error': str(e)})
        
        # Build Elasticsearch Query DSL
        must_conditions = []
        
        # Text search on message field
        if q:
            must_conditions.append({
                'match': {
                    'message': {
                        'query': q,
                        'operator': 'and',
                        'fuzziness': 'AUTO'
                    }
                }
            })
        
        # Log level filter (exact match)
        if level and level != 'ALL':
            must_conditions.append({
                'term': {
                    'level.keyword': level
                }
            })
        
        # Endpoint filter (exact match)
        if endpoint:
            must_conditions.append({
                'term': {
                    'endpoint.keyword': endpoint
                }
            })
        
        # Status code filter
        if status_code and status_code != 'ALL':
            if status_code == '2XX':
                must_conditions.append({
                    'range': {
                        'status_code': {
                            'gte': 200,
                            'lt': 300
                        }
                    }
                })
            elif status_code == '4XX':
                must_conditions.append({
                    'range': {
                        'status_code': {
                            'gte': 400,
                            'lt': 500
                        }
                    }
                })
            elif status_code == '5XX':
                must_conditions.append({
                    'range': {
                        'status_code': {
                            'gte': 500,
                            'lt': 600
                        }
                    }
                })
            else:
                # Specific status code
                try:
                    status_int = int(status_code)
                    must_conditions.append({
                        'term': {
                            'status_code': status_int
                        }
                    })
                except ValueError:
                    pass
        
        # Server filter
        if server and server != 'ALL':
            must_conditions.append({
                'term': {
                    'server.keyword': server
                }
            })
        
        # Date range filter
        if date_from or date_to:
            range_query = {}
            if date_from:
                range_query['gte'] = date_from
            if date_to:
                range_query['lte'] = date_to
            
            must_conditions.append({
                'range': {
                    '@timestamp': range_query
                }
            })
        
        # Build final query
        if must_conditions:
            query = {
                'bool': {
                    'must': must_conditions
                }
            }
        else:
            query = {'match_all': {}}
        
        # Build search body
        search_body = {
            'query': query,
            'sort': [
                {'@timestamp': {'order': 'desc'}}
            ],
            'from': (page - 1) * per_page,
            'size': per_page
        }
        
        # Execute search
        start_time = time.time()
        response = es_client.search(index='saas-logs-*', body=search_body)
        execution_time_ms = (time.time() - start_time) * 1000
        
        # Format results
        hits = response['hits']['hits']
        total = response['hits']['total']['value']
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0
        
        results = []
        for hit in hits:
            source = hit['_source']
            results.append({
                'timestamp': source.get('@timestamp'),
                'level': source.get('level'),
                'endpoint': source.get('endpoint'),
                'status_code': source.get('status_code'),
                'response_time_ms': source.get('response_time_ms'),
                'message': source.get('message'),
                'server': source.get('server'),
                'user_id': source.get('user_id'),
                'client_ip': source.get('client_ip')
            })
        
        # Save search history
        if search_history_model:
            try:
                filters_used = {
                    'level': level if level else None,
                    'status_code': status_code if status_code else None,
                    'server': server if server else None,
                    'endpoint': endpoint if endpoint else None,
                    'date_from': date_from if date_from else None,
                    'date_to': date_to if date_to else None,
                    'page': page,
                    'per_page': per_page
                }
                # Remove None values
                filters_used = {k: v for k, v in filters_used.items() if v is not None}
                
                search_history_model.save(
                    query=q,
                    filters=filters_used,
                    user=request.remote_addr,  # Use IP as user identifier
                    results_count=total,
                    execution_time_ms=execution_time_ms
                )
            except Exception as e:
                app.logger.warning(f"Error saving search history: {str(e)}")
        
        app.logger.info(f"Search completed: {total} results found in {execution_time_ms:.2f}ms")
        
        return jsonify({
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages
        })
        
    except (ValidationError, ElasticsearchError):
        # Re-raise custom exceptions
        raise
    except Exception as e:
        app.logger.error(f"Search error: {str(e)}", exc_info=True)
        raise ElasticsearchError(
            'An error occurred while searching logs',
            operation='search',
            details={'error': str(e)}
        )

@app.route('/api/export', methods=['POST'])
def export_logs():
    """Export logs to CSV with same filters as search"""
    if not es_client:
        return jsonify({'error': 'Elasticsearch client not initialized'}), 500
    
    try:
        import csv
        import io
        from flask import Response
        
        data = request.get_json()
        
        # Extract parameters (same as search)
        q = data.get('q', '').strip()
        level = data.get('level', '').upper()
        date_from = data.get('date_from', '')
        date_to = data.get('date_to', '')
        endpoint = data.get('endpoint', '').strip()
        status_code = data.get('status_code', '')
        server = data.get('server', '').strip()
        
        # Build Elasticsearch Query DSL (same as search, but no pagination)
        must_conditions = []
        
        # Text search on message field
        if q:
            must_conditions.append({
                'match': {
                    'message': {
                        'query': q,
                        'operator': 'and',
                        'fuzziness': 'AUTO'
                    }
                }
            })
        
        # Log level filter (exact match)
        if level and level != 'ALL':
            must_conditions.append({
                'term': {
                    'level.keyword': level
                }
            })
        
        # Endpoint filter (exact match)
        if endpoint:
            must_conditions.append({
                'term': {
                    'endpoint.keyword': endpoint
                }
            })
        
        # Status code filter
        if status_code and status_code != 'ALL':
            if status_code == '2XX':
                must_conditions.append({
                    'range': {
                        'status_code': {
                            'gte': 200,
                            'lt': 300
                        }
                    }
                })
            elif status_code == '4XX':
                must_conditions.append({
                    'range': {
                        'status_code': {
                            'gte': 400,
                            'lt': 500
                        }
                    }
                })
            elif status_code == '5XX':
                must_conditions.append({
                    'range': {
                        'status_code': {
                            'gte': 500,
                            'lt': 600
                        }
                    }
                })
            else:
                # Specific status code
                try:
                    status_int = int(status_code)
                    must_conditions.append({
                        'term': {
                            'status_code': status_int
                        }
                    })
                except ValueError:
                    pass
        
        # Server filter
        if server and server != 'ALL':
            must_conditions.append({
                'term': {
                    'server.keyword': server
                }
            })
        
        # Date range filter
        if date_from or date_to:
            range_query = {}
            if date_from:
                range_query['gte'] = date_from
            if date_to:
                range_query['lte'] = date_to
            
            must_conditions.append({
                'range': {
                    '@timestamp': range_query
                }
            })
        
        # Build final query
        if must_conditions:
            query = {
                'bool': {
                    'must': must_conditions
                }
            }
        else:
            query = {'match_all': {}}
        
        # Build search body - get up to 10000 results (Elasticsearch default max)
        search_body = {
            'query': query,
            'sort': [
                {'@timestamp': {'order': 'desc'}}
            ],
            'size': 10000  # Maximum results to export
        }
        
        # Execute search
        response = es_client.search(index='saas-logs-*', body=search_body)
        
        # Create CSV in memory
        output = io.StringIO()
        csv_writer = csv.writer(output)
        
        # Write header
        csv_writer.writerow([
            'timestamp',
            'level',
            'endpoint',
            'status_code',
            'response_time_ms',
            'message',
            'client_ip',
            'user_id',
            'server'
        ])
        
        # Write data rows
        hits = response['hits']['hits']
        for hit in hits:
            source = hit['_source']
            csv_writer.writerow([
                source.get('@timestamp', ''),
                source.get('level', ''),
                source.get('endpoint', ''),
                source.get('status_code', ''),
                source.get('response_time_ms', ''),
                source.get('message', '').replace('\n', ' ').replace('\r', ''),  # Remove newlines
                source.get('client_ip', ''),
                source.get('user_id', ''),
                source.get('server', '')
            ])
        
        # Generate filename with timestamp
        export_timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f'logs_export_{export_timestamp}.csv'
        
        # Create response with CSV data
        output.seek(0)
        response = Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
        
        return response
        
    except Exception as e:
        print(f"Export error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload CSV or JSON files with metadata storage"""
    try:
        app.logger.info(f"File upload request received from {request.remote_addr}")
        
        # Validate file presence
        if 'file' not in request.files:
            app.logger.warning("Upload failed: No file part in request")
            raise ValidationError('No file part in request', field='file')
        
        file = request.files['file']
        
        if file.filename == '':
            app.logger.warning("Upload failed: No file selected")
            raise ValidationError('No file selected', field='file')
        
        # Validate file type
        if not allowed_file(file.filename):
            app.logger.warning(f"Upload failed: Invalid file type - {file.filename}")
            raise ValidationError(
                'Invalid file type. Only .csv and .json files are allowed',
                field='file',
                details={'filename': file.filename, 'allowed_extensions': list(ALLOWED_EXTENSIONS)}
            )
        
        # Get file info
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        
        # Generate unique filename
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{original_filename}"
        
        # Save file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        app.logger.info(f"File saved: {unique_filename} ({file_size} bytes)")
        
        # Estimate log count
        log_count = 0
        try:
            with open(file_path, 'r') as f:
                if file_extension == 'json':
                    data = json.load(f)
                    log_count = len(data) if isinstance(data, list) else 1
                elif file_extension == 'csv':
                    import csv
                    log_count = sum(1 for row in csv.reader(f)) - 1  # Exclude header
        except Exception as e:
            app.logger.warning(f"Could not count logs in file: {str(e)}")
            log_count = 0
        
        # Store metadata in MongoDB using File model
        file_id = None
        if file_model:
            try:
                file_id = file_model.create(
                    filename=original_filename,
                    saved_as=unique_filename,
                    file_type=file_extension,
                    file_size=file_size,
                    log_count=log_count,
                    status='completed'
                )
                app.logger.info(f"File metadata saved with ID: {file_id}")
            except Exception as e:
                app.logger.error(f"Error saving file metadata: {str(e)}")
                raise DatabaseError(
                    'Failed to save file metadata',
                    operation='insert',
                    details={'error': str(e)}
                )
        
        # Invalidate files cache after upload
        invalidate_cache("files")
        app.logger.info(f"Cache invalidated for files after upload")
        
        app.logger.info(f"File upload completed successfully: {original_filename} ({log_count} logs)")
        
        return jsonify({
            'success': True,
            'file_id': file_id,
            'message': f'File uploaded successfully: {original_filename}',
            'details': {
                'filename': original_filename,
                'saved_as': unique_filename,
                'file_size': file_size,
                'log_count': log_count,
                'upload_date': datetime.utcnow().isoformat()
            }
        }), 200
        
    except (ValidationError, DatabaseError, FileProcessingError):
        # Re-raise custom exceptions to be handled by error handlers
        raise
    except Exception as e:
        app.logger.error(f"Unexpected error during file upload: {str(e)}", exc_info=True)
        raise FileProcessingError(
            'An unexpected error occurred during file upload',
            details={'error': str(e)}
        )

@app.route('/api/uploads', methods=['GET'])
def get_recent_uploads():
    """Get recent uploads from MongoDB"""
    try:
        if not mongo_client:
            return jsonify({'error': 'MongoDB not available'}), 503
        
        db = mongo_client['saas_monitoring']
        files_collection = db['files']
        
        # Get last 10 uploads
        uploads = list(files_collection.find(
            {},
            {'_id': 0}
        ).sort('upload_date', -1).limit(10))
        
        return jsonify({'success': True, 'uploads': uploads}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search/history', methods=['GET'])
def get_search_history():
    """Get recent search history"""
    try:
        if not search_history_model:
            return jsonify({'error': 'Search history not available'}), 503
        
        # Get query parameters
        limit = min(int(request.args.get('limit', 10)), 100)
        user = request.args.get('user', None)
        
        # Get recent searches
        searches = search_history_model.get_recent(limit=limit, user=user)
        
        return jsonify({
            'success': True,
            'searches': searches,
            'count': len(searches)
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search/history/popular', methods=['GET'])
def get_popular_queries():
    """Get most popular search queries"""
    try:
        if not search_history_model:
            return jsonify({'error': 'Search history not available'}), 503
        
        # Get query parameters
        limit = min(int(request.args.get('limit', 10)), 50)
        days = min(int(request.args.get('days', 7)), 90)
        
        # Get popular queries
        popular = search_history_model.get_popular_queries(limit=limit, days=days)
        
        return jsonify({
            'success': True,
            'popular_queries': popular,
            'count': len(popular)
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search/history/stats', methods=['GET'])
def get_search_stats():
    """Get search statistics"""
    try:
        if not search_history_model:
            return jsonify({'error': 'Search history not available'}), 503
        
        # Get query parameters
        days = min(int(request.args.get('days', 30)), 365)
        
        # Get statistics
        stats = search_history_model.get_statistics(days=days)
        
        return jsonify({
            'success': True,
            'statistics': stats
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/files')
def files_page():
    """Render files management page"""
    return render_template('files.html')

@app.route('/api/files', methods=['GET'])
@cache_result(timeout=600, key_prefix="files")
def get_files():
    """Get all uploaded files from MongoDB using File model (cached for 10 min)"""
    try:
        if not file_model:
            return jsonify({'error': 'File model not available'}), 503
        
        # Get all files using model
        files = file_model.get_all()
        
        # Get statistics using model
        stats = file_model.get_statistics()
        
        return jsonify({
            'success': True,
            'files': files,
            'stats': stats
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/files/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    """Delete a file from uploads folder and MongoDB using File model"""
    try:
        if not file_model:
            return jsonify({'error': 'File model not available'}), 503
        
        # Get file document using model
        file_doc = file_model.get_by_id(file_id)
        
        if not file_doc:
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        # Delete physical file
        saved_filename = file_doc.get('saved_as')
        if saved_filename:
            file_path = os.path.join(UPLOAD_FOLDER, saved_filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Deleted file: {file_path}")
        
        # Delete MongoDB document using model
        if file_model.delete(file_id):
            # Invalidate files cache after deletion
            invalidate_cache("files")
            
            return jsonify({
                'success': True,
                'message': f'File {file_doc.get("filename", "unknown")} deleted successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to delete file from database'
            }), 500
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cache/stats', methods=['GET'])
def get_cache_stats():
    """Get cache statistics"""
    try:
        if not cache_manager:
            return jsonify({'error': 'Cache manager not available'}), 503
        
        # Get cache statistics
        stats = cache_manager.get_stats()
        
        # Get Redis info if available
        redis_info = {}
        if redis_client:
            try:
                info = redis_client.info('stats')
                redis_info = {
                    'total_connections_received': info.get('total_connections_received', 0),
                    'total_commands_processed': info.get('total_commands_processed', 0),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0),
                    'used_memory_human': redis_client.info('memory').get('used_memory_human', 'N/A')
                }
                
                # Calculate Redis hit rate
                redis_hits = redis_info['keyspace_hits']
                redis_misses = redis_info['keyspace_misses']
                redis_total = redis_hits + redis_misses
                redis_hit_rate = (redis_hits / redis_total * 100) if redis_total > 0 else 0
                redis_info['redis_hit_rate_percent'] = round(redis_hit_rate, 2)
            except Exception as e:
                print(f"Error getting Redis info: {str(e)}")
        
        return jsonify({
            'success': True,
            'cache_stats': stats,
            'redis_info': redis_info
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
