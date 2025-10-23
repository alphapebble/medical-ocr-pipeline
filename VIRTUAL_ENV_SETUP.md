# Virtual Environment Setup for Medical OCR Pipeline

## Quick Start
```bash
# Create and activate virtual environment
./activate_venv.sh

# Or manually:
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

## Virtual Environment Structure
```
medical-ocr-pipeline/
├── venv/                     # Virtual environment (gitignored)
│   ├── bin/python           # Isolated Python executable
│   ├── lib/python3.11/      # Isolated packages
│   └── requirements_installed.txt  # Installation marker
├── activate_venv.sh         # Automated setup script
└── docker/                  # Docker requirements (separate from venv)
    ├── requirements-*.txt   # Service-specific dependencies
    └── Dockerfile.*         # Containerized environments
```

## Dependency Management Strategy

### Virtual Environment (Development)
- Used for local development and testing
- Base packages: fastapi, uvicorn, requests, pillow, numpy
- Isolated from system Python and conda environments

### Docker Containers (Production)
- Each OCR service has its own container with specific dependencies
- Updated for compatibility with latest AI model requirements
- Pillow >=10.2.0, torch >=2.3.0 for modern AI engines

## Fixed Dependency Conflicts

### Core Issues Resolved:
1. **Pillow Version Conflicts**
   - marker-pdf required >=10.1.0
   - surya-ocr required >=10.2.0
   - Solution: Set Pillow>=10.2.0 across all services

2. **PyTorch Compatibility**
   - Old torch==2.1.0 incompatible with surya-ocr 0.17.0
   - surya-ocr requires torch>=2.3.0
   - Solution: Updated to torch>=2.3.0, torchvision>=0.18.0

3. **Package Availability**
   - docling-core 1.8.1 was not available
   - Solution: Updated to latest version 2.49.0

4. **System Dependencies**
   - libgl1-mesa-glx not available in newer Debian
   - Solution: Updated to libgl1-mesa-dev

## Testing Status (10/13 Services Verified)

### ✅ Working Services:
1. **Tesseract OCR** (Port 8089) - Basic OCR with 100+ languages
2. **PaddleOCR** (Port 8090) - 109 languages, lightweight
3. **EasyOCR** (Port 8092) - 80+ languages, neural networks
4. **Surya OCR** (Port 8091) - v0.17.0, layout analysis + OCR ✨ FIXED
5. **Nanonets** (Port 8097) - Commercial API, medical specialization
6. **Chandra** (Port 8098) - Latest open-source OCR
7. **dots.ocr** (Port 8099) - 3B parameter model
8. **olmOCR** (Port 8100) - 2.7B specialized OCR model
9. **Marker PDF** (Port 8096) - PDF-to-markdown conversion ✨ FIXED
10. **DeepSeek-OCR** (Port 8095) - 3B parameter vision model ✨ FIXED

### 🔄 Remaining Services (Build Complete, Testing Pending):
11. **Docling** (Port 8093) - IBM's document processing (dependencies fixed)
12. **DocTR** (Port 8094) - Document text recognition (system deps pending)
13. **Qwen3-VL** (Port 8101) - 32B multimodal model (dependencies updated)

## Environment Variables
```bash
# Core service configuration
export HOST=0.0.0.0
export PORT=8089-8101

# API keys (optional, for services that need them)
export NANONETS_API_KEY=your_key_here

# Model caching
export HF_HOME=/app/.cache/huggingface
export TRANSFORMERS_CACHE=/app/.cache/huggingface
```

## Next Steps
1. Resolve Docker daemon filesystem issue
2. Complete testing of remaining 4 services
3. Deploy full 13-service stack with `docker-compose up --profile full`
4. Validate end-to-end medical document processing pipeline

## Usage Patterns
```bash
# Development with virtual environment
source venv/bin/activate
python scripts/test_local_ocr.py

# Production deployment
docker-compose up --profile lightweight  # 3 services
docker-compose up --profile ai-models    # 7 services  
docker-compose up --profile full         # All 13 services
```