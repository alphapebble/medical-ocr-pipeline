# 🚀 Quick Start Guide - Medical OCR Pipeline

## Prerequisites

1. **Docker Desktop** installed and running
2. **Git** for cloning the repository
3. **Python 3.8+** for health checks and utilities

## One-Command Setup

```bash
# Clone the repository
git clone https://github.com/alphapebble/medical-ocr-pipeline.git
cd medical-ocr-pipeline

# Run the quick start script
./scripts/quick_start.sh
```

This script will:
- ✅ Check if Docker is running
- ✅ Create `.env` configuration 
- ✅ Show deployment options
- ✅ Start selected services

## Deployment Options

### 🚀 Option 1: Lightweight (Recommended for Testing)

**Services**: Tesseract, EasyOCR, PaddleOCR
**Resources**: Low CPU/RAM, no GPU required
**Use case**: Basic document processing, development

```bash
docker-compose --profile lightweight up -d
```

### 🧠 Option 2: AI Models (High Performance)

**Services**: DeepSeek-OCR, Qwen3-VL, olmOCR, dots.ocr
**Resources**: GPU recommended, 8GB+ RAM
**Use case**: Complex medical documents, production quality

```bash
docker-compose --profile ai-models up -d
```

### 🔥 Option 3: Full Pipeline (Maximum Capability)

**Services**: All 13 OCR engines
**Resources**: GPU required, 16GB+ RAM
**Use case**: Production deployment, maximum redundancy

```bash
docker-compose --profile full up -d
```

## Service Configuration

### Environment Variables (.env file)

```bash
# Disable specific services
ENABLE_NANONETS=false          # Requires API key
ENABLE_QWEN=false              # Heavy GPU model
ENABLE_DEEPSEEK=false          # Heavy GPU model

# API Keys (optional)
NANONETS_API_KEY=your_key_here
```

### Docker Issues?

**Docker not running:**
```bash
# macOS: Open Docker Desktop app
# Linux: 
sudo systemctl start docker
```

**Permission issues:**
```bash
# Add user to docker group (Linux)
sudo usermod -a -G docker $USER
# Then logout and login again
```

## Health Monitoring

```bash
# Check all services
python scripts/health_check.py

# Check specific timeout
python scripts/health_check.py --timeout 5

# Monitor in real-time
watch -n 5 python scripts/health_check.py
```

## Service URLs

Once running, services are available at:

| Service | URL | Port |
|---------|-----|------|
| Tesseract | http://localhost:8089 | 8089 |
| PaddleOCR | http://localhost:8090 | 8090 |
| EasyOCR | http://localhost:8092 | 8092 |
| DeepSeek-OCR | http://localhost:8095 | 8095 |
| Qwen3-VL | http://localhost:8096 | 8096 |
| olmOCR | http://localhost:8100 | 8100 |
| dots.ocr | http://localhost:8101 | 8101 |

## Testing the Pipeline

```bash
# Test a single service
curl -X POST "http://localhost:8089/ocr" \
  -F "file=@test_image.jpg"

# Run full pipeline test
python notebooks/demo_all_ocr_engines.ipynb
```

## Troubleshooting

### Common Issues

1. **"NANONETS_API_KEY" variable not set**
   - Solution: Either add API key to `.env` or use profiles that exclude Nanonets

2. **Docker daemon not running**
   - Solution: Start Docker Desktop or `sudo systemctl start docker`

3. **Services not starting (out of memory)**
   - Solution: Use `--profile lightweight` or increase Docker memory limits

4. **Port conflicts**
   - Solution: Check if ports 8089-8101 are available: `lsof -i :8089`

### Performance Tips

- **For development**: Use `lightweight` profile
- **For production**: Use `full` profile with GPU support
- **Resource constrained**: Disable heavy models in `.env`

### Getting Help

```bash
# View service logs
docker-compose logs mcp-tesseract

# View all logs
docker-compose logs -f

# Restart specific service
docker-compose restart mcp-tesseract

# Complete cleanup
docker-compose down
docker system prune -f
```

## What's Next?

1. **Configure Services**: Edit `.env` for your needs
2. **Test Pipeline**: Run `python notebooks/demo_all_ocr_engines.ipynb`
3. **Process Documents**: Upload PDFs to `input_pdfs/` folder
4. **Monitor Performance**: Use health checks and logs

---

**Need more help?** Check the full documentation in `/docs/` or open an issue.