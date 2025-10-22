#!/bin/bash

# Simple MCP Environment Setup Script
# Creates conda environments for each MCP OCR server

echo "============================================"
echo "MCP OCR Server Environment Setup"
echo "============================================"
echo ""
echo "This script will create 4 conda environments:"
echo "  - mcp-tesseract (Traditional OCR)"
echo "  - mcp-easyocr   (Neural OCR)"
echo "  - mcp-paddle    (PaddleOCR)"
echo "  - mcp-surya     (Modern OCR)"
echo ""
echo "Each environment takes 5-15 minutes to create."
echo ""

read -p "Continue? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

echo "Starting environment creation..."
echo ""

# Function to create environment with error handling
create_env() {
    local env_name=$1
    local packages=$2
    
    echo "----------------------------------------"
    echo "Creating $env_name environment..."
    echo "----------------------------------------"
    
    # Create base environment
    echo "Creating conda environment..."
    conda create -n $env_name python=3.11 -y
    
    if [ $? -eq 0 ]; then
        echo "Installing packages..."
        conda run -n $env_name pip install $packages
        
        if [ $? -eq 0 ]; then
            echo "✓ $env_name environment created successfully"
        else
            echo "✗ Failed to install packages in $env_name"
        fi
    else
        echo "✗ Failed to create $env_name environment"
    fi
    echo ""
}

# Create each environment
create_env "mcp-tesseract" "pytesseract pillow fastapi uvicorn requests"
create_env "mcp-easyocr" "easyocr fastapi uvicorn requests pillow torch torchvision"
create_env "mcp-paddle" "paddlepaddle paddleocr fastapi uvicorn requests pillow"
create_env "mcp-surya" "surya-ocr fastapi uvicorn requests pillow torch transformers"

echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo ""
echo "Environments created:"
conda env list | grep mcp-

echo ""
echo "Next steps:"
echo "1. Open notebooks/00_mcp_server_management.ipynb"
echo "2. Run start_all_servers() to launch servers"
echo "3. Run check_servers() to verify they're working"
echo "4. Use the main pipeline: medical_ocr_pipeline_wrapper.ipynb"
echo ""