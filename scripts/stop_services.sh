#!/bin/bash
# Stop all services for the production RAG pipeline

set -e

echo "🛑 Stopping Production RAG Pipeline Services"

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

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Navigate to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

print_status "Stopping all services..."

# Stop services gracefully
docker-compose down

# Option to remove volumes
if [ "$1" = "--remove-data" ]; then
    print_warning "Removing all data volumes..."
    docker-compose down -v
    sudo rm -rf volumes/
    print_warning "All data has been removed!"
else
    print_status "Data volumes preserved. Use --remove-data to remove all data."
fi

# Clean up orphaned containers
docker container prune -f

print_success "All services stopped successfully!"

echo ""
echo "To restart services, run:"
echo "  ./scripts/start_services.sh"
echo ""
