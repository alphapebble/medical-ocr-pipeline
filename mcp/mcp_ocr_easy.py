# mcp_ocr_easy.py
# MCP-compatible OCR server using FastAPI + EasyOCR
# Tweaked for Indic languages (hi, ta, te, etc.), mixed handwritten/typed text, and table/image handling.
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw
import io
import uvicorn
import numpy as np
import tempfile
import os
import time
import json

app = FastAPI(title="MCP OCR - EasyOCR", version="1.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Lazy init per langs/handwritten combo
_READERS = {}  # key: (str(langs), handwritten) -> reader

def get_reader(langs=["en"], handwritten=False):
    """Initialize EasyOCR reader (lazy loading) with languages and handwritten mode."""
    key = (str(langs), handwritten)
    if key in _READERS:
        return _READERS[key]
    
    try:
        import easyocr
        print(f"[INFO] Initializing EasyOCR with languages: {langs}, handwritten={handwritten}")
        # EasyOCR doesn't have explicit handwritten mode; uses same Reader (limited accuracy for handwritten Indic)
        if handwritten:
            print(f"[WARN] Handwritten mode for {langs}: Using standard model as fallback (limited accuracy)")
        reader = easyocr.Reader(langs, gpu=False)  # Set gpu=True if CUDA available
        _READERS[key] = reader
        print("[INFO] EasyOCR initialized successfully")
        return reader
    except ImportError as e:
        raise RuntimeError(f"EasyOCR not available. Install with: pip install easyocr. Error: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to initialize EasyOCR: {e}")

def parse_easy_output(results, img_w, img_h):
    """Parse EasyOCR results into line-level blocks, grouping nearby detections for better table/image handling."""
    blocks = []
    if not results:
        return blocks
    
    # results: [([polygon], text, confidence), ...]
    detections = []
    for item in results:
        if len(item) < 3:
            continue
        polygon, text, confidence = item
        text = text.strip()
        if not text:
            continue
        conf = float(confidence)
        if conf > 1.0:
            conf = conf / 100.0
        # Bbox from polygon
        xs = [float(p[0]) for p in polygon]
        ys = [float(p[1]) for p in polygon]
        x0, y0 = min(xs), min(ys)
        x1, y1 = max(xs), max(ys)
        bbox = [x0, y0, x1, y1]
        detections.append({'bbox': bbox, 'text': text, 'conf': conf})
    
    # Sort by y-coordinate for line grouping (helps with table rows)
    detections.sort(key=lambda x: x['bbox'][1])
    
    # Group into pseudo-lines (within 10px vertical tolerance) for mixed content
    current_line = []
    for det in detections:
        y0 = det['bbox'][1]
        if current_line and abs(y0 - current_line[-1]['y0']) <= 10:
            current_line.append(det)
        else:
            # Flush current line
            if current_line:
                # Aggregate line: avg conf, union bbox, joined text
                texts = [item['text'] for item in current_line]
                confs = [item['conf'] for item in current_line]
                all_bboxes = [item['bbox'] for item in current_line]
                union_x0 = min(b[0] for b in all_bboxes)
                union_y0 = min(b[1] for b in all_bboxes)
                union_x1 = max(b[2] for b in all_bboxes)
                union_y1 = max(b[3] for b in all_bboxes)
                blocks.append({
                    "text": " ".join(texts),
                    "confidence": sum(confs) / len(confs),
                    "bbox": [union_x0, union_y0, union_x1, union_y1]
                })
            current_line = [det]
            current_line[-1]['y0'] = y0  # Store for grouping
    
    # Flush last line
    if current_line:
        texts = [item['text'] for item in current_line]
        confs = [item['conf'] for item in current_line]
        all_bboxes = [item['bbox'] for item in current_line]
        union_x0 = min(b[0] for b in all_bboxes)
        union_y0 = min(b[1] for b in all_bboxes)
        union_x1 = max(b[2] for b in all_bboxes)
        union_y1 = max(b[3] for b in all_bboxes)
        blocks.append({
            "text": " ".join(texts),
            "confidence": sum(confs) / len(confs),
            "bbox": [union_x0, union_y0, union_x1, union_y1]
        })
    
    return sorted(blocks, key=lambda b: b['bbox'][1])  # Sort by y for reading order

@app.get("/health")
async def health():
    try:
        # Quick health check without initializing models
        import easyocr
        return {"ok": True, "engine": "easyocr", "version": "latest", "indic_supported": True}
    except Exception as e:
        return {"ok": False, "engine": "easyocr", "error": str(e)}

@app.get("/warmup")
async def warmup(lang: str = "en", handwritten: bool = False):
    """Warmup EasyOCR with a tiny synthetic image to cache models."""
    try:
        # Map common language codes to EasyOCR format
        lang_map = {
            "en": ["en"],
            "hi": ["hi", "en"],
            "te": ["te", "en"],
            "mr": ["mr", "en"],
            "ta": ["ta", "en"],
            "es": ["es"],
            "fr": ["fr"],
            "de": ["de"],
            "zh": ["ch_sim", "en"],
            "ja": ["ja", "en"],
            "ko": ["ko", "en"],
        }
        langs = lang_map.get(lang.lower(), ["en"])
        
        reader = get_reader(langs, handwritten)
        import time
        t0 = time.time()
        # Tiny image with sample text (for Indic, use placeholder)
        img = Image.new("RGB", (200, 100), "white")
        draw = ImageDraw.Draw(img)
        sample_text = "test" if lang == "en" else "नमस्ते"  # Hello in Hindi for Indic test
        draw.text((10, 40), sample_text, fill="black")
        arr = np.array(img)
        # Run OCR
        results = reader.readtext(arr)
        dt = time.time() - t0
        blocks = parse_easy_output(results, img.width, img.height)
        return {"ok": True, "seconds": round(dt, 2), "blocks": len(blocks), "lang": lang, "handwritten": handwritten}
    except Exception as e:
        import traceback
        return JSONResponse({"ok": False, "error": str(e), "traceback": traceback.format_exc()}, status_code=500)

@app.post("/ocr")
async def ocr(image: UploadFile, lang: str = Form("en"), handwritten: bool = Form(False)):
    """
    Perform OCR on uploaded image.
    
    Args:
        image: Uploaded image file
        lang: Language code (default: "en"; supports Indic: hi, ta, te, mr)
        handwritten: Enable handwritten mode (default: False; limited for Indic)
    
    Returns:
        JSON with blocks: [{"text", "confidence", "bbox":[x0,y0,x1,y1]}, ...]
    """
    # Map common language codes to EasyOCR format
    lang_map = {
        "en": ["en"],
        "hi": ["hi", "en"],
        "te": ["te", "en"],
        "mr": ["mr", "en"],
        "ta": ["ta", "en"],
        "es": ["es"],
        "fr": ["fr"],
        "de": ["de"],
        "zh": ["ch_sim", "en"],
        "ja": ["ja", "en"],
        "ko": ["ko", "en"],
    }
    langs = lang_map.get(lang.lower(), ["en"])
    
    try:
        reader = get_reader(langs, handwritten)
        data = await image.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        arr = np.array(img)
        
        # EasyOCR returns: [([[x1,y1],[x2,y2],[x3,y3],[x4,y4]], text, confidence), ...]
        results = reader.readtext(arr)
        
        blocks = parse_easy_output(results, img.width, img.height)
        
        return JSONResponse({
            "engine": "easyocr",
            "blocks": blocks,
            "meta": {"lang": lang, "handwritten": handwritten}
        })
        
    except Exception as e:
        import traceback
        return JSONResponse(
            {"engine": "easyocr", "blocks": [], "error": str(e), "traceback": traceback.format_exc()},
            status_code=500
        )

# Optional MCP mount
try:
    from fastmcp import FastMCP
    mcp = FastMCP.from_fastapi(app)
    app.mount("/mcp", mcp.http_app(path="/mcp"))
    print("[INFO] MCP mounted at /mcp (easyocr)")
except Exception as e:
    print("[WARN] MCP not enabled for easyocr:", e)

if __name__ == "__main__":
    import os
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8092"))
    print(f"[INFO] Starting EasyOCR server on {host}:{port}")
    print("[INFO] Supports Indic (hi/ta/te/etc.), handwritten (limited), tables/images via line grouping")

    # Optional warmup on start (set EASY_WARMUP_ON_START=1)
    if os.getenv("EASY_WARMUP_ON_START", "0") == "1":
        try:
            import requests
            from threading import Thread
            def _bg_warm():
                try:
                    # wait a bit for server to come up then warm
                    import time; time.sleep(1)
                    print("[WARMUP] hitting /warmup?lang=en&handwritten=false ...")
                    requests.get(f"http://{host}:{port}/warmup?lang=en&handwritten=false", timeout=300)
                    print("[WARMUP] done (English)")
                    print("[WARMUP] hitting /warmup?lang=hi&handwritten=true ...")
                    requests.get(f"http://{host}:{port}/warmup?lang=hi&handwritten=true", timeout=300)
                    print("[WARMUP] done (Indic Handwritten)")
                except Exception as e:
                    print(f"[WARMUP] failed: {e}")
            Thread(target=_bg_warm, daemon=True).start()
        except Exception as e:
            print(f"[WARMUP] not scheduled: {e}")

    uvicorn.run(app, host=host, port=port)