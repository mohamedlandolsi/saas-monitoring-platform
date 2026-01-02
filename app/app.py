import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any, List, Tuple
from functools import wraps
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for, Response
from flask_cors import CORS
from flask_compress import Compress
from elasticsearch import Elasticsearch
from pymongo import MongoClient, ASCENDING
from redis import Redis
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import json
import time
import gzip
from models.file import File
from models.search_history import SearchHistory
from models.saved_search import SavedSearch
from models.user import User
from utils.cache import CacheManager, cache_result, invalidate_cache
from utils.errors import (
    AppError, ValidationError, DatabaseError, CacheError, 
    ElasticsearchError, FileProcessingError, NotFoundError,
    format_error_response, handle_generic_exception
)
from utils.performance import (
    connection_pool, get_es_client, get_mongo_client, get_redis_client,
    QueryCache, cache_query, Pagination, ESQueryOptimizer,
    ResponseCompression, PerformanceMonitor, measure_time
)

app = Flask(__name__)
CORS(app)

# Enable response compression (gzip)
compress = Compress()
compress.init_app(app)
app.config['COMPRESS_MIMETYPES'] = [
    'text/html', 'text/css', 'text/javascript', 
    'application/json', 'application/javascript'
]
app.config['COMPRESS_LEVEL'] = 6  # Compression level (1-9)
app.config['COMPRESS_MIN_SIZE'] = 1024  # Only compress responses > 1KB

# Configure secret key for sessions
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_TYPE'] = 'redis'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour

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

def allowed_file(filename: str) -> bool:
    """
    Check if file has an allowed extension.
    
    Args:
        filename (str): Name of the file to check
    
    Returns:
        bool: True if file extension is in ALLOWED_EXTENSIONS, False otherwise
    
    Examples:
        >>> allowed_file('data.csv')
        True
        >>> allowed_file('script.py')
        False
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ============================================================================
# Initialize Clients with Connection Pooling
# ============================================================================

def init_elasticsearch() -> Optional[Elasticsearch]:
    """
    Initialize and test Elasticsearch client connection with pooling.
    
    Attempts to connect to Elasticsearch using the host specified in
    ELASTICSEARCH_HOST environment variable. Tests connection with ping.
    
    Returns:
        Optional[Elasticsearch]: Elasticsearch client if connection successful, None otherwise
    
    Environment Variables:
        ELASTICSEARCH_HOST: Elasticsearch server URL (default: http://localhost:9200)
    """
    es_host = os.getenv('ELASTICSEARCH_HOST', 'http://localhost:9200')
    try:
        # Initialize connection pool
        mongo_uri = os.getenv('MONGODB_URI', 'mongodb://admin:password123@localhost:27017/')
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        
        connection_pool.initialize(es_host, mongo_uri, redis_host, redis_port)
        
        es = connection_pool.get_es_client()
        if es.ping():
            app.logger.info(f"✓ Connected to Elasticsearch at {es_host} (with connection pooling)")
            return es
        else:
            app.logger.error(f"✗ Failed to ping Elasticsearch at {es_host}")
            return None
    except Exception as e:
        app.logger.error(f"✗ Elasticsearch connection error: {str(e)}")
        return None

def init_mongodb() -> Optional[MongoClient]:
    """
    Initialize and test MongoDB client connection with pooling.
    
    Attempts to connect to MongoDB using the URI specified in
    MONGODB_URI environment variable. Tests connection with ping command.
    Also creates necessary indexes for performance.
    
    Returns:
        Optional[MongoClient]: MongoDB client if connection successful, None otherwise
    
    Environment Variables:
        MONGODB_URI: MongoDB connection URI (default: mongodb://admin:password123@localhost:27017/)
    """
    try:
        client = connection_pool.get_mongo_client()
        client.admin.command('ping')
        app.logger.info(f"✓ Connected to MongoDB (with connection pooling)")
        
        # Create performance indexes
        db = client['saas_logs']
        
        # Files collection indexes
        files_collection = db['files']
        files_collection.create_index([('upload_date', ASCENDING)], background=True)
        files_collection.create_index([('file_type', ASCENDING)], background=True)
        files_collection.create_index([('status', ASCENDING)], background=True)
        files_collection.create_index([('uploaded_by', ASCENDING)], background=True)
        app.logger.info("✓ Created MongoDB indexes for files collection")
        
        # Search history indexes
        search_history_collection = db['search_history']
        search_history_collection.create_index([('user_id', ASCENDING)], background=True)
        search_history_collection.create_index([('timestamp', ASCENDING)], background=True)
        app.logger.info("✓ Created MongoDB indexes for search_history collection")
        
        # Saved searches indexes
        saved_searches_collection = db['saved_searches']
        saved_searches_collection.create_index([('user_id', ASCENDING)], background=True)
        saved_searches_collection.create_index([('created_at', ASCENDING)], background=True)
        app.logger.info("✓ Created MongoDB indexes for saved_searches collection")
        
        # Users collection indexes
        users_collection = db['users']
        users_collection.create_index([('username', ASCENDING)], unique=True, background=True)
        users_collection.create_index([('email', ASCENDING)], unique=True, background=True)
        app.logger.info("✓ Created MongoDB indexes for users collection")
        
        return client
    except Exception as e:
        app.logger.error(f"✗ MongoDB connection error: {str(e)}")
        return None

def init_redis() -> Optional[Redis]:
    """
    Initialize and test Redis client connection with pooling.
    
    Attempts to connect to Redis using the host and port specified in
    environment variables. Tests connection with ping command.
    
    Returns:
        Optional[Redis]: Redis client if connection successful, None otherwise
    
    Environment Variables:
        REDIS_HOST: Redis server host (default: localhost)
        REDIS_PORT: Redis server port (default: 6379)
    """
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    try:
        client = connection_pool.get_redis_client()
        client.ping()
        app.logger.info(f"✓ Connected to Redis at {redis_host}:{redis_port} (with connection pooling)")
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
saved_search_model = None
user_model = None

if mongo_client:
    try:
        file_model = File(mongo_client)
        search_history_model = SearchHistory(mongo_client)
        saved_search_model = SavedSearch(mongo_client)
        user_model = User(mongo_client)
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
# Authentication Helpers
# ============================================================================

def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Get the current logged-in user from session.
    
    Returns:
        Dict: User document if logged in, None otherwise
    """
    user_id = session.get('user_id')
    if not user_id or not user_model:
        return None
    
    return user_model.get_by_id(user_id)

def login_required(f):
    """
    Decorator to protect routes that require authentication.
    
    If user is not logged in:
    - For HTML pages: redirect to /login
    - For API endpoints: return 401 JSON error
    
    Usage:
        @app.route('/protected')
        @login_required
        def protected():
            return 'Only logged in users see this'
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        
        if not user:
            # Check if this is an API request
            if request.path.startswith('/api/'):
                return jsonify({
                    'success': False,
                    'error': 'Authentication required',
                    'message': 'Please log in to access this resource'
                }), 401
            
            # For HTML pages, redirect to login
            return redirect(url_for('login_page', next=request.url))
        
        return f(*args, **kwargs)
    
    return decorated_function

def create_session(user_id: str, remember_me: bool = False) -> None:
    """
    Create a session for the user.
    
    Args:
        user_id: User document ID
        remember_me: If True, session persists for 30 days; otherwise 1 hour
    """
    session['user_id'] = user_id
    session['logged_in'] = True
    
    if remember_me:
        session.permanent = True
        # Set to 30 days
        app.config['PERMANENT_SESSION_LIFETIME'] = 30 * 24 * 3600
    else:
        session.permanent = False

def destroy_session() -> None:
    """
    Destroy the current session (logout).
    """
    session.clear()

# ============================================================================
# Routes
# ============================================================================

@app.route('/')
def index():
    """
    Render the main dashboard page.
    
    Returns:
        str: Rendered HTML template for the dashboard
    """
    user = get_current_user()
    return render_template('index.html', user=user)

@app.route('/search')
def search():
    """
    Render the search page for querying logs.
    
    Returns:
        str: Rendered HTML template for log search interface
    """
    user = get_current_user()
    return render_template('search.html', user=user)

@app.route('/upload')
@login_required
def upload():
    """
    Render the file upload page.
    
    Requires authentication.
    
    Returns:
        str: Rendered HTML template for file upload interface
    """
    user = get_current_user()
    return render_template('upload.html', user=user)

@app.route('/files')
@login_required
def files_page():
    """
    Render the files management page.
    
    Requires authentication.
    
    Returns:
        str: Rendered HTML template for files management
    """
    user = get_current_user()
    return render_template('files.html', user=user)

@app.route('/login')
def login_page():
    """
    Render the login page.
    
    If already logged in, redirect to dashboard.
    
    Returns:
        str: Rendered HTML template for login form
    """
    # If already logged in, redirect to dashboard
    if get_current_user():
        return redirect(url_for('index'))
    
    return render_template('login.html')

@app.route('/register')
def register_page():
    """
    Render the registration page.
    
    If already logged in, redirect to dashboard.
    
    Returns:
        str: Rendered HTML template for registration form
    """
    # If already logged in, redirect to dashboard
    if get_current_user():
        return redirect(url_for('index'))
    
    return render_template('register.html')

# ============================================================================
# Authentication API Endpoints
# ============================================================================

@app.route('/api/login', methods=['POST'])
def api_login() -> Tuple[Dict[str, Any], int]:
    """
    Authenticate user and create session.
    
    Request Body:
        {
            "username": str,      # Username or email
            "password": str,      # Plain text password
            "remember_me": bool   # Optional: persist session for 30 days
        }
    
    Returns:
        Tuple[Dict[str, Any], int]: JSON response with user info and HTTP status code
        
    Response Format:
        {
            "success": true,
            "message": "Login successful",
            "user": {
                "_id": str,
                "username": str,
                "email": str,
                "full_name": str
            }
        }
    
    Raises:
        ValidationError: If required fields are missing
        DatabaseError: If authentication fails
    """
    if not user_model:
        app.logger.error("Login failed: User model not initialized")
        raise DatabaseError('User authentication not available', operation='login')
    
    try:
        data = request.get_json()
        
        if not data:
            raise ValidationError('Request body is required', field='body')
        
        # Extract credentials
        username = data.get('username', '').strip()
        password = data.get('password', '')
        remember_me = data.get('remember_me', False)
        
        if not username:
            raise ValidationError('Username or email is required', field='username')
        
        if not password:
            raise ValidationError('Password is required', field='password')
        
        # Authenticate user
        user = user_model.authenticate(username, password)
        
        if not user:
            app.logger.warning(f"Failed login attempt for username: {username} from {request.remote_addr}")
            raise ValidationError(
                'Invalid username or password',
                field='credentials',
                details={'username': username}
            )
        
        # Create session
        create_session(user['_id'], remember_me)
        
        app.logger.info(f"User logged in: {user['username']} ({user['_id']}) from {request.remote_addr}")
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': {
                '_id': user['_id'],
                'username': user['username'],
                'email': user['email'],
                'full_name': user.get('full_name', '')
            }
        }), 200
        
    except (ValidationError, DatabaseError):
        raise
    except Exception as e:
        app.logger.error(f"Login error: {str(e)}", exc_info=True)
        raise DatabaseError(
            'An error occurred during login',
            operation='login',
            details={'error': str(e)}
        )

@app.route('/api/logout', methods=['POST'])
def api_logout() -> Tuple[Dict[str, Any], int]:
    """
    Logout user and destroy session.
    
    Returns:
        Tuple[Dict[str, Any], int]: JSON response with logout status and HTTP status code
        
    Response Format:
        {
            "success": true,
            "message": "Logout successful"
        }
    """
    user = get_current_user()
    
    if user:
        app.logger.info(f"User logged out: {user['username']} ({user['_id']}) from {request.remote_addr}")
    
    destroy_session()
    
    return jsonify({
        'success': True,
        'message': 'Logout successful'
    }), 200

@app.route('/api/register', methods=['POST'])
def api_register() -> Tuple[Dict[str, Any], int]:
    """
    Register a new user account.
    
    Request Body:
        {
            "username": str,    # Required: 3-20 chars, alphanumeric + underscore
            "email": str,       # Required: valid email format
            "password": str,    # Required: min 8 chars
            "full_name": str    # Optional: user's full name
        }
    
    Returns:
        Tuple[Dict[str, Any], int]: JSON response with registration status and HTTP status code
        
    Response Format:
        {
            "success": true,
            "message": "Registration successful",
            "user_id": str,
            "redirect": "/dashboard"
        }
    
    Raises:
        ValidationError: If required fields are missing or invalid
        DatabaseError: If registration fails
    """
    if not user_model:
        app.logger.error("Registration failed: User model not initialized")
        raise DatabaseError('User registration not available', operation='register')
    
    try:
        data = request.get_json()
        
        if not data:
            raise ValidationError('Request body is required', field='body')
        
        # Extract and validate fields
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        full_name = data.get('full_name', '').strip()
        
        # Validate username
        if not username:
            raise ValidationError('Username is required', field='username')
        
        if len(username) < 3:
            raise ValidationError('Username must be at least 3 characters long', field='username')
        
        if len(username) > 20:
            raise ValidationError('Username must be at most 20 characters long', field='username')
        
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise ValidationError(
                'Username can only contain letters, numbers, and underscores',
                field='username'
            )
        
        # Validate email
        if not email:
            raise ValidationError('Email is required', field='email')
        
        # Simple email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValidationError('Invalid email format', field='email')
        
        # Validate password
        if not password:
            raise ValidationError('Password is required', field='password')
        
        if len(password) < 8:
            raise ValidationError(
                'Password must be at least 8 characters long',
                field='password'
            )
        
        # Check password complexity (at least one letter and one number)
        if not re.search(r'[a-zA-Z]', password) or not re.search(r'[0-9]', password):
            raise ValidationError(
                'Password must contain at least one letter and one number',
                field='password'
            )
        
        # Create user
        try:
            user_id = user_model.create(
                username=username,
                email=email,
                password=password,
                full_name=full_name
            )
        except ValueError as e:
            # Handle duplicate username/email
            raise ValidationError(str(e), field='username')
        
        if not user_id:
            raise DatabaseError('Failed to create user', operation='register')
        
        # Create session for the new user
        create_session(user_id, remember_me=False)
        
        app.logger.info(f"New user registered: {username} ({user_id}) from {request.remote_addr}")
        
        return jsonify({
            'success': True,
            'message': 'Registration successful',
            'user_id': user_id,
            'redirect': '/'
        }), 201
        
    except (ValidationError, DatabaseError):
        raise
    except Exception as e:
        app.logger.error(f"Registration error: {str(e)}", exc_info=True)
        raise DatabaseError(
            'An error occurred during registration',
            operation='register',
            details={'error': str(e)}
        )

@app.route('/api/user/current', methods=['GET'])
@login_required
def api_current_user() -> Tuple[Dict[str, Any], int]:
    """
    Get current logged-in user information.
    
    Requires authentication.
    
    Returns:
        Tuple[Dict[str, Any], int]: JSON response with user info and HTTP status code
        
    Response Format:
        {
            "success": true,
            "user": {
                "_id": str,
                "username": str,
                "email": str,
                "full_name": str,
                "created_at": str,
                "last_login": str
            }
        }
    """
    user = get_current_user()
    
    return jsonify({
        'success': True,
        'user': user
    }), 200

@app.route('/api/health')
def health_check() -> Tuple[Dict[str, Any], int]:
    """
    Health check endpoint to verify service dependencies.
    
    Checks connectivity to Elasticsearch, MongoDB, and Redis.
    Returns overall health status and individual service statuses.
    
    Returns:
        Tuple[Dict[str, Any], int]: JSON response with health status and HTTP status code
        
    Response Format:
        {
            "status": "healthy" | "unhealthy",
            "elasticsearch": bool,
            "mongodb": bool,
            "redis": bool,
            "healthy": bool
        }
    """
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
def get_stats() -> Dict[str, Any]:
    """
    Get comprehensive log statistics from Elasticsearch.
    
    Retrieves aggregated statistics including total logs, error rates,
    response times, slowest endpoints, and system status. Results are
    cached for 60 seconds to improve performance.
    
    Returns:
        Dict[str, Any]: JSON response with statistics
        
    Response Format:
        {
            "total_logs": int,              # Total log count
            "total_logs_24h": int,          # Logs in last 24 hours
            "error_rate": float,            # Error percentage
            "avg_response_time_24h": float, # Average response time (ms)
            "top_slowest_endpoints": [...], # Top 5 slowest endpoints
            "unique_users_24h": int,        # Unique users in 24h
            "latest_error": {...},          # Most recent error log
            "system_status": {
                "elasticsearch": bool,
                "mongodb": bool,
                "redis": bool
            },
            "cluster_status": str,          # Elasticsearch cluster status
            "indices": [...],               # List of indices with counts
            "error": str | null             # Error message if any
        }
    
    Cache:
        TTL: 60 seconds
        Key: stats:get_stats:<hash>
    """
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
@measure_time('/api/search', 'api')
@cache_result(timeout=300, key_prefix="search")
def search_logs():
    """Search logs in Elasticsearch with advanced filters (cached for 5 min, optimized)"""
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
        
        # Extract sorting parameters
        sort_by = data.get('sort_by', '@timestamp').strip()
        sort_order = data.get('sort_order', 'desc').lower()
        
        # Validate sort parameters
        valid_sort_fields = ['@timestamp', 'level.keyword', 'status_code', 'response_time_ms', 'endpoint.keyword']
        if sort_by not in valid_sort_fields:
            sort_by = '@timestamp'
        if sort_order not in ['asc', 'desc']:
            sort_order = 'desc'
        
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
        
        # Build search body with optimization
        search_body = {
            'query': query,
            'sort': [
                {sort_by: {'order': sort_order}}
            ],
            'from': (page - 1) * per_page,
            'size': per_page,
            # Source filtering - only return needed fields
            '_source': [
                '@timestamp', 'level', 'endpoint', 'status_code',
                'response_time_ms', 'message', 'server', 'user_id', 'client_ip'
            ],
            'track_total_hits': True  # Get accurate total count
        }
        
        # Optimize query
        optimizer = ESQueryOptimizer()
        search_body = optimizer.optimize_query(search_body)
        
        # Execute search with timing
        start_time = time.time()
        response = es_client.search(index='saas-logs-*', body=search_body, request_timeout=30)
        execution_time_ms = (time.time() - start_time) * 1000
        
        # Record ES query time
        if redis_client:
            monitor = PerformanceMonitor(redis_client)
            monitor.record_es_query_time('search_logs', execution_time_ms)
        
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
@measure_time('/api/export', 'api')
def export_logs():
    """Export logs to CSV with same filters as search (optimized with scroll API)"""
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
        
        # Build search body with source filtering
        search_body = {
            'query': query,
            'sort': [
                {'@timestamp': {'order': 'desc'}}
            ],
            '_source': [
                '@timestamp', 'level', 'endpoint', 'status_code',
                'response_time_ms', 'message', 'client_ip', 'user_id', 'server'
            ]
        }
        
        # Use scroll API for large exports (efficient for 10k+ records)
        app.logger.info("Starting export with scroll API")
        start_time = time.time()
        
        optimizer = ESQueryOptimizer()
        all_hits = optimizer.scroll_query(
            es_client=es_client,
            index='saas-logs-*',
            query=search_body,
            scroll='2m',
            size=1000  # Batch size
        )
        
        export_time_ms = (time.time() - start_time) * 1000
        app.logger.info(f"Export fetched {len(all_hits)} documents in {export_time_ms:.2f}ms")
        
        # Record ES query time
        if redis_client:
            monitor = PerformanceMonitor(redis_client)
            monitor.record_es_query_time('export_logs', export_time_ms)
        
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
        for hit in all_hits:
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
        csv_data = output.getvalue()
        
        # Compress if large
        if len(csv_data) > 10240:  # > 10KB
            app.logger.info(f"Compressing export ({len(csv_data)} bytes)")
            response = Response(
                gzip.compress(csv_data.encode('utf-8')),
                mimetype='application/gzip',
                headers={
                    'Content-Disposition': f'attachment; filename={filename}.gz',
                    'Content-Encoding': 'gzip'
                }
            )
        else:
            response = Response(
                csv_data,
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

# ============================================================================
# Autocomplete and Saved Search Endpoints
# ============================================================================

@app.route('/api/autocomplete/endpoints', methods=['GET'])
def autocomplete_endpoints() -> Tuple[Dict[str, Any], int]:
    """
    Get autocomplete suggestions for endpoint field.
    
    Uses Elasticsearch terms aggregation to return the top 20 unique
    endpoints from the log index. Results are useful for autocomplete
    functionality in search forms.
    
    Returns:
        Tuple[Dict[str, Any], int]: JSON response with endpoint suggestions and HTTP status code
        
    Response Format:
        {
            "success": true,
            "endpoints": [
                "/api/users",
                "/api/orders",
                ...
            ],
            "count": int
        }
    
    Raises:
        ElasticsearchError: If Elasticsearch query fails
    """
    if not es_client:
        app.logger.error("Autocomplete failed: Elasticsearch client not initialized")
        raise ElasticsearchError('Elasticsearch client not initialized', operation='autocomplete')
    
    try:
        # Query parameter for filtering (optional)
        prefix = request.args.get('q', '').strip()
        
        # Build aggregation query
        search_body = {
            'size': 0,
            'aggs': {
                'unique_endpoints': {
                    'terms': {
                        'field': 'endpoint.keyword',
                        'size': 20,
                        'order': {'_count': 'desc'}
                    }
                }
            }
        }
        
        # Add prefix filter if provided
        if prefix:
            search_body['query'] = {
                'prefix': {
                    'endpoint.keyword': prefix
                }
            }
        
        # Execute search
        response = es_client.search(index='saas-logs-*', body=search_body)
        
        # Extract unique endpoints
        buckets = response['aggregations']['unique_endpoints']['buckets']
        endpoints = [bucket['key'] for bucket in buckets]
        
        app.logger.info(f"Autocomplete endpoints: {len(endpoints)} results for prefix '{prefix}'")
        
        return jsonify({
            'success': True,
            'endpoints': endpoints,
            'count': len(endpoints)
        }), 200
        
    except Exception as e:
        app.logger.error(f"Autocomplete endpoints error: {str(e)}", exc_info=True)
        raise ElasticsearchError(
            'Failed to fetch endpoint suggestions',
            operation='autocomplete',
            details={'error': str(e)}
        )

@app.route('/api/autocomplete/messages', methods=['GET'])
def autocomplete_messages() -> Tuple[Dict[str, Any], int]:
    """
    Get autocomplete suggestions for message field.
    
    Uses Elasticsearch match query with suggestions to return top 10
    matching log messages. Useful for autocomplete in search forms.
    
    Query Parameters:
        q (str): Search query/prefix for messages
    
    Returns:
        Tuple[Dict[str, Any], int]: JSON response with message suggestions and HTTP status code
        
    Response Format:
        {
            "success": true,
            "messages": [
                "User login successful",
                "User logout",
                ...
            ],
            "count": int
        }
    
    Raises:
        ValidationError: If query parameter is missing
        ElasticsearchError: If Elasticsearch query fails
    """
    if not es_client:
        app.logger.error("Autocomplete failed: Elasticsearch client not initialized")
        raise ElasticsearchError('Elasticsearch client not initialized', operation='autocomplete')
    
    try:
        # Get query parameter
        query = request.args.get('q', '').strip()
        
        if not query:
            raise ValidationError('Query parameter "q" is required', field='q')
        
        # Build match query for message field
        search_body = {
            'size': 10,
            'query': {
                'match': {
                    'message': {
                        'query': query,
                        'operator': 'and',
                        'fuzziness': 'AUTO'
                    }
                }
            },
            '_source': ['message'],
            'sort': [
                {'@timestamp': {'order': 'desc'}}
            ]
        }
        
        # Execute search
        response = es_client.search(index='saas-logs-*', body=search_body)
        
        # Extract unique messages
        hits = response['hits']['hits']
        messages = []
        seen = set()
        
        for hit in hits:
            message = hit['_source'].get('message', '')
            if message and message not in seen:
                messages.append(message)
                seen.add(message)
        
        app.logger.info(f"Autocomplete messages: {len(messages)} results for query '{query}'")
        
        return jsonify({
            'success': True,
            'messages': messages,
            'count': len(messages)
        }), 200
        
    except (ValidationError, ElasticsearchError):
        raise
    except Exception as e:
        app.logger.error(f"Autocomplete messages error: {str(e)}", exc_info=True)
        raise ElasticsearchError(
            'Failed to fetch message suggestions',
            operation='autocomplete',
            details={'error': str(e)}
        )

@app.route('/api/search/save', methods=['POST'])
def save_search() -> Tuple[Dict[str, Any], int]:
    """
    Save a search query with filters for later reuse.
    
    Saves search parameters to MongoDB, allowing users to quickly
    reapply frequently used search configurations.
    
    Request Body:
        {
            "name": str,                # Required: Name for saved search
            "description": str,         # Optional: Description
            "filters": {                # Required: Search filters
                "q": str,
                "level": str,
                "status_code": str,
                "endpoint": str,
                "server": str,
                "date_from": str,
                "date_to": str
            }
        }
    
    Returns:
        Tuple[Dict[str, Any], int]: JSON response with saved search details and HTTP status code
        
    Response Format:
        {
            "success": true,
            "message": "Search saved successfully",
            "search_id": str,
            "name": str
        }
    
    Raises:
        ValidationError: If required fields are missing or invalid
        DatabaseError: If MongoDB save operation fails
    """
    if not saved_search_model:
        app.logger.error("Save search failed: MongoDB not initialized")
        raise DatabaseError('Database not initialized', operation='save_search')
    
    try:
        data = request.get_json()
        
        if not data:
            raise ValidationError('Request body is required', field='body')
        
        # Extract and validate required fields
        name = data.get('name', '').strip()
        if not name:
            raise ValidationError('Search name is required', field='name')
        
        filters = data.get('filters', {})
        if not isinstance(filters, dict):
            raise ValidationError('Filters must be an object', field='filters')
        
        # Optional fields
        description = data.get('description', '').strip()
        
        # Use IP as user identifier (or implement proper user auth)
        user = request.remote_addr
        
        # Save to MongoDB
        search_id = saved_search_model.save(
            name=name,
            filters=filters,
            user=user,
            description=description
        )
        
        if not search_id:
            raise DatabaseError('Failed to save search', operation='save_search')
        
        app.logger.info(f"Search saved: '{name}' by user {user}")
        
        return jsonify({
            'success': True,
            'message': 'Search saved successfully',
            'search_id': search_id,
            'name': name
        }), 201
        
    except (ValidationError, DatabaseError):
        raise
    except Exception as e:
        app.logger.error(f"Save search error: {str(e)}", exc_info=True)
        raise DatabaseError(
            'An error occurred while saving search',
            operation='save_search',
            details={'error': str(e)}
        )

@app.route('/api/search/saved', methods=['GET'])
def get_saved_searches() -> Tuple[Dict[str, Any], int]:
    """
    Get all saved searches for the current user.
    
    Retrieves saved search configurations from MongoDB, ordered by
    last used timestamp. Returns list of saved searches with their
    filters and metadata.
    
    Query Parameters:
        limit (int): Maximum number of results (default: 50)
    
    Returns:
        Tuple[Dict[str, Any], int]: JSON response with saved searches and HTTP status code
        
    Response Format:
        {
            "success": true,
            "searches": [
                {
                    "_id": str,
                    "name": str,
                    "description": str,
                    "filters": {...},
                    "created_at": str,
                    "last_used": str,
                    "use_count": int
                },
                ...
            ],
            "count": int
        }
    
    Raises:
        DatabaseError: If MongoDB query fails
    """
    if not saved_search_model:
        app.logger.error("Get saved searches failed: MongoDB not initialized")
        raise DatabaseError('Database not initialized', operation='get_saved_searches')
    
    try:
        # Get limit parameter
        limit = request.args.get('limit', 50, type=int)
        if limit < 1 or limit > 100:
            limit = 50
        
        # Use IP as user identifier
        user = request.remote_addr
        
        # Get saved searches from MongoDB
        searches = saved_search_model.get_by_user(user=user, limit=limit)
        
        app.logger.info(f"Retrieved {len(searches)} saved searches for user {user}")
        
        return jsonify({
            'success': True,
            'searches': searches,
            'count': len(searches)
        }), 200
        
    except DatabaseError:
        raise
    except Exception as e:
        app.logger.error(f"Get saved searches error: {str(e)}", exc_info=True)
        raise DatabaseError(
            'An error occurred while retrieving saved searches',
            operation='get_saved_searches',
            details={'error': str(e)}
        )

@app.route('/api/search/saved/<search_id>', methods=['DELETE'])
def delete_saved_search(search_id: str) -> Tuple[Dict[str, Any], int]:
    """
    Delete a saved search by ID.
    
    Removes a saved search from MongoDB. Only the user who created
    the search can delete it.
    
    URL Parameters:
        search_id (str): ID of the saved search to delete
    
    Returns:
        Tuple[Dict[str, Any], int]: JSON response with deletion status and HTTP status code
        
    Response Format:
        {
            "success": true,
            "message": "Search deleted successfully"
        }
    
    Raises:
        ValidationError: If search_id is invalid
        NotFoundError: If search not found
        DatabaseError: If MongoDB delete operation fails
    """
    if not saved_search_model:
        app.logger.error("Delete saved search failed: MongoDB not initialized")
        raise DatabaseError('Database not initialized', operation='delete_saved_search')
    
    try:
        if not search_id:
            raise ValidationError('Search ID is required', field='search_id')
        
        # Use IP as user identifier
        user = request.remote_addr
        
        # Delete from MongoDB
        deleted = saved_search_model.delete(search_id=search_id, user=user)
        
        if not deleted:
            raise NotFoundError(
                'Search not found or not authorized to delete',
                resource='saved_search',
                resource_id=search_id
            )
        
        app.logger.info(f"Search deleted: {search_id} by user {user}")
        
        return jsonify({
            'success': True,
            'message': 'Search deleted successfully'
        }), 200
        
    except (ValidationError, NotFoundError, DatabaseError):
        raise
    except Exception as e:
        app.logger.error(f"Delete saved search error: {str(e)}", exc_info=True)
        raise DatabaseError(
            'An error occurred while deleting search',
            operation='delete_saved_search',
            details={'error': str(e)}
        )

# ============================================================================
# Chart Data Endpoints
# ============================================================================

@app.route('/api/charts/logs_per_hour', methods=['GET'])
def get_logs_per_hour() -> Tuple[Dict[str, Any], int]:
    """
    Get logs count per hour for the last 24 hours.
    
    Uses Elasticsearch date_histogram aggregation to bucket logs by hour.
    Useful for visualizing log volume trends.
    
    Returns:
        Tuple[Dict[str, Any], int]: JSON response with labels and data, status code
        
    Response Format:
        {
            "success": true,
            "labels": ["Oct 30, 10:00", "Oct 30, 11:00", ...],
            "data": [120, 145, 98, ...]
        }
    
    Raises:
        ElasticsearchError: If Elasticsearch is not available or query fails
    """
    try:
        if not es_client:
            app.logger.error("Charts API failed: Elasticsearch not available")
            raise ElasticsearchError('Elasticsearch client not initialized', operation='date_histogram')
        
        # Calculate time range: last 24 hours
        now = datetime.utcnow()
        time_24h_ago = now - timedelta(hours=24)
        
        # Build Elasticsearch query with date histogram aggregation
        search_body = {
            'size': 0,  # We only want aggregations, not individual documents
            'query': {
                'range': {
                    '@timestamp': {
                        'gte': time_24h_ago.isoformat(),
                        'lte': now.isoformat()
                    }
                }
            },
            'aggs': {
                'logs_per_hour': {
                    'date_histogram': {
                        'field': '@timestamp',
                        'fixed_interval': '1h',  # Hourly buckets
                        'time_zone': 'UTC',
                        'min_doc_count': 0  # Include empty buckets
                    }
                }
            }
        }
        
        # Execute search
        response = es_client.search(index='saas-logs-*', body=search_body)
        
        # Extract buckets from aggregation
        buckets = response.get('aggregations', {}).get('logs_per_hour', {}).get('buckets', [])
        
        # Format data for Chart.js
        labels = []
        data = []
        
        for bucket in buckets:
            # Convert timestamp to readable format
            timestamp = datetime.fromisoformat(bucket['key_as_string'].replace('Z', '+00:00'))
            label = timestamp.strftime('%b %d, %H:%M')
            labels.append(label)
            data.append(bucket['doc_count'])
        
        app.logger.info(f"Fetched logs per hour: {len(buckets)} data points")
        
        return jsonify({
            'success': True,
            'labels': labels,
            'data': data
        }), 200
        
    except ElasticsearchError:
        raise
    except Exception as e:
        app.logger.error(f"Error fetching logs per hour: {str(e)}", exc_info=True)
        raise ElasticsearchError(
            'Failed to fetch logs per hour data',
            operation='date_histogram',
            details={'error': str(e)}
        )

@app.route('/api/charts/top_endpoints', methods=['GET'])
def get_top_endpoints() -> Tuple[Dict[str, Any], int]:
    """
    Get top 5 endpoints by request count.
    
    Uses Elasticsearch terms aggregation to find most frequently accessed endpoints.
    
    Returns:
        Tuple[Dict[str, Any], int]: JSON response with labels and data, status code
        
    Response Format:
        {
            "success": true,
            "labels": ["/api/search", "/api/upload", ...],
            "data": [1500, 1200, 800, ...]
        }
    
    Raises:
        ElasticsearchError: If Elasticsearch is not available or query fails
    """
    try:
        if not es_client:
            app.logger.error("Charts API failed: Elasticsearch not available")
            raise ElasticsearchError('Elasticsearch client not initialized', operation='terms_aggregation')
        
        # Build Elasticsearch query with terms aggregation
        search_body = {
            'size': 0,
            'aggs': {
                'top_endpoints': {
                    'terms': {
                        'field': 'endpoint.keyword',  # Use keyword field for exact matching
                        'size': 5,  # Top 5 endpoints
                        'order': {
                            '_count': 'desc'  # Order by count descending
                        }
                    }
                }
            }
        }
        
        # Execute search
        response = es_client.search(index='saas-logs-*', body=search_body)
        
        # Extract buckets from aggregation
        buckets = response.get('aggregations', {}).get('top_endpoints', {}).get('buckets', [])
        
        # Format data for Chart.js
        labels = []
        data = []
        
        for bucket in buckets:
            labels.append(bucket['key'])
            data.append(bucket['doc_count'])
        
        app.logger.info(f"Fetched top {len(buckets)} endpoints")
        
        return jsonify({
            'success': True,
            'labels': labels,
            'data': data
        }), 200
        
    except ElasticsearchError:
        raise
    except Exception as e:
        app.logger.error(f"Error fetching top endpoints: {str(e)}", exc_info=True)
        raise ElasticsearchError(
            'Failed to fetch top endpoints data',
            operation='terms_aggregation',
            details={'error': str(e)}
        )

@app.route('/api/charts/status_distribution', methods=['GET'])
def get_status_distribution() -> Tuple[Dict[str, Any], int]:
    """
    Get distribution of HTTP status codes.
    
    Uses Elasticsearch terms aggregation to group logs by status code.
    Useful for visualizing success vs error rates.
    
    Returns:
        Tuple[Dict[str, Any], int]: JSON response with labels and data, status code
        
    Response Format:
        {
            "success": true,
            "labels": ["200", "404", "500", ...],
            "data": [8500, 450, 50, ...],
            "colors": ["#28a745", "#ffc107", "#dc3545", ...]
        }
    
    Raises:
        ElasticsearchError: If Elasticsearch is not available or query fails
    """
    try:
        if not es_client:
            app.logger.error("Charts API failed: Elasticsearch not available")
            raise ElasticsearchError('Elasticsearch client not initialized', operation='terms_aggregation')
        
        # Build Elasticsearch query with terms aggregation
        search_body = {
            'size': 0,
            'aggs': {
                'status_codes': {
                    'terms': {
                        'field': 'status_code',
                        'size': 10,  # Top 10 status codes
                        'order': {
                            '_count': 'desc'
                        }
                    }
                }
            }
        }
        
        # Execute search
        response = es_client.search(index='saas-logs-*', body=search_body)
        
        # Extract buckets from aggregation
        buckets = response.get('aggregations', {}).get('status_codes', {}).get('buckets', [])
        
        # Format data for Chart.js with color coding
        labels = []
        data = []
        colors = []
        
        # Color mapping for different status code ranges
        def get_status_color(code):
            """Get color based on HTTP status code"""
            if 200 <= code < 300:
                return '#28a745'  # Green for success
            elif 300 <= code < 400:
                return '#17a2b8'  # Cyan for redirects
            elif 400 <= code < 500:
                return '#ffc107'  # Yellow for client errors
            elif 500 <= code < 600:
                return '#dc3545'  # Red for server errors
            else:
                return '#6c757d'  # Gray for unknown
        
        for bucket in buckets:
            status_code = int(bucket['key'])
            labels.append(str(status_code))
            data.append(bucket['doc_count'])
            colors.append(get_status_color(status_code))
        
        app.logger.info(f"Fetched status distribution: {len(buckets)} status codes")
        
        return jsonify({
            'success': True,
            'labels': labels,
            'data': data,
            'colors': colors
        }), 200
        
    except ElasticsearchError:
        raise
    except Exception as e:
        app.logger.error(f"Error fetching status distribution: {str(e)}", exc_info=True)
        raise ElasticsearchError(
            'Failed to fetch status distribution data',
            operation='terms_aggregation',
            details={'error': str(e)}
        )

@app.route('/api/charts/error_rate', methods=['GET'])
def get_error_rate() -> Tuple[Dict[str, Any], int]:
    """
    Get error rate (5xx errors) over the last 7 days.
    
    Uses Elasticsearch date_histogram aggregation with filter to track
    server errors over time. Useful for monitoring system health trends.
    
    Returns:
        Tuple[Dict[str, Any], int]: JSON response with labels and data, status code
        
    Response Format:
        {
            "success": true,
            "labels": ["Oct 24", "Oct 25", "Oct 26", ...],
            "data": [25, 18, 32, ...],
            "total_errors": 150
        }
    
    Raises:
        ElasticsearchError: If Elasticsearch is not available or query fails
    """
    try:
        if not es_client:
            app.logger.error("Charts API failed: Elasticsearch not available")
            raise ElasticsearchError('Elasticsearch client not initialized', operation='date_histogram')
        
        # Calculate time range: last 7 days
        now = datetime.utcnow()
        time_7d_ago = now - timedelta(days=7)
        
        # Build Elasticsearch query with date histogram and error filter
        search_body = {
            'size': 0,
            'query': {
                'bool': {
                    'must': [
                        {
                            'range': {
                                '@timestamp': {
                                    'gte': time_7d_ago.isoformat(),
                                    'lte': now.isoformat()
                                }
                            }
                        },
                        {
                            'range': {
                                'status_code': {
                                    'gte': 500,  # Only 5xx errors
                                    'lt': 600
                                }
                            }
                        }
                    ]
                }
            },
            'aggs': {
                'errors_per_day': {
                    'date_histogram': {
                        'field': '@timestamp',
                        'fixed_interval': '1d',  # Daily buckets
                        'time_zone': 'UTC',
                        'min_doc_count': 0  # Include days with no errors
                    }
                }
            }
        }
        
        # Execute search
        response = es_client.search(index='saas-logs-*', body=search_body)
        
        # Extract buckets from aggregation
        buckets = response.get('aggregations', {}).get('errors_per_day', {}).get('buckets', [])
        total_errors = response.get('hits', {}).get('total', {}).get('value', 0)
        
        # Format data for Chart.js
        labels = []
        data = []
        
        for bucket in buckets:
            # Convert timestamp to readable format
            timestamp = datetime.fromisoformat(bucket['key_as_string'].replace('Z', '+00:00'))
            label = timestamp.strftime('%b %d')
            labels.append(label)
            data.append(bucket['doc_count'])
        
        app.logger.info(f"Fetched error rate: {len(buckets)} days, {total_errors} total errors")
        
        return jsonify({
            'success': True,
            'labels': labels,
            'data': data,
            'total_errors': total_errors
        }), 200
        
    except ElasticsearchError:
        raise
    except Exception as e:
        app.logger.error(f"Error fetching error rate: {str(e)}", exc_info=True)
        raise ElasticsearchError(
            'Failed to fetch error rate data',
            operation='date_histogram',
            details={'error': str(e)}
        )

# ============================================================================
# Performance Monitoring Endpoint
# ============================================================================

@app.route('/api/performance', methods=['GET'])
def get_performance_metrics() -> Tuple[Dict[str, Any], int]:
    """
    Get performance metrics for the application.
    
    Provides insights into:
    - Average API response times
    - Elasticsearch query times
    - MongoDB query times
    - Cache hit rates
    
    Returns:
        Tuple[Dict[str, Any], int]: JSON response with performance data, status code
        
    Response Format:
        {
            "success": true,
            "metrics": {
                "api_response_times": {
                    "api:/api/search": 145.23,
                    "api:/api/upload": 523.45,
                    ...
                },
                "elasticsearch_query_times": {
                    "es:search_logs": 89.12,
                    "es:aggregations": 156.78,
                    ...
                },
                "mongodb_query_times": {
                    "mongo:files": 23.45,
                    "mongo:search_history": 12.34,
                    ...
                },
                "cache_statistics": {
                    "total_keys": 150,
                    "hits": 1234,
                    "misses": 567,
                    "hit_rate": 68.5
                }
            },
            "timestamp": "2025-10-30T12:34:56Z"
        }
    
    Raises:
        DatabaseError: If Redis is not available
    """
    try:
        if not redis_client:
            raise DatabaseError('Redis client not initialized', operation='performance_metrics')
        
        # Get performance monitor
        monitor = PerformanceMonitor(redis_client)
        
        # Get all metrics
        metrics = monitor.get_all_metrics()
        
        # Get cache statistics
        cache = QueryCache(redis_client)
        cache_stats = cache.get_stats()
        
        # Format response
        response_data = {
            'success': True,
            'metrics': {
                'api_response_times': metrics.get('api_times', {}),
                'elasticsearch_query_times': metrics.get('es_query_times', {}),
                'mongodb_query_times': metrics.get('mongo_query_times', {}),
                'cache_statistics': cache_stats
            },
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
        app.logger.info("Performance metrics retrieved successfully")
        return jsonify(response_data), 200
        
    except DatabaseError:
        raise
    except Exception as e:
        app.logger.error(f"Error fetching performance metrics: {str(e)}", exc_info=True)
        raise DatabaseError(
            'Failed to fetch performance metrics',
            operation='performance_metrics',
            details={'error': str(e)}
        )


# ============================================================================
# Global Request Handlers for Performance Tracking
# ============================================================================

@app.before_request
def before_request():
    """Track request start time for performance monitoring."""
    request.start_time = time.time()


@app.after_request
def after_request(response):
    """
    Log request details and track performance metrics.
    
    - Records API response times
    - Logs request duration
    - Tracks endpoint performance
    """
    # Calculate request duration
    if hasattr(request, 'start_time'):
        duration = (time.time() - request.start_time) * 1000  # Convert to ms
        
        # Log request details
        app.logger.info(
            f"{request.method} {request.path} - {response.status_code} - {duration:.2f}ms"
        )
        
        # Record API performance metric
        if redis_client and request.path.startswith('/api/'):
            try:
                monitor = PerformanceMonitor(redis_client)
                monitor.record_api_time(request.path, duration)
            except Exception as e:
                app.logger.error(f"Error recording API metric: {e}")
    
    return response


@app.errorhandler(TimeoutError)
def handle_timeout(error):
    """Handle request timeout errors."""
    app.logger.error(f"Request timeout: {str(error)}")
    return jsonify({
        'success': False,
        'error': 'Request timeout',
        'message': 'The request took too long to process. Please try again.'
    }), 504


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
