#!/bin/bash
# Start all services for the production RAG pipeline

set -e

echo "🚀 Starting Production RAG Pipeline Services"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    print_error "docker-compose is not installed. Please install it first."
    exit 1
fi

# Navigate to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

print_status "Project root: $PROJECT_ROOT"

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p volumes/{milvus,redis,postgres,prometheus,grafana,etcd,minio}
mkdir -p volumes/grafana/{data,logs}
chmod 777 volumes/grafana/{data,logs}

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    if [ -f env.example ]; then
        print_status "Creating .env file from env.example..."
        cp env.example .env
        print_warning "Please review and update the .env file with your configuration"
    else
        print_error "env.example file not found. Please create a .env file."
        exit 1
    fi
fi

# Build custom images if needed
print_status "Building custom Docker images..."
if [ -f Dockerfile ]; then
    docker build -t prod-rag:latest .
fi

# Start infrastructure services first
print_status "Starting infrastructure services..."
docker-compose up -d etcd minio redis postgres

print_status "Waiting for infrastructure services to be ready..."
sleep 30

# Check if Minio is ready
print_status "Waiting for Minio to be ready..."
until curl -f http://localhost:9000/minio/health/live > /dev/null 2>&1; do
    printf '.'
    sleep 2
done
print_success "Minio is ready"

# Check if PostgreSQL is ready
print_status "Waiting for PostgreSQL to be ready..."
until docker-compose exec -T postgres pg_isready -U rag_user -d prod_rag > /dev/null 2>&1; do
    printf '.'
    sleep 2
done
print_success "PostgreSQL is ready"

# Start Milvus
print_status "Starting Milvus vector database..."
docker-compose up -d milvus

print_status "Waiting for Milvus to be ready..."
until curl -f http://localhost:9091/healthz > /dev/null 2>&1; do
    printf '.'
    sleep 5
done
print_success "Milvus is ready"

# Start monitoring services
print_status "Starting monitoring services..."
docker-compose up -d prometheus grafana jaeger

# Wait for services
print_status "Waiting for monitoring services..."
sleep 15

# Check services
print_status "Checking service health..."

services=(
    "Milvus:http://localhost:9091/healthz"
    "Redis:http://localhost:6379"
    "Prometheus:http://localhost:9090/-/healthy"
    "Grafana:http://localhost:3000/api/health"
    "Minio:http://localhost:9000/minio/health/live"
)

for service in "${services[@]}"; do
    name="${service%%:*}"
    url="${service#*:}"
    
    if [[ "$name" == "Redis" ]]; then
        # Special check for Redis
        if docker-compose exec -T redis redis-cli ping | grep -q PONG; then
            print_success "$name is healthy"
        else
            print_warning "$name may not be ready"
        fi
    else
        if curl -f "$url" > /dev/null 2>&1; then
            print_success "$name is healthy"
        else
            print_warning "$name may not be ready"
        fi
    fi
done

print_success "All infrastructure services started successfully!"

# Display service URLs
echo ""
echo "🌐 Service URLs:"
echo "  Milvus:     http://localhost:19530"
echo "  Minio:      http://localhost:9001 (admin:minioadmin/minioadmin)"
echo "  Prometheus: http://localhost:9090"
echo "  Grafana:    http://localhost:3000 (admin:admin)"
echo "  Jaeger:     http://localhost:16686"
echo "  PostgreSQL: localhost:5432 (rag_user:rag_password)"
echo "  Redis:      localhost:6379"
echo ""

print_status "Infrastructure is ready! You can now start the RAG API with:"
print_status "  python -m uvicorn src.prod_rag.api.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""

print_warning "Note: Remember to activate your Python virtual environment and install dependencies:"
print_warning "  pip install -r requirements.txt"
