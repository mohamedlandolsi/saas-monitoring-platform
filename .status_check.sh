#!/bin/bash
echo "=== Docker Status Check ==="
echo "Date: $(date)"
echo ""
echo "=== Docker Version ==="
docker --version
echo ""
echo "=== Running Containers ==="
docker ps
echo ""
echo "=== All Containers ==="
docker ps -a
echo ""
echo "=== Docker Compose Status ==="
cd /home/cosme/Dev/ITBS/saas-monitoring-platform
docker compose ps
echo ""
echo "=== Checking Ports ==="
echo "Port 5000 (Flask):"
netstat -tuln 2>/dev/null | grep 5000 || ss -tuln | grep 5000 || echo "Not listening"
echo "Port 9200 (Elasticsearch):"
netstat -tuln 2>/dev/null | grep 9200 || ss -tuln | grep 9200 || echo "Not listening"
echo "Port 5601 (Kibana):"
netstat -tuln 2>/dev/null | grep 5601 || ss -tuln | grep 5601 || echo "Not listening"
echo ""
echo "=== Service Tests ==="
echo "Elasticsearch test:"
curl -s http://localhost:9200 | head -5 || echo "Not responding"
echo ""
echo "Flask app test:"
curl -s http://localhost:5000/api/health | head -5 || echo "Not responding"
echo ""
echo "=== Done ==="
