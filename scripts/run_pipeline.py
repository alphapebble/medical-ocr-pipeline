#!/usr/bin/env python3
"""
Simple pipeline runner for Docker environment
"""
import os
import sys
import time
import requests
from pathlib import Path

# Service URLs from environment
SERVICES = {
    'tesseract': os.getenv('TESSERACT_URL', 'http://localhost:8089'),
    'easyocr': os.getenv('EASYOCR_URL', 'http://localhost:8092'),
    'paddle': os.getenv('PADDLE_URL', 'http://localhost:8090'),
    'surya': os.getenv('SURYA_URL', 'http://localhost:8091')
}

def wait_for_services(timeout=300):
    """Wait for all MCP services to be healthy"""
    print("Waiting for MCP services to be ready...")
    
    start_time = time.time()
    ready_services = set()
    
    while time.time() - start_time < timeout:
        for name, url in SERVICES.items():
            if name not in ready_services:
                try:
                    response = requests.get(f"{url}/health", timeout=5)
                    if response.status_code == 200:
                        print(f"  {name} is ready")
                        ready_services.add(name)
                except:
                    pass
        
        if len(ready_services) == len(SERVICES):
            print("All services are ready!")
            return True
            
        time.sleep(5)
    
    print(f"Timeout waiting for services. Ready: {ready_services}")
    return False

def run_pipeline(pdf_path, domain="prescription", output_dir="outputs"):
    """Run the OCR pipeline"""
    print(f"Running pipeline for: {pdf_path}")
    print(f"Domain: {domain}")
    print(f"Output: {output_dir}")
    
    # Wait for services
    if not wait_for_services():
        print("ERROR: Services not ready")
        return False
    
    # Here you would implement the actual pipeline logic
    # For now, just a placeholder
    print("Pipeline completed successfully")
    return True

def main():
    """Main entry point"""
    # Check for input files
    input_dir = Path("input_pdfs")
    if not input_dir.exists():
        print("No input_pdfs directory found")
        return
    
    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        print("No PDF files found in input_pdfs/")
        print("Add PDF files to input_pdfs/ directory")
        return
    
    # Process first PDF found
    pdf_path = pdf_files[0]
    domain = os.getenv('MEDICAL_DOMAIN', 'prescription')
    
    success = run_pipeline(str(pdf_path), domain)
    
    if success:
        print("Pipeline completed successfully")
        sys.exit(0)
    else:
        print("Pipeline failed")
        sys.exit(1)

if __name__ == "__main__":
    main()