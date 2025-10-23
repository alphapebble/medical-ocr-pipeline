#!/bin/bash

# OCR Services Health Monitor  
# Checks all 13 OCR services and reports their status

# Service name to port mapping
check_service() {
    service=$1
    port=$2
    
    # Try health check with 3 second timeout
    response=$(timeout 3 curl -s http://localhost:$port/health 2>/dev/null)
    exit_code=$?
    
    if [ $exit_code -eq 0 ] && [ -n "$response" ]; then
        # Parse JSON response to check if 'ok' is true
        ok_status=$(echo "$response" | jq -r '.ok // false' 2>/dev/null)
        if [ "$ok_status" = "true" ]; then
            echo "[OK] $service ($port): WORKING"
            return 0
        else
            error=$(echo "$response" | jq -r '.error // "unknown error"' 2>/dev/null)
            echo "[ERROR] $service ($port): ERROR - $error"
            return 2
        fi
    elif [ $exit_code -eq 124 ]; then
        echo "[LOADING] $service ($port): LOADING (timeout)"
        return 1
    else
        echo "[FAILED] $service ($port): UNREACHABLE"
        return 2
    fi
}

echo "=== OCR Services Health Check - $(date) ==="
echo

WORKING=0
LOADING=0
FAILED=0

# Check each service
check_service "tesseract" "8089"; case $? in 0) ((WORKING++));; 1) ((LOADING++));; 2) ((FAILED++));; esac
check_service "paddleocr" "8090"; case $? in 0) ((WORKING++));; 1) ((LOADING++));; 2) ((FAILED++));; esac
check_service "easyocr" "8092"; case $? in 0) ((WORKING++));; 1) ((LOADING++));; 2) ((FAILED++));; esac
check_service "docling" "8093"; case $? in 0) ((WORKING++));; 1) ((LOADING++));; 2) ((FAILED++));; esac
check_service "doctr" "8094"; case $? in 0) ((WORKING++));; 1) ((LOADING++));; 2) ((FAILED++));; esac
check_service "deepseek" "8095"; case $? in 0) ((WORKING++));; 1) ((LOADING++));; 2) ((FAILED++));; esac
check_service "surya" "8097"; case $? in 0) ((WORKING++));; 1) ((LOADING++));; 2) ((FAILED++));; esac
check_service "chandra" "8098"; case $? in 0) ((WORKING++));; 1) ((LOADING++));; 2) ((FAILED++));; esac
check_service "nanonets" "8099"; case $? in 0) ((WORKING++));; 1) ((LOADING++));; 2) ((FAILED++));; esac
check_service "qwen" "8100"; case $? in 0) ((WORKING++));; 1) ((LOADING++));; 2) ((FAILED++));; esac
check_service "marker" "8101"; case $? in 0) ((WORKING++));; 1) ((LOADING++));; 2) ((FAILED++));; esac
check_service "olmo" "8102"; case $? in 0) ((WORKING++));; 1) ((LOADING++));; 2) ((FAILED++));; esac
check_service "dots" "8103"; case $? in 0) ((WORKING++));; 1) ((LOADING++));; 2) ((FAILED++));; esac

echo
echo "Summary: $WORKING working, $LOADING loading, $FAILED failed/unreachable"
echo "Progress: $(( (WORKING * 100) / 13 ))% services operational"
echo