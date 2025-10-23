#!/bin/bash

# Deployment verification script for Medical OCR Pipeline
# Verifies all services and configurations are properly set up

set -e

echo "Medical OCR Pipeline - Deployment Verification"
echo "=============================================="

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Verification functions
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}[OK]${NC} $1"
        return 0
    else
        echo -e "${RED}[MISSING]${NC} $1"
        return 1
    fi
}

check_directory() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}[OK]${NC} $1/"
        return 0
    else
        echo -e "${RED}[MISSING]${NC} $1/"
        return 1
    fi
}

# Check project structure
echo -e "\n${BLUE}📁 Project Structure${NC}"
echo "===================="

# Core directories
check_directory "docker"
check_directory "mcp"
check_directory "scripts"
check_directory "config"
check_directory "notebooks"

# Docker files
echo -e "\n${BLUE}🐳 Docker Configuration${NC}"
echo "========================"

DOCKERFILES=(
    "docker/Dockerfile.tesseract"
    "docker/Dockerfile.easyocr"
    "docker/Dockerfile.paddle"
    "docker/Dockerfile.surya"
    "docker/Dockerfile.docling"
    "docker/Dockerfile.doctr"
    "docker/Dockerfile.deepseek"
    "docker/Dockerfile.qwen"
    "docker/Dockerfile.marker"
    "docker/Dockerfile.nanonets"
    "docker/Dockerfile.chandra"
    "docker/Dockerfile.pipeline"
)

failed_dockerfiles=0
for dockerfile in "${DOCKERFILES[@]}"; do
    if ! check_file "$dockerfile"; then
        ((failed_dockerfiles++))
    fi
done

# Requirements files
echo -e "\n${BLUE}📦 Requirements Files${NC}"
echo "====================="

REQUIREMENTS=(
    "docker/requirements-tesseract.txt"
    "docker/requirements-easyocr.txt"
    "docker/requirements-paddle.txt"
    "docker/requirements-surya.txt"
    "docker/requirements-docling.txt"
    "docker/requirements-doctr.txt"
    "docker/requirements-deepseek.txt"
    "docker/requirements-qwen.txt"
    "docker/requirements-marker.txt"
    "docker/requirements-nanonets.txt"
    "docker/requirements-chandra.txt"
)

failed_requirements=0
for req in "${REQUIREMENTS[@]}"; do
    if ! check_file "$req"; then
        ((failed_requirements++))
    fi
done

# MCP services
echo -e "\n${BLUE}[ISSUE] MCP Services${NC}"
echo "==============="

MCP_SERVICES=(
    "mcp/mcp_ocr_tesseract.py"
    "mcp/mcp_ocr_easy.py"
    "mcp/mcp_ocr_paddle.py"
    "mcp/mcp_ocr_surya.py"
    "mcp/mcp_ocr_docling.py"
    "mcp/mcp_ocr_doctr.py"
    "mcp/mcp_ocr_deepseek.py"
    "mcp/mcp_ocr_qwen.py"
    "mcp/mcp_ocr_marker.py"
    "mcp/mcp_ocr_nanonets.py"
    "mcp/mcp_ocr_chandra.py"
)

failed_services=0
for service in "${MCP_SERVICES[@]}"; do
    if ! check_file "$service"; then
        ((failed_services++))
    fi
done

# Scripts
echo -e "\n${BLUE}[LOG] Scripts${NC}"
echo "=========="

SCRIPTS=(
    "scripts/build_docker_images.sh"
    "scripts/health_check.py"
)

failed_scripts=0
for script in "${SCRIPTS[@]}"; do
    if ! check_file "$script"; then
        ((failed_scripts++))
    fi
done

# Configuration files
echo -e "\n${BLUE}⚙️ Configuration${NC}"
echo "=================="

check_file "docker-compose.yml"
check_file ".env.template"

# Docker Compose validation
echo -e "\n${BLUE}🐳 Docker Compose Validation${NC}"
echo "=============================="

if command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}[SUCCESS]${NC} docker-compose found"
    
    if docker-compose config &> /dev/null; then
        echo -e "${GREEN}[SUCCESS]${NC} docker-compose.yml is valid"
    else
        echo -e "${RED}[ERROR]${NC} docker-compose.yml has syntax errors"
        failed_scripts=$((failed_scripts + 1))
    fi
else
    echo -e "${YELLOW}⚠️${NC} docker-compose not found (install Docker Desktop)"
fi

# Summary
echo -e "\n${BLUE}[STATS] Verification Summary${NC}"
echo "======================="

total_errors=$((failed_dockerfiles + failed_requirements + failed_services + failed_scripts))

echo "Dockerfiles: $((${#DOCKERFILES[@]} - failed_dockerfiles))/${#DOCKERFILES[@]} [SUCCESS]"
echo "Requirements: $((${#REQUIREMENTS[@]} - failed_requirements))/${#REQUIREMENTS[@]} [SUCCESS]"
echo "MCP Services: $((${#MCP_SERVICES[@]} - failed_services))/${#MCP_SERVICES[@]} [SUCCESS]"
echo "Scripts: $((${#SCRIPTS[@]} - failed_scripts))/${#SCRIPTS[@]} [SUCCESS]"

if [ $total_errors -eq 0 ]; then
    echo -e "\n${GREEN}[COMPLETE] ALL CHECKS PASSED!${NC}"
    echo -e "${GREEN}[SUCCESS] Deployment is ready${NC}"
    
    echo -e "\n${BLUE}Next Steps:${NC}"
    echo "1. Set up API keys: cp .env.template .env && edit .env"
    echo "2. Build images: ./scripts/build_docker_images.sh"
    echo "3. Start services: docker-compose up -d"
    echo "4. Check health: python scripts/health_check.py"
    
    exit 0
else
    echo -e "\n${RED}[ERROR] $total_errors ERRORS FOUND${NC}"
    echo -e "${RED}⚠️ Please fix the missing files before deployment${NC}"
    exit 1
fi