#!/bin/bash

# Check specific service logs for model download progress
# Usage: ./check_service_logs.sh [service_name]

if [ -z "$1" ]; then
    echo "Usage: $0 <service_name>"
    echo "Available services: surya, qwen, marker, chandra, nanonets, olmo, dots, deepseek"
    exit 1
fi

service="$1"
daemon_name="${service}-daemon"

echo "=== Checking $service logs ==="
echo

# Check if container exists
if ! docker ps --format "{{.Names}}" | grep -q "^${daemon_name}$"; then
    echo "[ERROR] Container $daemon_name not found or not running"
    exit 1
fi

echo "Container Status:"
docker ps --format "{{.Names}}: {{.Status}}" | grep "$daemon_name"
echo

echo "Recent Logs (last 10 lines):"
docker logs "$daemon_name" --tail 10

echo
echo "Looking for download progress..."
docker logs "$daemon_name" 2>&1 | grep -E "(Download|progress|%|Loading|model)" | tail -5

echo
echo "Testing health endpoint..."
timeout 3 curl -s http://localhost:$(docker port "$daemon_name" | cut -d: -f2)/health || echo "Health check timeout/failed"