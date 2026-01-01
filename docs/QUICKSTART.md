# 🚀 Quick Start Guide

This guide covers how to start, stop, and manage the SaaS Monitoring Platform.

## Prerequisites

- **Docker Desktop** (v20.10+)
- **Docker Compose** (v2.0+)

Verify installation:
```bash
docker --version
docker compose version
```

---

## 🟢 Starting the Application

### Start All Services

```bash
cd /path/to/saas-monitoring-platform
docker compose up -d
```

This starts 6 containers:
| Service | Port | Description |
|---------|------|-------------|
| **webapp** | 5000 | Flask web dashboard |
| **elasticsearch** | 9200 | Search engine & log storage |
| **logstash** | 5044 | Log ingestion & processing |
| **kibana** | 5601 | Data visualization |
| **mongodb** | 27017 | User & metadata storage |
| **redis** | 6379 | Caching & sessions |

### Check Service Status

```bash
docker compose ps
```

All services should show `Up (healthy)`:
```
NAME            STATUS
elasticsearch   Up (healthy)
mongodb         Up (healthy)
redis           Up (healthy)
logstash        Up (healthy)
kibana          Up (healthy)
webapp          Up (healthy)
```

### Verify Services Are Running

```bash
# Check Elasticsearch
curl http://localhost:9200

# Check Flask app health
curl http://localhost:5000/api/health

# Check Redis
docker compose exec redis redis-cli ping
# Expected output: PONG
```

### Access the Platform

| Service | URL |
|---------|-----|
| **Flask Dashboard** | http://localhost:5000 |
| **Kibana** | http://localhost:5601 |
| **Elasticsearch API** | http://localhost:9200 |
| **Performance Metrics** | http://localhost:5000/api/performance |

---

## 🔴 Stopping the Application

### Stop All Services (Keep Data)

```bash
docker compose down
```

This stops and removes containers but **preserves data** in Docker volumes.

### Stop All Services and Remove Data

```bash
docker compose down -v
```

⚠️ **Warning**: This removes all data including:
- Elasticsearch logs
- MongoDB users and metadata
- Redis cache

### Stop a Specific Service

```bash
docker compose stop webapp
docker compose stop elasticsearch
```

---

## 🔄 Restarting Services

### Restart All Services

```bash
docker compose restart
```

### Restart a Specific Service

```bash
docker compose restart webapp
docker compose restart elasticsearch
```

---

## 📋 Viewing Logs

### View All Container Logs

```bash
docker compose logs -f
```

### View Logs for a Specific Service

```bash
docker compose logs -f webapp
docker compose logs -f elasticsearch
docker compose logs -f logstash
```

### View Last N Lines

```bash
docker compose logs --tail=100 webapp
```

---

## 🔧 Troubleshooting

### Service Won't Start

1. Check if ports are already in use:
   ```bash
   # Linux/Mac
   lsof -i :5000
   lsof -i :9200
   
   # Windows
   netstat -ano | findstr :5000
   ```

2. Check Docker resources (ensure enough memory):
   - Recommended: 8GB RAM for Docker

3. View container logs for errors:
   ```bash
   docker compose logs webapp
   ```

### Elasticsearch Not Starting

Elasticsearch requires more virtual memory:
```bash
# Linux only
sudo sysctl -w vm.max_map_count=262144
```

### Reset Everything (Clean Start)

```bash
# Stop all containers and remove volumes
docker compose down -v

# Remove all images (optional)
docker compose down --rmi all

# Start fresh
docker compose up -d
```

---

## 📊 Generate Sample Logs

After starting the application:

```bash
# Install Faker in the container (first time only)
docker compose exec webapp pip install Faker==20.1.0

# Copy and run the log generator
docker cp generate_saas_logs.py webapp:/app/
docker compose exec webapp python /app/generate_saas_logs.py --count 10000 --format json
```

Logs will be automatically processed by Logstash and indexed in Elasticsearch.

---

## 🔄 Common Workflows

### Daily Development

```bash
# Start your day
docker compose up -d

# Work on the project...

# End your day
docker compose down
```

### Quick Health Check

```bash
docker compose ps && curl -s http://localhost:5000/api/health | jq
```

### Rebuilding After Code Changes

```bash
docker compose up -d --build webapp
```

---

## 📚 Additional Resources

- [Full README](../README.md) - Complete documentation
- [Performance Optimizations](../PERFORMANCE_OPTIMIZATIONS.md)
- [System Status](../SYSTEM_STATUS.md)
