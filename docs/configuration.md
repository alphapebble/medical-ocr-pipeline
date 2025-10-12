# Pipeline Configuration

This document describes the configuration system for the medical OCR pipeline.

## Configuration Files

### 1. Main Configuration (`config/config.yml`)

Contains the main pipeline configuration including:
- OCR server endpoints
- Processing parameters
- Output settings
- Model configurations

Example structure:
```yaml
ocr:
  servers:
    - name: "tesseract"
      url: "http://localhost:8089"
      timeout: 30
    - name: "easyocr"
      url: "http://localhost:8092"
      timeout: 30

llm:
  model: "gpt-4"
  temperature: 0.1
  max_tokens: 2000

output:
  format: "json"
  validate_schema: true
  backup_enabled: true
```

### 2. Medical Terms Dictionary (`config/medical_terms.yml`)

Contains medical terminology mappings for text cleanup:
- Drug name standardization
- Medical abbreviations
- Common misspellings

### 3. Schema Definitions

#### Prescription Schema (`config/schema_prescription.json`)
Defines the expected structure for prescription documents:
- Patient information fields
- Medication details
- Dosage instructions
- Doctor information

#### Radiology Schema (`config/schema_radiology.json`)
Defines the expected structure for radiology reports:
- Patient demographics
- Study information
- Findings sections
- Impressions

## Environment Variables

The pipeline supports configuration via environment variables:

```bash
# OCR Settings
OCR_LANGUAGE=en           # Default OCR language
OCR_TIMEOUT=30           # Timeout for OCR requests
OCR_RETRY_COUNT=3        # Number of retry attempts

# LLM Settings
OPENAI_API_KEY=your_key  # OpenAI API key
LLM_MODEL=gpt-4         # Default LLM model
LLM_TEMPERATURE=0.1      # LLM temperature

# Pipeline Settings
PIPELINE_MODE=parallel   # parallel or sequential
CLEANUP_ENABLED=true     # Enable domain cleanup
VALIDATION_ENABLED=true  # Enable output validation

# Chunkr Settings
CHUNKR_API_URL=http://localhost:8000  # Local Chunkr instance
CHUNKR_ENABLED=false     # Enable Chunkr enhancement
CHUNKR_TIMEOUT=60        # Timeout for Chunkr requests
```

## Configuration Loading

The pipeline loads configuration in the following order (later values override earlier ones):

1. Default values (hardcoded)
2. `config/config.yml`
3. Environment variables
4. Runtime parameters (notebook cell parameters)

## Schema Validation

All configuration files are validated against their respective schemas on load. Invalid configurations will prevent pipeline execution.

## Best Practices

1. **Version Control:** Keep configuration files in version control
2. **Environment Separation:** Use different config files for dev/staging/prod
3. **Secrets Management:** Use environment variables for API keys
4. **Documentation:** Document all configuration changes
5. **Validation:** Test configuration changes before deployment