#!/bin/bash

# Simple OCR Service Checker
# Quick snapshot of service status

echo "OCR Service Status Check - $(date +%H:%M:%S)"
echo

echo "NEWLY STARTED SERVICES (checking readiness):"
curl -s --max-time 2 http://localhost:8098/health >/dev/null && echo "  [READY] Chandra (8098) - READY!" || echo "  [LOADING] Chandra (8098) - loading..."
curl -s --max-time 2 http://localhost:8099/health >/dev/null && echo "  [READY] Nanonets (8099) - READY!" || echo "  [LOADING] Nanonets (8099) - loading..."
curl -s --max-time 2 http://localhost:8102/health >/dev/null && echo "  [READY] OlmOCR (8102) - READY!" || echo "  [LOADING] OlmOCR (8102) - loading..."
curl -s --max-time 2 http://localhost:8103/health >/dev/null && echo "  [READY] DotsOCR (8103) - READY!" || echo "  [LOADING] DotsOCR (8103) - loading..."

echo
echo "LARGE MODEL SERVICES (downloading/processing):"
curl -s --max-time 1 http://localhost:8097/health >/dev/null && echo "  [READY] Surya (8097) - READY!" || echo "  [LOADING] Surya (8097) - downloading..."
curl -s --max-time 1 http://localhost:8100/health >/dev/null && echo "  [READY] Qwen (8100) - READY!" || echo "  [LOADING] Qwen (8100) - downloading..."
curl -s --max-time 1 http://localhost:8101/health >/dev/null && echo "  [READY] Marker (8101) - READY!" || echo "  [LOADING] Marker (8101) - downloading..."

echo
echo "DEBUGGING SERVICES:"
response=$(curl -s --max-time 2 http://localhost:8095/health 2>/dev/null)
if echo "$response" | jq -e '.ok == true' >/dev/null 2>&1; then
    echo "  [READY] DeepSeek (8095) - FIXED!"
elif echo "$response" | jq -e '.ok == false' >/dev/null 2>&1; then
    error=$(echo "$response" | jq -r '.error' | cut -c1-50)
    echo "  [ERROR] DeepSeek (8095) - Error: $error..."
else
    echo "  [LOADING] DeepSeek (8095) - loading..."
fi

echo
echo "Run './scripts/monitor_ocr_services.sh' for detailed status"
echo "Run './scripts/check_service_logs.sh <service>' to debug specific service"