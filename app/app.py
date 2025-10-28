import os
import subprocess
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from elasticsearch import Elasticsearch
from pymongo import MongoClient
import redis
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import uuid

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration from environment variables
ELASTICSEARCH_HOST = os.getenv('ELASTICSEARCH_HOST', 'http://localhost:9200')
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://admin:password123@localhost:27017/')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))

# File upload configuration
UPLOAD_FOLDER = '/app/uploads'
ALLOWED_EXTENSIONS = {'csv', 'json'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize clients
es_client = None
mongo_client = None
redis_client = None

def init_elasticsearch():
    """Initialize Elasticsearch client"""
    global es_client
    try:
        es_client = Elasticsearch(
            [ELASTICSEARCH_HOST],
            verify_certs=False,
            request_timeout=30
        )
        return es_client.ping()
    except Exception as e:
        app.logger.error(f"Elasticsearch connection failed: {e}")
        return False

def init_mongodb():
    """Initialize MongoDB client"""
    global mongo_client
    try:
        mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        # Test connection
        mongo_client.admin.command('ping')
        return True
    except Exception as e:
        app.logger.error(f"MongoDB connection failed: {e}")
        return False

def init_redis():
    """Initialize Redis client"""
    global redis_client
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            socket_connect_timeout=5
        )
        # Test connection
        redis_client.ping()
        return True
    except Exception as e:
        app.logger.error(f"Redis connection failed: {e}")
        return False

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_mongodb_database():
    """Get MongoDB database instance"""
    if mongo_client:
        return mongo_client['saas_logs']
    return None

def trigger_logstash_processing(file_id, file_path):
    """
    Trigger Logstash to process the uploaded file.
    Logstash watches the uploads directory, so we just need to ensure
    the file is there and optionally notify via Redis.
    """
    try:
        # Store file path in Redis for tracking
        if redis_client:
            redis_key = f"upload:{file_id}"
            redis_client.setex(
                redis_key,
                3600,  # 1 hour expiration
                file_path
            )
            app.logger.info(f"File path stored in Redis: {redis_key}")
        
        # Logstash automatically picks up files from /data/uploads
        # No explicit trigger needed due to file input plugin's monitoring
        
        return True
    except Exception as e:
        app.logger.error(f"Failed to trigger Logstash processing: {e}")
        return False

def check_processing_status(file_id):
    """Check if file has been processed by checking Elasticsearch"""
    try:
        if not es_client:
            return {'status': 'unknown', 'message': 'Elasticsearch not available'}
        
        # Wait a moment for Logstash to process
        time.sleep(2)
        
        # Check if any logs were indexed recently
        result = es_client.search(
            index='saas-logs-*',
            body={
                'query': {
                    'range': {
                        '@timestamp': {
                            'gte': 'now-1m'
                        }
                    }
                },
                'size': 1
            }
        )
        
        if result['hits']['total']['value'] > 0:
            return {
                'status': 'processing',
                'message': 'Logstash is processing the file',
                'indexed_count': result['hits']['total']['value']
            }
        else:
            return {
                'status': 'pending',
                'message': 'File uploaded, waiting for Logstash to process'
            }
    except Exception as e:
        app.logger.error(f"Failed to check processing status: {e}")
        return {'status': 'error', 'message': str(e)}

# Initialize all clients on startup
with app.app_context():
    init_elasticsearch()
    init_mongodb()
    init_redis()

@app.route('/')
def dashboard():
    """Render the main dashboard"""
    return render_template('index.html')

@app.route('/upload')
def upload_page():
    """Render the upload page"""
    return render_template('upload.html')

@app.route('/search')
def search_page():
    """Render the search page"""
    return render_template('search.html')

@app.route('/api/health')
def health_check():
    """Check health status of all services"""
    health_status = {
        'elasticsearch': False,
        'mongodb': False,
        'redis': False,
        'timestamp': datetime.now().isoformat()
    }
    
    # Check Elasticsearch
    try:
        if es_client and es_client.ping():
            health_status['elasticsearch'] = True
    except Exception as e:
        app.logger.error(f"Elasticsearch health check failed: {e}")
    
    # Check MongoDB
    try:
        if mongo_client:
            mongo_client.admin.command('ping')
            health_status['mongodb'] = True
    except Exception as e:
        app.logger.error(f"MongoDB health check failed: {e}")
    
    # Check Redis
    try:
        if redis_client and redis_client.ping():
            health_status['redis'] = True
    except Exception as e:
        app.logger.error(f"Redis health check failed: {e}")
    
    # Overall health
    health_status['healthy'] = all([
        health_status['elasticsearch'],
        health_status['mongodb'],
        health_status['redis']
    ])
    
    status_code = 200 if health_status['healthy'] else 503
    return jsonify(health_status), status_code

@app.route('/api/stats')
def get_stats():
    """Get log statistics from Elasticsearch"""
    stats = {
        'total_logs': 0,
        'indices': [],
        'cluster_status': 'unknown',
        'error': None
    }
    
    try:
        if not es_client:
            raise Exception("Elasticsearch client not initialized")
        
        # Get cluster health
        cluster_health = es_client.cluster.health()
        stats['cluster_status'] = cluster_health.get('status', 'unknown')
        
        # Count documents in saas-logs indices
        count_result = es_client.count(index='saas-logs-*')
        stats['total_logs'] = count_result.get('count', 0)
        
        # Get list of indices
        indices = es_client.cat.indices(index='saas-logs-*', format='json')
        stats['indices'] = [
            {
                'name': idx['index'],
                'docs_count': int(idx.get('docs.count', 0)),
                'store_size': idx.get('store.size', '0b')
            }
            for idx in indices
        ]
        
    except Exception as e:
        app.logger.error(f"Failed to get stats: {e}")
        stats['error'] = str(e)
    
    return jsonify(stats)

@app.route('/api/recent-logs')
def get_recent_logs():
    """Get recent logs from Elasticsearch"""
    try:
        if not es_client:
            raise Exception("Elasticsearch client not initialized")
        
        # Search for recent logs
        result = es_client.search(
            index='saas-logs-*',
            body={
                'query': {'match_all': {}},
                'sort': [{'@timestamp': {'order': 'desc'}}],
                'size': 50
            }
        )
        
        logs = [
            {
                'timestamp': hit['_source'].get('@timestamp'),
                'level': hit['_source'].get('level'),
                'log_type': hit['_source'].get('log_type'),
                'message': hit['_source'].get('message'),
                'endpoint': hit['_source'].get('endpoint'),
                'status_code': hit['_source'].get('status_code'),
                'response_time_ms': hit['_source'].get('response_time_ms')
            }
            for hit in result['hits']['hits']
        ]
        
        return jsonify({'logs': logs, 'total': result['hits']['total']['value']})
        
    except Exception as e:
        app.logger.error(f"Failed to get recent logs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """
    Upload CSV or JSON log files
    
    Steps:
    1. Validate file
    2. Save to uploads/ folder
    3. Store metadata in MongoDB
    4. Trigger Logstash processing
    5. Return file_id and status
    """
    try:
        # Check if file is present in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in request'}), 400
        
        file = request.files['file']
        
        # Check if file was selected
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file extension
        if not allowed_file(file.filename):
            return jsonify({
                'error': 'Invalid file type. Only CSV and JSON files are allowed'
            }), 400
        
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        
        # Secure the filename and add UUID prefix
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        new_filename = f"{file_id}.{file_extension}"
        
        # Save file to upload folder
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        file.save(file_path)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Calculate estimated processing time (rough estimate)
        estimated_time = max(5, (file_size / (1024 * 1024)) * 2)  # ~2 seconds per MB
        
        # Store metadata in MongoDB
        db = get_mongodb_database()
        metadata_stored = False
        
        if db is not None:
            upload_metadata = {
                'file_id': file_id,
                'original_filename': original_filename,
                'stored_filename': new_filename,
                'file_type': file_extension,
                'file_size': file_size,
                'file_path': file_path,
                'upload_timestamp': datetime.utcnow(),
                'status': 'uploaded',
                'processed': False,
                'processing_started': None,
                'processing_completed': None,
                'error_message': None
            }
            
            db.uploads.insert_one(upload_metadata)
            metadata_stored = True
            app.logger.info(f"File metadata stored in MongoDB: {file_id}")
        else:
            app.logger.warning("MongoDB not available, metadata not stored")
        
        # Trigger Logstash processing (or mark for processing)
        logstash_triggered = trigger_logstash_processing(file_id, file_path)
        
        # Return success response
        response_data = {
            'success': True,
            'file_id': file_id,
            'original_filename': original_filename,
            'file_size': file_size,
            'file_type': file_extension,
            'file_path': file_path,
            'metadata_stored': metadata_stored,
            'logstash_triggered': logstash_triggered,
            'estimated_processing_time': f"{estimated_time:.0f} seconds",
            'message': 'File uploaded successfully. Logstash will process it automatically.',
            'next_steps': [
                'Check processing status at /api/upload/status/' + file_id,
                'View logs in Kibana at http://localhost:5601',
                'Search logs at /search'
            ]
        }
        
        return jsonify(response_data), 201
        
    except Exception as e:
        app.logger.error(f"File upload failed: {e}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/upload/status/<file_id>', methods=['GET'])
def get_upload_status(file_id):
    """
    Get the processing status of an uploaded file
    """
    try:
        # Get metadata from MongoDB
        db = get_mongodb_database()
        if db is None:
            return jsonify({'error': 'MongoDB not available'}), 503
        
        upload = db.uploads.find_one({'file_id': file_id})
        
        if not upload:
            return jsonify({'error': 'File not found'}), 404
        
        # Check processing status
        processing_status = check_processing_status(file_id)
        
        # Build response
        response = {
            'file_id': file_id,
            'original_filename': upload.get('original_filename'),
            'file_type': upload.get('file_type'),
            'file_size': upload.get('file_size'),
            'upload_timestamp': upload.get('upload_timestamp').isoformat() if upload.get('upload_timestamp') else None,
            'status': upload.get('status'),
            'processed': upload.get('processed'),
            'processing_status': processing_status,
            'elasticsearch_available': es_client is not None and es_client.ping()
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        app.logger.error(f"Failed to get upload status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/uploads', methods=['GET'])
def list_uploads():
    """
    List all uploaded files with their metadata
    """
    try:
        db = get_mongodb_database()
        if db is None:
            return jsonify({'error': 'MongoDB not available'}), 503
        
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # Get total count
        total = db.uploads.count_documents({})
        
        # Get uploads with pagination
        uploads = list(db.uploads.find()
                      .sort('upload_timestamp', -1)
                      .skip((page - 1) * per_page)
                      .limit(per_page))
        
        # Convert ObjectId to string and format dates
        for upload in uploads:
            upload['_id'] = str(upload['_id'])
            if upload.get('upload_timestamp'):
                upload['upload_timestamp'] = upload['upload_timestamp'].isoformat()
            if upload.get('processing_started'):
                upload['processing_started'] = upload['processing_started'].isoformat()
            if upload.get('processing_completed'):
                upload['processing_completed'] = upload['processing_completed'].isoformat()
        
        return jsonify({
            'uploads': uploads,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        }), 200
        
    except Exception as e:
        app.logger.error(f"Failed to list uploads: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/search')
def search_logs():
    """Search logs with filters and pagination"""
    try:
        if not es_client:
            raise Exception("Elasticsearch client not initialized")
        
        # Get query parameters
        query_text = request.args.get('query', '').strip()
        log_level = request.args.get('level', '').strip()
        endpoint = request.args.get('endpoint', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        # Build Elasticsearch query
        must_clauses = []
        
        # Text search across multiple fields
        if query_text:
            must_clauses.append({
                'multi_match': {
                    'query': query_text,
                    'fields': ['message', 'endpoint', 'user_id', 'client_ip'],
                    'type': 'best_fields',
                    'operator': 'or'
                }
            })
        
        # Filter by log level
        if log_level:
            must_clauses.append({
                'match': {
                    'level': log_level
                }
            })
        
        # Filter by endpoint
        if endpoint:
            must_clauses.append({
                'wildcard': {
                    'endpoint': f"*{endpoint}*"
                }
            })
        
        # Date range filter
        if start_date or end_date:
            date_range = {}
            if start_date:
                date_range['gte'] = start_date
            if end_date:
                date_range['lte'] = end_date
            
            must_clauses.append({
                'range': {
                    '@timestamp': date_range
                }
            })
        
        # Build the query body
        query_body = {
            'query': {
                'bool': {
                    'must': must_clauses if must_clauses else [{'match_all': {}}]
                }
            },
            'sort': [
                {'@timestamp': {'order': 'desc'}}
            ],
            'from': (page - 1) * per_page,
            'size': per_page
        }
        
        # Execute search
        result = es_client.search(
            index='saas-logs-*',
            body=query_body
        )
        
        # Extract logs
        logs = [
            {
                '@timestamp': hit['_source'].get('@timestamp'),
                'timestamp': hit['_source'].get('@timestamp'),
                'level': hit['_source'].get('level'),
                'log_type': hit['_source'].get('log_type'),
                'message': hit['_source'].get('message'),
                'endpoint': hit['_source'].get('endpoint'),
                'status_code': hit['_source'].get('status_code'),
                'response_time_ms': hit['_source'].get('response_time_ms'),
                'user_id': hit['_source'].get('user_id'),
                'client_ip': hit['_source'].get('client_ip'),
                'method': hit['_source'].get('method')
            }
            for hit in result['hits']['hits']
        ]
        
        return jsonify({
            'logs': logs,
            'total': result['hits']['total']['value'],
            'page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        app.logger.error(f"Search failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
