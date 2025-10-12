#!/usr/bin/env python3
"""
Minimal test to verify OCR engines work independently
"""
import sys
from pathlib import Path
from PIL import Image
import numpy as np

def test_paddleocr(image_path):
    """Test PaddleOCR directly"""
    print("\n" + "="*60)
    print("Testing PaddleOCR directly")
    print("="*60)
    
    try:
        from paddleocr import PaddleOCR
        print("✅ PaddleOCR imported successfully")
        
        print("Initializing PaddleOCR...")
        # Minimal initialization for newer versions
        ocr = PaddleOCR(lang='en')
        print("✅ PaddleOCR initialized")
        
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
                print(f"✅ PDF converted: {img.size}")
            except ImportError:
                print("❌ pypdfium2 not installed. Install with: pip install pypdfium2")
                return False
        else:
            img = Image.open(image_path).convert('RGB')
        
        arr = np.array(img)
        print(f"✅ Image loaded: {arr.shape}")
        
        print("Running OCR...")
        # Newer PaddleOCR versions use predict() without cls parameter
        result = ocr.ocr(arr)
        print(f"✅ OCR completed")
        
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
        print(f"❌ PaddleOCR not installed: {e}")
        print("Install with: pip install paddleocr")
        return False
    except Exception as e:
        print(f"❌ PaddleOCR failed: {e}")
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
        print("✅ Surya imported successfully")
        
        print("Initializing Surya (this may take a while)...")
        foundation_predictor = FoundationPredictor(device='cpu', dtype=torch.float32)
        recognition_predictor = RecognitionPredictor(foundation_predictor)
        detection_predictor = DetectionPredictor(device='cpu', dtype=torch.float32)
        print("✅ Surya initialized")
        
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
                print(f"✅ PDF converted: {img.size}")
            except ImportError:
                print("❌ pypdfium2 not installed. Install with: pip install pypdfium2")
                return False
        else:
            img = Image.open(image_path).convert('RGB')
        
        print(f"✅ Image loaded: {img.size}")
        
        print("Running OCR...")
        # Use task name 'ocr_with_boxes', not language code!
        predictions = recognition_predictor(
            [img],
            ['ocr_with_boxes'],  # Task name, not language!
            det_predictor=detection_predictor
        )
        print(f"✅ OCR completed")
        
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
        print(f"❌ Surya not installed: {e}")
        print("Install with: pip install surya-ocr")
        return False
    except Exception as e:
        print(f"❌ Surya failed: {e}")
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
    
    print("🔍 OCR Engine Direct Test")
    print(f"Image: {image_path}")
    
    results = {
        'PaddleOCR': test_paddleocr(image_path),
        'Surya': test_surya(image_path)
    }
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{name:20s} {status}")

if __name__ == "__main__":
    main()