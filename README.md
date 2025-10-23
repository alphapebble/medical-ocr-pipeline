# Medical OCR Pipeline

A production-ready OCR pipeline for medical documents with containerized deployment and multiple orchestration options.

## Overview

This pipeline processes medical documents (PDFs, images) through multiple OCR engines and provides structured output:

1. **Multi-Engine OCR** - 11 OCR engines: Tesseract, EasyOCR, PaddleOCR, Surya, Docling, DocTR, DeepSeek-VL, Qwen3-VL, Marker, Nanonets, Chandra
2. **Domain Cleanup** - Medical terminology normalization
3. **LLM Enhancement** - Text cleaning and error correction  
4. **JSON Extraction** - Structured data extraction with schema validation
5. **Validation & Merge** - Final output validation

## Key Features

- **Docker-First Deployment** - Individual containers for each OCR service
- **Multiple Orchestration Options** - Shell scripts, Docker Compose, Prefect, Dagger
- **Multiple OCR Engines** - 11 engines including traditional (Tesseract, EasyOCR, PaddleOCR), modern (Surya, Docling, DocTR), vision-language models (DeepSeek-VL, Qwen3-VL), specialized tools (Marker, Nanonets, Chandra)
- **Medical Domain Specialization** - Prescription, radiology, pathology workflows
- **Service Isolation** - Each OCR engine runs in its own container/environment
- **Health Monitoring** - Built-in health checks and service monitoring

## Repository Structure

```
medical-ocr-pipeline/
├── docker/             # Docker configurations
│   ├── Dockerfile.tesseract   # Tesseract OCR container
│   ├── Dockerfile.easyocr     # EasyOCR container
│   ├── Dockerfile.paddle     # PaddleOCR container
│   ├── Dockerfile.surya      # Surya OCR container
│   ├── Dockerfile.docling    # Docling container
│   ├── Dockerfile.doctr      # DocTR container
│   ├── Dockerfile.deepseek   # DeepSeek-VL container
│   ├── Dockerfile.qwen       # Qwen3-VL container
│   ├── Dockerfile.marker     # Marker container
│   ├── Dockerfile.nanonets   # Nanonets container
│   ├── Dockerfile.chandra    # Chandra OCR container
│   ├── Dockerfile.pipeline   # Pipeline runner
│   └── requirements-*.txt    # Service dependencies
├── mcp/                # OCR service implementations
│   ├── mcp_ocr_tesseract.py
│   ├── mcp_ocr_easy.py
│   ├── mcp_ocr_paddle.py
│   ├── mcp_ocr_surya.py
│   ├── mcp_ocr_docling.py
│   ├── mcp_ocr_doctr.py
│   ├── mcp_ocr_deepseek.py
│   ├── mcp_ocr_qwen.py
│   ├── mcp_ocr_marker.py
│   ├── mcp_ocr_nanonets.py
│   └── mcp_ocr_chandra.py
├── scripts/            # Orchestration and setup
│   ├── mcp_orchestrator.sh      # Shell orchestrator
│   ├── build_docker_images.sh   # Docker build script
│   ├── validate_docker.sh       # Docker validation
│   └── setup_mcp_environments.sh
├── notebooks/          # Individual pipeline stages
│   ├── 01_blocks_all_mcp_compare.ipynb
│   ├── 02_cleanup_blocks.ipynb
│   ├── 03_llm_cleanup.ipynb
│   ├── 04_json_extraction.ipynb
│   └── 05_merge_and_validate.ipynb
├── config/             # Configuration files
│   ├── medical_terms.yml
│   ├── schema_prescription.json
│   └── schema_radiology.json
├── input_pdfs/         # Input documents
├── outputs/            # Pipeline outputs
├── docker-compose.yml  # Container orchestration
├── prefect_pipeline.py # Prefect workflow
└── dagger_pipeline.py  # Dagger workflow
```

## Quick Start

### API Keys Setup (Optional)

Some OCR engines require API keys:

1. **Copy environment template:**
```bash
cp .env.template .env
```

2. **Add your API keys to `.env`:**
```bash
# Nanonets OCR API Key (required for Nanonets engine)
NANONETS_API_KEY=your_nanonets_api_key_here

# Hugging Face token (optional, for DeepSeek/Qwen models)
HUGGING_FACE_HUB_TOKEN=your_huggingface_token_here
```

3. **Get API keys:**
   - **Nanonets:** Register at [nanonets.com](https://app.nanonets.com/) 
   - **Hugging Face:** Get token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)

### Docker Deployment (Recommended)

1. **Validate configuration:**
```bash
./scripts/validate_docker.sh
```

2. **Build Docker images:**
```bash
./scripts/build_docker_images.sh
```

3. **Start services:**
```bash
docker-compose up -d
```

4. **Wait for services to be ready:**
```bash
# Check health
docker-compose ps

# Monitor startup logs
docker-compose logs -f
```

5. **Run pipeline:**
```bash
# Copy PDF to input directory
cp your_document.pdf input_pdfs/

# Run pipeline
docker-compose exec pipeline-runner python scripts/run_pipeline.py
```

6. **Health checks:**
```bash
# Check all service health
python scripts/health_check.py

# Wait for services to be ready
python scripts/health_check.py --wait 120

# Custom timeout for health checks
python scripts/health_check.py --timeout 10
```

7. **Check results:**
```bash
ls -la outputs/
```

### Shell Script Orchestration (Alternative)

1. **Setup conda environments:**
```bash
./scripts/setup_mcp_environments.sh
```

2. **Start OCR services:**
```bash
./scripts/mcp_orchestrator.sh start
```

3. **Check service status:**
```bash
./scripts/mcp_orchestrator.sh status
```

4. **Run pipeline:**
```bash
./scripts/mcp_orchestrator.sh pipeline input_pdfs/document.pdf prescription
```

5. **Stop services:**
```bash
./scripts/mcp_orchestrator.sh stop
```

### 🌊 Prefect Orchestration (Advanced)

1. **Install Prefect:**
```bash
pip install prefect httpx
```

2. **Run pipeline:**
```bash
python prefect_pipeline.py input_pdfs/document.pdf prescription
```

## Prerequisites
- Python 3.11+
- Conda (for environment management)
- Docker & Docker Compose (optional)

## Pipeline Stages

### Stage 01: Multi-Engine OCR
- **Input:** PDF documents
- **Output:** Raw OCR blocks with confidence scores
- **Engines:** 11 OCR engines (see OCR Engines section below)
- **Features:** Parallel processing, confidence-based selection

### Stage 02: Domain Cleanup  
- **Input:** Raw OCR blocks
- **Output:** Cleaned text with medical term normalization
- **Features:** Medical dictionary, fuzzy matching, spaCy NER

### Stage 03: LLM Enhancement
- **Input:** Cleaned blocks
- **Output:** LLM-corrected text
- **Features:** Local Ollama models, batch processing

### Stage 04: JSON Extraction
- **Input:** Enhanced blocks
- **Output:** Structured JSON with schema validation
- **Features:** Schema-driven extraction, field mapping

### Stage 05: Validation & Merge
- **Input:** Extracted JSON
- **Output:** Final validated medical document structure
- **Features:** Cross-validation, completeness checking

## Medical Domains Supported

- **Prescription Documents:** Medication names, dosages, instructions
- **Radiology Reports:** Findings, impressions, measurements  
- **Pathology Reports:** Diagnoses, specimen details, results

## OCR Engines

The pipeline supports 11 different OCR engines, each with unique strengths:

### Traditional OCR Engines
- **Tesseract (Port 8089):** Google's OCR engine, excellent for clean text
- **EasyOCR (Port 8092):** Neural OCR with 80+ language support
- **PaddleOCR (Port 8090):** Baidu's OCR, strong on Chinese/Asian text

### Modern OCR Engines  
- **Surya (Port 8091):** Modern multilingual OCR with layout understanding
- **Docling (Port 8093):** IBM's document AI for complex layouts
- **DocTR (Port 8094):** PyTorch-based OCR with excellent accuracy

### Vision-Language Models
- **DeepSeek-VL (Port 8095):** Multimodal model with reasoning capabilities
- **Qwen3-VL (Port 8096):** Alibaba's vision-language model, 32-language support

### Specialized Tools
- **Marker (Port 8097):** Advanced document conversion to structured formats (Markdown/JSON/HTML) with layout preservation
- **Nanonets (Port 8098):** Cloud-based OCR API for documents/receipts/forms
- **Chandra (Port 8099):** Modern OCR engine with Tesseract fallback

### Engine Selection Strategy
- **Traditional documents:** Tesseract, EasyOCR
- **Complex layouts:** Docling, Surya, DocTR
- **Multilingual content:** Qwen3-VL, EasyOCR, PaddleOCR
- **Structured conversion:** Marker (for preserving document structure)
- **High accuracy OCR:** DeepSeek-VL, Nanonets
- **Fast processing:** Tesseract, Chandra (fallback mode)

## Architecture

### Shell Script Orchestration
```
mcp_orchestrator.sh
├── starts conda environments
├── launches MCP services
├── monitors health
├── runs pipeline stages
└── handles cleanup
```

### Service Mesh
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Tesseract   │    │  EasyOCR    │    │ PaddleOCR   │
│ :8089       │    │  :8092      │    │ :8090       │
└─────────────┘    └─────────────┘    └─────────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                  ┌─────────────┐
                  │ Orchestrator│
                  │ Pipeline    │
                  └─────────────┘
```

## Configuration

### Medical Terms (`config/medical_terms.yml`)
```yaml
terms:
  - "acetaminophen"
  - "ibuprofen"
  - "radiograph"
  # ... medical vocabulary
```

### Extraction Schema (`config/schema_prescription.json`)
```json
{
  "type": "object",
  "properties": {
    "patient_name": {"type": "string"},
    "medications": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "dosage": {"type": "string"}
        }
      }
    }
  }
}
```

## Development

### Adding New OCR Engines
1. Create MCP service: `mcp/mcp_ocr_newengine.py`
2. Add conda environment to setup script
3. Update orchestrator configuration
4. Test with health checks

### Adding New Medical Domains
1. Create schema: `config/schema_newdomain.json`
2. Add domain terms: `config/medical_terms.yml`
3. Update pipeline domain logic

## Troubleshooting

### Common Issues

**Services won't start:**
```bash
# Check conda environments
conda env list

# Recreate if needed
./scripts/setup_mcp_environments.sh
```

**Health checks fail:**
```bash
# Check logs
tail -f /tmp/tesseract.log

# Restart service
./scripts/mcp_orchestrator.sh restart tesseract
```

**Pipeline errors:**
```bash
# Check service status
./scripts/mcp_orchestrator.sh status

# Verify input file
ls -la input_pdfs/
```

### Performance Tuning

- **Parallel processing:** Adjust concurrent workers in orchestrator
- **Memory usage:** Tune conda environment resources
- **Accuracy vs speed:** Select appropriate OCR engines

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Submit pull request

## License

MIT License - see LICENSE file for details
- **Output:** Final validated output
- **Features:** Cross-validation, quality metrics

## 🔧 **Configuration**

### MCP Endpoints
```python
MCP_ENDPOINTS = {
    "tesseract": "http://127.0.0.1:8089/ocr",
    "easyocr": "http://127.0.0.1:8092/ocr", 
    "paddle": "http://127.0.0.1:8090/ocr",
    "surya": "http://127.0.0.1:8091/ocr",
    "docling": "http://127.0.0.1:8093/ocr"
}
```

### Chunkr Integration
```python
chunkr_base_url = "http://localhost:8000"
chunk_target_length = 512
chunk_overlap = 50
```

## 📈 **Performance**

- **Throughput:** ~2-5 pages/minute (depends on OCR engines)
- **Accuracy:** 95%+ on medical documents
- **Languages:** English, Hindi, Telugu, Marathi, Tamil

## 🧪 **Testing**

```bash
# Run unit tests
python -m pytest tests/

# Integration tests
jupyter nbconvert --execute notebooks/01_blocks_all_mcp_compare.ipynb
```

## 📚 **Documentation**

- [Chunkr Migration Plan](docs/CHUNKR_MIGRATION_PLAN.md)
- [MCP Server Setup](mcp/README.md)
- [Schema Documentation](config/README.md)

## 🤝 **Contributing**

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Submit pull request

## 📄 **License**

MIT License - see LICENSE file for details

## 🆘 **Support**

For issues and questions:
- Check existing issues
- Create new issue with detailed description
- Include sample documents (anonymized)