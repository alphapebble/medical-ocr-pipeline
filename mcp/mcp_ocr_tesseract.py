# mcp_ocr_tesseract.py
# Minimal MCP-compatible OCR server using FastAPI + Tesseract.
# Enhanced for Indic languages (hi, ta, te, etc.), mixed handwritten/typed text, and table/image handling.
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw
import io, pytesseract, uvicorn, tempfile, os, time, json

app = FastAPI(title="MCP OCR - Tesseract", version="1.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def parse_tess_output(d, img_w, img_h):
    """Parse Tesseract image_to_data into line-level blocks, grouping words for better table/image handling."""
    blocks = []
    if not d or "text" not in d:
        return blocks
    
    n = len(d["text"])
    detections = []
    for i in range(n):
        txt = (d["text"][i] or "").strip()
        conf = d.get("conf", ["-1"]*n)[i]
        try:
            conf = float(conf)
        except:
            conf = -1.0
        if txt and conf >= 0:
            x = float(d["left"][i])
            y = float(d["top"][i])
            w = float(d["width"][i])
            h = float(d["height"][i])
            bbox = [x, y, x + w, y + h]
            detections.append({'bbox': bbox, 'text': txt, 'conf': conf / 100.0})
    
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
        _ = pytesseract.get_tesseract_version()
        return {"ok": True, "engine": "tesseract", "version": str(_), "indic_supported": True}
    except Exception as e:
        return {"ok": False, "engine": "tesseract", "error": str(e)}

@app.get("/warmup")
async def warmup(lang: str = "en", handwritten: bool = False):
    """Warmup Tesseract with a tiny synthetic image to test config."""
    try:
        import time
        t0 = time.time()
        # Tiny image with sample text (for Indic, use placeholder)
        img = Image.new("RGB", (200, 100), "white")
        draw = ImageDraw.Draw(img)
        sample_text = "test" if lang == "en" else "नमस्ते"  # Hello in Hindi for Indic test
        draw.text((10, 40), sample_text, fill="black")
        
        # Map common language codes to Tesseract format
        tmap = {"en":"eng","hi":"hin","te":"tel","mr":"mar","ta":"tam"}
        lang_code = tmap.get(lang, "eng")
        
        # Config for handwritten: Use PSM 13 (raw line) or 8 (single word) for better cursive handling
        config = '--oem 1 --psm 6'  # Default: Single uniform block
        if handwritten:
            config += ' --psm 13'  # Raw line for handwritten
            print(f"[WARN] Handwritten mode for {lang}: Using PSM 13 (limited accuracy for Indic handwritten)")
        
        d = pytesseract.image_to_data(img, lang=lang_code, config=config, output_type=pytesseract.Output.DICT)
        dt = time.time() - t0
        blocks = parse_tess_output(d, img.width, img.height)
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
        lang: Language code (default: "en"; supports Indic: hi, ta, te, mr)
        handwritten: Enable handwritten mode (default: False; uses PSM 13 for raw lines)
    
    Returns:
        JSON with engine, blocks (text, confidence, bbox), and optional error
    """
    try:
        data = await image.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        
        # Map common language codes to Tesseract format
        tmap = {"en":"eng","hi":"hin","te":"tel","mr":"mar","ta":"tam"}
        lang_code = tmap.get(lang, "eng")
        
        # Config: OEM 1 (LSTM) for better accuracy; PSM 6 for uniform block (pages/tables)
        config = '--oem 1 --psm 6'
        if handwritten:
            config += ' --psm 13'  # Raw line for handwritten/cursive text
        
        # Use image_to_data for word/line-level boxes
        d = pytesseract.image_to_data(img, lang=lang_code, config=config, output_type=pytesseract.Output.DICT)
    except Exception as e:
        import traceback
        return JSONResponse({"blocks": [], "engine": "tesseract", "error": str(e), "traceback": traceback.format_exc()}, status_code=500)
    
    # Parse with grouping for tables/images
    blocks = parse_tess_output(d, img.width, img.height)
    
    return JSONResponse({
        "engine": "tesseract",
        "blocks": blocks,
        "meta": {"lang": lang, "handwritten": handwritten}
    })

# Optional: mount MCP for agent ecosystems
try:
    from fastmcp import FastMCP
    mcp = FastMCP.from_fastapi(app)
    app.mount("/mcp", mcp.http_app(path="/mcp"))
    print("[INFO] MCP mounted at /mcp (tesseract)")
except Exception as e:
    print("[WARN] MCP not enabled for tesseract:", e)

if __name__ == "__main__":
    import os
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8089"))
    print(f"[INFO] Starting Tesseract OCR server on {host}:{port}")
    print("[INFO] Supports Indic (hi/ta/te/etc.), handwritten (via PSM 13), tables/images via line grouping")

    # Optional warmup on start (set TESS_WARMUP_ON_START=1)
    if os.getenv("TESS_WARMUP_ON_START", "0") == "1":
        try:
            import requests
            from threading import Thread
            def _bg_warm():
                try:
                    # wait a bit for server to come up then warm
                    import time; time.sleep(1)
                    print("[WARMUP] hitting /warmup?lang=en&handwritten=false ...")
                    requests.get(f"http://{host}:{port}/warmup?lang=en&handwritten=false", timeout=60)
                    print("[WARMUP] done (English)")
                    print("[WARMUP] hitting /warmup?lang=hi&handwritten=true ...")
                    requests.get(f"http://{host}:{port}/warmup?lang=hi&handwritten=true", timeout=60)
                    print("[WARMUP] done (Indic Handwritten)")
                except Exception as e:
                    print(f"[WARMUP] failed: {e}")
            Thread(target=_bg_warm, daemon=True).start()
        except Exception as e:
            print(f"[WARMUP] not scheduled: {e}")

    uvicorn.run(app, host=host, port=port)