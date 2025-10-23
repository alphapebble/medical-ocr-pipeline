#!/bin/bash

# Continuous OCR Service Monitor
# Runs every 2 minutes and shows progress

echo "Starting continuous OCR service monitoring..."
echo "Will check every 2 minutes. Press Ctrl+C to stop."
echo

while true; do
    clear
    echo "=== OCR Services Health Monitor - $(date) ==="
    echo
    
    WORKING=0
    LOADING=0
    FAILED=0
    
    # Quick health checks
    services=("tesseract:8089" "paddleocr:8090" "easyocr:8092" "docling:8093" "doctr:8094" "deepseek:8095" "surya:8097" "chandra:8098" "nanonets:8099" "qwen:8100" "marker:8101" "olmo:8102" "dots:8103")
    
    for service_info in "${services[@]}"; do
        service=${service_info%:*}
        port=${service_info#*:}
        
        # Very quick check - 2 second timeout
        response=$(timeout 2 curl -s http://localhost:$port/health 2>/dev/null)
        exit_code=$?
        
        if [ $exit_code -eq 0 ] && [ -n "$response" ]; then
            ok_status=$(echo "$response" | jq -r '.ok // false' 2>/dev/null)
            if [ "$ok_status" = "true" ]; then
                printf "[OK] %-12s (%s): WORKING\n" "$service" "$port"
                ((WORKING++))
            else
                error=$(echo "$response" | jq -r '.error // "unknown"' 2>/dev/null | cut -c1-40)
                printf "[ERROR] %-12s (%s): ERROR - %s\n" "$service" "$port" "$error"
                ((FAILED++))
            fi
        else
            printf "[LOADING] %-12s (%s): LOADING...\n" "$service" "$port"
            ((LOADING++))
        fi
    done
    
    echo
    echo "Summary: $WORKING working | $LOADING loading | $FAILED failed"
    echo "Progress: $(( (WORKING * 100) / 13 ))% operational"
    
    # Show Docker status for debugging
    echo
    echo "Docker Status:"
    docker ps --format "{{.Names}}: {{.Status}}" | grep daemon | head -5
    
    echo
    echo "Next check in 2 minutes... (Ctrl+C to stop)"
    sleep 120
done