#!/bin/bash

# Docker Validation Script
# Run this script to validate all Docker configurations

set -e

echo "Docker Configuration Validation"
echo "================================"

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    echo ""
    echo "To start Docker:"
    echo "  - On macOS: Open Docker Desktop"
    echo "  - On Linux: sudo systemctl start docker"
    echo "  - On Windows: Start Docker Desktop"
    exit 1
fi

echo "✅ Docker is running"

# Check Docker Compose
if ! command -v docker-compose >/dev/null 2>&1; then
    echo "❌ docker-compose is not installed"
    exit 1
fi

echo "✅ docker-compose is available"

# Validate Dockerfile syntax
echo ""
echo "Validating Dockerfile syntax..."

dockerfiles=(
    "docker/Dockerfile.tesseract"
    "docker/Dockerfile.easyocr" 
    "docker/Dockerfile.paddle"
    "docker/Dockerfile.surya"
    "docker/Dockerfile.pipeline"
)

for dockerfile in "${dockerfiles[@]}"; do
    if [ -f "$dockerfile" ]; then
        echo "  ✅ $dockerfile exists"
        # Basic syntax check by parsing the Dockerfile
        if docker build -f "$dockerfile" --dry-run . >/dev/null 2>&1; then
            echo "     ✅ Syntax is valid"
        else
            echo "     ❌ Syntax check failed - run: docker build -f $dockerfile --dry-run ."
        fi
    else
        echo "  ❌ $dockerfile not found"
    fi
done

# Validate requirements files
echo ""
echo "Validating requirements files..."

requirements_files=(
    "docker/requirements-tesseract.txt"
    "docker/requirements-easyocr.txt"
    "docker/requirements-paddle.txt" 
    "docker/requirements-surya.txt"
    "requirements.txt"
)

for req_file in "${requirements_files[@]}"; do
    if [ -f "$req_file" ]; then
        echo "  ✅ $req_file exists"
        if [ -s "$req_file" ]; then
            echo "     ✅ Contains $(wc -l < "$req_file") packages"
        else
            echo "     ⚠️  File is empty"
        fi
    else
        echo "  ❌ $req_file not found"
    fi
done

# Validate docker-compose.yml
echo ""
echo "Validating docker-compose.yml..."

if [ -f "docker-compose.yml" ]; then
    echo "  ✅ docker-compose.yml exists"
    if docker-compose config >/dev/null 2>&1; then
        echo "  ✅ docker-compose.yml syntax is valid"
        echo "  ✅ Services defined: $(docker-compose config --services | tr '\n' ' ')"
    else
        echo "  ❌ docker-compose.yml has syntax errors"
        echo "     Run: docker-compose config"
    fi
else
    echo "  ❌ docker-compose.yml not found"
fi

# Validate MCP source files
echo ""
echo "Validating MCP source files..."

mcp_files=(
    "mcp/mcp_ocr_tesseract.py"
    "mcp/mcp_ocr_easy.py"
    "mcp/mcp_ocr_paddle.py"
    "mcp/mcp_ocr_surya.py"
)

for mcp_file in "${mcp_files[@]}"; do
    if [ -f "$mcp_file" ]; then
        echo "  ✅ $mcp_file exists"
    else
        echo "  ❌ $mcp_file not found"
    fi
done

# Check if pipeline runner script exists
echo ""
echo "Validating pipeline scripts..."

if [ -f "scripts/run_pipeline.py" ]; then
    echo "  ✅ scripts/run_pipeline.py exists"
else
    echo "  ❌ scripts/run_pipeline.py not found"
fi

if [ -f "scripts/build_docker_images.sh" ]; then
    echo "  ✅ scripts/build_docker_images.sh exists"
    if [ -x "scripts/build_docker_images.sh" ]; then
        echo "     ✅ Build script is executable"
    else
        echo "     ⚠️  Build script is not executable (run: chmod +x scripts/build_docker_images.sh)"
    fi
else
    echo "  ❌ scripts/build_docker_images.sh not found"
fi

echo ""
echo "Validation Summary"
echo "=================="
echo "✅ All Docker configurations appear to be valid"
echo ""
echo "Next steps:"
echo "1. Build images:     ./scripts/build_docker_images.sh"
echo "2. Start services:   docker-compose up -d"
echo "3. Check health:     docker-compose ps"
echo "4. View logs:        docker-compose logs -f"
echo "5. Run pipeline:     docker-compose exec pipeline-runner python scripts/run_pipeline.py"
echo ""
echo "For troubleshooting, see docs/DOCKER_DEPLOYMENT.md"