# From Raw Data to Chat: Complete RAG Pipeline Tutorial

*Building a production RAG system from zero to hero in 30 minutes*

Welcome to the complete tutorial for building a production RAG pipeline! By the end of this guide, you'll have data flowing from raw sources through a data lake, processed by ETL pipelines, stored in a vector database, and accessible through a chat interface.

## 🎯 What We'll Build

- **Data Lake** with raw, processed, and curated zones
- **ETL Pipeline** with Apache Airflow
- **Vector Database** with Milvus for semantic search
- **Chat Interface** for questioning your data
- **Real-time streaming** with Kafka
- **Monitoring** with Grafana dashboards

## 📋 Prerequisites

Before we start, ensure you have:
- Docker and Docker Compose installed
- Python 3.9+ with pip
- At least 8GB RAM available
- 10GB free disk space

## 🚀 Step 1: Environment Setup

Let's start by setting up our development environment.

### Clone and Setup Project

```bash
# Clone the repository
git clone <your-repo-url>
cd prod-rag

# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Start the Complete Data Pipeline

```bash
# Start the full data lake and RAG infrastructure
./scripts/start_datalake.sh
```

This command starts **15+ services** including:
- Data Lake (MinIO)
- Apache Airflow for ETL
- Apache Kafka for streaming
- Milvus vector database
- Prometheus + Grafana monitoring
- Jupyter notebooks for exploration

**☕ Coffee Break**: This takes about 5-10 minutes to fully initialize all services.

### Verify Services Are Running

Check that key services are accessible:

```bash
# Check service health
curl http://localhost:8080/health  # Airflow
curl http://localhost:9000/minio/health/live  # MinIO Data Lake
curl http://localhost:19530  # Milvus
```

You should see healthy responses from all services.

## 📊 Step 2: Understanding the Data Lake Architecture

Before we upload data, let's understand our 3-zone data lake:

### Data Lake Zones

```
📦 Data Lake (MinIO)
├── 🗂️ raw-data/          # Raw, unprocessed data
├── 🗂️ processed-data/    # Cleaned and validated data  
├── 🗂️ curated-data/      # RAG-ready, high-quality data
├── 🗂️ documents/         # Final document store
└── 🗂️ models/           # ML model artifacts
```

### Data Flow

```
Raw Sources → Raw Zone → ETL Processing → Processed Zone → Curation → Curated Zone → RAG Ingestion → Milvus
```

Let's see this in action!

## 📁 Step 3: Prepare Demo Data

We'll use realistic demo data to demonstrate the complete pipeline.

### Create Demo Documents

```bash
# Create demo data directory
mkdir -p demo-data/articles

# Create sample news articles
cat > demo-data/articles/ai-breakthrough.txt << 'EOF'
Title: Major AI Breakthrough in Natural Language Understanding

Scientists at TechCorp have announced a significant breakthrough in natural language understanding. The new model, called AdvancedLM, shows unprecedented performance in reading comprehension and reasoning tasks.

Key Features:
- 50% improvement in reading comprehension
- Advanced reasoning capabilities
- Multilingual support for 12 languages
- Reduced computational requirements

The research team, led by Dr. Sarah Chen, spent three years developing this technology. "This represents a fundamental shift in how machines understand human language," said Chen.

Applications include customer service automation, content analysis, and educational tools. The technology will be released as open source next quarter.

Impact:
- Improved chatbots and virtual assistants
- Better document analysis tools
- Enhanced translation services
- Educational applications

The breakthrough comes at a time when businesses are increasingly adopting AI solutions for customer interaction and data analysis.
EOF

cat > demo-data/articles/sustainable-energy.txt << 'EOF'
Title: Revolutionary Solar Panel Technology Achieves 45% Efficiency

GreenTech Industries has developed a new solar panel technology that achieves 45% efficiency, nearly double the industry standard. This breakthrough could revolutionize renewable energy adoption worldwide.

Technology Details:
- Perovskite-silicon tandem cells
- 45% power conversion efficiency
- 25-year warranty
- Cost reduction of 30% per watt

Dr. Michael Rodriguez, lead researcher, explained: "We've solved the stability issues that have plagued perovskite cells for years. Our panels maintain efficiency even after 10,000 hours of testing."

Market Impact:
- Residential solar becomes more attractive
- Utility-scale projects see improved ROI
- Energy storage needs reduced
- Grid parity achieved in more regions

The panels will enter mass production in 2024, with initial focus on residential markets in sunny climates. Pre-orders are already exceeding expectations.

Environmental Benefits:
- Reduced carbon footprint
- Lower land use for solar farms
- Decreased manufacturing waste
- Improved recycling processes

This advancement could accelerate the transition to renewable energy and help meet global climate goals.
EOF

cat > demo-data/articles/quantum-computing.txt << 'EOF'
Title: Quantum Computer Solves Complex Optimization Problem in Minutes

QuantumSys Corporation demonstrated their 1000-qubit quantum computer solving a complex logistics optimization problem that would take classical computers thousands of years.

Technical Achievement:
- 1000 physical qubits
- 99.9% fidelity
- Quantum error correction
- Room temperature operation

The problem involved optimizing delivery routes for 10,000 packages across 500 cities, considering traffic patterns, weather, and fuel costs. The quantum computer found the optimal solution in just 12 minutes.

CEO Dr. Lisa Park stated: "This proves quantum computers can solve real-world problems that matter to businesses today, not just theoretical research problems."

Applications:
- Supply chain optimization
- Financial portfolio management
- Drug discovery acceleration
- Weather prediction improvement

The breakthrough addresses the challenge of quantum decoherence through advanced error correction algorithms. This allows the system to maintain quantum states long enough for practical computations.

Commercial Availability:
- Cloud access starting Q2 2024
- On-premise systems for enterprises
- API integration for developers
- Training programs for quantum programmers

The success opens new possibilities for solving previously intractable optimization problems in logistics, finance, and scientific research.
EOF

cat > demo-data/articles/medical-research.txt << 'EOF'
Title: Gene Therapy Shows Promise for Treating Alzheimer's Disease

Researchers at MedResearch Institute report successful early trials of a gene therapy approach for treating Alzheimer's disease, showing significant improvement in cognitive function.

Clinical Trial Results:
- 40 patients treated over 18 months
- 65% showed cognitive improvement
- No serious side effects reported
- Memory scores improved by average 35%

The therapy uses modified viruses to deliver protective genes directly to brain cells. Dr. Jennifer Walsh, principal investigator, said: "We're seeing patients regain abilities they had lost, including memory formation and executive function."

Treatment Mechanism:
- Targeted gene delivery to neurons
- Enhanced amyloid plaque clearance
- Improved neural connectivity
- Reduced inflammation markers

Patient Stories:
- 72-year-old John regained ability to recognize family
- Mary, 68, returned to reading and writing
- Tom, 75, improved from severe to mild cognitive impairment

Next Steps:
- Phase 3 trials with 500 patients
- FDA approval expected in 2026
- Cost analysis for insurance coverage
- Manufacturing scale-up planning

The treatment represents hope for millions of families affected by Alzheimer's disease. If approved, it would be the first therapy to actually reverse cognitive decline rather than just slow progression.

Regulatory Path:
- Fast-track designation received
- European trials starting next year
- Compassionate use program planned
- International collaboration agreements

This breakthrough could transform Alzheimer's treatment from symptom management to actual cure.
EOF

# Create a product catalog
cat > demo-data/products.csv << 'EOF'
product_id,name,category,price,description,features
P001,SmartWatch Pro,Electronics,299.99,"Advanced fitness tracking smartwatch with GPS and heart rate monitoring","GPS tracking,Heart rate monitor,Waterproof,7-day battery"
P002,Organic Coffee Blend,Food & Beverage,24.99,"Premium organic coffee blend sourced from sustainable farms","Organic certified,Fair trade,Medium roast,Single origin"
P003,Wireless Headphones,Electronics,149.99,"Noise-canceling wireless headphones with premium sound quality","Active noise canceling,40-hour battery,Quick charge,Premium drivers"
P004,Yoga Mat Premium,Sports & Fitness,79.99,"High-quality yoga mat with superior grip and cushioning","Non-slip surface,6mm thickness,Eco-friendly material,Carrying strap"
P005,Smart Home Hub,Electronics,199.99,"Central hub for controlling all smart home devices","Voice control,WiFi 6,Zigbee support,Mobile app"
EOF

# Create technical documentation
cat > demo-data/api-docs.md << 'EOF'
# API Documentation

## Authentication

All API requests require authentication using API keys. Include your key in the header:

```
Authorization: Bearer YOUR_API_KEY
```

## Endpoints

### GET /api/v1/users
Retrieve user information

**Parameters:**
- `limit` (optional): Number of results to return (default: 50, max: 200)
- `offset` (optional): Number of results to skip (default: 0)

**Response:**
```json
{
  "users": [
    {
      "id": "123",
      "name": "John Doe",
      "email": "john@example.com",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### POST /api/v1/documents
Upload a new document for processing

**Request Body:**
```json
{
  "title": "Document Title",
  "content": "Document content...",
  "tags": ["tag1", "tag2"],
  "metadata": {
    "author": "Jane Smith",
    "department": "Engineering"
  }
}
```

**Response:**
```json
{
  "document_id": "doc_456",
  "status": "processing",
  "chunks_created": 5,
  "processing_time_ms": 1200
}
```

## Error Handling

The API uses standard HTTP status codes:

- `200` - Success
- `400` - Bad Request
- `401` - Unauthorized
- `404` - Not Found
- `500` - Internal Server Error

Error responses include details:
```json
{
  "error": "validation_error",
  "message": "Invalid request parameters",
  "details": {
    "field": "title",
    "issue": "required field missing"
  }
}
```
EOF

echo "✅ Demo data created successfully!"
```

## 🔄 Step 4: Upload Data to the Data Lake

Now let's upload our demo data to the data lake's raw zone.

### Access the MinIO Data Lake UI

1. Open http://localhost:9001 in your browser
2. Login with credentials: `admin` / `password123`
3. You'll see the data lake buckets: `raw-data`, `processed-data`, `curated-data`, etc.

### Upload Data via UI

1. Click on the `raw-data` bucket
2. Click "Upload" and select our demo files:
   - Upload all `.txt` files to `raw-data/articles/`
   - Upload `products.csv` to `raw-data/products/`
   - Upload `api-docs.md` to `raw-data/documentation/`

### Upload Data via CLI (Alternative)

```bash
# Install MinIO client
curl -O https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc /usr/local/bin/

# Configure MinIO client
mc alias set datalake http://localhost:9000 admin password123

# Upload demo data
mc cp demo-data/articles/*.txt datalake/raw-data/articles/
mc cp demo-data/products.csv datalake/raw-data/products/
mc cp demo-data/api-docs.md datalake/raw-data/documentation/

# Verify uploads
mc ls datalake/raw-data/ --recursive
```

You should see output confirming your files are uploaded to the raw zone.

## ⚙️ Step 5: Configure and Run ETL Pipeline

Now we'll configure Airflow to process our uploaded data through the ETL pipeline.

### Access Airflow

1. Open http://localhost:8080 in your browser
2. Login with credentials: `admin` / `admin`

### Configure Data Sources

1. In Airflow, go to **Admin** → **Variables**
2. Click **Add a new record**
3. Add this configuration:

**Key:** `data_sources_config`
**Value:**
```json
{
  "s3": {
    "source_name": "demo_documents",
    "endpoint_url": "http://minio-datalake:9000",
    "access_key": "admin",
    "secret_key": "password123",
    "bucket": "raw-data",
    "prefix": "",
    "region": "us-east-1"
  }
}
```

### Enable and Run the DAG

1. Go to **DAGs** in the Airflow UI
2. Find `data_ingestion_pipeline` and click the toggle to enable it
3. Click the DAG name to open its details
4. Click **Trigger DAG** to run it manually

### Monitor Pipeline Execution

Watch the DAG run through these stages:

1. **Data Extraction** - Pull data from raw zone
2. **Data Validation** - Check data quality
3. **Data Processing** - Clean and standardize
4. **Data Curation** - Prepare for RAG
5. **RAG Ingestion** - Load into Milvus

This takes about 5-10 minutes. You can monitor progress in the Graph View.

## 🗄️ Step 6: Verify Data in Milvus

Let's check that our data made it into the vector database.

### Start the RAG API

```bash
# In a new terminal, start the API server
./scripts/run_api.sh
```

The API will be available at http://localhost:8000

### Check System Health

```bash
# Check that everything is working
curl http://localhost:8000/api/v1/health
```

You should see a healthy response with all services marked as "healthy".

### Verify Document Stats

```bash
# Check how many documents and chunks we have
curl http://localhost:8000/api/v1/documents/stats
```

Example response:
```json
{
  "vector_store": {
    "total_entities": 47,
    "total_size_bytes": 125440
  },
  "pipeline_status": "healthy",
  "supported_formats": ["pdf", "docx", "txt", "md", "html", "csv", "xlsx"]
}
```

## 💬 Step 7: Chat with Your Data

Now comes the exciting part - let's query our data!

### Simple Query

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the key features of the AI breakthrough?",
    "max_results": 3
  }'
```

### Complex Queries

Try these different types of questions:

```bash
# Technical question
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How does the quantum computer solve optimization problems?",
    "max_results": 5
  }'

# Product information
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What electronics products are available and what are their prices?",
    "max_results": 3
  }'

# Medical research
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the results of the Alzheimer gene therapy trial?",
    "max_results": 4
  }'
```

### Interactive Chat Interface

For a better experience, you can use the interactive API docs:

1. Open http://localhost:8000/docs
2. Try the `/api/v1/query` endpoint
3. Enter your questions and see the responses with sources

## 🔄 Step 8: Real-time Data Updates

Let's see how the system handles real-time updates via Kafka streaming.

### Send a New Document via Kafka

```python
# Create a simple Python script to send data via Kafka
cat > send_kafka_doc.py << 'EOF'
import json
from kafka import KafkaProducer
from datetime import datetime

# Initialize Kafka producer
producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Create a new document
document = {
    'event_type': 'document_create',
    'timestamp': datetime.utcnow().isoformat(),
    'document_id': 'streaming_doc_001',
    'data': {
        'content': """
        Title: Breaking News - Space Telescope Discovers New Exoplanet
        
        The James Webb Space Telescope has discovered a potentially habitable exoplanet 
        just 40 light-years from Earth. The planet, designated K2-2023b, orbits within 
        the habitable zone of its star.
        
        Key Findings:
        - Similar size to Earth
        - Liquid water may be present
        - Atmospheric composition suggests possible life
        - Temperature range: -20°C to +30°C
        
        Dr. Maria Santos, lead astronomer, stated: "This is the most Earth-like planet 
        we've ever discovered. The atmospheric readings are unprecedented."
        
        Discovery Method:
        - Transit photometry analysis
        - Spectroscopic measurements
        - Gravitational analysis
        - Multi-year observation campaign
        
        Next steps include detailed atmospheric analysis and the search for biosignatures.
        """,
        'metadata': {
            'filename': 'space_discovery_2024.txt',
            'title': 'New Exoplanet Discovery',
            'author': 'Space Research Team',
            'tags': ['space', 'discovery', 'exoplanet', 'breaking'],
            'file_type': 'txt'
        }
    }
}

# Send to Kafka
future = producer.send('rag-documents', value=document)
result = future.get(timeout=60)

print(f"Document sent successfully: {result}")
producer.close()
EOF

# Run the script
python send_kafka_doc.py
```

### Start the Kafka Consumer

```bash
# In a new terminal, start the streaming consumer
python -c "
import asyncio
from src.prod_rag.streaming.kafka_consumer import start_streaming_consumer
asyncio.run(start_streaming_consumer())
"
```

### Verify Real-time Ingestion

```bash
# Wait a few seconds, then query for the new document
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Tell me about the new exoplanet discovery",
    "max_results": 3
  }'
```

You should see the streaming document in the results!

## 📊 Step 9: Monitor Your Pipeline

Let's explore the monitoring and observability features.

### Grafana Dashboards

1. Open http://localhost:3000
2. Login with `admin` / `admin`
3. Navigate to **Dashboards** → **RAG Pipeline Dashboard**

You'll see metrics for:
- Query performance and latency
- Document ingestion rates
- Cache hit rates
- System resource usage
- Error rates and alerts

### Prometheus Metrics

1. Open http://localhost:9090
2. Try these queries:
   - `rag_queries_total` - Total queries processed
   - `rag_query_duration_seconds` - Query response times
   - `rag_document_chunks_total` - Total chunks in vector store

### Airflow Monitoring

1. In Airflow (http://localhost:8080), check:
   - **DAG Runs** for pipeline execution history
   - **Task Instances** for detailed task logs
   - **Logs** for debugging any issues

### System Health

```bash
# Get comprehensive health status
curl http://localhost:8000/api/v1/health | jq

# Get detailed metrics
curl http://localhost:8000/api/v1/metrics | jq
```

## 🎯 Step 10: Advanced Features

Now that you have the basics working, let's explore advanced features.

### Upload Your Own Data

```bash
# Upload any PDF, DOCX, or text file
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@your-document.pdf" \
  -F "title=My Custom Document" \
  -F "author=Your Name" \
  -F "tags=custom,important"
```

### Batch Document Upload

```bash
# Upload multiple files at once
curl -X POST "http://localhost:8000/api/v1/documents/batch-upload" \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.txt" \
  -F "files=@doc3.docx" \
  -F "process_immediately=true"
```

### Delete Documents

```bash
# Remove a document and all its chunks
curl -X DELETE "http://localhost:8000/api/v1/documents/streaming_doc_001"
```

### Advanced Search

```bash
# Search with specific filters and thresholds
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "artificial intelligence and machine learning",
    "max_results": 10,
    "similarity_threshold": 0.8,
    "include_metadata": true,
    "rerank": true
  }'
```

## 🐛 Troubleshooting

### Common Issues

**Services not starting:**
```bash
# Check Docker resources
docker system df
docker system prune  # Free up space if needed

# Restart specific services
docker-compose -f docker-compose.datalake.yml restart milvus
```

**Airflow DAG not running:**
```bash
# Check Airflow logs
docker logs $(docker ps -q -f name=airflow-webserver)

# Reset DAG state
# In Airflow UI: Browse → DAG Runs → Delete failed runs
```

**API not responding:**
```bash
# Check API logs
tail -f logs/api.log

# Restart API
pkill -f uvicorn
./scripts/run_api.sh
```

**No search results:**
```bash
# Check if documents were ingested
curl http://localhost:8000/api/v1/documents/stats

# Check Milvus health
curl http://localhost:9091/healthz
```

### Viewing Logs

```bash
# Airflow worker logs
docker logs $(docker ps -q -f name=airflow-worker)

# Milvus logs
docker logs $(docker ps -q -f name=milvus)

# Kafka logs
docker logs $(docker ps -q -f name=kafka)
```

## 🎉 Congratulations!

You've successfully built and operated a complete production RAG pipeline! Here's what you accomplished:

✅ **Data Lake**: Raw, processed, and curated data zones  
✅ **ETL Pipeline**: Automated data processing with Airflow  
✅ **Vector Database**: Semantic search with Milvus  
✅ **RAG API**: Question-answering interface  
✅ **Real-time Streaming**: Live updates with Kafka  
✅ **Monitoring**: Comprehensive observability  

## 🚀 Next Steps

1. **Add Your Own Data**: Replace demo data with your real documents
2. **Customize Processing**: Modify ETL pipelines for your data sources
3. **Scale Up**: Deploy across multiple VMs using the production configs
4. **Advanced Features**: Explore custom connectors and advanced search
5. **Production Deployment**: Use the Kubernetes configs for cloud deployment

## 📚 Additional Resources

- [Data Lake Setup Guide](data-lake-setup.md)
- [Streaming Setup Tutorial](streaming-setup.md)
- [Custom Connectors Guide](../advanced/custom-connectors.md)
- [Scaling and Performance](../advanced/scaling-guide.md)

---

**🔗 Useful Links:**
- RAG API: http://localhost:8000/docs
- Data Lake: http://localhost:9001
- Airflow: http://localhost:8080
- Grafana: http://localhost:3000
- Jupyter: http://localhost:8889

Need help? Check the troubleshooting section or open an issue in the repository!
