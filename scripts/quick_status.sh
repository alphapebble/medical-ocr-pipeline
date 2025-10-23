#!/bin/bash

# Simple OCR Service Checker
# Quick snapshot of service status

echo "Quick OCR Service Status Check - $(date +%H:%M:%S)"
echo

# Test the 5 known working services first
echo "CONFIRMED WORKING:"
curl -s --max-time 1 http://localhost:8089/health >/dev/null && echo "  * Tesseract (8089)" || echo "  [FAIL] Tesseract (8089)"
curl -s --max-time 1 http://localhost:8090/health >/dev/null && echo "  * PaddleOCR (8090)" || echo "  [FAIL] PaddleOCR (8090)"  
curl -s --max-time 1 http://localhost:8092/health >/dev/null && echo "  * EasyOCR (8092)" || echo "  [FAIL] EasyOCR (8092)"
curl -s --max-time 1 http://localhost:8093/health >/dev/null && echo "  * Docling (8093)" || echo "  [FAIL] Docling (8093)"
curl -s --max-time 1 http://localhost:8094/health >/dev/null && echo "  * DocTR (8094)" || echo "  [FAIL] DocTR (8094)"

echo
echo "NEWLY STARTED (might be ready):"
curl -s --max-time 2 http://localhost:8098/health >/dev/null && echo "  [READY] Chandra (8098) - READY!" || echo "  [LOADING] Chandra (8098) - loading..."
curl -s --max-time 2 http://localhost:8099/health >/dev/null && echo "  [READY] Nanonets (8099) - READY!" || echo "  [LOADING] Nanonets (8099) - loading..."
curl -s --max-time 2 http://localhost:8102/health >/dev/null && echo "  [READY] OlmOCR (8102) - READY!" || echo "  [LOADING] OlmOCR (8102) - loading..."
curl -s --max-time 2 http://localhost:8103/health >/dev/null && echo "  [READY] DotsOCR (8103) - READY!" || echo "  [LOADING] DotsOCR (8103) - loading..."

echo
echo "LARGE MODEL DOWNLOADS:"
curl -s --max-time 1 http://localhost:8097/health >/dev/null && echo "  [READY] Surya (8097) - READY!" || echo "  [LOADING] Surya (8097) - downloading..."
curl -s --max-time 1 http://localhost:8100/health >/dev/null && echo "  [READY] Qwen (8100) - READY!" || echo "  [LOADING] Qwen (8100) - downloading..."
curl -s --max-time 1 http://localhost:8101/health >/dev/null && echo "  [READY] Marker (8101) - READY!" || echo "  [LOADING] Marker (8101) - downloading..."

echo
echo "KNOWN ISSUES:"
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