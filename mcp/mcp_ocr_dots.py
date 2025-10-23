# mcp_ocr_dots_new.py
# MCP-compatible OCR server using FastAPI + dots.ocr (proper implementation)
# Advanced 3B OCR model from Rednote-HiLab following official documentation

import io
import os
import sys
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

app = FastAPI(title="MCP OCR - dots.ocr", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Global lazy init
_PARSER = None

def get_parser():
    """Initialize dots.ocr parser (lazy loading)."""
    global _PARSER
    if _PARSER is None:
        try:
            # Try importing from the official Docker image environment
            try:
                from dots_ocr.parser import DotsOCRParser
                print("[INFO] Found dots_ocr.parser in official image")
            except ImportError:
                # Try alternative paths that might be in the official image
                import sys
                possible_paths = ["/app", "/workspace", "/opt/dots_ocr", "/usr/local/lib/python3.12/site-packages"]
                for path in possible_paths:
                    if path not in sys.path:
                        sys.path.append(path)
                        print(f"[DEBUG] Added {path} to Python path")
                
                from dots_ocr.parser import DotsOCRParser
                print("[INFO] Found dots_ocr.parser after path adjustment")
            
            print("[INFO] Initializing DotsOCR parser (HuggingFace backend)...")
            # Use HuggingFace backend for better compatibility
            _PARSER = DotsOCRParser(use_hf=True)
            print("[INFO] DotsOCR parser loaded successfully")
            
        except Exception as e:
            print(f"[ERROR] Failed to load DotsOCR parser: {e}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            
            # Try to see what's available in the environment
            try:
                import os
                print(f"[DEBUG] Current working directory: {os.getcwd()}")
                print(f"[DEBUG] Python path: {sys.path}")
                print(f"[DEBUG] Environment variables: {dict(os.environ)}")
            except:
                pass
            
            # Set fallback flag
            _PARSER = "fallback"
    
    return _PARSER

def perform_dots_ocr(image: Image.Image) -> List[Dict[str, Any]]:
    """Perform OCR using DotsOCR parser."""
    try:
        parser = get_parser()
        
        if parser == "fallback":
            # Return empty if DotsOCR is not available
            print("[WARN] DotsOCR not available, returning empty results")
            return []
        
        # Save image temporarily for parser
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            image.save(tmp_file.name, 'PNG')
            tmp_path = tmp_file.name
        
        try:
            print(f"[INFO] Running DotsOCR on {tmp_path}")
            # Use layout detection + OCR (recommended)
            result = parser.parse(tmp_path, prompt="prompt_layout_all_en")
            print(f"[INFO] DotsOCR result type: {type(result)}")
            
            # Clean up temp file
            os.unlink(tmp_path)
            
            return parse_dots_result(result, image.width, image.height)
            
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise e
            
    except Exception as e:
        print(f"[ERROR] DotsOCR failed: {e}")
        print("[INFO] Use dedicated Tesseract service at port 8089 for basic OCR")
        return []

def parse_dots_result(result: Any, img_w: int, img_h: int) -> List[Dict[str, Any]]:
    """Parse DotsOCR result into standard blocks format."""
    blocks = []
    
    try:
        print(f"[DEBUG] Parsing DotsOCR result: {type(result)}")
        
        # DotsOCR returns various formats depending on the prompt
        if isinstance(result, str):
            # Plain text output
            lines = [line.strip() for line in result.strip().split('\n') if line.strip()]
            for i, line in enumerate(lines):
                block = {
                    "id": f"dots_block_{i + 1}",
                    "bbox": [0, i * 25, img_w, (i + 1) * 25],
                    "polygon": [[0, i * 25], [img_w, i * 25], [img_w, (i + 1) * 25], [0, i * 25]],
                    "text": line,
                    "confidence": 0.95,
                    "type": "text",
                    "properties": {
                        "font_size": 11,
                        "reading_order": i + 1,
                        "engine": "dots.ocr"
                    }
                }
                blocks.append(block)
        
        elif isinstance(result, dict):
            # Structured output with layout info
            if 'blocks' in result:
                for i, block_data in enumerate(result['blocks']):
                    if 'text' in block_data and block_data['text'].strip():
                        text = block_data['text'].strip()
                        bbox = block_data.get('bbox', [0, 0, img_w, img_h])
                        
                        block = {
                            "id": f"dots_block_{i + 1}",
                            "bbox": bbox,
                            "polygon": [
                                [bbox[0], bbox[1]], 
                                [bbox[2], bbox[1]], 
                                [bbox[2], bbox[3]], 
                                [bbox[0], bbox[3]]
                            ],
                            "text": text,
                            "confidence": block_data.get('confidence', 0.95),
                            "type": block_data.get('type', 'text'),
                            "properties": {
                                "font_size": block_data.get('font_size', 11),
                                "reading_order": i + 1,
                                "engine": "dots.ocr"
                            }
                        }
                        blocks.append(block)
            
            elif 'text' in result:
                # Single text block
                text = result['text'].strip()
                if text:
                    block = {
                        "id": "dots_block_1",
                        "bbox": [0, 0, img_w, img_h],
                        "polygon": [[0, 0], [img_w, 0], [img_w, img_h], [0, img_h]],
                        "text": text,
                        "confidence": result.get('confidence', 0.95),
                        "type": "text",
                        "properties": {"font_size": 11, "reading_order": 1, "engine": "dots.ocr"}
                    }
                    blocks.append(block)
        
        elif isinstance(result, list):
            # List of text blocks
            for i, item in enumerate(result):
                if isinstance(item, str) and item.strip():
                    block = {
                        "id": f"dots_block_{i + 1}",
                        "bbox": [0, i * 25, img_w, (i + 1) * 25],
                        "polygon": [[0, i * 25], [img_w, i * 25], [img_w, (i + 1) * 25], [0, i * 25]],
                        "text": item.strip(),
                        "confidence": 0.95,
                        "type": "text",
                        "properties": {
                            "font_size": 11,
                            "reading_order": i + 1,
                            "engine": "dots.ocr"
                        }
                    }
                    blocks.append(block)
                elif isinstance(item, dict) and 'text' in item:
                    text = item['text'].strip()
                    if text:
                        bbox = item.get('bbox', [0, i * 25, img_w, (i + 1) * 25])
                        block = {
                            "id": f"dots_block_{i + 1}",
                            "bbox": bbox,
                            "polygon": [
                                [bbox[0], bbox[1]], 
                                [bbox[2], bbox[1]], 
                                [bbox[2], bbox[3]], 
                                [bbox[0], bbox[3]]
                            ],
                            "text": text,
                            "confidence": item.get('confidence', 0.95),
                            "type": item.get('type', 'text'),
                            "properties": {
                                "font_size": item.get('font_size', 11),
                                "reading_order": i + 1,
                                "engine": "dots.ocr"
                            }
                        }
                        blocks.append(block)
    
    except Exception as e:
        print(f"[ERROR] Failed to parse DotsOCR result: {e}")
        print(f"[DEBUG] Result was: {result}")
        # Return empty on parse error
        blocks = []
    
    return blocks

@app.get("/health")
async def health():
    """Health check endpoint."""
    parser = get_parser()
    if parser == "fallback":
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "engine": "dots.ocr", 
                "version": "latest",
                "status": "unavailable",
                "message": "DotsOCR model not loaded, use Tesseract service at port 8089"
            }
        )
    
    return {
        "ok": True,
        "engine": "dots.ocr", 
        "version": "latest",
        "status": "ready",
        "enhanced_processing": True
    }

@app.get("/warmup")
async def warmup():
    """Warmup the model to reduce cold start latency."""
    try:
        parser = get_parser()
        if parser == "fallback":
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable", 
                    "engine": "dots.ocr",
                    "message": "DotsOCR model not available"
                }
            )
        
        # Test with a small dummy image
        dummy_img = Image.new('RGB', (100, 50), color='white')
        blocks = perform_dots_ocr(dummy_img)
        
        return {
            "status": "warmed up", 
            "engine": "dots.ocr",
            "test_blocks": len(blocks)
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Warmup failed: {str(e)}"}
        )

@app.post("/ocr")
async def ocr_endpoint(
    file: UploadFile,
    extract_type: str = Form("text"),
    confidence_threshold: float = Form(0.5),
    language: str = Form("en")
):
    """
    OCR endpoint that processes uploaded images and returns structured text blocks.
    
    Args:
        file: Uploaded image file
        extract_type: Type of extraction (text, layout, etc.)
        confidence_threshold: Minimum confidence for text blocks
        language: Language hint (en, es, fr, etc.)
    
    Returns:
        JSON response with extracted text blocks
    """
    try:
        # Read and process image
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if necessary
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        
        print(f"[INFO] Processing image: {image.size} ({image.mode})")
        
        # Perform OCR
        start_time = time.time()
        blocks = perform_dots_ocr(image)
        processing_time = time.time() - start_time
        
        # Filter by confidence threshold
        filtered_blocks = [
            block for block in blocks 
            if block['confidence'] >= confidence_threshold
        ]
        
        return {
            "blocks": filtered_blocks,
            "engine": "dots.ocr",
            "processing_time": round(processing_time, 2),
            "image_info": {
                "width": image.width,
                "height": image.height,
                "mode": image.mode
            },
            "total_blocks": len(filtered_blocks),
            "confidence_threshold": confidence_threshold
        }
        
    except Exception as e:
        import traceback
        return JSONResponse(
            {"blocks": [], "engine": "dots.ocr", "error": str(e), "traceback": traceback.format_exc()},
            status_code=500
        )

# Optional MCP mount
try:
    from fastmcp import FastMCP
    mcp = FastMCP.from_fastapi(app)
    app.mount("/mcp", mcp.http_app(path="/mcp"))
    print("[INFO] MCP mounted at /mcp (dots.ocr)")
except Exception as e:
    print(f"[WARN] MCP not enabled for dots.ocr: {e}")

if __name__ == "__main__":
    import os
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print(f"[INFO] Starting DotsOCR server on {host}:{port}")
    print("[INFO] Advanced 3B OCR with layout detection")
    
    # Optional warmup on start
    if os.getenv("DOTS_WARMUP_ON_START", "0") == "1":
        try:
            import requests
            from threading import Thread
            def _bg_warm():
                import time
                time.sleep(10)  # Wait for server to start
                try:
                    requests.get(f"http://{host}:{port}/warmup", timeout=60)
                    print("[WARMUP] DotsOCR warmup completed")
                except Exception as e:
                    print(f"[WARMUP] Failed: {e}")
            Thread(target=_bg_warm, daemon=True).start()
        except Exception as e:
            print(f"[WARMUP] not scheduled: {e}")
    
    uvicorn.run(app, host=host, port=port)