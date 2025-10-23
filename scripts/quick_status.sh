#!/bin/bash

# Simple OCR Service Checker
# Quick snapshot of service status
# NOTE: Chandra and Surya are known slow services due to large model sizes
# NOTE: Nanonets disabled - requires commercial API key

echo "OCR Service Status Check - $(date +%H:%M:%S)"
echo

echo "WORKING SERVICES:"
timeout 3 curl -s http://localhost:8089/health >/dev/null 2>&1 && echo "  [READY] Tesseract (8089) - READY!" || echo "  [FAIL] Tesseract (8089) - failed"
timeout 3 curl -s http://localhost:8092/health >/dev/null 2>&1 && echo "  [READY] EasyOCR (8092) - READY!" || echo "  [FAIL] EasyOCR (8092) - failed"
timeout 3 curl -s http://localhost:8093/health >/dev/null 2>&1 && echo "  [READY] Docling (8093) - READY!" || echo "  [FAIL] Docling (8093) - failed"
timeout 3 curl -s http://localhost:8094/health >/dev/null 2>&1 && echo "  [READY] DocTR (8094) - READY!" || echo "  [FAIL] DocTR (8094) - failed"

echo
echo "OPEN-SOURCE SERVICES (model loading):"
timeout 8 curl -s http://localhost:8098/health >/dev/null 2>&1 && echo "  [READY] Chandra (8098) - READY!" || echo "  [SLOW] Chandra (8098) - large model loading (slow)..."
timeout 5 curl -s http://localhost:8102/health >/dev/null 2>&1 && echo "  [READY] OlmOCR (8102) - READY!" || echo "  [LOADING] OlmOCR (8102) - models loading..."
timeout 5 curl -s http://localhost:8103/health >/dev/null 2>&1 && echo "  [READY] DotsOCR (8103) - READY!" || echo "  [FAIL] DotsOCR (8103) - complex dependencies, use Tesseract or Chandra"

echo
echo "LARGE MODEL SERVICES (downloading/processing):"
timeout 8 curl -s http://localhost:8097/health >/dev/null 2>&1 && echo "  [READY] Surya (8097) - READY!" || echo "  [SLOW] Surya (8097) - large model downloading (very slow)..."
timeout 3 curl -s http://localhost:8100/health >/dev/null 2>&1 && echo "  [READY] Qwen (8100) - READY!" || echo "  [LOADING] Qwen (8100) - downloading..."
timeout 3 curl -s http://localhost:8101/health >/dev/null 2>&1 && echo "  [READY] Marker (8101) - READY!" || echo "  [LOADING] Marker (8101) - downloading..."

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