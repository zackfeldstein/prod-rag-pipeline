#!/bin/bash
# Start complete data lake and RAG pipeline

set -e

echo "🏗️ Starting Complete Data Lake and RAG Pipeline"

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

# Check dependencies
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed"
    exit 1
fi

# Create necessary directories
print_status "Creating directories..."
mkdir -p volumes/{milvus,redis,postgres,prometheus,grafana,etcd,minio}
mkdir -p {dags,plugins,logs,spark/{apps,data},notebooks,great_expectations,kafka-plugins,mlflow,data}

# Set permissions for Grafana
chmod 777 volumes/grafana 2>/dev/null || sudo chmod 777 volumes/grafana

# Create environment file if it doesn't exist
if [ ! -f .env ]; then
    if [ -f env.example ]; then
        print_status "Creating .env from example..."
        cp env.example .env
    fi
fi

# Create Airflow environment file
if [ ! -f .env.airflow ]; then
    print_status "Creating Airflow environment..."
    cat > .env.airflow << 'EOF'
# Airflow Configuration
AIRFLOW_UID=50000
AIRFLOW_GID=0
AIRFLOW__CORE__EXECUTOR=CeleryExecutor
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres-airflow/airflow
AIRFLOW__CELERY__RESULT_BACKEND=db+postgresql://airflow:airflow@postgres-airflow/airflow
AIRFLOW__CELERY__BROKER_URL=redis://:@redis-airflow:6379/0
AIRFLOW__CORE__FERNET_KEY=
AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true
AIRFLOW__CORE__LOAD_EXAMPLES=false
AIRFLOW__API__AUTH_BACKENDS=airflow.api.auth.backend.basic_auth
AIRFLOW__WEBSERVER__EXPOSE_CONFIG=true
_AIRFLOW_DB_MIGRATE=true
_AIRFLOW_WWW_USER_CREATE=true
_AIRFLOW_WWW_USER_USERNAME=admin
_AIRFLOW_WWW_USER_PASSWORD=admin
PYTHONPATH=/opt/airflow/dags:/app/src
EOF
fi

print_status "Building custom Docker images..."

# Build Airflow image
if [ ! -f Dockerfile.airflow ]; then
    print_error "Dockerfile.airflow not found"
    exit 1
fi

docker build -f Dockerfile.airflow -t airflow-rag:latest .

print_status "Starting data lake infrastructure..."

# Start with docker-compose for data lake
docker-compose -f docker-compose.datalake.yml --env-file .env.airflow up -d

print_status "Waiting for services to initialize..."

# Wait for core services
services_to_check=(
    "minio-datalake:9000"
    "kafka:9092" 
    "postgres-airflow:5432"
    "redis-airflow:6379"
)

for service in "${services_to_check[@]}"; do
    service_name="${service%%:*}"
    port="${service##*:}"
    
    print_status "Waiting for $service_name..."
    timeout=60
    while ! nc -z localhost $port 2>/dev/null; do
        sleep 2
        timeout=$((timeout - 2))
        if [ $timeout -le 0 ]; then
            print_warning "$service_name may not be ready (timeout)"
            break
        fi
    done
    
    if nc -z localhost $port 2>/dev/null; then
        print_success "$service_name is ready"
    fi
done

# Initialize Kafka topics
print_status "Creating Kafka topics..."
docker exec -it $(docker ps -q -f name=kafka) kafka-topics --create --bootstrap-server localhost:9092 --topic rag-documents --partitions 3 --replication-factor 1 2>/dev/null || echo "Topic may already exist"
docker exec -it $(docker ps -q -f name=kafka) kafka-topics --create --bootstrap-server localhost:9092 --topic rag-document-updates --partitions 3 --replication-factor 1 2>/dev/null || echo "Topic may already exist"
docker exec -it $(docker ps -q -f name=kafka) kafka-topics --create --bootstrap-server localhost:9092 --topic rag-document-deletions --partitions 1 --replication-factor 1 2>/dev/null || echo "Topic may already exist"
docker exec -it $(docker ps -q -f name=kafka) kafka-topics --create --bootstrap-server localhost:9092 --topic rag-metadata-updates --partitions 1 --replication-factor 1 2>/dev/null || echo "Topic may already exist"

# Wait a bit more for Airflow to fully initialize
print_status "Waiting for Airflow to initialize..."
sleep 30

# Check service health
print_status "Checking service health..."

health_checks=(
    "MinIO:http://localhost:9000/minio/health/live"
    "Airflow:http://localhost:8080/health"
    "Kafka Connect:http://localhost:8083/connectors"
    "Schema Registry:http://localhost:8081/subjects"
    "Spark Master:http://localhost:8082"
    "MLflow:http://localhost:5000"
    "Jupyter:http://localhost:8889"
)

for check in "${health_checks[@]}"; do
    name="${check%%:*}"
    url="${check#*:}"
    
    if curl -f "$url" > /dev/null 2>&1; then
        print_success "$name is healthy"
    else
        print_warning "$name may not be ready"
    fi
done

print_success "Data Lake Pipeline started successfully!"

echo ""
echo "🌐 Service URLs:"
echo "  Data Lake (MinIO):     http://localhost:9001 (admin:password123)"
echo "  Apache Airflow:        http://localhost:8080 (admin:admin)"  
echo "  Kafka Connect:         http://localhost:8083"
echo "  Schema Registry:       http://localhost:8081"
echo "  Spark Master:          http://localhost:8082"
echo "  MLflow:                http://localhost:5000"
echo "  Jupyter Notebooks:     http://localhost:8889"
echo "  Prometheus:            http://localhost:9090"
echo "  Grafana:               http://localhost:3000 (admin:admin)"
echo "  Jaeger Tracing:        http://localhost:16686"
echo ""

echo "📊 Data Lake Zones:"
echo "  Raw Zone:     s3://raw-data/"
echo "  Processed:    s3://processed-data/"
echo "  Curated:      s3://curated-data/"
echo "  Documents:    s3://documents/"
echo "  Models:       s3://models/"
echo ""

echo "🔄 Data Flow:"
echo "  1. Data Sources → Connectors → Raw Zone"
echo "  2. Raw Zone → Processing → Processed Zone"
echo "  3. Processed Zone → Curation → Curated Zone"
echo "  4. Curated Zone → RAG Ingestion → Vector Store"
echo "  5. Real-time: Kafka → Stream Processing → RAG"
echo ""

print_warning "Next steps:"
print_warning "1. Configure data source connections in Airflow Variables"
print_warning "2. Start the RAG API: ./scripts/run_api.sh"
print_warning "3. Activate DAGs in Airflow UI"
print_warning "4. Monitor data flow in Grafana dashboards"
echo ""

print_status "For configuration examples, check:"
print_status "  - Data source configs: ./configs/data_sources_example.json"
print_status "  - Airflow DAGs: ./dags/"
print_status "  - Notebooks: ./notebooks/"
