#!/bin/bash
# Quick start script for the complete RAG pipeline tutorial

set -e

echo "🚀 RAG Pipeline Quick Start Guide"
echo "================================="

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

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Navigate to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

print_status "Starting from: $PROJECT_ROOT"

# Check if demo data exists
if [ ! -d "demo-data" ]; then
    print_status "Generating demo data..."
    python tutorials/demo-data/create_demo_data.py
else
    print_status "Demo data already exists"
fi

echo ""
echo "📚 Tutorial Options:"
echo "1. Complete Data Lake Pipeline (recommended)"
echo "2. Basic RAG Pipeline (simpler)"
echo "3. Just generate and view demo data"
echo ""

read -p "Choose an option (1-3): " choice

case $choice in
    1)
        echo ""
        print_status "🏗️ Starting Complete Data Lake Pipeline..."
        print_warning "This will start 15+ services and requires ~8GB RAM"
        read -p "Continue? (y/N): " confirm
        
        if [[ $confirm =~ ^[Yy]$ ]]; then
            print_status "Starting data lake infrastructure..."
            ./scripts/start_datalake.sh
            
            print_success "Data lake started! Follow the tutorial:"
            print_success "📖 tutorials/getting-started/data-to-chat-complete-guide.md"
            echo ""
            echo "🌐 Key URLs:"
            echo "  Data Lake: http://localhost:9001 (admin:password123)"
            echo "  Airflow:   http://localhost:8080 (admin:admin)"
            echo "  Grafana:   http://localhost:3000 (admin:admin)"
        else
            print_warning "Cancelled. You can start the pipeline later with:"
            print_warning "  ./scripts/start_datalake.sh"
        fi
        ;;
    2)
        echo ""
        print_status "🏗️ Starting Basic RAG Pipeline..."
        print_warning "This will start core services (Milvus, Redis, etc.)"
        read -p "Continue? (y/N): " confirm
        
        if [[ $confirm =~ ^[Yy]$ ]]; then
            print_status "Starting basic infrastructure..."
            ./scripts/start_services.sh
            
            print_success "Basic pipeline started! Follow the tutorial:"
            print_success "📖 tutorials/getting-started/data-to-chat-complete-guide.md"
            echo ""
            echo "🌐 Key URLs:"
            echo "  Milvus:    http://localhost:9091"
            echo "  Grafana:   http://localhost:3000 (admin:admin)"
        else
            print_warning "Cancelled. You can start the pipeline later with:"
            print_warning "  ./scripts/start_services.sh"
        fi
        ;;
    3)
        echo ""
        print_status "📁 Demo data is ready in the demo-data/ directory"
        print_status "Exploring generated content..."
        
        echo ""
        echo "📰 Articles:"
        find demo-data/articles -name "*.txt" | head -5
        
        echo ""
        echo "📦 Product Data:"
        ls -la demo-data/products/
        
        echo ""
        echo "📚 Documentation:"
        find demo-data/documentation -name "*.md" | head -3
        
        echo ""
        print_success "Demo data ready! You can:"
        print_success "1. Upload to data lake via MinIO console"
        print_success "2. Use in ETL pipelines"
        print_success "3. Test streaming with: python tutorials/demo-data/test_streaming.py"
        ;;
    *)
        print_error "Invalid choice. Please run the script again and choose 1, 2, or 3."
        exit 1
        ;;
esac

echo ""
print_status "📖 Available Tutorials:"
echo "  🚀 Complete Guide: tutorials/getting-started/data-to-chat-complete-guide.md"
echo "  🏗️ Data Lake Setup: tutorials/getting-started/data-lake-setup.md"
echo "  🔄 Streaming Setup: tutorials/getting-started/streaming-setup.md"
echo ""

print_status "🛠️ Useful Commands:"
echo "  # Check service health"
echo "  curl http://localhost:8000/api/v1/health"
echo ""
echo "  # Test streaming (after starting pipeline)"
echo "  python tutorials/demo-data/test_streaming.py"
echo ""
echo "  # Start RAG API"
echo "  ./scripts/run_api.sh"
echo ""

print_success "Quick start complete! Follow the tutorials to learn more."
print_success "📖 Start with: tutorials/getting-started/data-to-chat-complete-guide.md"
