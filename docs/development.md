# Development Setup

This document provides instructions for setting up the development environment for the medical OCR pipeline.

## Prerequisites

- Python 3.9+
- Docker and Docker Compose
- Git
- 8GB+ RAM (recommended)
- GPU support (optional, for better performance)

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd medical-ocr-pipeline
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start MCP servers**
   ```bash
   cd mcp
   docker compose up -d
   ```

4. **Verify setup**
   ```bash
   # Check server health
   curl http://localhost:8089/  # Tesseract
   curl http://localhost:8092/  # EasyOCR
   curl http://localhost:8090/  # PaddleOCR
   ```

5. **Run the pipeline**
   ```bash
   jupyter lab
   # Open notebooks/01_blocks_all_mcp_compare.ipynb
   ```

## Detailed Setup

### Python Environment

We recommend using a virtual environment:

```bash
# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### MCP Server Setup

#### Option 1: Docker Compose (Recommended)
```bash
cd mcp
docker compose up -d
```

#### Option 2: Individual Servers
```bash
# Tesseract
python mcp_ocr_tesseract.py

# EasyOCR (in separate terminal)
python mcp_ocr_easy.py

# PaddleOCR (in separate terminal)
python mcp_ocr_paddle.py
```

### Chunkr Setup (Optional)

For semantic enhancement capabilities:

```bash
# Run the setup script
./scripts/setup_local_chunkr.sh

# Verify Chunkr is running
curl http://localhost:8000/health
```

## Development Workflow

### 1. Data Preparation
- Place PDF files in `input_pdfs/`
- Ensure proper file naming conventions
- Check file formats and quality

### 2. Pipeline Execution
1. **Stage 1:** Extract blocks using `01_blocks_all_mcp_compare.ipynb`
2. **Stage 2:** Domain cleanup using `02_cleanup_blocks.ipynb`
3. **Stage 3:** LLM cleanup using `03_llm_cleanup.ipynb`
4. **Stage 3b:** Chunkr enhancement using `03b_chunkr_enhance.ipynb` (optional)
5. **Stage 4:** JSON extraction using `04_json_extraction.ipynb`
6. **Stage 5:** Merge and validate using `05_merge_and_validate.ipynb`

### 3. Testing
```bash
# Run unit tests
python -m pytest tests/

# Run specific test
python -m pytest tests/test_ocr_pipeline.py

# Run with coverage
python -m pytest --cov=src tests/
```

### 4. Code Quality
```bash
# Format code
black notebooks/ scripts/

# Lint code
flake8 notebooks/ scripts/

# Type checking
mypy scripts/
```

## Configuration

### Environment Variables
Create a `.env` file in the root directory:

```bash
# API Keys
OPENAI_API_KEY=your_openai_key

# OCR Settings
OCR_LANGUAGE=en
OCR_TIMEOUT=30

# Pipeline Settings
PIPELINE_MODE=parallel
OUTPUT_DIR=outputs/
```

### Configuration Files
- `config/config.yml`: Main pipeline configuration
- `config/medical_terms.yml`: Medical terminology mappings
- `config/schema_*.json`: Output validation schemas

## Troubleshooting

### Common Issues

1. **MCP servers not starting**
   ```bash
   # Check Docker status
   docker ps
   
   # Check logs
   docker compose logs tesseract
   ```

2. **Memory issues**
   ```bash
   # Reduce batch size in config
   # Use sequential processing instead of parallel
   ```

3. **Import errors**
   ```bash
   # Ensure virtual environment is activated
   # Reinstall dependencies
   pip install -r requirements.txt --force-reinstall
   ```

### Performance Optimization

1. **GPU Acceleration**
   - Install CUDA drivers
   - Use GPU-enabled Docker images
   - Configure EasyOCR and PaddleOCR for GPU

2. **Memory Management**
   - Process files in smaller batches
   - Use chunked processing for large documents
   - Clear cache between runs

3. **Parallel Processing**
   - Enable parallel OCR processing
   - Use multiple worker processes
   - Configure optimal batch sizes

## IDE Setup

### VS Code
Recommended extensions:
- Python
- Jupyter
- Docker
- YAML
- JSON

### JupyterLab
```bash
# Install JupyterLab
pip install jupyterlab

# Start JupyterLab
jupyter lab
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and add tests
4. Run quality checks
5. Submit a pull request

See `CONTRIBUTING.md` for detailed guidelines.