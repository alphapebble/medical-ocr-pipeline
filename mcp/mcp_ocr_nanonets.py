# mcp_ocr_nanonets.py
# MCP-compatible OCR server using FastAPI + Nanonets API.
# Cloud-based OCR with high accuracy for documents, receipts, and forms.
import io
import os
import json
import time
import base64
import traceback
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import uvicorn

app = FastAPI(title="MCP OCR - Nanonets", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def get_nanonets_client():
    """Get Nanonets API configuration."""
    api_key = os.getenv("NANONETS_API_KEY")
    if not api_key:
        raise ValueError("NANONETS_API_KEY environment variable is required")
    
    model_id = os.getenv("NANONETS_MODEL_ID", "d4f9b9a8-1234-5678-9012-123456789abc")  # Generic OCR model
    return api_key, model_id

def parse_nanonets_output(response_data: Dict, img_w: int, img_h: int) -> List[Dict[str, Any]]:
    """Parse Nanonets API response into standard blocks format."""
    blocks = []
    
    try:
        # Handle different Nanonets response formats
        if "result" in response_data and isinstance(response_data["result"], list):
            predictions = response_data["result"]
        elif "predictions" in response_data:
            predictions = response_data["predictions"]
        else:
            return []
        
        for pred in predictions:
            if "ocr_text" in pred:
                # Text extraction format
                text = pred["ocr_text"].strip()
                if not text:
                    continue
                
                # Get bounding box if available
                if "bbox" in pred:
                    bbox = pred["bbox"]
                    # Nanonets usually provides normalized coordinates [0-1]
                    if all(coord <= 1.0 for coord in bbox):
                        x1, y1, x2, y2 = bbox
                        bbox = [int(x1 * img_w), int(y1 * img_h), int(x2 * img_w), int(y2 * img_h)]
                else:
                    # No bbox, use full image
                    bbox = [0, 0, img_w, img_h]
                
                confidence = pred.get("confidence", 0.9)
                
                blocks.append({
                    "text": text,
                    "confidence": confidence,
                    "bbox": bbox
                })
            
            elif "label" in pred and "value" in pred:
                # Key-value extraction format
                text = f"{pred['label']}: {pred['value']}"
                confidence = pred.get("confidence", 0.9)
                
                # Get bounding box if available
                if "bbox" in pred:
                    bbox = pred["bbox"]
                    if all(coord <= 1.0 for coord in bbox):
                        x1, y1, x2, y2 = bbox
                        bbox = [int(x1 * img_w), int(y1 * img_h), int(x2 * img_w), int(y2 * img_h)]
                else:
                    bbox = [0, 0, img_w, img_h]
                
                blocks.append({
                    "text": text,
                    "confidence": confidence,
                    "bbox": bbox
                })
        
        # If no structured data, try to extract raw text
        if not blocks and "message" in response_data:
            text = response_data["message"]
            if text and text.strip():
                blocks.append({
                    "text": text.strip(),
                    "confidence": 0.8,
                    "bbox": [0, 0, img_w, img_h]
                })
    
    except Exception as e:
        print(f"[WARN] Failed to parse Nanonets response: {e}")
    
    return blocks

@app.get("/health")
async def health():
    try:
        api_key, model_id = get_nanonets_client()
        return {"ok": True, "engine": "nanonets", "version": "api", "model_id": model_id[:8] + "...", "cloud_based": True}
    except Exception as e:
        return {"ok": False, "engine": "nanonets", "error": str(e)}

@app.get("/warmup")
async def warmup():
    """Warmup Nanonets with a test API call."""
    try:
        api_key, model_id = get_nanonets_client()
        
        # Create a simple test image
        test_img = Image.new("RGB", (200, 100), "white")
        from PIL import ImageDraw
        draw = ImageDraw.Draw(test_img)
        draw.text((10, 40), "Test", fill="black")
        
        # Convert to base64
        buffer = io.BytesIO()
        test_img.save(buffer, format="PNG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        t0 = time.time()
        
        # Make test API call
        import requests
        
        url = f"https://app.nanonets.com/api/v2/OCR/Model/{model_id}/LabelFile/"
        
        data = {
            'file': f'data:image/png;base64,{img_base64}',
            'modelId': model_id
        }
        
        headers = {
            'Authorization': f'Basic {base64.b64encode(f"{api_key}:".encode()).decode()}'
        }
        
        response = requests.post(url, data=data, headers=headers, timeout=30)
        dt = time.time() - t0
        
        if response.status_code == 200:
            return {"ok": True, "seconds": round(dt, 2), "model": model_id, "status": "ready"}
        else:
            return {"ok": False, "error": f"API returned {response.status_code}: {response.text}"}
        
    except Exception as e:
        import traceback
        return JSONResponse(
            {"ok": False, "error": str(e), "traceback": traceback.format_exc()},
            status_code=500
        )

@app.post("/ocr")
async def ocr(image: UploadFile, lang: str = Form("en")):
    """
    Perform OCR using Nanonets cloud API.
    
    Args:
        image: Uploaded image file
        lang: Language code (default: "en")
    
    Returns:
        JSON with engine, blocks (text, confidence, bbox), and optional error
    """
    try:
        api_key, model_id = get_nanonets_client()
    except Exception as e:
        return JSONResponse(
            {"blocks": [], "engine": "nanonets", "error": str(e)},
            status_code=500
        )
    
    try:
        data = await image.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img_w, img_h = img.size
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Prepare API request
        import requests
        
        url = f"https://app.nanonets.com/api/v2/OCR/Model/{model_id}/LabelFile/"
        
        request_data = {
            'file': f'data:image/png;base64,{img_base64}',
            'modelId': model_id
        }
        
        # Add language parameter if supported
        if lang != "en":
            request_data['language'] = lang
        
        headers = {
            'Authorization': f'Basic {base64.b64encode(f"{api_key}:".encode()).decode()}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        # Make API call
        response = requests.post(url, data=request_data, headers=headers, timeout=60)
        
        if response.status_code != 200:
            return JSONResponse(
                {"blocks": [], "engine": "nanonets", "error": f"API error {response.status_code}: {response.text}"},
                status_code=500
            )
        
        response_data = response.json()
        blocks = parse_nanonets_output(response_data, img_w, img_h)
        
        return {
            "engine": "nanonets",
            "blocks": blocks,
            "meta": {
                "processing_time_s": 0.0,  # Not tracked separately
                "language": lang,
                "total_blocks": len(blocks),
                "model_id": model_id,
                "cloud_based": True,
                "high_accuracy": True
            }
        }
        
    except Exception as e:
        import traceback
        return JSONResponse(
            {"blocks": [], "engine": "nanonets", "error": str(e), "traceback": traceback.format_exc()},
            status_code=500
        )

# Optional MCP mount
try:
    from fastmcp import FastMCP
    mcp = FastMCP.from_fastapi(app)
    app.mount("/mcp", mcp.http_app(path="/mcp"))
    print("[INFO] MCP mounted at /mcp (nanonets)")
except Exception as e:
    print(f"[WARN] MCP not enabled for nanonets: {e}")

if __name__ == "__main__":
    import os
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8098"))
    print(f"[INFO] Starting Nanonets OCR server on {host}:{port}")
    print("[INFO] Cloud-based OCR with high accuracy for documents, receipts, and forms")
    print("[INFO] Requires NANONETS_API_KEY environment variable")
    
    # Optional warmup on start
    if os.getenv("NANONETS_WARMUP_ON_START", "0") == "1":
        try:
            import requests
            from threading import Thread
            def _bg_warm():
                import time
                time.sleep(5)  # Wait for server to start
                try:
                    requests.get(f"http://{host}:{port}/warmup", timeout=60)
                    print("[WARMUP] Nanonets warmup completed")
                except Exception as e:
                    print(f"[WARMUP] Failed: {e}")
            Thread(target=_bg_warm, daemon=True).start()
        except Exception as e:
            print(f"[WARMUP] not scheduled: {e}")
    
    uvicorn.run(app, host=host, port=port)