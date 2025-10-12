#!/bin/bash
# setup_local_chunkr.sh - Setup local Chunkr for semantic enhancement

set -e

echo "🧠 Setting up Local Chunkr for Semantic Enhancement"
echo "=================================================="

# Check requirements
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is required but not installed."
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker compose &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is required but not installed."
    echo "Please install Docker Compose first."
    exit 1
fi

# Create chunkr workspace
WORKSPACE_DIR="chunkr_workspace"
mkdir -p "$WORKSPACE_DIR"
cd "$WORKSPACE_DIR"

echo "📁 Created workspace: $(pwd)"

# Clone Chunkr if not exists
if [ ! -d "chunkr" ]; then
    echo "📥 Cloning Chunkr repository..."
    git clone https://github.com/lumina-ai-inc/chunkr.git
else
    echo "📁 Chunkr repository already exists"
fi

cd chunkr

# Setup environment
echo "⚙️ Configuring environment..."
cp .env.example .env
cp models.example.yaml models.yaml

# Configure for local LLM (Ollama)
cat > models.yaml << 'EOF'
models:
  - id: local-llama
    model: llama3.2:latest
    provider_url: http://ollama:11434/v1/chat/completions
    api_key: "ollama"
    default: true
    rate-limit: 100
    
  - id: local-mistral
    model: mistral:7b
    provider_url: http://ollama:11434/v1/chat/completions
    api_key: "ollama"
    rate-limit: 100
EOF

# Detect system architecture for compose strategy
ARCH=$(uname -m)
COMPOSE_CMD="docker compose"
COMPOSE_FILES="compose.yaml"

if [[ "$ARCH" == "arm64" ]] || [[ "$ARCH" == "aarch64" ]]; then
    echo "🔧 Detected ARM architecture (Apple Silicon)"
    COMPOSE_FILES="$COMPOSE_FILES -f compose.cpu.yaml -f compose.mac.yaml"
elif command -v nvidia-smi &> /dev/null; then
    echo "🔧 Detected NVIDIA GPU"
    # Use default GPU compose
else
    echo "🔧 Using CPU-only configuration"
    COMPOSE_FILES="$COMPOSE_FILES -f compose.cpu.yaml"
fi

# Create override for Ollama integration
cat > docker-compose.override.yml << 'EOF'
services:
  ollama:
    image: ollama/ollama:latest
    container_name: chunkr_ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    restart: unless-stopped
    networks:
      - chunkr_network

volumes:
  ollama_data:
EOF

echo "🐳 Starting Chunkr services..."
$COMPOSE_CMD $COMPOSE_FILES up -d

echo "⏳ Waiting for services to initialize..."
sleep 15

# Setup Ollama models
echo "📦 Setting up Ollama models..."
echo "This may take a few minutes for first-time model downloads..."

# Pull required models
docker exec chunkr_ollama ollama pull llama3.2:latest &
LLAMA_PID=$!

docker exec chunkr_ollama ollama pull mistral:7b &
MISTRAL_PID=$!

echo "📥 Downloading models in parallel (this may take 5-10 minutes)..."
wait $LLAMA_PID
echo "✅ Llama 3.2 model ready"

wait $MISTRAL_PID  
echo "✅ Mistral 7B model ready"

# Wait for Chunkr core to be ready
echo "⏳ Waiting for Chunkr core service..."
for i in {1..30}; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Chunkr core is ready!"
        break
    fi
    echo "Waiting for core service... ($i/30)"
    sleep 10
done

# Verify API endpoints
echo "🧪 Testing API endpoints..."

# Test health
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Chunkr API: http://localhost:8000 - Healthy"
else
    echo "❌ Chunkr API: http://localhost:8000 - Not responding"
fi

# Test web UI
if curl -f http://localhost:5173 > /dev/null 2>&1; then
    echo "✅ Chunkr Web UI: http://localhost:5173 - Available"
else
    echo "⚠️ Chunkr Web UI: http://localhost:5173 - Not responding (may still be starting)"
fi

# Test Ollama
if curl -f http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama API: http://localhost:11434 - Ready"
else
    echo "❌ Ollama API: http://localhost:11434 - Not responding"
fi

echo ""
echo "🎉 Chunkr Local Setup Complete!"
echo ""
echo "🔗 Service URLs:"
echo "   • Chunkr API: http://localhost:8000"
echo "   • Chunkr Web UI: http://localhost:5173"  
echo "   • Ollama API: http://localhost:11434"
echo ""
echo "📖 API Documentation: http://localhost:8000/docs"
echo ""
echo "🧪 Quick Test:"
echo '   curl -X POST http://localhost:8000/api/v1/task \'
echo '     -F "file=@your_document.pdf" \'
echo '     -F "ocr_strategy=Auto"'
echo ""
echo "🔄 To run the semantic enhancement:"
echo "   cd $(dirname "$(pwd)")"
echo "   python 03b_chunkr_enhance.py"
echo ""
echo "⏹️ To stop services:"
echo "   docker compose $COMPOSE_FILES down"
echo ""
echo "📋 To view logs:"
echo "   docker compose $COMPOSE_FILES logs -f"