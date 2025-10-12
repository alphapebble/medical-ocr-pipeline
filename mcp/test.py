import os
os.environ['OMP_NUM_THREADS'] = '4'
from paddleocr import PaddleOCR
ocr = PaddleOCR(lang='en')
print("Init successful!")
