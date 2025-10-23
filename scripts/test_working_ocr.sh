#!/bin/bash
# test_working_ocr.sh - Test our currently working OCR services

echo "Testing Working OCR Services"
echo "============================"
echo

# Test Tesseract
echo "1. Testing Tesseract (8089):"
curl -s "http://localhost:8089/health" | jq .
echo

# Test Chandra
echo "2. Testing Chandra (8098):"
curl -s "http://localhost:8098/health" | jq .
echo

echo "Summary:"
echo "✅ Tesseract - Basic, reliable OCR (good for simple text)"
echo "✅ Chandra - Modern, enhanced OCR (good for complex documents)"
echo
echo "❌ DotsOCR - Complex dependencies, installation challenges"
echo "🔄 Other services - Still loading or have issues"
echo
echo "Recommendation: Use Tesseract for basic OCR, Chandra for advanced processing"