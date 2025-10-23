# 🔧 Configuration Solutions

## Fixed Issues:

### 1. ✅ NANONETS_API_KEY Warning - SOLVED
- **Problem**: Warning about missing NANONETS_API_KEY
- **Solution**: 
  - Created `.env` file with `NANONETS_API_KEY=` (blank = disabled)
  - Updated docker-compose.yml to use `${NANONETS_API_KEY:-}` (default to empty)
  - Added profiles to exclude Nanonets from lightweight deployments

### 2. ✅ Docker Version Warning - SOLVED  
- **Problem**: `version` attribute is obsolete warning
- **Solution**: Removed `version: '3.8'` from docker-compose.yml

### 3. ✅ Service Selection - SOLVED
- **Problem**: Need to disable specific models
- **Solution**: Added Docker Compose profiles for selective deployment

## Deployment Profiles:

### 🚀 Lightweight Profile (Recommended to start)
```bash
docker-compose --profile lightweight up -d
```
**Includes**: Tesseract, EasyOCR, PaddleOCR (3 services)
**Resources**: Low CPU/RAM, fast startup
**No API keys required**

### 🧠 AI Models Profile  
```bash
docker-compose --profile ai-models up -d
```
**Includes**: DeepSeek-OCR, Qwen3-VL, olmOCR, dots.ocr (4 services)
**Resources**: GPU recommended

### 🔥 Full Profile
```bash
docker-compose --profile full up -d
```
**Includes**: All 13 engines
**Resources**: High CPU/GPU/RAM

## Next Steps:

1. **Start Docker Desktop** (the whale icon in menu bar)
2. **Run quick start**: `./scripts/quick_start.sh`
3. **Choose profile**: Start with "Lightweight" (option 1)
4. **Test services**: `python scripts/health_check.py`

## Configuration Files Created:

- ✅ `.env` - Environment variables (Nanonets disabled by default)
- ✅ `.env.example` - Template with all options
- ✅ `scripts/quick_start.sh` - Smart deployment script
- ✅ `QUICKSTART.md` - Complete setup guide

The system is now configured to work without any API keys and with selective model deployment! 🎯