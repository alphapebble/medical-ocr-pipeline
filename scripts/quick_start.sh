#!/bin/bash

# Quick Start Script for Medical OCR Pipeline
# Handles Docker startup and provides deployment options

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Medical OCR Pipeline - Quick Start${NC}"
echo "====================================="

# Check if Docker is running
check_docker() {
    if ! docker info &> /dev/null; then
        echo -e "${RED}Docker is not running!${NC}"
        echo ""
        echo "Please start Docker Desktop and try again."
        echo ""
        echo "On macOS:"
        echo "  1. Open Docker Desktop app"
        echo "  2. Wait for it to start (whale icon in menu bar)"
        echo "  3. Run this script again"
        echo ""
        echo "On Linux:"
        echo "  sudo systemctl start docker"
        echo ""
        exit 1
    fi
    echo -e "${GREEN}Docker is running${NC}"
}

# Check if .env file exists
check_env() {
    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}Creating .env file from template...${NC}"
        cp .env.example .env
        echo -e "${GREEN}.env file created${NC}"
        echo ""
        echo "Note: Nanonets is disabled by default (no API key required)"
        echo "Edit .env file to enable more services or add API keys"
    fi
}

# Show deployment options
show_options() {
    echo ""
    echo "Choose deployment profile:"
    echo ""
    echo -e "${GREEN}1) Lightweight${NC} - Traditional OCR engines only (Tesseract, EasyOCR, PaddleOCR)"
    echo "   - Fast startup, low resource usage"
    echo "   - Good for basic document processing"
    echo ""
    echo -e "${BLUE}2) AI Models${NC} - Advanced AI engines only (DeepSeek, Qwen, olmOCR, dots.ocr)"
    echo "   - High accuracy, requires GPU/more RAM"
    echo "   - Best for complex medical documents"
    echo ""
    echo -e "${YELLOW}3) Full Pipeline${NC} - All 13 engines (requires significant resources)"
    echo "   - Maximum redundancy and accuracy"
    echo "   - Production deployment"
    echo ""
    echo -e "${RED}4) Custom${NC} - Edit docker-compose.yml manually"
    echo ""
}

# Main execution
main() {
    check_docker
    check_env
    show_options
    
    read -p "Enter choice (1-4): " choice
    
    case $choice in
        1)
            echo -e "${GREEN}Starting lightweight profile...${NC}"
            docker-compose --profile lightweight up -d
            ;;
        2)
            echo -e "${BLUE}Starting AI models profile...${NC}"
            docker-compose --profile ai-models up -d
            ;;
        3)
            echo -e "${YELLOW}Starting full pipeline...${NC}"
            docker-compose --profile full up -d
            ;;
        4)
            echo -e "${RED}Please edit docker-compose.yml and run:${NC}"
            echo "docker-compose up -d"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice. Please run the script again.${NC}"
            exit 1
            ;;
    esac
    
    echo ""
    echo -e "${GREEN}Services starting...${NC}"
    echo ""
    echo "Monitor status with:"
    echo "  docker-compose ps"
    echo "  python scripts/health_check.py"
    echo ""
    echo "View logs with:"
    echo "  docker-compose logs -f"
    echo ""
    echo "Stop services with:"
    echo "  docker-compose down"
}

main "$@"