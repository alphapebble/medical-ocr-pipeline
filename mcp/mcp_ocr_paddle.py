# mcp_ocr_paddle.py
# MCP-compatible OCR server using FastAPI + PaddleOCR.
# Returns line-level boxes with confidences via /ocr; MCP is mounted at /mcp if fastmcp is available.
# Enhanced for Indic languages (hi, ta, te, etc.), mixed handwritten/typed text, and table/image handling.
# Fixes deprecation (use_textline_orientation, predict() over ocr()), input fallbacks, and scan optimizations.
# Mac ARM stability: OMP_NUM_THREADS=1, explicit models, keyword input for 3.2.0.
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
import traceback
import warnings

# Suppress deprecation warnings for clean logs
warnings.filterwarnings("ignore", message="use_angle_cls")

# Mac ARM stability: Limit threads to 1 (avoids OpenBLAS multi-thread crashes)
os.environ['OMP_NUM_THREADS'] = '1'

app = FastAPI(title="MCP OCR - PaddleOCR", version="1.2.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Lazy init per lang/handwritten combo
_MODELS = {}  # key: (lang, handwritten) -> model

def get_ocr(lang="en", handwritten=False):
    """Initialize PaddleOCR with the specified language and handwritten mode."""
    key = (lang, handwritten)
    if key in _MODELS:
        return _MODELS[key]
    
    try:
        from paddleocr import PaddleOCR
        import paddleocr  # For version check
        version = paddleocr.__version__
    except ImportError as e:
        raise RuntimeError(f"PaddleOCR not available. Install with: pip install paddleocr. Error: {e}")
    
    # Safe kwargs across versions
    import inspect
    params = set(inspect.signature(PaddleOCR).parameters.keys())
    kw = {
        "lang": lang,
    }
    
    # GPU: Only add if supported (removed in some 3.x versions)
    if "use_gpu" in params:
        kw["use_gpu"] = False   # Set to True if you have CUDA setup
    
    # Text orientation: Prioritize new param (replaces deprecated use_angle_cls)
    if "use_textline_orientation" in params:
        kw["use_textline_orientation"] = True
    elif "use_angle_cls" in params:
        kw["use_angle_cls"] = True  # Legacy fallback for older versions
    
    # 3.x/2025: Use PP-OCRv5 mobile for speed/accuracy (better Indic/handwritten)
    det_model = "PP-OCRv5_mobile_det"
    rec_model = "en_PP-OCRv5_mobile_rec" if lang == "en" else f"{lang}_PP-OCRv5_mobile_rec"
    
    if handwritten:
        # For handwritten: Use printed fallback (v5 improves cursive somewhat)
        print(f"[WARN] Handwritten mode for {lang}: Using printed model as fallback (limited accuracy)")
    
    # Use model_name params for 3.x stability (prevents loading crashes)
    if "det_model_name" in params:
        kw["det_model_name"] = det_model
    if "rec_model_name" in params:
        kw["rec_model_name"] = rec_model
    
    # Enhance for mixed tables/images: Enable layout analysis if available (helps with table regions)
    if "use_doc_orientation_classify" in params:
        kw.update(
            use_doc_orientation_classify=True,  # Better for mixed orientations in tables/images
            use_doc_unwarping=True,             # Unwarp skewed text in scanned docs/tables
            use_textline_orientation=True       # Handle vertical/horizontal in tables
        )
    
    print(f"[INFO] Initializing PaddleOCR v{version} with lang={lang}, handwritten={handwritten}, det={det_model}, rec={rec_model}")
    model = PaddleOCR(**kw)
    _MODELS[key] = model
    print(f"[INFO] PaddleOCR initialized successfully for {key}")
    return model

def parse_paddle_output(res, img_w, img_h):
    """Parse PaddleOCR results into line-level blocks, grouping nearby detections for better table/image handling."""
    blocks = []
    if not res:
        return blocks
    
    # Flatten batches: res is list of lists [[poly, (text, conf)], ...]
    detections = []
    if isinstance(res, list):
        for batch in res:
            if isinstance(batch, list):
                detections.extend(batch)
    
    # Sort by min y-coordinate for line grouping (helps with table rows)
    detections.sort(key=lambda det: min(float(p[1]) for p in det[0]) if det and det[0] and len(det[0]) > 0 else float('inf'))
    
    # Group into pseudo-lines (within 10px vertical tolerance) for mixed content
    current_line = []
    for det in detections:
        if not det or len(det) < 2:
            continue
        poly, rec = det[0], det[1]
        if not poly or not rec:
            continue
        txt = (rec[0] or "").strip()
        conf = float(rec[1]) if len(rec) > 1 else 1.0
        if not txt:
            continue
        
        # Bbox from poly
        xs = [float(p[0]) for p in poly]
        ys = [float(p[1]) for p in poly]
        x0, y0 = min(xs), min(ys)
        x1, y1 = max(xs), max(ys)
        bbox = [x0, y0, x1, y1]
        
        # Group if close vertically (tolerance for table cells/images)
        if current_line and abs(y0 - current_line[-1]['bbox'][1]) <= 10:
            current_line.append({'bbox': bbox, 'text': txt, 'conf': conf})
        else:
            # Flush current line
            if current_line:
                # Sort by x for left-to-right order within line (better for tables)
                current_line.sort(key=lambda item: item['bbox'][0])
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
            current_line = [{'bbox': bbox, 'text': txt, 'conf': conf}]
    
    # Flush last line
    if current_line:
        # Sort by x for left-to-right order within line (better for tables)
        current_line.sort(key=lambda item: item['bbox'][0])
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
        _ = get_ocr("en")
        _ = get_ocr("hi")  # Test Indic (lazy, won't crash if not called)
        return {"ok": True, "engine": "paddleocr", "version": "PP-OCRv5", "indic_supported": True}
    except Exception as e:
        return {"ok": False, "engine": "paddleocr", "error": str(e)}

@app.get("/warmup")
async def warmup(lang: str = "en", handwritten: bool = False):
    """Warmup PaddleOCR with a tiny synthetic image to cache models."""
    try:
        ocr_engine = get_ocr(lang, handwritten)
        import time
        t0 = time.time()
        # Tiny image with sample text
        img = Image.new("RGB", (200, 100), "white")
        draw = ImageDraw.Draw(img)
        sample_text = "test"
        draw.text((10, 40), sample_text, fill="black")
        arr = np.array(img)
        # 3.2.0: Use predict(input=arr) explicitly for numpy (positional may fail in some envs)
        try:
            res = ocr_engine.predict(input=arr)
        except (AttributeError, TypeError):
            # Fallback to ocr(input=arr) if predict not available
            try:
                res = ocr_engine.ocr(input=arr)
            except TypeError:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                    temp_path = tf.name
                    img.save(temp_path)
                try:
                    res = ocr_engine.predict(input=temp_path) if hasattr(ocr_engine, 'predict') else ocr_engine.ocr(input=temp_path)
                finally:
                    os.unlink(temp_path)
        dt = time.time() - t0
        blocks = parse_paddle_output(res, img.width, img.height)
        return {"ok": True, "seconds": round(dt, 2), "blocks": len(blocks), "lang": lang, "handwritten": handwritten}
    except Exception as e:
        import traceback
        return JSONResponse({"ok": False, "error": str(e), "traceback": traceback.format_exc()}, status_code=500)

@app.post("/ocr")
async def ocr(image: UploadFile, lang: str = Form("en"), handwritten: bool = Form(False)):
    """
    Perform OCR on an uploaded image.
    
    Args:
        image: Uploaded image file
        lang: Language code (default: "en"; supports Indic: hi, ta, te, mr, ka, ml)
        handwritten: Enable handwritten mode (default: False; limited for Indic)
    
    Returns:
        JSON with engine, blocks (text, confidence, bbox), and optional error
    """
    try:
        ocr_engine = get_ocr(lang, handwritten)
    except Exception as e:
        return JSONResponse(
            {"blocks": [], "engine": "paddleocr", "error": str(e)},
            status_code=500
        )
    
    try:
        data = await image.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        arr = np.array(img)
        
        # 3.2.0: Use predict(input=arr) explicitly for numpy (positional may fail in some envs)
        try:
            # Try direct array input first
            res = ocr_engine.ocr(arr)
        except (AttributeError, TypeError) as te:
            if "str or Path" in str(te) or any(x in str(te).lower() for x in ["path", "file"]):
                # Fallback: save to temp path (enhanced for scans)
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                    temp_path = tf.name
                    img.save(temp_path, 'JPEG', quality=95, dpi=(300, 300))  # High-res for scans
                try:
                    res = ocr_engine.ocr(temp_path)
                finally:
                    os.unlink(temp_path)
            else:
                raise te
    except Exception as e:
        import traceback
        return JSONResponse(
            {"blocks": [], "engine": "paddleocr", "error": str(e), "traceback": traceback.format_exc()},
            status_code=500
        )
    
    # Parse results with grouping for tables/images
    blocks = parse_paddle_output(res, img.width, img.height)
    
    return JSONResponse({
        "engine": "paddleocr",
        "blocks": blocks,
        "meta": {"lang": lang, "handwritten": handwritten}
    })


# Optional MCP mount
try:
    from fastmcp import FastMCP
    mcp = FastMCP.from_fastapi(app)
    app.mount("/mcp", mcp.http_app(path="/mcp"))
    print("[INFO] MCP mounted at /mcp (paddle)")
except Exception as e:
    print("[WARN] MCP not enabled for paddle:", e)

if __name__ == "__main__":
    import os
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8090"))
    print(f"[INFO] Starting PaddleOCR server on {host}:{port}")
    print("[INFO] Supports Indic (hi/ta/te/etc.), handwritten (limited), tables/images via line grouping")

    # Optional warmup on start (set PADDLE_WARMUP_ON_START=1)
    if os.getenv("PADDLE_WARMUP_ON_START", "0") == "1":
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