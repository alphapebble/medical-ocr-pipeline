# mcp_ocr_deepseek.py
# MCP-compatible OCR server using FastAPI + DeepSeek-OCR.
# Specialized 3B OCR model with context-based optical compression for documents.
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

app = FastAPI(title="MCP OCR - DeepSeek-OCR", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Global lazy init
_MODEL = None
_PROCESSOR = None

def get_model():
    """Initialize DeepSeek-OCR model (lazy loading)."""
    global _MODEL, _PROCESSOR
    if _MODEL is None:
        try:
            import torch
            from transformers import AutoModel, AutoProcessor
            
            model_path = os.getenv("DEEPSEEK_MODEL", "deepseek-ai/DeepSeek-OCR")
            
            print(f"[INFO] Loading DeepSeek-OCR model: {model_path}")
            _PROCESSOR = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
            _MODEL = AutoModel.from_pretrained(
                model_path, 
                trust_remote_code=True,
                torch_dtype=torch.bfloat16,
                device_map="auto"
            ).eval()
            
            print("[INFO] DeepSeek-OCR model loaded successfully")
        except Exception as e:
            print(f"[ERROR] Failed to load DeepSeek-OCR model: {e}")
            raise e
    
    return _MODEL, _PROCESSOR

def parse_deepseek_output(response_text: str, img_w: int, img_h: int) -> List[Dict[str, Any]]:
    """Parse DeepSeek-VL output into standard blocks format."""
    # DeepSeek-VL provides text description, we create a single block covering the whole image
    if not response_text or not response_text.strip():
        return []
    
    return [{
        "text": response_text.strip(),
        "confidence": 0.95,  # High confidence for vision-language model
        "bbox": [0, 0, img_w, img_h]  # Full image coverage
    }]

@app.get("/health")
async def health():
    try:
        _ = get_model()
        return {"ok": True, "engine": "deepseek-vl", "version": "7b-chat", "multimodal": True}
    except Exception as e:
        return {"ok": False, "engine": "deepseek-vl", "error": str(e)}

@app.get("/warmup")
async def warmup():
    """Warmup DeepSeek-VL with a synthetic conversation."""
    try:
        model, processor = get_model()
        
        # Create a simple test image
        test_img = Image.new("RGB", (200, 100), "white")
        from PIL import ImageDraw
        draw = ImageDraw.Draw(test_img)
        draw.text((10, 40), "Test text", fill="black")
        
        # Simple conversation for OCR
        conversation = [{
            "role": "User",
            "content": "Extract any text from this image.",
            "images": [test_img],
        }, {"role": "Assistant", "content": ""}]
        
        t0 = time.time()
        
        # Process with DeepSeek-VL
        from deepseek_vl.utils.io import load_pil_images
        pil_images = [test_img]  # Direct PIL images
        
        prepare_inputs = processor(
            conversations=conversation,
            images=pil_images,
            force_batchify=True
        ).to(model.device)
        
        inputs_embeds = model.prepare_inputs_embeds(**prepare_inputs)
        
        with torch.no_grad():
            outputs = model.language_model.generate(
                inputs_embeds=inputs_embeds,
                attention_mask=prepare_inputs.attention_mask,
                pad_token_id=processor.tokenizer.eos_token_id,
                bos_token_id=processor.tokenizer.bos_token_id,
                eos_token_id=processor.tokenizer.eos_token_id,
                max_new_tokens=128,
                do_sample=False,
                use_cache=True
            )
        
        dt = time.time() - t0
        return {"ok": True, "seconds": round(dt, 2), "model": "deepseek-vl-7b-chat"}
        
    except Exception as e:
        import traceback
        return JSONResponse(
            {"ok": False, "error": str(e), "traceback": traceback.format_exc()},
            status_code=500
        )

@app.post("/ocr")
async def ocr(image: UploadFile, lang: str = Form("en")):
    """
    Perform OCR using DeepSeek-VL vision-language model.
    
    Args:
        image: Uploaded image file
        lang: Language code (used for prompting, default: "en")
    
    Returns:
        JSON with engine, blocks (text, confidence, bbox), and optional error
    """
    try:
        model, processor = get_model()
    except Exception as e:
        return JSONResponse(
            {"blocks": [], "engine": "deepseek-vl", "error": str(e)},
            status_code=500
        )
    
    try:
        data = await image.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img_w, img_h = img.size
        
        # Create conversation for OCR task
        ocr_prompt = {
            "en": "Extract all text from this image. Provide the text content exactly as it appears.",
            "hi": "इस छवि से सभी पाठ निकालें। पाठ सामग्री को बिल्कुल वैसे ही प्रदान करें जैसे यह दिखाई देती है।",
            "te": "ఈ చిత్రం నుండి అన్ని వచనాన్ని సంగ్రహించండి। వచన కంటెంట్‌ను అది కనిపించే విధంగా అందించండి।",
            "ta": "இந்த படத்திலிருந்து அனைத்து உரையையும் பிரித்தெடுக்கவும். உரை உள்ளடக்கத்தை அது தோன்றும் வண்ணம் வழங்கவும்।",
            "mr": "या प्रतिमेतून सर्व मजकूर काढा. मजकूर सामग्री जशी दिसते तशीच प्रदान करा।"
        }.get(lang, "Extract all text from this image. Provide the text content exactly as it appears.")
        
        conversation = [{
            "role": "User",
            "content": ocr_prompt,
            "images": [img],
        }, {"role": "Assistant", "content": ""}]
        
        # Process with DeepSeek-VL
        import torch
        from deepseek_vl.utils.io import load_pil_images
        
        pil_images = [img]
        prepare_inputs = processor(
            conversations=conversation,
            images=pil_images,
            force_batchify=True
        ).to(model.device)
        
        inputs_embeds = model.prepare_inputs_embeds(**prepare_inputs)
        
        with torch.no_grad():
            outputs = model.language_model.generate(
                inputs_embeds=inputs_embeds,
                attention_mask=prepare_inputs.attention_mask,
                pad_token_id=processor.tokenizer.eos_token_id,
                bos_token_id=processor.tokenizer.bos_token_id,
                eos_token_id=processor.tokenizer.eos_token_id,
                max_new_tokens=512,
                do_sample=False,
                use_cache=True
            )
        
        # Decode response
        answer = processor.tokenizer.decode(outputs[0].cpu().tolist(), skip_special_tokens=True)
        # Extract only the assistant's response
        if "Assistant:" in answer:
            response_text = answer.split("Assistant:")[-1].strip()
        else:
            response_text = answer.strip()
        
        blocks = parse_deepseek_output(response_text, img_w, img_h)
        
        return {
            "engine": "deepseek-vl",
            "blocks": blocks,
            "meta": {
                "processing_time_s": 0.0,  # Not tracked in this simple version
                "language": lang,
                "total_blocks": len(blocks),
                "model": "deepseek-vl-7b-chat"
            }
        }
        
    except Exception as e:
        import traceback
        return JSONResponse(
            {"blocks": [], "engine": "deepseek-vl", "error": str(e), "traceback": traceback.format_exc()},
            status_code=500
        )

# Optional MCP mount
try:
    from fastmcp import FastMCP
    mcp = FastMCP.from_fastapi(app)
    app.mount("/mcp", mcp.http_app(path="/mcp"))
    print("[INFO] MCP mounted at /mcp (deepseek-vl)")
except Exception as e:
    print(f"[WARN] MCP not enabled for deepseek-vl: {e}")

if __name__ == "__main__":
    import os
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8095"))
    print(f"[INFO] Starting DeepSeek-VL OCR server on {host}:{port}")
    print("[INFO] Vision-Language model for document understanding and OCR")
    
    # Optional warmup on start
    if os.getenv("DEEPSEEK_WARMUP_ON_START", "0") == "1":
        try:
            import requests
            from threading import Thread
            def _bg_warm():
                import time
                time.sleep(5)  # Wait for server to start
                try:
                    requests.get(f"http://{host}:{port}/warmup", timeout=30)
                    print("[WARMUP] DeepSeek-VL warmup completed")
                except Exception as e:
                    print(f"[WARMUP] Failed: {e}")
            Thread(target=_bg_warm, daemon=True).start()
        except Exception as e:
            print(f"[WARMUP] not scheduled: {e}")
    
    uvicorn.run(app, host=host, port=port)