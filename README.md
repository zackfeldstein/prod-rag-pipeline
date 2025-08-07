# Production RAG Pipeline

A production-ready Retrieval Augmented Generation (RAG) pipeline built with the most popular and battle-tested open-source tools.

## 🏗️ Architecture

- **LangChain**: RAG orchestration and document processing
- **Milvus**: Scalable vector database for semantic search
- **FastAPI**: High-performance API framework with automatic docs
- **Redis**: Caching and session management
- **PostgreSQL**: Metadata and user management
- **Sentence Transformers**: State-of-the-art embedding models
- **Prometheus + Grafana**: Comprehensive monitoring and dashboards
- **Docker**: Containerized deployment for easy scaling

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.9+ (for local development)
- 8GB+ RAM recommended
- GPU support optional (for faster embeddings)

### 1. Start Infrastructure Services

```bash
# Clone and navigate to the project
git clone <repository>
cd prod-rag

# Start all infrastructure services
./scripts/start_services.sh
```

This will start:
- Milvus vector database
- Redis for caching
- PostgreSQL for metadata
- Prometheus for metrics
- Grafana for dashboards
- Jaeger for tracing

### 2. Install Python Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Start the RAG API

```bash
# Start the API server
./scripts/run_api.sh

# Or manually:
python -m uvicorn src.prod_rag.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Access the Services

- **API Documentation**: http://localhost:8000/docs
- **Grafana Dashboard**: http://localhost:3000 (admin:admin)
- **Prometheus Metrics**: http://localhost:9090
- **Minio Console**: http://localhost:9001 (minioadmin:minioadmin)
- **Jaeger Tracing**: http://localhost:16686

## 📖 Usage

### Document Ingestion

Upload documents via the API:

```bash
# Upload a single document
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf" \
  -F "title=My Document" \
  -F "author=John Doe"

# Or via CLI
python main.py ingest document1.pdf document2.docx document3.txt
```

### Querying

Ask questions about your documents:

```bash
# Via API
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the main topic of the documents?",
    "max_results": 5,
    "similarity_threshold": 0.7
  }'

# Via Python
import requests

response = requests.post("http://localhost:8000/api/v1/query", json={
    "query": "What is machine learning?",
    "max_results": 3
})

print(response.json())
```

### Supported Document Formats

- PDF (`.pdf`)
- Microsoft Word (`.docx`)
- Plain Text (`.txt`)
- Markdown (`.md`)
- HTML (`.html`)
- CSV (`.csv`)
- Excel (`.xlsx`)

## 🔧 Configuration

### Environment Variables

Copy `env.example` to `.env` and configure:

```bash
cp env.example .env
```

Key configuration options:

```env
# API Settings
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Embedding Model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu  # or cuda for GPU

# Document Processing
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Caching
ENABLE_CACHE=true
CACHE_TTL=3600

# Vector Database
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

### Scaling Configuration

For production deployment across multiple VMs:

1. **Jetson GPU Node**: Embedding generation and vector search
2. **VM Cluster**: Distributed Milvus, API load balancing, monitoring

## 📊 Monitoring

### Health Checks

```bash
# Check system health
curl http://localhost:8000/api/v1/health

# Get metrics
curl http://localhost:8000/api/v1/metrics

# CLI health check
python main.py health
```

### Grafana Dashboards

Pre-configured dashboards for:
- Query performance and latency
- Cache hit rates
- Document ingestion metrics
- System resource usage
- Error rates and alerting

### Prometheus Metrics

- `rag_queries_total`: Total number of queries processed
- `rag_query_duration_seconds`: Query processing time
- `rag_cache_hits_total`: Cache hit statistics
- `rag_document_chunks_total`: Total chunks in vector store
- `http_requests_total`: HTTP request metrics

## 🚀 Production Deployment

### Docker Compose Production

```bash
# Production deployment with load balancing
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes

```bash
# Deploy to Kubernetes (charts provided)
helm install prod-rag ./k8s/helm/
```

### Scaling Considerations

1. **Horizontal Scaling**: Multiple API instances behind load balancer
2. **Vector Store**: Milvus cluster across multiple nodes
3. **Caching**: Redis Sentinel for high availability
4. **Monitoring**: Centralized logging with ELK stack

## 🔒 Security

- JWT token authentication for API endpoints
- Input validation and sanitization
- Rate limiting to prevent abuse
- HTTPS termination at load balancer
- Secrets management with environment variables

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test suite
pytest tests/test_rag_engine.py

# Run with coverage
pytest --cov=src
```

## 📁 Project Structure

```
prod-rag/
├── src/prod_rag/           # Main application code
│   ├── api/                # FastAPI endpoints
│   ├── core/               # Core RAG engine
│   ├── data/               # Document ingestion
│   ├── models/             # Pydantic schemas
│   └── utils/              # Utilities
├── configs/                # Configuration files
├── scripts/                # Deployment scripts
├── tests/                  # Test suite
├── docker-compose.yml      # Development environment
├── docker-compose.prod.yml # Production environment
└── requirements.txt        # Python dependencies
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Documentation**: Check the `/docs` endpoint when running
- **Issues**: Create GitHub issues for bugs or feature requests
- **Monitoring**: Use Grafana dashboards for operational insights

## 🔄 Roadmap

- [ ] Support for more LLM providers (OpenAI, Anthropic, local models)
- [ ] Advanced chunking strategies
- [ ] Multi-modal document support (images, tables)
- [ ] Fine-tuning capabilities for domain-specific models
- [ ] Advanced security features (RBAC, audit logging)
- [ ] Multi-tenant support
- [ ] Real-time document synchronization
- [ ] Advanced analytics and insights
