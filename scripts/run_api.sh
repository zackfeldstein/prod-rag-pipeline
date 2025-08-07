#!/bin/bash
# Run the FastAPI RAG server

set -e

echo "🚀 Starting Production RAG API Server"

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

# Navigate to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Check if virtual environment is active
if [[ "$VIRTUAL_ENV" == "" ]]; then
    print_warning "No virtual environment detected. It's recommended to use a virtual environment."
fi

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    print_error "FastAPI not found. Please install dependencies:"
    print_error "  pip install -r requirements.txt"
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    print_status "Loaded environment variables from .env"
else
    print_warning "No .env file found. Using default settings."
fi

# Set default values if not provided
export API_HOST=${API_HOST:-"0.0.0.0"}
export API_PORT=${API_PORT:-8000}
export API_WORKERS=${API_WORKERS:-4}
export API_RELOAD=${API_RELOAD:-false}
export LOG_LEVEL=${LOG_LEVEL:-"info"}

# Check if services are running
print_status "Checking required services..."

# Check Milvus
if ! curl -f http://localhost:19530 > /dev/null 2>&1; then
    print_error "Milvus is not running. Please start services first:"
    print_error "  ./scripts/start_services.sh"
    exit 1
fi

# Check Redis
if ! docker exec -it $(docker ps -q -f name=redis) redis-cli ping > /dev/null 2>&1; then
    print_warning "Redis may not be running. Some caching features may not work."
fi

print_success "Required services are available"

# Set Python path
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

print_status "Starting API server..."
print_status "Host: $API_HOST"
print_status "Port: $API_PORT"
print_status "Workers: $API_WORKERS"
print_status "Log Level: $LOG_LEVEL"

echo ""
echo "🌐 API will be available at:"
echo "  Main API: http://$API_HOST:$API_PORT"
echo "  Docs: http://$API_HOST:$API_PORT/docs"
echo "  Redoc: http://$API_HOST:$API_PORT/redoc"
echo "  Health: http://$API_HOST:$API_PORT/api/v1/health"
echo "  Metrics: http://$API_HOST:$API_PORT/api/v1/metrics"
echo ""

# Development vs Production mode
if [ "$API_RELOAD" = "true" ]; then
    print_status "Running in DEVELOPMENT mode with auto-reload"
    uvicorn src.prod_rag.api.main:app \
        --host "$API_HOST" \
        --port "$API_PORT" \
        --reload \
        --log-level "$LOG_LEVEL"
else
    print_status "Running in PRODUCTION mode"
    if [ "$API_WORKERS" -gt 1 ]; then
        gunicorn src.prod_rag.api.main:app \
            -w "$API_WORKERS" \
            -k uvicorn.workers.UvicornWorker \
            --bind "$API_HOST:$API_PORT" \
            --log-level "$LOG_LEVEL" \
            --access-logfile - \
            --error-logfile -
    else
        uvicorn src.prod_rag.api.main:app \
            --host "$API_HOST" \
            --port "$API_PORT" \
            --log-level "$LOG_LEVEL"
    fi
fi
