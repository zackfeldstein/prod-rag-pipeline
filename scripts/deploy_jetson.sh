#!/bin/bash
# Deployment script for Jetson GPU node

set -e

echo "🚀 Deploying RAG Pipeline to Jetson GPU Node"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if running on Jetson
if ! grep -q "tegra" /proc/version 2>/dev/null; then
    print_warning "This script is optimized for Jetson devices but will continue anyway"
fi

# Navigate to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

print_status "Deploying from: $PROJECT_ROOT"

# Check dependencies
print_status "Checking dependencies..."

# Check Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    print_warning "Please log out and back in for Docker permissions to take effect"
fi

# Check NVIDIA Container Toolkit
if ! command -v nvidia-container-runtime &> /dev/null; then
    print_status "Installing NVIDIA Container Toolkit..."
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
    curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
    
    sudo apt-get update
    sudo apt-get install -y nvidia-container-toolkit
    sudo systemctl restart docker
fi

# Create optimized environment for Jetson
print_status "Creating Jetson-optimized configuration..."

cat > .env.jetson << 'EOF'
# Jetson GPU Configuration
EMBEDDING_DEVICE=cuda
EMBEDDING_BATCH_SIZE=16
LLM_DEVICE=cuda

# Optimized for Jetson memory constraints
CHUNK_SIZE=800
CHUNK_OVERLAP=150
MAX_CONCURRENT_REQUESTS=10

# Cache settings for limited memory
CACHE_TTL=1800
ENABLE_CACHE=true

# Milvus settings for Jetson
MILVUS_HOST=localhost
MILVUS_PORT=19530

# API settings
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=2

# Monitoring (lightweight)
PROMETHEUS_PORT=9090
LOG_LEVEL=INFO
EOF

# Create Jetson-specific Docker Compose
print_status "Creating Jetson Docker Compose configuration..."

cat > docker-compose.jetson.yml << 'EOF'
version: '3.8'

services:
  # RAG API optimized for Jetson
  rag-api:
    build: 
      context: .
      dockerfile: Dockerfile.jetson
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - API_WORKERS=2
      - EMBEDDING_DEVICE=cuda
      - EMBEDDING_BATCH_SIZE=16
    ports:
      - "8000:8000"
      - "8001:8001"
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  # Lightweight Redis for caching
  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    restart: unless-stopped

  # Prometheus for monitoring
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./configs/prometheus.jetson.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=7d'
      - '--web.enable-lifecycle'
    restart: unless-stopped

volumes:
  redis_data:
  prometheus_data:
EOF

# Create Jetson-optimized Dockerfile
print_status "Creating Jetson Dockerfile..."

cat > Dockerfile.jetson << 'EOF'
# Jetson-optimized Dockerfile
FROM nvcr.io/nvidia/l4t-pytorch:r35.2.1-pth2.0-py3

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    git \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies optimized for Jetson
COPY requirements.jetson.txt .
RUN pip install --no-cache-dir -r requirements.jetson.txt

# Copy application code
COPY src/ ./src/
COPY configs/ ./configs/
COPY main.py .
COPY .env.jetson .env

# Create app user
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

# Expose ports
EXPOSE 8000 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Start command
CMD ["python", "-m", "uvicorn", "src.prod_rag.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
EOF

# Create Jetson-specific requirements
print_status "Creating Jetson requirements..."

cat > requirements.jetson.txt << 'EOF'
# Core dependencies optimized for Jetson
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.1

# PyTorch (already in base image)
# torch==2.0.0+nv23.05
# torchvision==0.15.0

# Sentence Transformers (Jetson compatible)
sentence-transformers==2.2.2
transformers==4.36.2

# Vector database
pymilvus==2.3.4

# LangChain (lightweight)
langchain==0.1.0
langchain-community==0.0.13

# Document processing
pypdf==3.17.4
python-docx==1.1.0
openpyxl==3.1.2

# Data processing
pandas==2.1.4
numpy==1.24.3

# Caching
redis==5.0.1

# Monitoring
prometheus-client==0.19.0

# HTTP
httpx==0.25.2
aiofiles==23.2.1

# Configuration
python-dotenv==1.0.0
pyyaml==6.0.1

# Logging
structlog==23.2.0
EOF

# Create Jetson Prometheus config
mkdir -p configs
cat > configs/prometheus.jetson.yml << 'EOF'
global:
  scrape_interval: 30s
  evaluation_interval: 30s

scrape_configs:
  - job_name: 'rag-api-jetson'
    static_configs:
      - targets: ['localhost:8001']
    scrape_interval: 15s
    metrics_path: /metrics

  - job_name: 'rag-fastapi-jetson'
    static_configs:
      - targets: ['localhost:8000']
    scrape_interval: 15s
    metrics_path: /prometheus-metrics

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']
    scrape_interval: 30s
EOF

# Build and start services
print_status "Building Jetson-optimized containers..."
docker-compose -f docker-compose.jetson.yml build

print_status "Starting services on Jetson..."
docker-compose -f docker-compose.jetson.yml up -d

# Wait for services to start
print_status "Waiting for services to initialize..."
sleep 30

# Check GPU availability
print_status "Checking GPU availability..."
if nvidia-smi > /dev/null 2>&1; then
    print_success "NVIDIA GPU detected and available"
    nvidia-smi
else
    print_warning "No NVIDIA GPU detected or nvidia-smi not available"
fi

# Test the deployment
print_status "Testing deployment..."
if curl -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    print_success "RAG API is responding"
else
    print_error "RAG API is not responding"
fi

# Display connection info
print_success "Jetson deployment completed!"
echo ""
echo "🌐 Service URLs:"
echo "  RAG API:    http://$(hostname):8000"
echo "  API Docs:   http://$(hostname):8000/docs"
echo "  Health:     http://$(hostname):8000/api/v1/health"
echo "  Prometheus: http://$(hostname):9090"
echo ""
echo "💡 Usage examples:"
echo "  # Upload document"
echo "  curl -X POST http://$(hostname):8000/api/v1/documents/upload -F 'file=@document.pdf'"
echo ""
echo "  # Query"
echo "  curl -X POST http://$(hostname):8000/api/v1/query -H 'Content-Type: application/json' -d '{\"query\":\"What is this about?\"}'"
echo ""
print_warning "Note: This Jetson configuration is optimized for limited resources."
print_warning "For production workloads, consider connecting to a remote Milvus cluster."
