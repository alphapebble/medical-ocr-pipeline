#!/bin/bash

# Start all MCP OCR services in parallel xterm windows
# This script opens each service in its own xterm window for monitoring

set -e

echo "Starting Medical OCR Pipeline - All Services"
echo "============================================="

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if xterm is available
if ! command -v xterm &> /dev/null; then
    echo "ERROR: xterm not found. Installing..."
    
    # Install xterm based on OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &> /dev/null; then
            echo "Installing xterm via Homebrew..."
            brew install xterm
        else
            echo "Please install Homebrew first: https://brew.sh/"
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "Installing xterm via apt/yum..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y xterm
        elif command -v yum &> /dev/null; then
            sudo yum install -y xterm
        else
            echo "Please install xterm manually"
            exit 1
        fi
    else
        echo "Unsupported OS. Please install xterm manually."
        exit 1
    fi
fi

# Function to start service in xterm
start_service_xterm() {
    local service_name="$1"
    local port="$2"
    local docker_service="$3"
    
    echo -e "${BLUE}Starting $service_name on port $port...${NC}"
    
    # Start in xterm with specific title and geometry
    xterm -T "MCP OCR - $service_name (Port $port)" \
          -geometry 100x30+$((200 + port - 8089))x$((100 + (port - 8089) * 50)) \
          -e "echo 'Starting $service_name...'; docker-compose up $docker_service; echo 'Service stopped. Press Enter to close.'; read" &
    
    # Give each service a moment to start
    sleep 2
}

# Function to start all services via docker-compose
start_all_docker_compose() {
    echo -e "${YELLOW}Starting all services via Docker Compose...${NC}"
    
    # Start all services in detached mode first
    docker-compose up -d
    
    # Then open monitoring windows
    xterm -T "Docker Compose - All Services" \
          -geometry 120x40+50+50 \
          -e "echo 'Monitoring all Docker services...'; docker-compose logs -f; echo 'Monitoring stopped. Press Enter to close.'; read" &
    
    # Health monitoring window
    sleep 5
    xterm -T "Health Monitor" \
          -geometry 100x30+800+50 \
          -e "echo 'Health monitoring...'; while true; do python scripts/health_check.py; echo '---'; sleep 30; done" &
}

# MCP services configuration
declare -A SERVICES=(
    ["tesseract"]="8089:mcp-tesseract"
    ["easyocr"]="8092:mcp-easyocr" 
    ["paddle"]="8090:mcp-paddle"
    ["surya"]="8091:mcp-surya"
    ["docling"]="8093:mcp-docling"
    ["doctr"]="8094:mcp-doctr"
    ["deepseek"]="8095:mcp-deepseek"
    ["qwen"]="8096:mcp-qwen"
    ["marker"]="8097:mcp-marker"
    ["nanonets"]="8098:mcp-nanonets"
    ["chandra"]="8099:mcp-chandra"
    ["olmo"]="8100:mcp-olmo"
    ["dots"]="8101:mcp-dots"
)

echo "Choose startup mode:"
echo "1) Individual xterm windows for each service (detailed monitoring)"
echo "2) Docker Compose with monitoring windows (recommended)"
echo "3) Background services only (no windows)"

read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo -e "${BLUE}Starting services in individual xterm windows...${NC}"
        
        # Start each service in its own xterm window
        for service in "${!SERVICES[@]}"; do
            IFS=':' read -r port docker_service <<< "${SERVICES[$service]}"
            start_service_xterm "$service" "$port" "$docker_service"
        done
        
        echo -e "${GREEN}All services starting in individual windows${NC}"
        ;;
        
    2)
        start_all_docker_compose
        echo -e "${GREEN}All services started with monitoring windows${NC}"
        ;;
        
    3)
        echo -e "${BLUE}Starting services in background...${NC}"
        docker-compose up -d
        echo -e "${GREEN}All services started in background${NC}"
        ;;
        
    *)
        echo "Invalid choice. Using Docker Compose mode..."
        start_all_docker_compose
        ;;
esac

# Wait a moment for services to initialize
echo -e "${YELLOW}Waiting for services to initialize...${NC}"
sleep 10

# Run health check
echo -e "${BLUE}Running health check...${NC}"
python scripts/health_check.py --wait 60

if [ $? -eq 0 ]; then
    echo -e "${GREEN}All services are healthy${NC}"
    echo -e "${BLUE}Ready to run pipeline notebooks${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Run: ./scripts/start_notebook_pipeline.sh"
    echo "2. Or manually open notebooks in order:"
    echo "   - notebooks/01_blocks_all_mcp_compare.ipynb"
    echo "   - notebooks/02_cleanup_blocks.ipynb"
    echo "   - notebooks/03_llm_cleanup.ipynb"
    echo "   - notebooks/04_json_extraction.ipynb"
    echo "   - notebooks/05_merge_and_validate.ipynb"
else
    echo -e "${YELLOW}Some services may not be ready yet${NC}"
    echo "Check the xterm windows for detailed logs"
fi

echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo "- Stop all: docker-compose down"
echo "- Health check: python scripts/health_check.py"
echo "- View logs: docker-compose logs -f [service-name]"
echo "- Restart service: docker-compose restart [service-name]"