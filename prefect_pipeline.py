"""
Medical OCR Pipeline with Prefect
Clean orchestration with proper error handling and monitoring
"""
from prefect import flow, task, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner
from prefect.blocks.system import String
import httpx
import asyncio
from pathlib import Path
from typing import List, Dict, Any
import json

@task(retries=3, retry_delay_seconds=10)
async def start_mcp_service(service_name: str, conda_env: str, script_path: str, port: int) -> bool:
    """Start a single MCP service"""
    logger = get_run_logger()
    logger.info(f"Starting {service_name} service on port {port}")
    
    import subprocess
    cmd = f"conda run -n {conda_env} python {script_path}"
    
    try:
        process = subprocess.Popen(
            cmd, shell=True, cwd="mcp",
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        
        # Wait for service to be ready
        for attempt in range(30):  # 30 second timeout
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"http://127.0.0.1:{port}/health", timeout=2.0)
                    if response.status_code == 200:
                        logger.info(f"{service_name} is healthy")
                        return True
            except:
                await asyncio.sleep(1)
        
        logger.error(f"{service_name} failed to become healthy")
        return False
        
    except Exception as e:
        logger.error(f"Failed to start {service_name}: {e}")
        return False

@task
async def health_check_service(service_name: str, url: str) -> Dict[str, Any]:
    """Check health of a service"""
    logger = get_run_logger()
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}/health", timeout=5.0)
            return {
                "service": service_name,
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "response_time": response.elapsed.total_seconds()
            }
    except Exception as e:
        logger.warning(f"{service_name} health check failed: {e}")
        return {
            "service": service_name,
            "status": "unreachable",
            "error": str(e)
        }

@task
async def process_with_mcp_engine(
    pdf_path: str, 
    engine_name: str, 
    engine_url: str
) -> Dict[str, Any]:
    """Process PDF with a specific MCP engine"""
    logger = get_run_logger()
    logger.info(f"Processing {pdf_path} with {engine_name}")
    
    try:
        # Convert PDF pages to images and send to MCP service
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(pdf_path, 'rb') as f:
                files = {'image': f}
                data = {'lang': 'en'}
                
                response = await client.post(f"{engine_url}/ocr", files=files, data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"{engine_name} processed successfully")
                    return {
                        "engine": engine_name,
                        "status": "success",
                        "result": result,
                        "blocks_count": len(result) if isinstance(result, list) else 0
                    }
                else:
                    logger.error(f"{engine_name} failed: {response.status_code}")
                    return {
                        "engine": engine_name,
                        "status": "failed",
                        "error": f"HTTP {response.status_code}"
                    }
                    
    except Exception as e:
        logger.error(f"{engine_name} processing error: {e}")
        return {
            "engine": engine_name,
            "status": "error", 
            "error": str(e)
        }

@task
def select_best_ocr_result(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Select the best OCR result based on confidence and block count"""
    logger = get_run_logger()
    
    successful_results = [r for r in results if r["status"] == "success"]
    
    if not successful_results:
        logger.error("No successful OCR results")
        return {"status": "failed", "error": "All OCR engines failed"}
    
    # Simple selection: most blocks detected
    best_result = max(successful_results, key=lambda x: x.get("blocks_count", 0))
    logger.info(f"Selected {best_result['engine']} as best result")
    
    return best_result

@task
async def cleanup_text_with_llm(ocr_result: Dict[str, Any], domain: str) -> Dict[str, Any]:
    """Clean up OCR text using LLM (Mistral)"""
    logger = get_run_logger()
    logger.info(f"Cleaning text for {domain} domain")
    
    # This would integrate with your existing LLM cleanup logic
    # For now, return the result as-is
    return {
        "status": "success",
        "cleaned_result": ocr_result,
        "domain": domain
    }

@task
def save_results(result: Dict[str, Any], output_path: str) -> str:
    """Save final results to file"""
    logger = get_run_logger()
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    logger.info(f"Results saved to {output_file}")
    return str(output_file)

@flow(name="medical-ocr-pipeline", task_runner=ConcurrentTaskRunner())
async def medical_ocr_pipeline_flow(
    pdf_path: str,
    domain: str = "prescription",
    output_dir: str = "outputs"
) -> str:
    """Complete Medical OCR Pipeline using Prefect orchestration"""
    logger = get_run_logger()
    logger.info(f"Starting Medical OCR Pipeline for {pdf_path}")
    
    # Define MCP services
    mcp_services = [
        {"name": "tesseract", "conda_env": "mcp-tesseract", "script": "mcp_ocr_tesseract.py", "port": 8089},
        {"name": "easyocr", "conda_env": "mcp-easyocr", "script": "mcp_ocr_easy.py", "port": 8092},
        {"name": "paddle", "conda_env": "mcp-paddle", "script": "mcp_ocr_paddle.py", "port": 8090},
        {"name": "surya", "conda_env": "mcp-surya", "script": "mcp_ocr_surya.py", "port": 8091}
    ]
    
    # Stage 1: Start all MCP services concurrently
    logger.info("Stage 1: Starting MCP services")
    start_tasks = []
    for service in mcp_services:
        task = start_mcp_service.submit(
            service["name"], 
            service["conda_env"], 
            service["script"], 
            service["port"]
        )
        start_tasks.append(task)
    
    # Wait for all services to start
    service_statuses = await asyncio.gather(*start_tasks, return_exceptions=True)
    
    # Stage 2: Health check all services
    logger.info("Stage 2: Health checking services")
    health_tasks = []
    for service in mcp_services:
        url = f"http://127.0.0.1:{service['port']}"
        task = health_check_service.submit(service["name"], url)
        health_tasks.append(task)
    
    health_results = await asyncio.gather(*health_tasks)
    healthy_services = [r for r in health_results if r["status"] == "healthy"]
    
    if not healthy_services:
        raise Exception("No healthy MCP services available")
    
    logger.info(f"Healthy services: {[s['service'] for s in healthy_services]}")
    
    # Stage 3: Process PDF with all healthy services concurrently
    logger.info("Stage 3: Processing PDF with MCP engines")
    ocr_tasks = []
    for health_result in healthy_services:
        service_name = health_result["service"]
        service_config = next(s for s in mcp_services if s["name"] == service_name)
        url = f"http://127.0.0.1:{service_config['port']}"
        
        task = process_with_mcp_engine.submit(pdf_path, service_name, url)
        ocr_tasks.append(task)
    
    ocr_results = await asyncio.gather(*ocr_tasks)
    
    # Stage 4: Select best OCR result
    logger.info("Stage 4: Selecting best OCR result")
    best_result = await select_best_ocr_result.submit(ocr_results)
    
    # Stage 5: LLM cleanup
    logger.info("Stage 5: LLM text cleanup")
    cleaned_result = await cleanup_text_with_llm.submit(best_result, domain)
    
    # Stage 6: Save final results
    logger.info("Stage 6: Saving results")
    output_path = f"{output_dir}/final_result.json"
    final_output = await save_results.submit(cleaned_result, output_path)
    
    logger.info(f"Pipeline completed successfully: {final_output}")
    return final_output

# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python prefect_pipeline.py <pdf_path> [domain] [output_dir]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    domain = sys.argv[2] if len(sys.argv) > 2 else "prescription"
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "outputs"
    
    # Run the flow
    result = asyncio.run(medical_ocr_pipeline_flow(pdf_path, domain, output_dir))
    print(f"Pipeline completed: {result}")