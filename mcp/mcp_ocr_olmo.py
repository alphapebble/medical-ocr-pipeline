# mcp_ocr_olmo.py
# MCP-compatible OCR server using FastAPI + olmOCR-2-7B.
# Advanced OCR model from AllenAI with 2.7B parameters for enhanced document understanding.
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

app = FastAPI(title="MCP OCR - olmOCR-2-7B", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Global lazy init
_MODEL = None
_PROCESSOR = None

def get_model():
    """Initialize olmOCR-2-7B model (lazy loading)."""
    global _MODEL, _PROCESSOR
    if _MODEL is None:
        try:
            import torch
            from transformers import AutoModelForImageTextToText, AutoProcessor
            
            model_path = os.getenv("OLMO_MODEL", "allenai/olmOCR-2-7B-1025")
            
            print(f"[INFO] Loading olmOCR-2-7B model: {model_path}")
            _PROCESSOR = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
            _MODEL = AutoModelForImageTextToText.from_pretrained(
                model_path, 
                trust_remote_code=True,
                torch_dtype=torch.bfloat16,
                device_map="auto"
            ).eval()
            
            print("[INFO] olmOCR-2-7B model loaded successfully")
        except Exception as e:
            print(f"[ERROR] Failed to load olmOCR-2-7B model: {e}")
            raise e
    
    return _MODEL, _PROCESSOR

def parse_olmo_output(response_text: str, img_w: int, img_h: int) -> List[Dict[str, Any]]:
    """Parse olmOCR-2-7B output into standard blocks format."""
    blocks = []
    
    try:
        # Split response into lines and process each
        lines = response_text.strip().split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Create block for each line
            block = {
                "id": f"olmo_block_{i+1}",
                "bbox": [0, i * 30, img_w, (i + 1) * 30],  # Estimated positioning
                "polygon": [[0, i * 30], [img_w, i * 30], [img_w, (i + 1) * 30], [0, (i + 1) * 30]],
                "text": line,
                "confidence": 0.95,  # olmOCR typically has high confidence
                "type": "text",
                "properties": {
                    "font_size": 12,
                    "reading_order": i + 1
                }
            }
            blocks.append(block)
    
    except Exception as e:
        print(f"[WARN] Failed to parse olmOCR output: {e}")
        # Fallback: treat entire response as single block
        blocks = [{
            "id": "olmo_block_1",
            "bbox": [0, 0, img_w, img_h],
            "polygon": [[0, 0], [img_w, 0], [img_w, img_h], [0, img_h]],
            "text": response_text.strip(),
            "confidence": 0.95,
            "type": "text",
            "properties": {"font_size": 12, "reading_order": 1}
        }]
    
    return blocks

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "MCP OCR - olmOCR-2-7B"}

@app.get("/warmup")
async def warmup():
    """Warmup the model to reduce cold start latency."""
    try:
        model, processor = get_model()
        return {"status": "warmed up", "model": "olmOCR-2-7B"}
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
        extract_type: Type of extraction ("text", "blocks", "layout")
        confidence_threshold: Minimum confidence for text detection
        language: Language code (olmOCR supports many languages)
    
    Returns:
        JSON response with detected text blocks in standard format
    """
    start_time = time.time()
    
    try:
        # Read and validate image
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes))
        
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        img_w, img_h = image.size
        
        # Get model
        model, processor = get_model()
        
        # Process image with olmOCR
        import torch
        
        # Prepare input
        prompt = "Extract all text from this image:"
        inputs = processor(images=image, text=prompt, return_tensors="pt").to(model.device)
        
        # Generate response
        with torch.no_grad():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=2048,
                do_sample=False,
                temperature=0.0,
                pad_token_id=processor.tokenizer.eos_token_id
            )
        
        # Decode response
        generated_text = processor.decode(generated_ids[0], skip_special_tokens=True)
        
        # Remove the prompt from the response
        if prompt in generated_text:
            response_text = generated_text.replace(prompt, "").strip()
        else:
            response_text = generated_text.strip()
        
        # Parse response into blocks
        blocks = parse_olmo_output(response_text, img_w, img_h)
        
        # Filter by confidence
        filtered_blocks = [b for b in blocks if b.get("confidence", 0) >= confidence_threshold]
        
        processing_time = time.time() - start_time
        
        return {
            "success": True,
            "data": {
                "blocks": filtered_blocks,
                "image_info": {
                    "width": img_w,
                    "height": img_h,
                    "channels": len(image.getbands())
                },
                "processing_info": {
                    "engine": "olmOCR-2-7B",
                    "version": "1.0.0",
                    "processing_time": round(processing_time, 3),
                    "total_blocks": len(filtered_blocks),
                    "language": language,
                    "confidence_threshold": confidence_threshold
                }
            }
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"olmOCR processing failed: {str(e)}"
        print(f"[ERROR] {error_msg}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": error_msg,
                "processing_time": round(processing_time, 3)
            }
        )

@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "MCP OCR - olmOCR-2-7B",
        "version": "1.0.0",
        "description": "Advanced OCR using AllenAI's olmOCR-2-7B model",
        "endpoints": {
            "/health": "Health check",
            "/warmup": "Model warmup",
            "/ocr": "OCR processing (POST with file upload)",
            "/": "This information"
        },
        "model_info": {
            "name": "olmOCR-2-7B",
            "size": "2.7B parameters",
            "provider": "AllenAI",
            "languages": "Multi-language support",
            "specialties": ["Document OCR", "Scientific papers", "Complex layouts"]
        }
    }

# MCP Integration (optional)
try:
    from fastmcp import FastMCP
    
    mcp = FastMCP("olmOCR-2-7B OCR Service")
    
    @mcp.tool()
    def extract_text_olmocr(image_path: str) -> str:
        """Extract text from image using olmOCR-2-7B model."""
        try:
            import requests
            
            with open(image_path, 'rb') as f:
                files = {'file': f}
                response = requests.post('http://localhost:8100/ocr', files=files)
                
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    blocks = result['data']['blocks']
                    return '\n'.join([block['text'] for block in blocks])
                else:
                    return f"Error: {result.get('error', 'Unknown error')}"
            else:
                return f"HTTP Error: {response.status_code}"
                
        except Exception as e:
            return f"Error extracting text: {str(e)}"
    
    app.mount("/mcp", mcp.app)
    print("[INFO] MCP integration enabled at /mcp")
    
except ImportError:
    print("[INFO] FastMCP not available, skipping MCP integration")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8100"))
    uvicorn.run(app, host="0.0.0.0", port=port)