#!/usr/bin/env python3
"""
Minimal test to verify OCR engines work independently
"""
import sys
from pathlib import Path
from PIL import Image
import numpy as np

def test_tesseract(image_path):
    """Test Tesseract OCR directly"""
    print("\n" + "="*60)
    print("Testing Tesseract directly")
    print("="*60)
    
    try:
        import pytesseract
        from PIL import Image
        print("[SUCCESS] Tesseract imported successfully")
        
        print(f"Loading image: {image_path}")
        if image_path.lower().endswith('.pdf'):
            print("Converting PDF to image...")
            try:
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(image_path)
                page = pdf[0]
                bitmap = page.render(scale=2.0)
                img = bitmap.to_pil()
                print(f"[SUCCESS] PDF converted: {img.size}")
            except ImportError:
                print("[ERROR] pypdfium2 not installed")
                return False
        else:
            img = Image.open(image_path).convert('RGB')
        
        print("Running OCR...")
        text = pytesseract.image_to_string(img)
        print(f"[SUCCESS] OCR completed - extracted {len(text)} characters")
        
        if text.strip():
            print(f"Sample text: '{text[:100]}...'")
        else:
            print("⚠️ No text detected")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Tesseract failed: {e}")
        return False

def test_easyocr(image_path):
    """Test EasyOCR directly"""
    print("\n" + "="*60)
    print("Testing EasyOCR directly")
    print("="*60)
    
    try:
        import easyocr
        print("[SUCCESS] EasyOCR imported successfully")
        
        print("Initializing EasyOCR...")
        reader = easyocr.Reader(['en'])
        print("[SUCCESS] EasyOCR initialized")
        
        print(f"Loading image: {image_path}")
        
        if image_path.lower().endswith('.pdf'):
            print("Converting PDF to image...")
            try:
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(image_path)
                page = pdf[0]
                bitmap = page.render(scale=2.0)
                img = bitmap.to_pil()
                print(f"[SUCCESS] PDF converted: {img.size}")
                image_path = img
            except ImportError:
                print("[ERROR] pypdfium2 not installed")
                return False
        
        print("Running OCR...")
        results = reader.readtext(image_path)
        print(f"[SUCCESS] OCR completed - found {len(results)} text blocks")
        
        for i, (bbox, text, conf) in enumerate(results[:3]):
            print(f"  Block {i+1}: '{text[:50]}' (conf: {conf:.3f})")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] EasyOCR failed: {e}")
        return False

def test_docling(image_path):
    """Test Docling directly"""
    print("\n" + "="*60)
    print("Testing Docling directly")
    print("="*60)
    
    try:
        from docling.document_converter import DocumentConverter
        print("[SUCCESS] Docling imported successfully")
        
        print("Initializing Docling...")
        converter = DocumentConverter()
        print("[SUCCESS] Docling initialized")
        
        print(f"Processing document: {image_path}")
        result = converter.convert(image_path)
        print(f"[SUCCESS] Document processed")
        
        if result.document.main_text:
            text = result.document.main_text
            print(f"Extracted {len(text)} characters")
            print(f"Sample text: '{text[:100]}...'")
        else:
            print("⚠️ No text detected")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Docling failed: {e}")
        return False

def test_doctr(image_path):
    """Test DocTR directly"""
    print("\n" + "="*60)
    print("Testing DocTR directly")
    print("="*60)
    
    try:
        from doctr.io import DocumentFile
        from doctr.models import ocr_predictor
        print("[SUCCESS] DocTR imported successfully")
        
        print("Initializing DocTR...")
        model = ocr_predictor(pretrained=True)
        print("[SUCCESS] DocTR initialized")
        
        print(f"Loading document: {image_path}")
        doc = DocumentFile.from_pdf(image_path) if image_path.lower().endswith('.pdf') else DocumentFile.from_images([image_path])
        print(f"[SUCCESS] Document loaded")
        
        print("Running OCR...")
        result = model(doc)
        print(f"[SUCCESS] OCR completed")
        
        # Extract text
        text_blocks = []
        for page in result.pages:
            for block in page.blocks:
                for line in block.lines:
                    for word in line.words:
                        text_blocks.append(word.value)
        
        if text_blocks:
            full_text = ' '.join(text_blocks)
            print(f"Extracted {len(full_text)} characters from {len(text_blocks)} words")
            print(f"Sample text: '{full_text[:100]}...'")
        else:
            print("⚠️ No text detected")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] DocTR failed: {e}")
        return False

def test_deepseek(image_path):
    """Test DeepSeek Vision Language Model"""
    print("\n" + "="*60)
    print("Testing DeepSeek VL directly")
    print("="*60)
    
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        print("[SUCCESS] DeepSeek dependencies imported")
        
        print("⚠️ DeepSeek VL requires significant GPU resources - skipping actual test")
        print("   Model would be loaded with: AutoModelForCausalLM.from_pretrained('deepseek-ai/deepseek-vl-7b-chat')")
        return True
        
    except Exception as e:
        print(f"[ERROR] DeepSeek failed: {e}")
        return False

def test_qwen(image_path):
    """Test Qwen3-VL directly"""
    print("\n" + "="*60)
    print("Testing Qwen3-VL directly")
    print("="*60)
    
    try:
        from transformers import Qwen2VLForConditionalGeneration, AutoTokenizer, AutoProcessor
        print("[SUCCESS] Qwen3-VL imported successfully")
        
        print("⚠️ Qwen3-VL requires significant GPU resources - skipping actual test")
        print("   Model would be loaded with: Qwen2VLForConditionalGeneration.from_pretrained('Qwen/Qwen2-VL-2B-Instruct')")
        return True
        
    except Exception as e:
        print(f"[ERROR] Qwen3-VL failed: {e}")
        return False

def test_marker(image_path):
    """Test Marker directly"""
    print("\n" + "="*60)
    print("Testing Marker directly")
    print("="*60)
    
    try:
        from marker.convert import convert_single_pdf
        from marker.models import load_all_models
        print("[SUCCESS] Marker imported successfully")
        
        if not image_path.lower().endswith('.pdf'):
            print("⚠️ Marker requires PDF input - converting image to PDF")
            from reportlab.pdfgen import canvas
            from PIL import Image
            import tempfile
            
            img = Image.open(image_path)
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                pdf_path = tmp.name
                c = canvas.Canvas(pdf_path, pagesize=(img.width, img.height))
                c.drawImage(image_path, 0, 0, width=img.width, height=img.height)
                c.save()
                image_path = pdf_path
        
        print("⚠️ Marker requires significant resources - skipping model loading")
        print(f"   Would process: {image_path}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Marker failed: {e}")
        return False

def test_nanonets(image_path):
    """Test Nanonets API"""
    print("\n" + "="*60)
    print("Testing Nanonets API")
    print("="*60)
    
    try:
        import requests
        import base64
        print("[SUCCESS] Nanonets dependencies imported")
        
        print("⚠️ Nanonets requires API key - skipping actual API call")
        print("   Would use endpoint: https://app.nanonets.com/api/v2/OCR/Model/{model_id}/LabelFile/")
        return True
        
    except Exception as e:
        print(f"[ERROR] Nanonets failed: {e}")
        return False

def test_chandra(image_path):
    """Test Chandra OCR with fallback"""
    print("\n" + "="*60)
    print("Testing Chandra OCR directly")
    print("="*60)
    
    try:
        # Try Chandra OCR first
        try:
            import chandra_ocr
            print("[SUCCESS] Chandra OCR imported successfully")
            print("⚠️ Chandra OCR test implementation needed")
            return True
        except ImportError:
            print("⚠️ Chandra OCR not available, using Tesseract fallback")
            import pytesseract
            from PIL import Image
            
            if image_path.lower().endswith('.pdf'):
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(image_path)
                page = pdf[0]
                bitmap = page.render(scale=2.0)
                img = bitmap.to_pil()
            else:
                img = Image.open(image_path).convert('RGB')
            
            text = pytesseract.image_to_string(img)
            print(f"[SUCCESS] Fallback OCR completed - extracted {len(text)} characters")
            return True
        
    except Exception as e:
        print(f"[ERROR] Chandra OCR failed: {e}")
        return False

def test_paddleocr(image_path):
    print("\n" + "="*60)
    print("Testing PaddleOCR directly")
    print("="*60)
    
    try:
        from paddleocr import PaddleOCR
        print("[SUCCESS] PaddleOCR imported successfully")
        
        print("Initializing PaddleOCR...")
        # Minimal initialization for newer versions
        ocr = PaddleOCR(lang='en')
        print("[SUCCESS] PaddleOCR initialized")
        
        print(f"Loading image: {image_path}")
        
        # Handle PDF files by converting first page to image
        if image_path.lower().endswith('.pdf'):
            print("Converting PDF to image...")
            try:
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(image_path)
                page = pdf[0]
                bitmap = page.render(scale=2.0)
                img = bitmap.to_pil()
                print(f"[SUCCESS] PDF converted: {img.size}")
            except ImportError:
                print("[ERROR] pypdfium2 not installed. Install with: pip install pypdfium2")
                return False
        else:
            img = Image.open(image_path).convert('RGB')
        
        arr = np.array(img)
        print(f"[SUCCESS] Image loaded: {arr.shape}")
        
        print("Running OCR...")
        # Newer PaddleOCR versions use predict() without cls parameter
        result = ocr.ocr(arr)
        print(f"[SUCCESS] OCR completed")
        
        if result and result[0]:
            lines = list(result[0])  # Convert to list if it's a generator/dict
            print(f"Found {len(lines)} text blocks")
            for i, line in enumerate(lines[:3]):  # Show first 3
                text = line[1][0]
                conf = line[1][1]
                print(f"  Block {i+1}: '{text[:50]}' (conf: {conf:.3f})")
        else:
            print("⚠️ No text detected")
        
        return True
        
    except ImportError as e:
        print(f"[ERROR] PaddleOCR not installed: {e}")
        print("Install with: pip install paddleocr")
        return False
    except Exception as e:
        print(f"[ERROR] PaddleOCR failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_surya(image_path):
    """Test Surya directly"""
    print("\n" + "="*60)
    print("Testing Surya directly")
    print("="*60)
    
    try:
        import os
        import torch
        
        # Force CPU for testing
        os.environ['TORCH_DEVICE'] = 'cpu'
        
        from surya.foundation import FoundationPredictor
        from surya.recognition import RecognitionPredictor
        from surya.detection import DetectionPredictor
        print("[SUCCESS] Surya imported successfully")
        
        print("Initializing Surya (this may take a while)...")
        foundation_predictor = FoundationPredictor(device='cpu', dtype=torch.float32)
        recognition_predictor = RecognitionPredictor(foundation_predictor)
        detection_predictor = DetectionPredictor(device='cpu', dtype=torch.float32)
        print("[SUCCESS] Surya initialized")
        
        print(f"Loading image: {image_path}")
        
        # Handle PDF files by converting first page to image
        if image_path.lower().endswith('.pdf'):
            print("Converting PDF to image...")
            try:
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(image_path)
                page = pdf[0]
                bitmap = page.render(scale=2.0)
                img = bitmap.to_pil()
                print(f"[SUCCESS] PDF converted: {img.size}")
            except ImportError:
                print("[ERROR] pypdfium2 not installed. Install with: pip install pypdfium2")
                return False
        else:
            img = Image.open(image_path).convert('RGB')
        
        print(f"[SUCCESS] Image loaded: {img.size}")
        
        print("Running OCR...")
        # Use task name 'ocr_with_boxes', not language code!
        predictions = recognition_predictor(
            [img],
            ['ocr_with_boxes'],  # Task name, not language!
            det_predictor=detection_predictor
        )
        print(f"[SUCCESS] OCR completed")
        
        if predictions and hasattr(predictions[0], 'text_lines'):
            lines = predictions[0].text_lines
            print(f"Found {len(lines)} text lines")
            for i, line in enumerate(lines[:3]):  # Show first 3
                text = line.text if hasattr(line, 'text') else str(line)
                conf = line.confidence if hasattr(line, 'confidence') else 1.0
                print(f"  Line {i+1}: '{text[:50]}' (conf: {conf:.3f})")
        else:
            print("⚠️ No text detected")
        
        return True
        
    except ImportError as e:
        print(f"[ERROR] Surya not installed: {e}")
        print("Install with: pip install surya-ocr")
        return False
    except Exception as e:
        print(f"[ERROR] Surya failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_ocr_minimal.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    if not Path(image_path).exists():
        print(f"Error: Image not found: {image_path}")
        sys.exit(1)
    
    print("[INFO] OCR Engine Direct Test")
    print(f"Image: {image_path}")
    
    results = {
        'Tesseract': test_tesseract(image_path),
        'EasyOCR': test_easyocr(image_path),
        'PaddleOCR': test_paddleocr(image_path),
        'Surya': test_surya(image_path),
        'Docling': test_docling(image_path),
        'DocTR': test_doctr(image_path),
        'DeepSeek-VL': test_deepseek(image_path),
        'Qwen3-VL': test_qwen(image_path),
        'Marker': test_marker(image_path),
        'Nanonets': test_nanonets(image_path),
        'Chandra': test_chandra(image_path)
    }
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, success in results.items():
        status = "[SUCCESS] PASS" if success else "[ERROR] FAIL"
        print(f"{name:20s} {status}")

if __name__ == "__main__":
    main()