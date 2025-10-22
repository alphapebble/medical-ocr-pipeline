# mcp_ocr_qwen.py
# MCP-compatible OCR server using FastAPI + Qwen3-VL.
# Latest vision-language model with enhanced OCR capabilities for 32 languages.
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

app = FastAPI(title="MCP OCR - Qwen3-VL", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Global lazy init
_MODEL = None
_PROCESSOR = None

def get_model():
    """Initialize Qwen3-VL model (lazy loading)."""
    global _MODEL, _PROCESSOR
    if _MODEL is None:
        try:
            import torch
            from transformers import AutoModelForImageTextToText, AutoProcessor
            
            model_path = os.getenv("QWEN_MODEL", "Qwen/Qwen3-VL-8B-Instruct")
            
            print(f"[INFO] Loading Qwen3-VL model: {model_path}")
            _PROCESSOR = AutoProcessor.from_pretrained(model_path)
            _MODEL = AutoModelForImageTextToText.from_pretrained(
                model_path,
                torch_dtype=torch.bfloat16,
                attn_implementation="flash_attention_2",
                device_map="auto"
            ).eval()
            
            print("[INFO] Qwen3-VL model loaded successfully")
        except Exception as e:
            print(f"[ERROR] Failed to load Qwen3-VL model: {e}")
            raise e
    
    return _MODEL, _PROCESSOR

def parse_qwen_output(response_text: str, img_w: int, img_h: int) -> List[Dict[str, Any]]:
    """Parse Qwen3-VL output into standard blocks format."""
    if not response_text or not response_text.strip():
        return []
    
    # Split text into lines for better granularity
    lines = [line.strip() for line in response_text.strip().split('\n') if line.strip()]
    blocks = []
    
    if not lines:
        return []
    
    # If only one line, return full image block
    if len(lines) == 1:
        return [{
            "text": lines[0],
            "confidence": 0.95,
            "bbox": [0, 0, img_w, img_h]
        }]
    
    # Multiple lines - distribute vertically
    line_height = img_h // len(lines)
    for i, line in enumerate(lines):
        y_start = i * line_height
        y_end = min((i + 1) * line_height, img_h)
        
        blocks.append({
            "text": line,
            "confidence": 0.95,
            "bbox": [0, y_start, img_w, y_end]
        })
    
    return blocks

@app.get("/health")
async def health():
    try:
        _ = get_model()
        return {"ok": True, "engine": "qwen3-vl", "version": "8B-Instruct", "languages": 32, "multimodal": True}
    except Exception as e:
        return {"ok": False, "engine": "qwen3-vl", "error": str(e)}

@app.get("/warmup")
async def warmup():
    """Warmup Qwen3-VL with a synthetic image."""
    try:
        model, processor = get_model()
        
        # Create a simple test image
        test_img = Image.new("RGB", (200, 100), "white")
        from PIL import ImageDraw
        draw = ImageDraw.Draw(test_img)
        draw.text((10, 40), "Test OCR", fill="black")
        
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": test_img},
                {"type": "text", "text": "Extract all text from this image."}
            ]
        }]
        
        t0 = time.time()
        
        # Process with Qwen3-VL
        import torch
        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt"
        ).to(model.device)
        
        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=64)
            generated_ids_trimmed = [
                out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]
            response = processor.batch_decode(
                generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )
        
        dt = time.time() - t0
        return {"ok": True, "seconds": round(dt, 2), "model": "qwen3-vl-8b-instruct", "response": response[0] if response else ""}
        
    except Exception as e:
        import traceback
        return JSONResponse(
            {"ok": False, "error": str(e), "traceback": traceback.format_exc()},
            status_code=500
        )

@app.post("/ocr")
async def ocr(image: UploadFile, lang: str = Form("en")):
    """
    Perform OCR using Qwen3-VL vision-language model.
    
    Args:
        image: Uploaded image file
        lang: Language code (supports 32 languages, default: "en")
    
    Returns:
        JSON with engine, blocks (text, confidence, bbox), and optional error
    """
    try:
        model, processor = get_model()
    except Exception as e:
        return JSONResponse(
            {"blocks": [], "engine": "qwen3-vl", "error": str(e)},
            status_code=500
        )
    
    try:
        data = await image.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img_w, img_h = img.size
        
        # Create optimized prompt for OCR task based on language
        lang_prompts = {
            "en": "Extract all text from this image. Provide only the text content, preserving line breaks and layout.",
            "hi": "इस छवि से सभी पाठ निकालें। केवल पाठ सामग्री प्रदान करें, लाइन ब्रेक और लेआउट को संरक्षित करते हुए।",
            "te": "ఈ చిత్రం నుండి అన్ని వచనాన్ని సంగ్రహించండి। లైన్ బ్రేక్‌లు మరియు లేఅవుట్‌ను సంరక్షిస్తూ వచన కంటెంట్‌ను మాత్రమే అందించండి।",
            "ta": "இந்த படத்திலிருந்து அனைத்து உரையையும் பிரித்தெடுக்கவும். வரி முறிவுகள் மற்றும் தளவமைப்பைப் பாதுகாத்து, உரை உள்ளடக்கத்தை மட்டும் வழங்கவும்।",
            "mr": "या प्रतिमेतून सर्व मजकूर काढा. रेषा खंड आणि मांडणी जतन करून केवळ मजकूर सामग्री प्रदान करा।",
            "zh": "从这张图片中提取所有文本。只提供文本内容，保持换行和布局。",
            "ja": "この画像からすべてのテキストを抽出してください。改行とレイアウトを保持して、テキストコンテンツのみを提供してください。",
            "ko": "이 이미지에서 모든 텍스트를 추출하세요. 줄 바꿈과 레이아웃을 유지하면서 텍스트 내용만 제공하세요.",
            "ar": "استخرج كل النص من هذه الصورة. قدم محتوى النص فقط، مع الحفاظ على فواصل الأسطر والتخطيط.",
            "fr": "Extrayez tout le texte de cette image. Fournissez uniquement le contenu textuel, en préservant les sauts de ligne et la mise en page.",
            "de": "Extrahieren Sie den gesamten Text aus diesem Bild. Geben Sie nur den Textinhalt an und bewahren Sie Zeilenumbrüche und das Layout.",
            "es": "Extrae todo el texto de esta imagen. Proporciona solo el contenido del texto, conservando los saltos de línea y el diseño.",
            "pt": "Extraia todo o texto desta imagem. Forneça apenas o conteúdo do texto, preservando quebras de linha e layout.",
            "ru": "Извлеките весь текст из этого изображения. Предоставьте только текстовое содержимое, сохраняя разрывы строк и макет.",
            "it": "Estrai tutto il testo da questa immagine. Fornisci solo il contenuto del testo, preservando interruzioni di riga e layout."
        }
        
        ocr_prompt = lang_prompts.get(lang, lang_prompts["en"])
        
        messages = [{
            "role": "user", 
            "content": [
                {"type": "image", "image": img},
                {"type": "text", "text": ocr_prompt}
            ]
        }]
        
        # Process with Qwen3-VL
        import torch
        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt"
        ).to(model.device)
        
        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=512)
            generated_ids_trimmed = [
                out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]
            output_text = processor.batch_decode(
                generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )
        
        response_text = output_text[0] if output_text else ""
        blocks = parse_qwen_output(response_text, img_w, img_h)
        
        return {
            "engine": "qwen3-vl",
            "blocks": blocks,
            "meta": {
                "processing_time_s": 0.0,  # Not tracked in this simple version
                "language": lang,
                "total_blocks": len(blocks),
                "model": "qwen3-vl-8b-instruct",
                "enhanced_ocr": True,
                "supported_languages": 32
            }
        }
        
    except Exception as e:
        import traceback
        return JSONResponse(
            {"blocks": [], "engine": "qwen3-vl", "error": str(e), "traceback": traceback.format_exc()},
            status_code=500
        )

# Optional MCP mount
try:
    from fastmcp import FastMCP
    mcp = FastMCP.from_fastapi(app)
    app.mount("/mcp", mcp.http_app(path="/mcp"))
    print("[INFO] MCP mounted at /mcp (qwen3-vl)")
except Exception as e:
    print(f"[WARN] MCP not enabled for qwen3-vl: {e}")

if __name__ == "__main__":
    import os
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8096"))
    print(f"[INFO] Starting Qwen3-VL OCR server on {host}:{port}")
    print("[INFO] Enhanced OCR with 32 language support, spatial understanding, and advanced reasoning")
    
    # Optional warmup on start
    if os.getenv("QWEN_WARMUP_ON_START", "0") == "1":
        try:
            import requests
            from threading import Thread
            def _bg_warm():
                import time
                time.sleep(5)  # Wait for server to start
                try:
                    requests.get(f"http://{host}:{port}/warmup", timeout=60)
                    print("[WARMUP] Qwen3-VL warmup completed")
                except Exception as e:
                    print(f"[WARMUP] Failed: {e}")
            Thread(target=_bg_warm, daemon=True).start()
        except Exception as e:
            print(f"[WARMUP] not scheduled: {e}")
    
    uvicorn.run(app, host=host, port=port)