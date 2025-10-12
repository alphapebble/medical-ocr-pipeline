# Chunkr Integration Migration Plan

## 🚨 **IMPORTANT: Commit Current State First**

Before making any changes, commit your current working pipeline:

```bash
git add .
git commit -m "Working pipeline before Chunkr integration - baseline"
git push
```

## 📋 **Current Pipeline State (Preserve This!)**

```
01_blocks_all_mcp_compare.ipynb    → Multiple OCR engines (Tesseract, EasyOCR, Paddle, Surya)
02_cleanup_blocks.ipynb            → Domain cleanup + medical term normalization  
03_llm_cleanup.ipynb              → LLM-based text cleaning
04_json_extraction.ipynb          → Schema-based JSON extraction
05_merge_and_validate.ipynb       → Final merging and validation
```

## 🎯 **Proposed Changes (What Will Be Modified)**

### **Option A: Minimal Integration (Recommended for Testing)**

**Files to Modify:**
1. **03b_chunkr_enhance.ipynb** (NEW) - Add semantic enhancement step
2. **04_json_extraction.ipynb** (MODIFY) - Update input directory
3. **setup_local_chunkr.sh** (NEW) - Chunkr setup script

**Files to Keep Unchanged:**
- All existing notebooks (01, 02, 03, 05)
- All MCP servers in `/mcp/` directory
- Configuration files

### **Changes Required:**

#### **1. Add New Stage: 03b_chunkr_enhance.ipynb**
```python
# NEW NOTEBOOK - No existing code modified
blocks_dir = "outputs/run_001/03_llmcleaned"     # Input from existing pipeline
output_dir = "outputs/run_001/03b_chunkr_enhanced"  # New output directory
```

#### **2. Modify 04_json_extraction.ipynb**
**BEFORE:**
```python
# Current input discovery
search_order = ["03_llmcleaned", "02_cleaned", "01_blocks"]
```

**AFTER:**
```python
# Enhanced input discovery (backward compatible)
search_order = ["03b_chunkr_enhanced", "03_llmcleaned", "02_cleaned", "01_blocks"]
```

**File patterns to add:**
```python
patterns = [
    "page_*_blocks.chunkr.json",        # NEW: From Chunkr enhancement
    "page_*_blocks.llmcleaned.json",    # Existing
    "page_*_blocks.cleaned.json",       # Existing
    "page_*_blocks.json"                # Existing
]
```

## 🔄 **Migration Steps (Safe & Reversible)**

### **Step 1: Setup Chunkr (No Code Changes)**
```bash
# Run setup script (creates separate workspace)
./setup_local_chunkr.sh
```

### **Step 2: Test Chunkr Separately**
```bash
# Test with existing output files
cd chunkr_workspace/chunkr
curl -X POST http://localhost:8000/api/v1/task \
  -F "file=@../../outputs/run_001/sample.pdf"
```

### **Step 3: Add Enhancement Stage (Non-Breaking)**
```bash
# Copy the new notebook
cp 03b_chunkr_enhance.ipynb notebooks/
# Run it with existing data - creates NEW output directory
```

### **Step 4: Update JSON Extraction (Backward Compatible)**
```python
# In 04_json_extraction.ipynb, update search order only
# Falls back to existing directories if Chunkr enhanced files not found
```

## 🛡️ **Safety Measures**

### **1. Directory Structure (Before/After)**

**BEFORE:**
```
outputs/run_001/
├── 01_blocks/           # OCR blocks
├── 02_cleaned/          # Domain cleaned
├── 03_llmcleaned/      # LLM cleaned
└── 04_jsonextracted/   # JSON extracted
```

**AFTER:**
```
outputs/run_001/
├── 01_blocks/           # OCR blocks (unchanged)
├── 02_cleaned/          # Domain cleaned (unchanged)
├── 03_llmcleaned/      # LLM cleaned (unchanged)
├── 03b_chunkr_enhanced/ # NEW - Chunkr enhanced
└── 04_jsonextracted/   # JSON extracted (enhanced input)
```

### **2. Rollback Plan**
If Chunkr integration causes issues:

```bash
# Rollback code changes
git checkout HEAD~1 04_json_extraction.ipynb

# Remove Chunkr outputs (keep originals)
rm -rf outputs/run_001/03b_chunkr_enhanced/

# Stop Chunkr services
cd chunkr_workspace/chunkr
docker compose down

# Pipeline reverts to original behavior
```

### **3. A/B Testing Capability**
```python
# In 04_json_extraction.ipynb
use_chunkr_enhancement = True  # Toggle flag

if use_chunkr_enhancement:
    search_order = ["03b_chunkr_enhanced", "03_llmcleaned", ...]
else:
    search_order = ["03_llmcleaned", "02_cleaned", ...]
```

## 📊 **Impact Assessment**

### **Low Risk Changes:**
- ✅ New notebook (03b) - doesn't affect existing flow
- ✅ New output directory - doesn't overwrite existing data
- ✅ Backward-compatible file discovery in 04_json_extraction

### **Medium Risk Changes:**
- ⚠️ Modified 04_json_extraction.ipynb - test thoroughly
- ⚠️ New Docker services - may affect system resources

### **Zero Risk (No Changes):**
- ✅ All existing notebooks (01, 02, 03, 05)
- ✅ MCP servers and configurations
- ✅ Existing output data

## 🧪 **Testing Protocol**

### **1. Baseline Test (Before Changes)**
```bash
# Run complete pipeline on test document
jupyter nbconvert --execute 01_blocks_all_mcp_compare.ipynb
jupyter nbconvert --execute 02_cleanup_blocks.ipynb
jupyter nbconvert --execute 03_llm_cleanup.ipynb
jupyter nbconvert --execute 04_json_extraction.ipynb

# Save outputs as baseline
cp -r outputs/run_001/ outputs/baseline_before_chunkr/
```

### **2. Enhanced Test (After Changes)**
```bash
# Run with Chunkr enhancement
jupyter nbconvert --execute 03b_chunkr_enhance.ipynb
jupyter nbconvert --execute 04_json_extraction.ipynb

# Compare outputs
diff -r outputs/baseline_before_chunkr/04_jsonextracted/ \
        outputs/run_001/04_jsonextracted/
```

### **3. Quality Metrics**
```python
# Compare extraction quality
- Field extraction accuracy
- Schema validation errors  
- Processing time
- Semantic chunking quality
```

## 🎯 **Success Criteria**

### **Phase 1: Basic Integration**
- [ ] Chunkr processes existing documents without errors
- [ ] Enhanced blocks maintain backward compatibility
- [ ] JSON extraction works with both original and enhanced inputs

### **Phase 2: Quality Improvement**
- [ ] Better semantic chunking for medical documents
- [ ] Improved form field detection
- [ ] Enhanced table structure preservation

### **Phase 3: Production Ready**
- [ ] Processing time acceptable
- [ ] Error handling robust
- [ ] Documentation complete

## 🚀 **Next Steps**

1. **Commit current state**: `git commit -m "Pre-Chunkr baseline"`
2. **Setup Chunkr**: Run `./setup_local_chunkr.sh`
3. **Test separately**: Verify Chunkr works on sample documents
4. **Integrate gradually**: Add 03b notebook, test, then modify 04
5. **Compare results**: Baseline vs enhanced outputs
6. **Decide**: Keep, modify, or rollback based on results

---

**Remember: This is designed to be additive and reversible. Your existing pipeline remains intact and functional throughout the testing process.**