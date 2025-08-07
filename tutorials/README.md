# Production RAG Pipeline Tutorials

Welcome to the comprehensive tutorial series for building and operating a production RAG pipeline with data lake integration!

## 📚 Tutorial Series

### 🚀 Getting Started
1. **[Complete Data-to-Chat Tutorial](getting-started/data-to-chat-complete-guide.md)** - *Start here!*
   - Upload data to the data lake
   - Run ETL pipelines
   - Ingest into Milvus
   - Chat with your data
   - End-to-end walkthrough with demo data

2. **[Data Lake Setup and Configuration](getting-started/data-lake-setup.md)**
   - Understanding the 3-zone architecture
   - Configuring data connectors
   - Setting up Airflow DAGs

3. **[Real-time Streaming with Kafka](getting-started/streaming-setup.md)**
   - Setting up Kafka for real-time ingestion
   - Stream processing
   - Live document updates

### 🔧 Advanced Topics
1. **[Custom Data Connectors](advanced/custom-connectors.md)**
   - Building your own data source connectors
   - Advanced ETL patterns

2. **[Scaling and Performance](advanced/scaling-guide.md)**
   - Multi-node deployment
   - Performance optimization
   - Monitoring and alerting

3. **[Data Quality and Governance](advanced/data-governance.md)**
   - Data validation pipelines
   - Lineage tracking
   - Quality metrics

## 🎯 Demo Data Sets

We provide several demo datasets to help you get started:

- **📰 News Articles** - Sample news articles for general knowledge
- **📖 Technical Documentation** - Software documentation for technical Q&A
- **📊 Product Catalogs** - E-commerce product information
- **🎓 Educational Content** - Learning materials and tutorials

## 🛠️ Prerequisites

Before starting the tutorials, make sure you have:

- Docker and Docker Compose installed
- Python 3.9+ with virtual environment
- At least 8GB RAM available
- Basic familiarity with command line

## 🎬 Quick Start

If you're new here, start with the **Complete Data-to-Chat Tutorial** - it will walk you through the entire process from raw data to a working chat interface in about 30 minutes.

```bash
# 1. Clone and setup the project
git clone <repository>
cd prod-rag

# 2. Follow the complete tutorial
open tutorials/getting-started/data-to-chat-complete-guide.md
```

## 💡 Tips for Success

1. **Start Small**: Begin with the demo data before using your own
2. **Monitor Everything**: Use the provided dashboards to understand what's happening
3. **Iterate Gradually**: Make small changes and test frequently
4. **Check the Logs**: When something goes wrong, the logs are your friend

## 🆘 Getting Help

- Check the **troubleshooting sections** in each tutorial
- Look at the **monitoring dashboards** for system health
- Review the **logs** in each service
- Open an issue if you find bugs or have suggestions

Happy learning! 🎉
