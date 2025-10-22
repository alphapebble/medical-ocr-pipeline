# Docker Deployment Guide

This document explains how to deploy the Medical OCR Pipeline using Docker containers.

## Architecture

The Docker deployment consists of 5 services:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Tesseract      │    │    EasyOCR      │    │   PaddleOCR     │    │     Surya       │
│  :8089          │    │    :8092        │    │   :8090         │    │     :8091       │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │
         └───────────────────────┼───────────────────────┼───────────────────────┘
                                 │                       │
                        ┌─────────────────┐    ┌─────────────────┐
                        │ Pipeline Runner │    │   Docker Net    │
                        │ (orchestrator)  │    │ medical-ocr-net │
                        └─────────────────┘    └─────────────────┘
```

## Individual Dockerfiles

### 1. Tesseract OCR Service (`docker/Dockerfile.tesseract`)
- **Base**: `python:3.11-slim`
- **OCR Engine**: Tesseract with English language pack
- **Port**: 8089
- **Dependencies**: pytesseract, fastapi, uvicorn

### 2. EasyOCR Service (`docker/Dockerfile.easyocr`)
- **Base**: `python:3.11-slim`
- **OCR Engine**: EasyOCR with neural networks
- **Port**: 8092
- **Dependencies**: easyocr, torch, torchvision
- **Startup time**: ~60 seconds (model downloads)

### 3. PaddleOCR Service (`docker/Dockerfile.paddle`)
- **Base**: `python:3.11-slim`
- **OCR Engine**: PaddleOCR
- **Port**: 8090
- **Dependencies**: paddlepaddle, paddleocr
- **Startup time**: ~60 seconds (model downloads)

### 4. Surya OCR Service (`docker/Dockerfile.surya`)
- **Base**: `python:3.11-slim`
- **OCR Engine**: Surya (transformer-based)
- **Port**: 8091
- **Dependencies**: surya-ocr, transformers, torch
- **Startup time**: ~120 seconds (large model downloads)

### 5. Pipeline Runner (`docker/Dockerfile.pipeline`)
- **Base**: `python:3.11-slim`
- **Purpose**: Orchestrates the OCR pipeline
- **Dependencies**: Full pipeline requirements
- **Volumes**: Input PDFs, outputs, configuration

## Quick Start

### 1. Build All Images
```bash
# Build all Docker images
./scripts/build_docker_images.sh
```

### 2. Start Services
```bash
# Start all services in background
docker-compose up -d

# Check service status
docker-compose ps
```

### 3. Wait for Services to be Ready
```bash
# Monitor logs
docker-compose logs -f

# Check health of individual services
curl http://localhost:8089/health  # Tesseract
curl http://localhost:8092/health  # EasyOCR
curl http://localhost:8090/health  # PaddleOCR
curl http://localhost:8091/health  # Surya
```

### 4. Run Pipeline
```bash
# Copy PDF to input directory
cp your_document.pdf input_pdfs/

# Run pipeline
docker-compose exec pipeline-runner python scripts/run_pipeline.py

# Or run interactively
docker-compose exec pipeline-runner bash
```

### 5. Check Results
```bash
# Results will be in outputs/ directory
ls -la outputs/
```

## Advanced Usage

### Build Individual Images
```bash
# Build only Tesseract service
docker build -f docker/Dockerfile.tesseract -t mcp-tesseract:latest .

# Build only EasyOCR service
docker build -f docker/Dockerfile.easyocr -t mcp-easyocr:latest .

# Build only PaddleOCR service
docker build -f docker/Dockerfile.paddle -t mcp-paddle:latest .

# Build only Surya service
docker build -f docker/Dockerfile.surya -t mcp-surya:latest .
```

### Run Individual Services
```bash
# Run only Tesseract
docker run -d -p 8089:8089 --name tesseract-ocr mcp-tesseract:latest

# Run only EasyOCR
docker run -d -p 8092:8092 --name easyocr-service mcp-easyocr:latest
```

### Scale Services
```bash
# Scale EasyOCR to 3 instances
docker-compose up -d --scale mcp-easyocr=3

# Use load balancer for high availability
# (requires additional nginx/haproxy configuration)
```

### Development Mode
```bash
# Mount source code for development
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

## Configuration

### Environment Variables

```bash
# MCP Service URLs
TESSERACT_URL=http://mcp-tesseract:8089
EASYOCR_URL=http://mcp-easyocr:8092
PADDLE_URL=http://mcp-paddle:8090
SURYA_URL=http://mcp-surya:8091

# Pipeline Settings
MEDICAL_DOMAIN=prescription  # prescription, radiology, pathology
OUTPUT_FORMAT=json          # json, csv
```

### Volume Mounts

```yaml
volumes:
  - ./input_pdfs:/app/input_pdfs      # Input documents
  - ./outputs:/app/outputs            # Pipeline results
  - ./config:/app/config              # Configuration files
```

## Troubleshooting

### Common Issues

**Services won't start:**
```bash
# Check logs
docker-compose logs mcp-tesseract

# Rebuild images
docker-compose build --no-cache
```

**Health checks fail:**
```bash
# Check individual service
docker-compose exec mcp-tesseract curl http://localhost:8089/health

# Restart service
docker-compose restart mcp-tesseract
```

**Out of memory errors:**
```bash
# Increase Docker memory limits
# Docker Desktop: Settings > Resources > Memory
# Or add to docker-compose.yml:
deploy:
  resources:
    limits:
      memory: 4G
```

**Model download issues:**
```bash
# EasyOCR/Surya models download on first run
# Check if internet access is available
docker-compose exec mcp-easyocr ping google.com

# Pre-download models
docker-compose exec mcp-easyocr python -c "import easyocr; easyocr.Reader(['en'])"
```

### Performance Tuning

**Resource Allocation:**
```yaml
# In docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 4G
    reservations:
      memory: 2G
```

**Parallel Processing:**
```bash
# Run multiple pipeline instances
docker-compose up -d --scale pipeline-runner=3
```

### Monitoring

**Health Checks:**
```bash
# Check all services
docker-compose ps

# Detailed health status
docker inspect $(docker-compose ps -q) | grep -A 5 Health
```

**Resource Usage:**
```bash
# Container stats
docker stats

# Disk usage
docker system df
```

## Production Deployment

### Security Considerations
- Use non-root users in containers
- Implement proper network segmentation
- Use secrets management for sensitive data
- Regular security updates

### High Availability
- Use Docker Swarm or Kubernetes
- Implement load balancing
- Set up health monitoring
- Configure auto-restart policies

### Backup and Recovery
- Regular backup of output data
- Version control for configurations
- Container image registry
- Disaster recovery procedures

## Integration

### With CI/CD
```yaml
# Example GitHub Actions
- name: Build and test
  run: |
    ./scripts/build_docker_images.sh
    docker-compose up -d
    # Run tests
    docker-compose down
```

### With Kubernetes
```yaml
# Convert docker-compose to k8s
kompose convert -f docker-compose.yml
```

### With Cloud Platforms
- **AWS ECS**: Use task definitions
- **Google Cloud Run**: Deploy individual services
- **Azure Container Instances**: Multi-container groups