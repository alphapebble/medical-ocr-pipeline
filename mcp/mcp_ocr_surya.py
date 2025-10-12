# mcp_ocr_surya.py
# MCP-compatible OCR server using FastAPI + Surya OCR.
# Enhanced for Indic languages (hi, ta, te, etc.), mixed handwritten/typed text, and table/image handling.
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import io
from PIL import Image, ImageDraw
import os
import time
import json
import traceback

app = FastAPI(title="MCP OCR - Surya", version="1.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_PREDICTORS = None

def get_predictors():
    """Initialize Surya OCR predictors with proper error handling."""
    global _PREDICTORS
    if _PREDICTORS is not None:
        return _PREDICTORS
    
    try:
        import torch
        
        # For surya-ocr 0.17.0, use the foundation + recognition + detection predictor pattern
        from surya.foundation import FoundationPredictor
        from surya.recognition import RecognitionPredictor
        from surya.detection import DetectionPredictor
        
        # Force CPU if MPS BFloat16 is not supported (macOS < 14)
        # You can also set TORCH_DEVICE=cpu as an environment variable
        device = os.getenv("TORCH_DEVICE")
        dtype = None
        
        if device is None:
            # Auto-detect device
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                # Check macOS version for MPS support
                import platform
                macos_version = tuple(map(int, platform.mac_ver()[0].split('.')[:2]))
                if macos_version < (14, 0):
                    print("[WARN] MPS BFloat16 not supported on macOS < 14, using CPU")
                    device = "cpu"
                else:
                    device = "mps"
            else:
                device = "cpu"
        
        # Use float32 for CPU to avoid bfloat16 issues
        if device == "cpu":
            dtype = torch.float32
        
        print(f"[INFO] Loading Surya OCR models on device: {device}, dtype: {dtype}")
        
        foundation_predictor = FoundationPredictor(device=device, dtype=dtype)
        recognition_predictor = RecognitionPredictor(foundation_predictor)
        detection_predictor = DetectionPredictor(device=device, dtype=dtype)
        
        _PREDICTORS = {
            'foundation': foundation_predictor,
            'recognition': recognition_predictor,
            'detection': detection_predictor
        }
        print("[INFO] Surya OCR models loaded successfully")
        return _PREDICTORS
    except Exception as e:
        import traceback
        print(f"[ERROR] Failed to load Surya OCR: {traceback.format_exc()}")
        raise RuntimeError(f"Failed to load Surya OCR: {e}")

def parse_surya_output(predictions, img_w, img_h):
    """Parse Surya predictions into line-level blocks, grouping nearby detections for better table/image handling."""
    blocks = []
    if not predictions or len(predictions) == 0:
        return blocks
    
    pred = predictions[0]  # First image result
    
    # pred.text_lines: list of TextLine objects
    detections = []
    if hasattr(pred, 'text_lines'):
        for line in pred.text_lines:
            txt = line.text.strip() if hasattr(line, 'text') else str(line).strip()
            if not txt:
                continue
            
            conf = float(line.confidence) if hasattr(line, 'confidence') else 1.0
            
            # Get bounding box - try bbox first, then polygon
            box = None
            if hasattr(line, 'bbox') and line.bbox is not None:
                bbox = line.bbox
                # bbox should be [x1, y1, x2, y2] or tensor
                if isinstance(bbox, torch.Tensor):
                    bbox = bbox.tolist()
                box = [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
            elif hasattr(line, 'polygon') and line.polygon is not None:
                # polygon is [(x1,y1), (x2,y2), (x3,y3), (x4,y4)] or tensor
                poly = line.polygon
                if isinstance(poly, torch.Tensor):
                    poly = poly.tolist()
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                box = [min(xs), min(ys), max(xs), max(ys)]
            
            # Normalize confidence to 0-1 range
            if conf > 1.0:
                conf = conf / 100.0
            
            if box:
                detections.append({'bbox': box, 'text': txt, 'conf': conf})
    
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
        _ = get_predictors()
        return {"ok": True, "engine": "surya", "version": "0.17.0", "indic_supported": True}
    except Exception as e:
        return {"ok": False, "engine": "surya", "error": str(e)}

@app.get("/warmup")
async def warmup(lang: str = "en", handwritten: bool = False):
    """Warmup Surya with a tiny synthetic image to cache models."""
    try:
        predictors = get_predictors()
        import time
        t0 = time.time()
        # Tiny image with sample text (for Indic, use placeholder)
        img = Image.new("RGB", (200, 100), "white")
        draw = ImageDraw.Draw(img)
        sample_text = "test" if lang == "en" else "नमस्ते"  # Hello in Hindi for Indic test
        draw.text((10, 40), sample_text, fill="black")
        
        # Run OCR (Surya is lang-agnostic, but param for meta)
        predictions = predictors['recognition'](
            [img],
            ['ocr_with_boxes'],  # Task name
            det_predictor=predictors['detection']
        )
        dt = time.time() - t0
        blocks = parse_surya_output(predictions, img.width, img.height)
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
        lang: Language code (default: "en"; Surya supports Indic: hi, ta, te, etc. via multilingual model)
        handwritten: Enable handwritten mode (default: False; limited, uses same model with warning)
    
    Returns:
        JSON with engine, blocks (text, confidence, bbox), and optional error
    """
    if handwritten:
        print(f"[WARN] Handwritten mode for {lang}: Surya optimized for printed text (limited accuracy for handwritten Indic)")
    
    try:
        predictors = get_predictors()
        data = await image.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        
        # Run OCR using Surya 0.17.0 API
        # recognition_predictor takes task names, not language codes
        # Supported tasks: 'ocr_with_boxes', 'ocr_without_boxes', 'block_without_boxes'
        predictions = predictors['recognition'](
            [img],
            ['ocr_with_boxes'],  # Task name, not language!
            det_predictor=predictors['detection']
        )
        
        # Parse with grouping for tables/images
        blocks = parse_surya_output(predictions, img.width, img.height)
        
        return JSONResponse({
            "engine": "surya",
            "blocks": blocks,
            "meta": {"lang": lang, "handwritten": handwritten}
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[ERROR] OCR failed: {error_detail}")
        return JSONResponse(
            {"engine": "surya", "blocks": [], "error": str(e), "traceback": error_detail},
            status_code=500
        )


# Optional MCP mount
try:
    from fastmcp import FastMCP
    mcp = FastMCP.from_fastapi(app)
    app.mount("/mcp", mcp.http_app(path="/mcp"))
    print("[INFO] MCP mounted at /mcp (surya)")
except Exception as e:
    print("[WARN] MCP not enabled for surya:", e)

if __name__ == "__main__":
    import os
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8091"))
    print(f"[INFO] Starting Surya OCR server on {host}:{port}")
    print("[INFO] Supports Indic (hi/ta/te/etc. via multilingual), handwritten (limited), tables/images via line grouping")

    # Optional warmup on start (set SURYA_WARMUP_ON_START=1)
    if os.getenv("SURYA_WARMUP_ON_START", "0") == "1":
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