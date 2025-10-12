# MCP Servers

Model Context Protocol servers for OCR processing.

## Available Servers

### 1. Tesseract MCP (`mcp_ocr_tesseract.py`)
- **Port:** 8089
- **Engine:** Tesseract OCR
- **Features:** Multi-language support, configurable parameters

### 2. EasyOCR MCP (`mcp_ocr_easy.py`)
- **Port:** 8092
- **Engine:** EasyOCR
- **Features:** GPU acceleration, 80+ languages

### 3. PaddleOCR MCP (`mcp_ocr_paddle.py`)
- **Port:** 8090
- **Engine:** PaddleOCR
- **Features:** Chinese text support, table detection

### 4. Surya MCP (`mcp_ocr_surya.py`)
- **Port:** 8091
- **Engine:** Surya OCR
- **Features:** Layout analysis, reading order

### 5. Docling MCP (`mcp_ocr_docling.py`)
- **Port:** 8093
- **Engine:** Docling
- **Features:** Document structure analysis

## Setup

### Docker Compose (Recommended)
```bash
cd mcp
docker compose up -d
```

### Individual Servers
```bash
# Tesseract
python mcp_ocr_tesseract.py

# EasyOCR
python mcp_ocr_easy.py

# PaddleOCR
python mcp_ocr_paddle.py

# Surya
python mcp_ocr_surya.py

# Docling
python mcp_ocr_docling.py
```

## API Contract

All servers implement the same API contract:

### Endpoint: `POST /ocr`

**Request:**
```
Content-Type: multipart/form-data

image: <file>
lang: <language_code>  # e.g., 'en', 'hi', 'te'
```

**Response:**
```json
{
  "engine": "engine_name",
  "blocks": [
    {
      "text": "extracted text",
      "confidence": 0.95,
      "bbox": [x0, y0, x1, y1]
    }
  ],
  "meta": {
    "processing_time_s": 1.23,
    "language": "en",
    "total_blocks": 10
  }
}
```

## Health Check

Each server provides a health check endpoint:

```bash
curl http://localhost:8089/  # Tesseract
curl http://localhost:8092/  # EasyOCR
curl http://localhost:8090/  # PaddleOCR
curl http://localhost:8091/  # Surya
curl http://localhost:8093/  # Docling
```

## Configuration

Environment variables for each server:

```bash
# Tesseract
TESSERACT_TIMEOUT_S=30
TESSERACT_DPI=300

# EasyOCR
EASYOCR_GPU=true
EASYOCR_BATCH_SIZE=1

# PaddleOCR
PADDLE_USE_GPU=true
PADDLE_LANG=en

# Surya
SURYA_MODEL_PATH=/models
SURYA_BATCH_SIZE=4

# Docling
DOCLING_MODEL=granite_docling
DOCLING_PIPELINE=vlm
```