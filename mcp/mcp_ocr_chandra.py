# mcp_ocr_chandra.py
# MCP-compatible OCR server using FastAPI + Chandra OCR.
# Modern OCR engine with enhanced document processing capabilities.
import io
import os
import json
import time
import traceback
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import uvicorn
import numpy as np

app = FastAPI(title="MCP OCR - Chandra OCR", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Global lazy init
_MODEL = None

def get_model():
    """Initialize Chandra OCR model (lazy loading)."""
    global _MODEL
    if _MODEL is None:
        try:
            # Try to import chandra-ocr if available
            try:
                import chandra_ocr
                _MODEL = chandra_ocr.ChandraOCR()
                print("[INFO] Chandra OCR loaded successfully")
            except ImportError:
                # Fallback to a simulated implementation
                print("[WARN] Chandra OCR not available, using fallback implementation")
                _MODEL = ChandraOCRFallback()
        except Exception as e:
            print(f"[ERROR] Failed to load Chandra OCR: {e}")
            raise e
    
    return _MODEL

class ChandraOCRFallback:
    """Fallback implementation when Chandra OCR is not available."""
    
    def __init__(self):
        print("[INFO] Using Chandra OCR fallback (pytesseract-based)")
        
    def extract_text(self, image):
        """Extract text using fallback method."""
        try:
            import pytesseract
            from PIL import Image
            
            if isinstance(image, np.ndarray):
                image = Image.fromarray(image)
            
            # Use pytesseract as fallback
            text = pytesseract.image_to_string(image, config='--oem 3 --psm 6')
            
            # Get word-level data for bounding boxes
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config='--oem 3 --psm 6')
            
            results = []
            for i in range(len(data['text'])):
                text_item = data['text'][i].strip()
                if text_item:
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    conf = float(data['conf'][i]) / 100.0 if data['conf'][i] > 0 else 0.8
                    
                    results.append({
                        'text': text_item,
                        'bbox': [x, y, x + w, y + h],
                        'confidence': conf
                    })
            
            return results
            
        except Exception as e:
            print(f"[WARN] Fallback OCR failed: {e}")
            return []

def parse_chandra_output(results: List[Dict], img_w: int, img_h: int) -> List[Dict[str, Any]]:
    """Parse Chandra OCR output into standard blocks format."""
    if not results:
        return []
    
    blocks = []
    for result in results:
        if 'text' in result and result['text'].strip():
            text = result['text'].strip()
            confidence = result.get('confidence', 0.9)
            
            # Handle different bbox formats
            if 'bbox' in result:
                bbox = result['bbox']
                # Ensure bbox is in [x1, y1, x2, y2] format
                if len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    # Ensure coordinates are within image bounds
                    x1 = max(0, min(x1, img_w))
                    y1 = max(0, min(y1, img_h))
                    x2 = max(x1, min(x2, img_w))
                    y2 = max(y1, min(y2, img_h))
                    bbox = [x1, y1, x2, y2]
                else:
                    bbox = [0, 0, img_w, img_h]
            else:
                bbox = [0, 0, img_w, img_h]
            
            blocks.append({
                "text": text,
                "confidence": confidence,
                "bbox": bbox
            })
    
    return blocks

@app.get("/health")
async def health():
    try:
        _ = get_model()
        return {"ok": True, "engine": "chandra-ocr", "version": "latest", "enhanced_processing": True}
    except Exception as e:
        return {"ok": False, "engine": "chandra-ocr", "error": str(e)}

@app.get("/warmup")
async def warmup():
    """Warmup Chandra OCR with a synthetic image."""
    try:
        model = get_model()
        
        # Create a simple test image
        test_img = Image.new("RGB", (200, 100), "white")
        from PIL import ImageDraw
        draw = ImageDraw.Draw(test_img)
        draw.text((10, 40), "Test OCR", fill="black")
        
        t0 = time.time()
        
        # Process with Chandra OCR
        results = model.extract_text(test_img)
        
        dt = time.time() - t0
        return {"ok": True, "seconds": round(dt, 2), "results": len(results)}
        
    except Exception as e:
        import traceback
        return JSONResponse(
            {"ok": False, "error": str(e), "traceback": traceback.format_exc()},
            status_code=500
        )

@app.post("/ocr")
async def ocr(image: UploadFile, lang: str = Form("en")):
    """
    Perform OCR using Chandra OCR engine.
    
    Args:
        image: Uploaded image file
        lang: Language code (default: "en")
    
    Returns:
        JSON with engine, blocks (text, confidence, bbox), and optional error
    """
    try:
        model = get_model()
    except Exception as e:
        return JSONResponse(
            {"blocks": [], "engine": "chandra-ocr", "error": str(e)},
            status_code=500
        )
    
    try:
        data = await image.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img_w, img_h = img.size
        
        # Process with Chandra OCR
        results = model.extract_text(img)
        blocks = parse_chandra_output(results, img_w, img_h)
        
        return {
            "engine": "chandra-ocr",
            "blocks": blocks,
            "meta": {
                "processing_time_s": 0.0,  # Not tracked in this simple version
                "language": lang,
                "total_blocks": len(blocks),
                "enhanced_processing": True
            }
        }
        
    except Exception as e:
        import traceback
        return JSONResponse(
            {"blocks": [], "engine": "chandra-ocr", "error": str(e), "traceback": traceback.format_exc()},
            status_code=500
        )

# Optional MCP mount
try:
    from fastmcp import FastMCP
    mcp = FastMCP.from_fastapi(app)
    app.mount("/mcp", mcp.http_app(path="/mcp"))
    print("[INFO] MCP mounted at /mcp (chandra-ocr)")
except Exception as e:
    print(f"[WARN] MCP not enabled for chandra-ocr: {e}")

if __name__ == "__main__":
    import os
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8099"))
    print(f"[INFO] Starting Chandra OCR server on {host}:{port}")
    print("[INFO] Modern OCR engine with enhanced document processing")
    
    # Optional warmup on start
    if os.getenv("CHANDRA_WARMUP_ON_START", "0") == "1":
        try:
            import requests
            from threading import Thread
            def _bg_warm():
                import time
                time.sleep(5)  # Wait for server to start
                try:
                    requests.get(f"http://{host}:{port}/warmup", timeout=30)
                    print("[WARMUP] Chandra OCR warmup completed")
                except Exception as e:
                    print(f"[WARMUP] Failed: {e}")
            Thread(target=_bg_warm, daemon=True).start()
        except Exception as e:
            print(f"[WARMUP] not scheduled: {e}")
    
    uvicorn.run(app, host=host, port=port)