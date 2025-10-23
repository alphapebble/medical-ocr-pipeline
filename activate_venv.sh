#!/bin/bash
# Medical OCR Pipeline - Virtual Environment Activation Script

echo "[ISSUE] Medical OCR Pipeline - Virtual Environment Setup"
echo "=================================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "[FAST] Activating virtual environment..."
source venv/bin/activate

# Verify activation
echo "[SUCCESS] Virtual environment activated:"
echo "   Python: $(which python)"
echo "   Version: $(python --version)"

# Install basic requirements if needed
if [ ! -f "venv/requirements_installed.txt" ]; then
    echo "📥 Installing base requirements..."
    pip install --upgrade pip
    pip install fastapi uvicorn requests pillow numpy
    echo "$(date)" > venv/requirements_installed.txt
fi

echo ""
echo "[LAUNCH] Ready for development!"
echo "   Run: docker-compose up --profile lightweight"
echo "   Or:  docker-compose up --profile full"
echo ""