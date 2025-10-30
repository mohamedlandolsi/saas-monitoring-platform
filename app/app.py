import os
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from elasticsearch import Elasticsearch
from pymongo import MongoClient
from redis import Redis
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import json

app = Flask(__name__)
CORS(app)

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

# Initialize clients
def init_elasticsearch():
    """Initialize Elasticsearch client"""
    es_host = os.getenv('ELASTICSEARCH_HOST', 'http://localhost:9200')
    try:
        es = Elasticsearch([es_host], verify_certs=False, request_timeout=30)
        if es.ping():
            print(f"✓ Connected to Elasticsearch at {es_host}")
            return es
        else:
            print(f"✗ Failed to ping Elasticsearch at {es_host}")
            return None
    except Exception as e:
        print(f"✗ Elasticsearch connection error: {str(e)}")
        return None

def init_mongodb():
    """Initialize MongoDB client"""
    mongo_uri = os.getenv('MONGODB_URI', 'mongodb://admin:password123@localhost:27017/')
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print(f"✓ Connected to MongoDB")
        return client
    except Exception as e:
        print(f"✗ MongoDB connection error: {str(e)}")
        return None

def init_redis():
    """Initialize Redis client"""
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    try:
        client = Redis(host=redis_host, port=redis_port, decode_responses=True, socket_connect_timeout=5)
        client.ping()
        print(f"✓ Connected to Redis at {redis_host}:{redis_port}")
        return client
    except Exception as e:
        print(f"✗ Redis connection error: {str(e)}")
        return None

# Initialize clients
es_client = init_elasticsearch()
mongo_client = init_mongodb()
redis_client = init_redis()

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
def get_stats():
    """Get comprehensive log statistics from Elasticsearch"""
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
def search_logs():
    """Search logs in Elasticsearch with advanced filters"""
    if not es_client:
        return jsonify({'error': 'Elasticsearch client not initialized'}), 500
    
    try:
        data = request.get_json()
        
        # Extract parameters
        q = data.get('q', '').strip()
        level = data.get('level', '').upper()
        date_from = data.get('date_from', '')
        date_to = data.get('date_to', '')
        endpoint = data.get('endpoint', '').strip()
        status_code = data.get('status_code', '')
        server = data.get('server', '').strip()
        page = int(data.get('page', 1))
        per_page = min(int(data.get('per_page', 50)), 100)  # Max 100 per page
        
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
        response = es_client.search(index='saas-logs-*', body=search_body)
        
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
        
        return jsonify({
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages
        })
        
    except Exception as e:
        print(f"Search error: {str(e)}")
        return jsonify({'error': str(e)}), 500

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
        # Validate file presence
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file part in request'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Validate file type
        if not allowed_file(file.filename):
            return jsonify({
                'success': False, 
                'error': 'Invalid file type. Only .csv and .json files are allowed'
            }), 400
        
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
        except:
            log_count = 0
        
        # Store metadata in MongoDB
        file_metadata = {
            'filename': original_filename,
            'saved_as': unique_filename,
            'file_type': file_extension,
            'file_size': file_size,
            'upload_date': datetime.utcnow().isoformat(),
            'status': 'completed',
            'log_count': log_count
        }
        
        if mongo_client:
            try:
                db = mongo_client['saas_monitoring']
                files_collection = db['files']
                result = files_collection.insert_one(file_metadata)
                file_id = str(result.inserted_id)
            except Exception as e:
                print(f"MongoDB insert error: {str(e)}")
                file_id = None
        else:
            file_id = None
        
        return jsonify({
            'success': True,
            'file_id': file_id,
            'message': f'File uploaded successfully: {original_filename}',
            'details': {
                'filename': original_filename,
                'saved_as': unique_filename,
                'file_size': file_size,
                'log_count': log_count,
                'upload_date': file_metadata['upload_date']
            }
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
