# Docker Configuration

This directory contains all Docker-related configurations for the Medical OCR Pipeline.

## Files Overview

### Dockerfiles

| File | Purpose | Base Image | Port | OCR Engine |
|------|---------|------------|------|------------|
| `Dockerfile.tesseract` | Traditional OCR service | python:3.11-slim | 8089 | Tesseract |
| `Dockerfile.easyocr` | Neural network OCR | python:3.11-slim | 8092 | EasyOCR |
| `Dockerfile.paddle` | Deep learning OCR | python:3.11-slim | 8090 | PaddleOCR |
| `Dockerfile.surya` | Transformer-based OCR | python:3.11-slim | 8091 | Surya |
| `Dockerfile.pipeline` | Pipeline orchestrator | python:3.11-slim | - | All engines |

### Requirements Files

| File | Description | Key Dependencies |
|------|-------------|------------------|
| `requirements-tesseract.txt` | Tesseract service deps | pytesseract, fastapi, uvicorn |
| `requirements-easyocr.txt` | EasyOCR service deps | easyocr, torch, torchvision |
| `requirements-paddle.txt` | PaddleOCR service deps | paddlepaddle, paddleocr |
| `requirements-surya.txt` | Surya service deps | surya-ocr, transformers |

## Container Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Medical OCR Network                          │
├─────────────────┬─────────────────┬─────────────────┬───────────┤
│  Tesseract      │    EasyOCR      │   PaddleOCR     │   Surya   │
│  Container      │    Container    │   Container     │ Container │
│  Port: 8089     │    Port: 8092   │   Port: 8090    │Port: 8091 │
│                 │                 │                 │           │
│ ┌─────────────┐ │ ┌─────────────┐ │ ┌─────────────┐ │┌─────────┐│
│ │   FastAPI   │ │ │   FastAPI   │ │ │   FastAPI   │ ││ FastAPI ││
│ │   Server    │ │ │   Server    │ │ │   Server    │ ││ Server  ││
│ └─────────────┘ │ └─────────────┘ │ └─────────────┘ │└─────────┘│
│ ┌─────────────┐ │ ┌─────────────┐ │ ┌─────────────┐ │┌─────────┐│
│ │ Tesseract   │ │ │  EasyOCR    │ │ │ PaddleOCR   │ ││  Surya  ││
│ │   Engine    │ │ │   Engine    │ │ │   Engine    │ ││ Engine  ││
│ └─────────────┘ │ └─────────────┘ │ └─────────────┘ │└─────────┘│
└─────────────────┴─────────────────┴─────────────────┴───────────┘
                                │
                ┌─────────────────────────────────┐
                │      Pipeline Runner            │
                │      Container                  │
                │                                 │
                │  ┌─────────────────────────────┐│
                │  │   Orchestration Logic       ││
                │  │   - Document processing     ││
                │  │   - OCR service calls       ││
                │  │   - Result aggregation      ││
                │  └─────────────────────────────┘│
                └─────────────────────────────────┘
```

## Service Details

### Tesseract Container (`Dockerfile.tesseract`)

**Purpose**: Fast, traditional OCR for clear text documents

**System Dependencies**:
- `tesseract-ocr` - Core OCR engine
- `tesseract-ocr-eng` - English language pack
- `libtesseract-dev` - Development headers
- `curl` - Health check support

**Python Dependencies** (from `requirements-tesseract.txt`):
- `pytesseract` - Python wrapper for Tesseract
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `pillow` - Image processing

**Startup Time**: ~10 seconds
**Resource Usage**: Low CPU/Memory

### EasyOCR Container (`Dockerfile.easyocr`)

**Purpose**: Neural network-based OCR for complex layouts

**System Dependencies**:
- `libglib2.0-0` - System library for GUI applications
- `curl` - Health check support

**Python Dependencies** (from `requirements-easyocr.txt`):
- `easyocr` - Neural OCR engine
- `torch` - PyTorch framework
- `torchvision` - Computer vision utilities
- `fastapi` - Web framework
- `uvicorn` - ASGI server

**Model Storage**: `/root/.EasyOCR/`
**Startup Time**: ~60 seconds (model download)
**Resource Usage**: Medium GPU/CPU

### PaddleOCR Container (`Dockerfile.paddle`)

**Purpose**: Production-grade deep learning OCR

**System Dependencies**:
- `curl` - Health check support

**Python Dependencies** (from `requirements-paddle.txt`):
- `paddlepaddle` - PaddlePaddle framework
- `paddleocr` - PaddleOCR engine
- `fastapi` - Web framework
- `uvicorn` - ASGI server

**Startup Time**: ~60 seconds (model download)
**Resource Usage**: Medium GPU/CPU

### Surya Container (`Dockerfile.surya`)

**Purpose**: State-of-the-art transformer-based OCR

**System Dependencies**:
- `curl` - Health check support

**Python Dependencies** (from `requirements-surya.txt`):
- `surya-ocr` - Surya OCR engine
- `transformers` - Hugging Face transformers
- `torch` - PyTorch framework
- `fastapi` - Web framework
- `uvicorn` - ASGI server

**Startup Time**: ~120 seconds (large model download)
**Resource Usage**: High GPU/Memory

### Pipeline Runner Container (`Dockerfile.pipeline`)

**Purpose**: Orchestrates the complete OCR pipeline

**Python Dependencies** (from project `requirements.txt`):
- All pipeline dependencies
- HTTP client libraries for service communication
- Data processing libraries

**Environment Variables**:
- `TESSERACT_URL=http://mcp-tesseract:8089`
- `EASYOCR_URL=http://mcp-easyocr:8092`
- `PADDLE_URL=http://mcp-paddle:8090`
- `SURYA_URL=http://mcp-surya:8091`

## Health Checks

All OCR service containers include health check endpoints:

```bash
# Check individual services
curl http://localhost:8089/health  # Tesseract
curl http://localhost:8092/health  # EasyOCR
curl http://localhost:8090/health  # PaddleOCR
curl http://localhost:8091/health  # Surya
```

Health checks verify:
- Service is responsive
- OCR engine is loaded
- Required models are available

## Build Process

### Individual Builds
```bash
# From project root
docker build -f docker/Dockerfile.tesseract -t mcp-tesseract:latest .
docker build -f docker/Dockerfile.easyocr -t mcp-easyocr:latest .
docker build -f docker/Dockerfile.paddle -t mcp-paddle:latest .
docker build -f docker/Dockerfile.surya -t mcp-surya:latest .
docker build -f docker/Dockerfile.pipeline -t medical-ocr-pipeline:latest .
```

### Automated Build
```bash
# Use the build script
./scripts/build_docker_images.sh
```

## Volume Mounts

### For OCR Services
- No persistent volumes needed (stateless services)
- Models downloaded and cached in containers

### For Pipeline Runner
```yaml
volumes:
  - ./input_pdfs:/app/input_pdfs      # Input documents
  - ./outputs:/app/outputs            # Pipeline results  
  - ./config:/app/config              # Configuration files
```

## Network Configuration

All containers run on the `medical-ocr-network` Docker network:
- Internal communication between services
- External access only through exposed ports
- Service discovery by container name

## Resource Recommendations

### Minimum System Requirements
- **CPU**: 4 cores
- **RAM**: 8GB
- **Storage**: 10GB free space
- **Docker**: 4GB memory limit

### Production Requirements
- **CPU**: 8+ cores
- **RAM**: 16GB+
- **GPU**: Optional but recommended for neural services
- **Storage**: 20GB+ free space

### Container Resource Limits
```yaml
# Example docker-compose resource limits
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 4G
    reservations:
      memory: 2G
```

## Troubleshooting

### Common Issues

**Build Failures**:
- Ensure Docker is running
- Check disk space
- Verify internet connectivity for package downloads

**Runtime Issues**:
- Check container logs: `docker-compose logs <service>`
- Verify health endpoints
- Monitor resource usage: `docker stats`

**Model Download Issues**:
- EasyOCR and Surya download models on first run
- Ensure internet connectivity
- Allow extra startup time (60-120 seconds)

### Debug Commands
```bash
# Check all containers
docker-compose ps

# View logs
docker-compose logs -f mcp-tesseract

# Enter container for debugging
docker-compose exec mcp-tesseract bash

# Check resource usage
docker stats

# Validate configuration
../scripts/validate_docker.sh
```