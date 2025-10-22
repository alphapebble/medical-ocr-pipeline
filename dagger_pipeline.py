"""
Medical OCR Pipeline with Dagger
Modern orchestration for MCP services
"""
import dagger
from dagger import dag, function, object_type, field
from typing import List, Optional
import asyncio

@object_type
class MedicalOcrPipeline:
    """Medical OCR Pipeline using Dagger for orchestration"""

    @function
    async def build_mcp_services(self) -> List[dagger.Service]:
        """Build all MCP OCR services"""
        services = []
        
        # Define MCP services
        mcp_configs = [
            {"name": "tesseract", "port": 8089, "dockerfile": "Dockerfile.tesseract"},
            {"name": "easyocr", "port": 8092, "dockerfile": "Dockerfile.easyocr"},
            {"name": "paddle", "port": 8090, "dockerfile": "Dockerfile.paddle"},
            {"name": "surya", "port": 8091, "dockerfile": "Dockerfile.surya"}
        ]
        
        for config in mcp_configs:
            # Build container for each MCP service
            container = (
                dag.container()
                .from_("python:3.11-slim")
                .with_directory("/app", dag.host().directory("./mcp"))
                .with_workdir("/app")
                .with_exec(["pip", "install", "-r", "requirements.txt"])
                .with_exec(["python", f"mcp_ocr_{config['name']}.py"])
                .with_exposed_port(config["port"])
            )
            
            # Create service
            service = container.as_service()
            services.append(service)
            
        return services

    @function
    async def run_ocr_pipeline(
        self, 
        pdf_path: str,
        domain: str = "prescription",
        output_dir: str = "outputs"
    ) -> dagger.Directory:
        """Run the complete OCR pipeline"""
        
        # Start MCP services
        mcp_services = await self.build_mcp_services()
        
        # Build pipeline runner
        pipeline_container = (
            dag.container()
            .from_("python:3.11-slim")
            .with_directory("/app", dag.host().directory("."))
            .with_workdir("/app")
            .with_exec(["pip", "install", "-r", "requirements.txt"])
            .with_file(f"/app/input.pdf", dag.host().file(pdf_path))
        )
        
        # Configure service endpoints
        for i, service in enumerate(mcp_services):
            service_name = ["tesseract", "easyocr", "paddle", "surya"][i]
            port = [8089, 8092, 8090, 8091][i]
            pipeline_container = pipeline_container.with_service_binding(
                f"mcp-{service_name}", service
            ).with_env_variable(
                f"{service_name.upper()}_URL", 
                f"http://mcp-{service_name}:{port}"
            )
        
        # Run pipeline stages
        result = await (
            pipeline_container
            .with_exec([
                "python", "-c", 
                f"""
import sys
sys.path.append('/app')
from scripts.run_pipeline import run_complete_pipeline
run_complete_pipeline(
    pdf_path='/app/input.pdf',
    domain='{domain}',
    output_dir='/app/{output_dir}'
)
                """
            ])
            .directory(f"/app/{output_dir}")
        )
        
        return result

    @function
    async def health_check_services(self) -> str:
        """Check health of all MCP services"""
        services = await self.build_mcp_services()
        
        health_results = []
        for i, service in enumerate(services):
            service_name = ["tesseract", "easyocr", "paddle", "surya"][i]
            port = [8089, 8092, 8090, 8091][i]
            
            try:
                # Test health endpoint
                result = await (
                    dag.container()
                    .from_("curlimages/curl")
                    .with_service_binding(f"mcp-{service_name}", service)
                    .with_exec([
                        "curl", "-f", f"http://mcp-{service_name}:{port}/health"
                    ])
                    .stdout()
                )
                health_results.append(f"{service_name}: HEALTHY")
            except Exception as e:
                health_results.append(f"{service_name}: UNHEALTHY - {str(e)}")
        
        return "\n".join(health_results)