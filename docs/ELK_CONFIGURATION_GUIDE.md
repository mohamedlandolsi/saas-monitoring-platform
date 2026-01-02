# 🔧 ELK Stack Configuration Guide

This guide covers the complete configuration of Elasticsearch, Logstash, and Kibana for the SaaS Monitoring Platform.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Elasticsearch Configuration](#elasticsearch-configuration)
3. [Logstash Configuration](#logstash-configuration)
4. [Kibana Configuration](#kibana-configuration)
5. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Upload    │────▶│  Logstash   │────▶│Elasticsearch│◀────│   Kibana    │
│   (Flask)   │     │  (Pipeline) │     │   (Index)   │     │   (UI)      │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                  │                    │                   │
   CSV/JSON         Parse & Enrich        Store & Search      Visualize
```

**Data Flow:**
1. User uploads CSV/JSON files via Flask web interface
2. Files are saved to `/app/uploads/` directory (mounted as `/data/uploads/` in Logstash)
3. Logstash watches this directory and processes new files
4. Logstash parses, transforms, and enriches the data
5. Data is indexed into Elasticsearch with daily indices (`saas-logs-YYYY.MM.dd`)
6. Kibana provides visualization and search interface

---

## Elasticsearch Configuration

### Connection Settings

| Setting | Value |
|---------|-------|
| Host | `http://elasticsearch:9200` |
| Security | Disabled (development) |
| Discovery Type | `single-node` |

### Index Template

Create an index template for proper field mappings:

```bash
curl -X PUT "http://localhost:9200/_index_template/saas-logs" -H "Content-Type: application/json" -d '
{
  "index_patterns": ["saas-logs-*"],
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 0,
      "refresh_interval": "30s"
    },
    "mappings": {
      "properties": {
        "@timestamp": { "type": "date" },
        "log_type": { "type": "keyword" },
        "level": { "type": "keyword" },
        "client_ip": { "type": "ip" },
        "user_id": { "type": "integer" },
        "method": { "type": "keyword" },
        "endpoint": { "type": "keyword" },
        "status_code": { "type": "integer" },
        "response_time_ms": { "type": "float" },
        "user_agent": { "type": "text" },
        "message": { "type": "text" },
        "sql_query": { "type": "text" },
        "query_duration_ms": { "type": "float" },
        "server": { "type": "keyword" },
        "tenant_id": { "type": "keyword" },
        "source_type": { "type": "keyword" },
        "geoip": {
          "properties": {
            "location": { "type": "geo_point" },
            "country_name": { "type": "keyword" },
            "city_name": { "type": "keyword" }
          }
        }
      }
    }
  }
}'
```

### Data Types

| Field | Type | Description |
|-------|------|-------------|
| `@timestamp` | `date` | Log timestamp (ISO8601) |
| `log_type` | `keyword` | Type of log (web_request, database_query) |
| `level` | `keyword` | Severity (INFO, WARNING, ERROR, CRITICAL) |
| `client_ip` | `ip` | Client IP address |
| `status_code` | `integer` | HTTP status code |
| `response_time_ms` | `float` | Response time in milliseconds |
| `endpoint` | `keyword` | API endpoint path |

### Index Lifecycle Management (ILM)

For production, configure ILM to manage old indices:

```bash
curl -X PUT "http://localhost:9200/_ilm/policy/saas-logs-policy" -H "Content-Type: application/json" -d '
{
  "policy": {
    "phases": {
      "hot": { "min_age": "0ms", "actions": { "rollover": { "max_size": "5GB", "max_age": "1d" } } },
      "delete": { "min_age": "30d", "actions": { "delete": {} } }
    }
  }
}'
```

---

## Logstash Configuration

### Pipeline Location

```
logstash/pipeline/logstash.conf
```

### Input Configuration

Two file inputs watch the uploads directory:

#### CSV Input
```
input {
  file {
    path => "/data/uploads/*.csv"
    start_position => "beginning"
    sincedb_path => "/dev/null"
    mode => "read"
    tags => ["csv"]
  }
}
```

#### JSON Input
```
input {
  file {
    path => "/data/uploads/*.json"
    start_position => "beginning"
    sincedb_path => "/dev/null"
    mode => "read"
    codec => "json"
    tags => ["json"]
  }
}
```

### Filter Configuration

#### CSV Parsing
```
filter {
  if "csv" in [tags] {
    csv {
      separator => ","
      skip_header => true
      columns => [
        "timestamp", "log_type", "level", "client_ip",
        "user_id", "method", "endpoint", "status_code",
        "response_time_ms", "user_agent", "message",
        "sql_query", "query_duration_ms", "server", "tenant_id"
      ]
    }
  }
}
```

#### Date Parsing
```
date {
  match => ["timestamp", "ISO8601", "yyyy-MM-dd HH:mm:ss"]
  target => "@timestamp"
  remove_field => ["timestamp"]
}
```

#### Type Conversion
```
mutate {
  convert => {
    "status_code" => "integer"
    "response_time_ms" => "float"
    "query_duration_ms" => "float"
  }
}
```

#### GeoIP Enrichment
```
geoip {
  source => "client_ip"
  target => "geoip"
  tag_on_failure => ["_geoip_lookup_failure"]
}
```

### Output Configuration

```
output {
  elasticsearch {
    hosts => ["http://elasticsearch:9200"]
    index => "saas-logs-%{+YYYY.MM.dd}"
  }
}
```

### Testing Pipeline

```bash
# Check Logstash pipeline status
curl http://localhost:9600/_node/pipelines?pretty

# View Logstash logs
docker compose logs logstash --tail=50

# Check document count
curl "http://localhost:9200/saas-logs-*/_count"
```

---

## Kibana Configuration

### Access

| Setting | Value |
|---------|-------|
| URL | http://localhost:5601 |

### Creating Index Pattern

1. Navigate to **Stack Management** → **Index Patterns**
2. Click **Create index pattern**
3. Enter pattern: `saas-logs-*`
4. Select `@timestamp` as the time field
5. Click **Create index pattern**

### Recommended Visualizations

Create these 3+ visualizations for dashboards:

#### 1. Request Volume Over Time (Line Chart)
- **Index**: `saas-logs-*`
- **Y-axis**: Count
- **X-axis**: Date Histogram on `@timestamp`
- **Split**: By `level.keyword`

#### 2. HTTP Status Code Distribution (Pie Chart)
- **Index**: `saas-logs-*`
- **Slice Size**: Count
- **Split Slices**: Terms on `status_code`

#### 3. Response Time Metrics (Metric)
- **Index**: `saas-logs-*`
- **Metrics**: Average, P95, Max of `response_time_ms`

#### 4. Top Endpoints (Bar Chart)
- **Index**: `saas-logs-*`
- **Y-axis**: Count
- **X-axis**: Terms on `endpoint.keyword` (Top 10)

#### 5. Error Rate Over Time (Area Chart)
- **Index**: `saas-logs-*`
- **Filter**: `level: ERROR OR level: CRITICAL`

#### 6. Geographic Distribution (Maps)
- **Index**: `saas-logs-*`
- **Layer**: `geoip.location`

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| No documents found | Wait 30s for Logstash, check file format |
| Mapping conflict | Delete index, recreate with template |
| Connection refused | Check `docker compose ps` |
| Kibana unavailable | Wait 2-3 min for startup |

### Useful Commands

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Check health
docker compose ps

# View logs
docker compose logs -f

# Document count
curl "http://localhost:9200/saas-logs-*/_count"

# Search logs
curl "http://localhost:9200/saas-logs-*/_search?q=level:ERROR&size=10"
```

### Service URLs

| Service | URL |
|---------|-----|
| Flask Dashboard | http://localhost:5000 |
| Elasticsearch | http://localhost:9200 |
| Kibana | http://localhost:5601 |
| Logstash API | http://localhost:9600 |
