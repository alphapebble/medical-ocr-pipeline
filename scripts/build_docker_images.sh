#!/bin/bash

# Build all Docker images for MCP OCR services
set -e

echo "Building MCP OCR Docker Images"
echo "=============================="

# Build directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Build each MCP service
echo "Building Tesseract MCP service..."
docker build -f docker/Dockerfile.tesseract -t mcp-tesseract:latest .

echo "Building EasyOCR MCP service..."
docker build -f docker/Dockerfile.easyocr -t mcp-easyocr:latest .

echo "Building PaddleOCR MCP service..."
docker build -f docker/Dockerfile.paddle -t mcp-paddle:latest .

echo "Building Surya OCR MCP service..."
docker build -f docker/Dockerfile.surya -t mcp-surya:latest .

echo "Building Docling MCP service..."
docker build -f docker/Dockerfile.docling -t mcp-docling:latest .

echo "Building DocTR MCP service..."
docker build -f docker/Dockerfile.doctr -t mcp-doctr:latest .

echo "Building DeepSeek OCR MCP service..."
docker build -f docker/Dockerfile.deepseek -t mcp-deepseek:latest .

echo "Building Qwen3-VL MCP service..."
docker build -f docker/Dockerfile.qwen -t mcp-qwen:latest .

echo "Building Marker MCP service..."
docker build -f docker/Dockerfile.marker -t mcp-marker:latest .

echo "Building Nanonets MCP service..."
docker build -f docker/Dockerfile.nanonets -t mcp-nanonets:latest .

echo "Building Chandra OCR MCP service..."
docker build -f docker/Dockerfile.chandra -t mcp-chandra:latest .

echo "Building Pipeline Runner..."
docker build -f docker/Dockerfile.pipeline -t medical-ocr-pipeline:latest .

echo ""
echo "Build Complete!"
echo "==============="
echo ""
echo "Available images:"
docker images | grep -E "(mcp-|medical-ocr-pipeline)"

echo ""
echo "To start services:"
echo "  docker-compose up -d"
echo ""
echo "To run pipeline:"
echo "  docker-compose exec pipeline-runner python scripts/run_pipeline.py"