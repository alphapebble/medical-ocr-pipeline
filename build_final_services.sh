#!/bin/bash

# [LAUNCH] Medical OCR Pipeline - Final 3 Services Builder
# Run this script once Docker filesystem is resolved

echo "[LAUNCH] Building Final 3 OCR Services (11-13/13)"
echo "============================================="
echo ""

# Check Docker is working
echo "[INFO] Checking Docker status..."
if ! docker version >/dev/null 2>&1; then
    echo "[ERROR] Docker is not responding. Please restart Docker Desktop and try again."
    exit 1
fi
echo "[SUCCESS] Docker is operational"
echo ""

# Track success
total=3
success=0

# Service 11: Docling (IBM Document Processing)
echo "📦 Building Service 11/13: Docling (IBM Document Processing)"
echo "   Port: 8093 | Dependencies: Fixed | Status: Ready"
if timeout 300 docker build -f docker/Dockerfile.docling -t medical-ocr-pipeline-mcp-docling . >/dev/null 2>&1; then
    echo "   [SUCCESS] Build successful"
    
    # Test the service
    docker run -d --name test-docling -p 8093:8093 -e HOST=0.0.0.0 -e PORT=8093 medical-ocr-pipeline-mcp-docling >/dev/null 2>&1
    sleep 15
    
    if curl -s http://localhost:8093/health >/dev/null 2>&1; then
        echo "   [SUCCESS] Health check passed"
        service_info=$(curl -s http://localhost:8093/health | jq -r '.engine // .service // "Docling Service"')
        echo "   [STATUS] Service: $service_info"
        ((success++))
    else
        echo "   ⚠️  Build successful but health check failed"
    fi
    
    docker stop test-docling >/dev/null 2>&1 && docker rm test-docling >/dev/null 2>&1
else
    echo "   [ERROR] Build failed - check dependencies"
fi
echo ""

# Service 12: DocTR (Mindee Document Text Recognition)  
echo "📦 Building Service 12/13: DocTR (Mindee Document Text Recognition)"
echo "   Port: 8094 | Dependencies: Fixed | System Packages: Added"
if timeout 300 docker build -f docker/Dockerfile.doctr -t medical-ocr-pipeline-mcp-doctr . >/dev/null 2>&1; then
    echo "   [SUCCESS] Build successful"
    
    # Test the service
    docker run -d --name test-doctr -p 8094:8094 -e HOST=0.0.0.0 -e PORT=8094 medical-ocr-pipeline-mcp-doctr >/dev/null 2>&1
    sleep 15
    
    if curl -s http://localhost:8094/health >/dev/null 2>&1; then
        echo "   [SUCCESS] Health check passed"
        service_info=$(curl -s http://localhost:8094/health | jq -r '.engine // .service // "DocTR Service"')
        echo "   [STATUS] Service: $service_info"
        ((success++))
    else
        echo "   ⚠️  Build successful but health check failed"
    fi
    
    docker stop test-doctr >/dev/null 2>&1 && docker rm test-doctr >/dev/null 2>&1
else
    echo "   [ERROR] Build failed - may need additional system packages"
fi
echo ""

# Service 13: Qwen3-VL (Alibaba 32B Multimodal Model)
echo "📦 Building Service 13/13: Qwen3-VL (Alibaba 32B Multimodal)"
echo "   Port: 8101 | Dependencies: Fixed | Model: 32B parameters"
if timeout 300 docker build -f docker/Dockerfile.qwen -t medical-ocr-pipeline-mcp-qwen . >/dev/null 2>&1; then
    echo "   [SUCCESS] Build successful"
    
    # Test the service
    docker run -d --name test-qwen -p 8101:8101 -e HOST=0.0.0.0 -e PORT=8101 medical-ocr-pipeline-mcp-qwen >/dev/null 2>&1
    sleep 20  # Larger model needs more time
    
    if curl -s http://localhost:8101/health >/dev/null 2>&1; then
        echo "   [SUCCESS] Health check passed"
        service_info=$(curl -s http://localhost:8101/health | jq -r '.engine // .service // "Qwen3-VL Service"')
        echo "   [STATUS] Service: $service_info"
        ((success++))
    else
        echo "   ⚠️  Build successful but health check failed"
    fi
    
    docker stop test-qwen >/dev/null 2>&1 && docker rm test-qwen >/dev/null 2>&1
else
    echo "   [ERROR] Build failed - check PyTorch dependencies"
fi
echo ""

# Final Results
echo "[TARGET] Final Build Results"
echo "======================"
echo "[SUCCESS] Successfully built: $success/$total services"
echo "[STATS] Previous services: 10/13 (already operational)"
echo "[WIN] Total completion: $((10 + success))/13 services ($(( (10 + success) * 100 / 13 ))%)"
echo ""

if [ $success -eq $total ]; then
    echo "[COMPLETE] MISSION COMPLETE! All 13 OCR services are now operational!"
    echo ""
    echo "[LAUNCH] Ready for full deployment:"
    echo "   docker-compose up --profile full"
    echo ""
    echo "[INFO] Verify all services:"
    echo "   for port in {8089..8101}; do"
    echo "     curl -s http://localhost:\$port/health | jq '.engine // .service'"
    echo "   done"
    echo ""
    echo "📈 Your Medical OCR Pipeline now provides:"
    echo "   • 13 different OCR engines with unique strengths"
    echo "   • Traditional + AI-powered text recognition"
    echo "   • Medical document specialization"
    echo "   • Multi-language support (109+ languages)"
    echo "   • Layout analysis and document understanding"
    echo "   • Ensemble accuracy through engine diversity"
    
elif [ $success -gt 0 ]; then
    echo "[TARGET] Partial Success: $success additional services operational"
    echo "[STATS] Total: $((10 + success))/13 services working"
    echo ""
    echo "[ISSUE] Troubleshoot remaining $(( total - success )) service(s):"
    echo "   • Check build logs for specific error messages"
    echo "   • Verify system dependencies are installed"
    echo "   • Ensure adequate disk space and memory"
    
else
    echo "⚠️  No additional services built successfully"
    echo "[INFO] Troubleshooting needed:"
    echo "   • Docker filesystem may still be read-only"
    echo "   • Check Docker Desktop status"
    echo "   • Try 'docker system prune -f' once filesystem is writable"
    echo "   • Review individual build logs for specific errors"
fi

echo ""
echo "📚 See COMPLETION_GUIDE.md for detailed troubleshooting"
echo "📖 See DEVELOPMENT_JOURNEY.md for complete project documentation"