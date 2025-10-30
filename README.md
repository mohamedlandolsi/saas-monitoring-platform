# SaaS Application Log Monitoring Platform

A complete ELK Stack (Elasticsearch, Logstash, Kibana) monitoring solution for SaaS applications, built with Docker Compose.

## 🏗️ Architecture

**Scenario D: Application Web SaaS**

This project implements a comprehensive log monitoring platform with:
- **Elasticsearch 8.11**: Search and analytics engine for log storage
- **Logstash 8.11**: Data processing pipeline for CSV and JSON logs
- **Kibana 8.11**: Visualization and exploration interface
- **MongoDB 7**: NoSQL database for metadata storage
- **Redis 7**: In-memory cache for session management
- **Flask 3.0 Web App**: Custom dashboard for monitoring

## 📋 Prerequisites

- **Docker Desktop** (with WSL2 backend on Windows)
- **WSL2** (Windows Subsystem for Linux) - recommended for Windows users
- **8GB RAM minimum** (16GB recommended)
- **10GB free disk space**

## 🚀 Quick Start

### 1. Clone or Navigate to Project Directory

```bash
cd /path/to/saas-monitoring-platform
```

### 2. Create Upload Directory

```bash
mkdir -p uploads
```

### 3. Start All Services

```bash
docker-compose up -d
```

This will start all 6 services in detached mode.

### 4. Wait for Services to Initialize

Wait 2-3 minutes for all services to fully start. Check status:

```bash
docker-compose ps
```

All services should show "healthy" status.

### 5. Access the Dashboards

- **Flask Dashboard**: http://localhost:5000
- **Kibana**: http://localhost:5601
- **Elasticsearch API**: http://localhost:9200
- **MongoDB**: localhost:27017 (credentials: admin/password123)
- **Redis**: localhost:6379

## 📊 Using the Platform

### Generating Sample Logs

The project includes a log generator script to create realistic test data:

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Generate 10,000 sample logs
python generate_logs.py
```

This will create:
- `uploads/saas_logs_sample.csv` - CSV format logs
- `uploads/saas_logs_sample.json` - JSON format logs (JSONL)

The generator creates realistic logs with:
- Timestamps spread over the last 30 days
- Common SaaS endpoints (auth, payments, products, orders, etc.)
- Weighted status code distribution (60% success, 25% client errors, 4% server errors)
- Realistic response times (10-500ms for success, 1000-5000ms for errors)
- User agents, IP addresses, tenant IDs
- SQL queries for database logs

### Uploading Logs

1. Place your CSV or JSON log files in the `uploads/` directory
2. Logstash will automatically detect and process them
3. Logs will be indexed in Elasticsearch as `saas-logs-YYYY.MM.dd`

### CSV Log Format

Expected CSV columns:
```
timestamp,log_type,level,client_ip,user_id,method,endpoint,status_code,response_time_ms,user_agent,message,sql_query,query_duration_ms,server,tenant_id
```

### JSON Log Format

JSON files should contain log objects with fields like:
```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "log_type": "api",
  "level": "info",
  "message": "Request processed",
  "endpoint": "/api/users",
  "status_code": 200
}
```

## 🔧 Common Commands

### View Logs

```bash
# View all services logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f webapp
docker-compose logs -f elasticsearch
docker-compose logs -f logstash
```

### Stop Services

```bash
docker-compose down
```

### Stop and Remove All Data

```bash
docker-compose down -v
```

### Restart a Specific Service

```bash
docker-compose restart webapp
docker-compose restart logstash
```

### Check Service Health

```bash
docker-compose ps
```

## 🛠️ Configuration

### Elasticsearch

- **Port**: 9200
- **Heap Size**: 512MB
- **Mode**: Single-node
- **Security**: Disabled for development

### Logstash

- **Port**: 5044 (Beats input), 9600 (API)
- **Pipeline**: `./logstash/pipeline/logstash.conf`
- **Data Source**: `./uploads/` directory

### MongoDB

- **Port**: 27017
- **Username**: admin
- **Password**: password123

### Redis

- **Port**: 6379
- **Max Memory**: 256MB
- **Eviction Policy**: allkeys-lru

### Flask Web App

- **Port**: 5000
- **Auto-refresh**: 30 seconds
- **Health Check**: `/api/health`
- **Statistics**: `/api/stats`

## 📁 Project Structure

```
saas-monitoring-platform/
├── docker-compose.yml          # Docker services configuration
├── app/
│   ├── Dockerfile              # Flask app container
│   ├── requirements.txt        # Python dependencies
│   ├── app.py                  # Flask application
│   └── templates/
│       └── index.html          # Dashboard UI
├── logstash/
│   └── pipeline/
│       └── logstash.conf       # Logstash configuration
├── uploads/                    # Log files directory (CSV/JSON)
├── .gitignore
└── README.md
```

## 🔍 Troubleshooting

### Elasticsearch Won't Start

- Check available memory: `docker stats`
- Increase Docker memory limit to at least 4GB
- Check logs: `docker-compose logs elasticsearch`

### Logstash Not Processing Files

- Verify files are in `uploads/` directory
- Check Logstash logs: `docker-compose logs logstash`
- Ensure CSV files have the correct header

### Web App Shows "Offline" Services

- Wait 2-3 minutes for all services to initialize
- Check service health: `docker-compose ps`
- Restart services: `docker-compose restart`

### Port Conflicts

If ports are already in use, modify `docker-compose.yml`:
- Elasticsearch: Change `9200:9200` to `9201:9200`
- Kibana: Change `5601:5601` to `5602:5601`
- Flask: Change `5000:5000` to `5001:5000`

## 🔐 Security Notes

**⚠️ This configuration is for DEVELOPMENT ONLY**

For production:
1. Enable Elasticsearch security (xpack.security.enabled=true)
2. Configure TLS/SSL certificates
3. Use strong passwords and change default credentials
4. Enable authentication on all services
5. Use environment variables for sensitive data
6. Configure network isolation
7. Enable audit logging

## 📚 Additional Resources

- [Elasticsearch Documentation](https://www.elastic.co/guide/en/elasticsearch/reference/8.11/index.html)
- [Logstash Documentation](https://www.elastic.co/guide/en/logstash/8.11/index.html)
- [Kibana Documentation](https://www.elastic.co/guide/en/kibana/8.11/index.html)
- [Flask Documentation](https://flask.palletsprojects.com/)

## 📝 License

This project is provided as-is for educational and development purposes.

## 🤝 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review service logs: `docker-compose logs [service-name]`
3. Ensure all prerequisites are met
4. Verify Docker and WSL2 are running correctly

---

**Project**: SaaS Application Log Monitoring Platform  
**Tech Stack**: Docker Compose, ELK Stack 8.11, MongoDB 7, Redis 7, Flask 3.0  
**Scenario**: Application Web SaaS (Scenario D)
