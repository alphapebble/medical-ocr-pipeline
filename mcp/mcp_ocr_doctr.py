# mcp_ocr_doctr.py
# MCP-compatible OCR server using FastAPI + docTR (Mindee).
# Returns line-level boxes with confidences via /ocr; MCP is mounted at /mcp if fastmcp is available.
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import io
import uvicorn
import numpy as np
import tempfile
import os
import time
import json

app = FastAPI(title="MCP OCR - docTR", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Lazy init
_MODEL = None
_LANG = None

def get_model(lang="en"):
    """Initialize docTR OCR predictor with the specified language."""
    global _MODEL, _LANG
    if _MODEL is not None and _LANG == lang:
        return _MODEL
    
    try:
        from doctr.io import DocumentFile
        from doctr.models import ocr_predictor
    except ImportError as e:
        raise RuntimeError(f"docTR not available. Install with: pip install python-doctr[torch]. Error: {e}")
    
    # Default to English; for other langs, use multilingual (simplified)
    reco_arch = 'crnn_vgg16_bn' if lang == 'en' else 'crnn_mobilenet_v3_small_multi'
    print(f"[INFO] Initializing docTR with lang={lang}, reco_arch={reco_arch}")
    
    _MODEL = ocr_predictor(det_arch='db_resnet50', reco_arch=reco_arch, pretrained=True)
    _LANG = lang
    print(f"[INFO] docTR initialized successfully")
    return _MODEL

def parse_doctr_output(result, img_w, img_h):
    """Parse docTR result.export() into line-level blocks."""
    blocks = []
    output = result.export()
    if not output or 'pages' not in output or not output['pages']:
        return blocks
    
    page = output['pages'][0]  # Assume single page
    page_h, page_w = page['dimensions']  # [height, width]
    
    for block in page.get('blocks', []):
        for line in block.get('lines', []):
            words = line.get('words', [])
            if not words:
                continue
            
            # Aggregate words into line
            texts = [word.get('value', '').strip() for word in words]
            confs = [float(word.get('confidence', 0.0)) for word in words]
            text = ' '.join(texts)
            if not text:
                continue
            avg_conf = sum(confs) / len(confs) if confs else 0.0
            
            # Union bbox from word geometries
            all_xs, all_ys = [], []
            for word in words:
                geom = word.get('geometry', [])
                if len(geom) >= 2:
                    x0, y0 = geom[0]
                    x1, y1 = geom[1]
                    all_xs.extend([x0, x1])
                    all_ys.extend([y0, y1])
            
            if all_xs and all_ys:
                bbox = [
                    min(all_xs) * page_w,
                    min(all_ys) * page_h,
                    max(all_xs) * page_w,
                    max(all_ys) * page_h
                ]
                blocks.append({
                    "text": text,
                    "confidence": avg_conf,
                    "bbox": bbox
                })
    
    return blocks

@app.get("/health")
async def health():
    try:
        _ = get_model("en")
        return {"ok": True, "engine": "doctr", "version": "latest"}
    except Exception as e:
        return {"ok": False, "engine": "doctr", "error": str(e)}

@app.get("/warmup")
async def warmup():
    """Warmup docTR with a tiny synthetic image to cache models."""
    try:
        model = get_model("en")
        import time
        t0 = time.time()
        # Tiny image with text
        img = Image.new("RGB", (200, 100), "white")
        draw = ImageDraw.Draw(img)
        draw.text((10, 40), "doctr warmup", fill="black")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        doc = DocumentFile.from_images(buf)
        result = model(doc)
        dt = time.time() - t0
        blocks = parse_doctr_output(result, img.width, img.height)
        return {"ok": True, "seconds": round(dt, 2), "blocks": len(blocks)}
    except Exception as e:
        import traceback
        return JSONResponse({"ok": False, "error": str(e), "traceback": traceback.format_exc()}, status_code=500)

@app.post("/ocr")
async def ocr(image: UploadFile, lang: str = Form("en")):
    """
    Perform OCR on an uploaded image.
    
    Args:
        image: Uploaded image file
        lang: Language code (default: "en")
    
    Returns:
        JSON with engine, blocks (text, confidence, bbox), and optional error
    """
    try:
        model = get_model(lang)
    except Exception as e:
        return JSONResponse(
            {"blocks": [], "engine": "doctr", "error": str(e)},
            status_code=500
        )
    
    try:
        data = await image.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        doc = DocumentFile.from_images(io.BytesIO(data))
        result = model(doc)
    except Exception as e:
        import traceback
        return JSONResponse(
            {"blocks": [], "engine": "doctr", "error": str(e), "traceback": traceback.format_exc()},
            status_code=500
        )
    
    # Parse results
    blocks = parse_doctr_output(result, img.width, img.height)
    
    return JSONResponse({"engine": "doctr", "blocks": blocks})


# Optional MCP mount
try:
    from fastmcp import FastMCP
    mcp = FastMCP.from_fastapi(app)
    app.mount("/mcp", mcp.http_app(path="/mcp"))
    print("[INFO] MCP mounted at /mcp (doctr)")
except Exception as e:
    print("[WARN] MCP not enabled for doctr:", e)

if __name__ == "__main__":
    import os
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8094"))  # Different port, e.g., 8094
    print(f"[INFO] Starting docTR OCR server on {host}:{port}")

    # Optional warmup on start (set DOCTR_WARMUP_ON_START=1)
    if os.getenv("DOCTR_WARMUP_ON_START", "0") == "1":
        try:
            import requests
            from threading import Thread
            def _bg_warm():
                try:
                    # wait a bit for server to come up then warm
                    import time; time.sleep(1)
                    print("[WARMUP] hitting /warmup ...")
                    requests.get(f"http://{host}:{port}/warmup", timeout=300)
                    print("[WARMUP] done")
                except Exception as e:
                    print(f"[WARMUP] failed: {e}")
            Thread(target=_bg_warm, daemon=True).start()
        except Exception as e:
            print(f"[WARMUP] not scheduled: {e}")

    uvicorn.run(app, host=host, port=port)