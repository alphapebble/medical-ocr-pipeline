# mcp_ocr_marker.py
# MCP-compatible OCR server using FastAPI + Marker.
# High-performance document conversion to markdown, JSON, and HTML.
import io
import os
import json
import time
import tempfile
import traceback
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import uvicorn

app = FastAPI(title="MCP OCR - Marker", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Global lazy init
_CONVERTER = None

def get_converter():
    """Initialize Marker converter (lazy loading)."""
    global _CONVERTER
    if _CONVERTER is None:
        try:
            from marker.converters.pdf import PdfConverter
            from marker.models import create_model_dict
            
            print("[INFO] Loading Marker models...")
            _CONVERTER = PdfConverter(
                artifact_dict=create_model_dict(),
            )
            print("[INFO] Marker converter loaded successfully")
        except Exception as e:
            print(f"[ERROR] Failed to load Marker converter: {e}")
            raise e
    
    return _CONVERTER

def parse_marker_output(rendered_result, img_w: int, img_h: int) -> List[Dict[str, Any]]:
    """Parse Marker output into standard blocks format."""
    try:
        from marker.output import text_from_rendered
        text, _, images = text_from_rendered(rendered_result)
        
        if not text or not text.strip():
            return []
        
        # Split into paragraphs/lines for better granularity
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if not paragraphs:
            # Fallback to line splitting
            paragraphs = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not paragraphs:
            return []
        
        blocks = []
        
        # If single paragraph, return full image block
        if len(paragraphs) == 1:
            return [{
                "text": paragraphs[0],
                "confidence": 0.98,  # High confidence for Marker
                "bbox": [0, 0, img_w, img_h]
            }]
        
        # Multiple paragraphs - distribute vertically
        para_height = img_h // len(paragraphs)
        for i, para in enumerate(paragraphs):
            y_start = i * para_height
            y_end = min((i + 1) * para_height, img_h)
            
            blocks.append({
                "text": para,
                "confidence": 0.98,
                "bbox": [0, y_start, img_w, y_end]
            })
        
        return blocks
        
    except Exception as e:
        print(f"[WARN] Failed to parse Marker output: {e}")
        return []

@app.get("/health")
async def health():
    try:
        _ = get_converter()
        return {"ok": True, "engine": "marker", "version": "latest", "formats": ["pdf", "image"], "high_accuracy": True}
    except Exception as e:
        return {"ok": False, "engine": "marker", "error": str(e)}

@app.get("/warmup")
async def warmup():
    """Warmup Marker with a synthetic PDF."""
    try:
        converter = get_converter()
        
        # Create a simple test PDF with text
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            c = canvas.Canvas(tmp_pdf.name, pagesize=letter)
            c.drawString(100, 750, "Test OCR Document")
            c.drawString(100, 700, "This is a test for Marker OCR.")
            c.save()
            
            t0 = time.time()
            rendered = converter(tmp_pdf.name)
            dt = time.time() - t0
            
            os.unlink(tmp_pdf.name)
            
            return {"ok": True, "seconds": round(dt, 2), "engine": "marker"}
        
    except Exception as e:
        import traceback
        return JSONResponse(
            {"ok": False, "error": str(e), "traceback": traceback.format_exc()},
            status_code=500
        )

@app.post("/ocr")
async def ocr(image: UploadFile, lang: str = Form("en")):
    """
    Perform OCR using Marker document conversion.
    
    Args:
        image: Uploaded image file (converted to PDF for processing)
        lang: Language code (default: "en")
    
    Returns:
        JSON with engine, blocks (text, confidence, bbox), and optional error
    """
    try:
        converter = get_converter()
    except Exception as e:
        return JSONResponse(
            {"blocks": [], "engine": "marker", "error": str(e)},
            status_code=500
        )
    
    try:
        data = await image.read()
        
        # Handle different input types
        content_type = image.content_type or ""
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            if content_type == "application/pdf" or data[:4] == b"%PDF":
                # Direct PDF processing
                pdf_path = os.path.join(tmp_dir, "input.pdf")
                with open(pdf_path, "wb") as f:
                    f.write(data)
            else:
                # Convert image to PDF
                img = Image.open(io.BytesIO(data)).convert("RGB")
                img_w, img_h = img.size
                
                pdf_path = os.path.join(tmp_dir, "input.pdf")
                img.save(pdf_path, "PDF", resolution=300.0)
            
            # Get image dimensions for bbox calculation
            if 'img_w' not in locals():
                # For direct PDF, estimate dimensions
                img_w, img_h = 612, 792  # Standard letter size
            
            # Process with Marker
            rendered = converter(pdf_path)
            blocks = parse_marker_output(rendered, img_w, img_h)
            
            return {
                "engine": "marker",
                "blocks": blocks,
                "meta": {
                    "processing_time_s": 0.0,  # Not tracked in this simple version
                    "language": lang,
                    "total_blocks": len(blocks),
                    "high_accuracy": True,
                    "supports_pdf": True,
                    "supports_images": True
                }
            }
        
    except Exception as e:
        import traceback
        return JSONResponse(
            {"blocks": [], "engine": "marker", "error": str(e), "traceback": traceback.format_exc()},
            status_code=500
        )

# Optional MCP mount
try:
    from fastmcp import FastMCP
    mcp = FastMCP.from_fastapi(app)
    app.mount("/mcp", mcp.http_app(path="/mcp"))
    print("[INFO] MCP mounted at /mcp (marker)")
except Exception as e:
    print(f"[WARN] MCP not enabled for marker: {e}")

if __name__ == "__main__":
    import os
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8097"))
    print(f"[INFO] Starting Marker OCR server on {host}:{port}")
    print("[INFO] High-performance document conversion with superior accuracy")
    
    # Optional warmup on start
    if os.getenv("MARKER_WARMUP_ON_START", "0") == "1":
        try:
            import requests
            from threading import Thread
            def _bg_warm():
                import time
                time.sleep(5)  # Wait for server to start
                try:
                    requests.get(f"http://{host}:{port}/warmup", timeout=60)
                    print("[WARMUP] Marker warmup completed")
                except Exception as e:
                    print(f"[WARMUP] Failed: {e}")
            Thread(target=_bg_warm, daemon=True).start()
        except Exception as e:
            print(f"[WARMUP] not scheduled: {e}")
    
    uvicorn.run(app, host=host, port=port)