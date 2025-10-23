#!/bin/bash

# 🧹 Medical OCR Pipeline - Cleanup & Optimization Script
# Removes unused Docker resources and optimizes for final builds

echo "🧹 Medical OCR Pipeline - Docker Cleanup"
echo "========================================"
echo ""

# Check Docker status
echo "[INFO] Checking Docker status..."
if ! docker version >/dev/null 2>&1; then
    echo "[ERROR] Docker is not responding. Please restart Docker Desktop first."
    exit 1
fi

# Show current usage
echo "[STATS] Current Docker usage:"
docker system df
echo ""

# Stop all containers
echo "🛑 Stopping all containers..."
docker stop $(docker ps -q) 2>/dev/null || echo "No running containers"
docker-compose down 2>/dev/null || echo "No compose services running"
echo ""

# List our medical OCR images
echo "📦 Current Medical OCR Pipeline images:"
docker images --format "table {{.Repository}}\t{{.Size}}" | grep medical-ocr-pipeline
echo ""

# Calculate total size
total_size=$(docker images --format "{{.Size}}" | grep -E '^[0-9.]+GB$' | sed 's/GB//' | awk '{sum += $1} END {print sum}')
echo "💾 Total pipeline images: ~${total_size}GB"
echo ""

# Ask user what to clean
echo "[TARGET] Cleanup Options:"
echo "1. Remove TESTED images (keep core 8 + ready-to-build 3)"
echo "2. Remove ALL images (clean slate)"
echo "3. Remove build cache only"
echo "4. Skip cleanup"
echo ""
read -p "Choose option (1-4): " choice

case $choice in
    1)
        echo "🗑️ Removing tested images to save space..."
        # Keep core working services, remove the larger tested ones
        docker rmi medical-ocr-pipeline-mcp-marker 2>/dev/null || echo "Marker already removed"
        docker rmi medical-ocr-pipeline-mcp-deepseek 2>/dev/null || echo "DeepSeek removal failed"
        docker rmi medical-ocr-pipeline-mcp-paddle 2>/dev/null || echo "PaddleOCR removal failed"
        docker rmi medical-ocr-pipeline-mcp-easyocr 2>/dev/null || echo "EasyOCR removal failed"
        echo "[SUCCESS] Cleanup attempt completed"
        ;;
    2)
        echo "🗑️ Removing ALL medical OCR images..."
        docker rmi $(docker images -q --filter "reference=medical-ocr-pipeline-*") 2>/dev/null || echo "Some images could not be removed"
        echo "[SUCCESS] Clean slate - ready for fresh builds"
        ;;
    3)
        echo "🧹 Cleaning build cache..."
        docker builder prune -f 2>/dev/null || echo "Build cache cleanup failed (filesystem issue)"
        echo "[SUCCESS] Build cache cleanup attempted"
        ;;
    4)
        echo "⏭️ Skipping cleanup"
        ;;
    *)
        echo "[ERROR] Invalid option"
        exit 1
        ;;
esac

echo ""

# Show final status
echo "[STATS] Post-cleanup Docker usage:"
docker system df
echo ""

# Check what medical OCR images remain
remaining=$(docker images -q --filter "reference=medical-ocr-pipeline-*" | wc -l)
echo "📦 Remaining medical OCR images: $remaining"

if [ $remaining -gt 0 ]; then
    echo "[STATUS] Remaining images:"
    docker images --format "table {{.Repository}}\t{{.Size}}" | grep medical-ocr-pipeline
else
    echo "🧹 No medical OCR images remaining - clean slate for rebuilding"
fi

echo ""
echo "[TARGET] Next Steps:"
echo "1. If Docker filesystem is working: ./build_final_services.sh"
echo "2. If Docker filesystem still broken: Restart Docker Desktop"
echo "3. For fresh rebuild: docker-compose build --no-cache"
echo ""
echo "[SUCCESS] Cleanup complete!"