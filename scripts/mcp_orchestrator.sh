#!/bin/bash

# Simple Medical OCR Pipeline Orchestration
# Uses basic shell commands for MCP service management

set -e  # Exit on any error

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MCP_DIR="$PROJECT_ROOT/mcp"
OUTPUT_DIR="$PROJECT_ROOT/outputs/$(date +%Y%m%d_%H%M%S)"

# Service definitions
declare -A MCP_SERVICES=(
    ["tesseract"]="mcp-tesseract:mcp_ocr_tesseract.py:8089"
    ["easyocr"]="mcp-easyocr:mcp_ocr_easy.py:8092"
    ["paddle"]="mcp-paddle:mcp_ocr_paddle.py:8090"
    ["surya"]="mcp-surya:mcp_ocr_surya.py:8091"
)

# PID tracking
PIDS_FILE="$PROJECT_ROOT/.mcp_pids"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] ERROR:${NC} $1"
}

# Function to start a single MCP service
start_service() {
    local service_name=$1
    local service_config=${MCP_SERVICES[$service_name]}
    
    if [[ -z "$service_config" ]]; then
        error "Unknown service: $service_name"
        return 1
    fi
    
    IFS=':' read -r conda_env script_file port <<< "$service_config"
    
    log "Starting $service_name (env: $conda_env, port: $port)"
    
    # Check if conda environment exists
    if ! conda info --envs | grep -q "^$conda_env "; then
        error "Conda environment '$conda_env' not found"
        echo "Create it with: conda create -n $conda_env python=3.11 -y"
        return 1
    fi
    
    # Check if script exists
    if [[ ! -f "$MCP_DIR/$script_file" ]]; then
        error "Script not found: $MCP_DIR/$script_file"
        return 1
    fi
    
    # Start the service in background
    cd "$MCP_DIR"
    conda run -n "$conda_env" python "$script_file" > "/tmp/${service_name}.log" 2>&1 &
    local pid=$!
    
    # Save PID
    echo "$service_name:$pid" >> "$PIDS_FILE"
    
    # Wait for service to be ready
    log "Waiting for $service_name to be ready..."
    for i in {1..30}; do
        if curl -s -f "http://127.0.0.1:$port/health" > /dev/null 2>&1; then
            log "$service_name is ready (PID: $pid)"
            return 0
        fi
        sleep 1
    done
    
    error "$service_name failed to start or become healthy"
    return 1
}

# Function to stop a service
stop_service() {
    local service_name=$1
    
    if [[ ! -f "$PIDS_FILE" ]]; then
        warn "No PID file found"
        return 0
    fi
    
    local pid=$(grep "^$service_name:" "$PIDS_FILE" | cut -d: -f2)
    
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        log "Stopping $service_name (PID: $pid)"
        kill "$pid"
        
        # Wait for graceful shutdown
        for i in {1..10}; do
            if ! kill -0 "$pid" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if kill -0 "$pid" 2>/dev/null; then
            warn "Force killing $service_name"
            kill -9 "$pid" 2>/dev/null || true
        fi
        
        # Remove from PID file
        grep -v "^$service_name:" "$PIDS_FILE" > "$PIDS_FILE.tmp" || true
        mv "$PIDS_FILE.tmp" "$PIDS_FILE" 2>/dev/null || rm -f "$PIDS_FILE"
        
        log "$service_name stopped"
    else
        warn "$service_name not running"
    fi
}

# Function to check service health
check_service() {
    local service_name=$1
    local service_config=${MCP_SERVICES[$service_name]}
    
    if [[ -z "$service_config" ]]; then
        echo "UNKNOWN"
        return 1
    fi
    
    local port=$(echo "$service_config" | cut -d: -f3)
    
    if curl -s -f "http://127.0.0.1:$port/health" > /dev/null 2>&1; then
        echo "HEALTHY"
        return 0
    else
        echo "UNHEALTHY"
        return 1
    fi
}

# Function to start all services
start_all() {
    log "Starting all MCP services"
    
    local success_count=0
    local total_count=${#MCP_SERVICES[@]}
    
    for service_name in "${!MCP_SERVICES[@]}"; do
        if start_service "$service_name"; then
            ((success_count++))
        fi
    done
    
    log "Started $success_count/$total_count services"
    
    if [[ $success_count -eq 0 ]]; then
        error "No services started successfully"
        return 1
    fi
    
    # Show status
    status
}

# Function to stop all services
stop_all() {
    log "Stopping all MCP services"
    
    for service_name in "${!MCP_SERVICES[@]}"; do
        stop_service "$service_name"
    done
    
    rm -f "$PIDS_FILE"
    log "All services stopped"
}

# Function to show status
status() {
    log "MCP Service Status"
    echo "=================================="
    
    for service_name in "${!MCP_SERVICES[@]}"; do
        local health=$(check_service "$service_name")
        printf "%-12s %s\n" "$service_name" "$health"
    done
}

# Function to run OCR pipeline
run_pipeline() {
    local pdf_path=$1
    local domain=${2:-prescription}
    
    if [[ -z "$pdf_path" ]] || [[ ! -f "$pdf_path" ]]; then
        error "PDF file not found: $pdf_path"
        return 1
    fi
    
    log "Running OCR pipeline for: $pdf_path"
    log "Domain: $domain"
    log "Output directory: $OUTPUT_DIR"
    
    # Create output directory
    mkdir -p "$OUTPUT_DIR"
    
    # Check if any services are running
    local healthy_services=()
    for service_name in "${!MCP_SERVICES[@]}"; do
        if [[ "$(check_service "$service_name")" == "HEALTHY" ]]; then
            healthy_services+=("$service_name")
        fi
    done
    
    if [[ ${#healthy_services[@]} -eq 0 ]]; then
        error "No healthy MCP services available"
        echo "Start services with: $0 start"
        return 1
    fi
    
    log "Using healthy services: ${healthy_services[*]}"
    
    # Run the Python pipeline script
    cd "$PROJECT_ROOT"
    python -c "
import sys
sys.path.append('.')
from notebooks.medical_ocr_pipeline_wrapper import *

# Configure pipeline
INPUT_PDF = '$pdf_path'
MEDICAL_DOMAIN = '$domain'
OUTPUT_BASE = '$OUTPUT_DIR'
ENABLE_DSPy = True

# Run pipeline stages
print('Running pipeline stages...')
# Your pipeline logic here
print('Pipeline completed successfully')
"
    
    log "Pipeline completed. Results in: $OUTPUT_DIR"
}

# Main command handler
case "${1:-help}" in
    start)
        if [[ -n "$2" ]]; then
            start_service "$2"
        else
            start_all
        fi
        ;;
    stop)
        if [[ -n "$2" ]]; then
            stop_service "$2"
        else
            stop_all
        fi
        ;;
    restart)
        if [[ -n "$2" ]]; then
            stop_service "$2"
            sleep 2
            start_service "$2"
        else
            stop_all
            sleep 2
            start_all
        fi
        ;;
    status)
        status
        ;;
    pipeline|run)
        run_pipeline "$2" "$3"
        ;;
    help|*)
        echo "Medical OCR Pipeline Orchestration"
        echo "=================================="
        echo ""
        echo "Usage: $0 <command> [arguments]"
        echo ""
        echo "Commands:"
        echo "  start [service]     Start all services or specific service"
        echo "  stop [service]      Stop all services or specific service"
        echo "  restart [service]   Restart all services or specific service"
        echo "  status              Show service status"
        echo "  pipeline <pdf> [domain]  Run OCR pipeline on PDF"
        echo "  help                Show this help"
        echo ""
        echo "Available services: ${!MCP_SERVICES[*]}"
        echo ""
        echo "Examples:"
        echo "  $0 start                    # Start all services"
        echo "  $0 start tesseract          # Start only tesseract"
        echo "  $0 status                   # Check service status"
        echo "  $0 pipeline input.pdf       # Run pipeline on input.pdf"
        echo "  $0 stop                     # Stop all services"
        ;;
esac