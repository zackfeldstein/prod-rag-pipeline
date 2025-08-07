#!/usr/bin/env python3
"""
Test script for Kafka streaming functionality.
Sends sample documents via Kafka for real-time processing.
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent.parent))

async def test_kafka_streaming():
    """Test Kafka streaming with sample documents."""
    
    try:
        from src.prod_rag.streaming.kafka_producer import get_kafka_producer
        print("✅ Successfully imported Kafka producer")
    except ImportError as e:
        print(f"❌ Failed to import Kafka producer: {e}")
        print("Make sure the RAG pipeline is set up correctly")
        return False
    
    try:
        producer = get_kafka_producer()
        print("✅ Kafka producer initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Kafka producer: {e}")
        print("Make sure Kafka is running: docker-compose -f docker-compose.datalake.yml up -d kafka")
        return False
    
    # Test documents to send
    test_documents = [
        {
            'document_id': 'streaming_test_001',
            'content': f'''
            Title: Streaming Test Document #{1}
            Created: {datetime.now().isoformat()}
            
            This is a test document sent via Kafka streaming to verify the real-time 
            ingestion pipeline is working correctly.
            
            Test Features:
            - Real-time document ingestion via Kafka
            - Automatic processing and chunking
            - Vector embedding generation
            - Immediate availability for search
            
            If you can search for this content immediately after it's sent, 
            the streaming pipeline is working perfectly!
            
            Technology Stack:
            - Apache Kafka for streaming
            - Python asyncio for async processing
            - Milvus for vector storage
            - LangChain for document processing
            ''',
            'metadata': {
                'filename': 'streaming_test_001.txt',
                'title': 'Streaming Test Document #1',
                'author': 'Test System',
                'source': 'kafka_streaming_test',
                'category': 'test',
                'file_type': 'txt',
                'tags': ['test', 'streaming', 'kafka', 'real-time'],
                'test_timestamp': datetime.now().isoformat()
            }
        },
        {
            'document_id': 'streaming_test_002',
            'content': f'''
            Title: Advanced Streaming Features Test
            Created: {datetime.now().isoformat()}
            
            This document tests advanced streaming features including:
            
            Batch Processing:
            - Multiple documents in single batch
            - Efficient resource utilization
            - Ordered processing guarantees
            
            Error Handling:
            - Retry mechanisms for failed messages
            - Dead letter queue for problematic documents
            - Graceful degradation on errors
            
            Performance Features:
            - Compression for large documents
            - Partitioning for parallel processing
            - Consumer group load balancing
            
            Monitoring and Observability:
            - Real-time metrics via Prometheus
            - Consumer lag monitoring
            - Processing time tracking
            - Error rate alerts
            
            This comprehensive test ensures all streaming features work correctly.
            ''',
            'metadata': {
                'filename': 'streaming_test_002.txt',
                'title': 'Advanced Streaming Features Test',
                'author': 'Test System',
                'source': 'kafka_streaming_test',
                'category': 'advanced_test',
                'file_type': 'txt',
                'tags': ['test', 'streaming', 'advanced', 'features'],
                'test_timestamp': datetime.now().isoformat()
            }
        }
    ]
    
    print(f"\n🚀 Sending {len(test_documents)} test documents via Kafka...")
    
    success_count = 0
    
    for i, doc in enumerate(test_documents, 1):
        print(f"\n📤 Sending document {i}/{len(test_documents)}: {doc['document_id']}")
        
        try:
            success = await producer.send_document(
                document_data=doc,
                document_id=doc['document_id'],
                partition_key='streaming_test'
            )
            
            if success:
                print(f"✅ Document {doc['document_id']} sent successfully")
                success_count += 1
            else:
                print(f"❌ Failed to send document {doc['document_id']}")
                
        except Exception as e:
            print(f"❌ Error sending document {doc['document_id']}: {e}")
    
    print(f"\n📊 Results: {success_count}/{len(test_documents)} documents sent successfully")
    
    if success_count > 0:
        print("\n⏳ Wait 10-15 seconds for processing, then test search...")
        print("\nTo test search, run:")
        print("curl -X POST 'http://localhost:8000/api/v1/query' \\")
        print("  -H 'Content-Type: application/json' \\")
        print("  -d '{\"query\": \"streaming test document kafka real-time\", \"max_results\": 3}'")
        
        print("\nOr use the interactive API docs:")
        print("http://localhost:8000/docs")
        
        return True
    else:
        print("\n❌ No documents sent successfully. Check:")
        print("1. Kafka is running: docker ps | grep kafka")
        print("2. Topics exist: docker exec -it <kafka-container> kafka-topics --list --bootstrap-server localhost:9092")
        print("3. No firewall blocking port 9092")
        
        return False

async def test_document_update():
    """Test document update functionality."""
    
    print("\n🔄 Testing document update...")
    
    try:
        from src.prod_rag.streaming.kafka_producer import get_kafka_producer
        producer = get_kafka_producer()
        
        # Send update for existing document
        updates = {
            'content': f'''
            Title: UPDATED Streaming Test Document
            Updated: {datetime.now().isoformat()}
            
            This document has been UPDATED via Kafka streaming to test the 
            real-time update functionality.
            
            Update Features Tested:
            - Document content modification via streaming
            - Metadata updates in real-time
            - Re-indexing in vector store
            - Search result updates
            - Version tracking
            
            This updated content should replace the previous version in search results.
            The streaming pipeline should handle updates seamlessly.
            ''',
            'metadata': {
                'title': 'UPDATED: Streaming Test Document',
                'last_updated': datetime.now().isoformat(),
                'version': '2.0',
                'update_type': 'content_refresh',
                'file_type': 'txt'
            }
        }
        
        success = await producer.send_document_update(
            document_id='streaming_test_001',
            updates=updates,
            update_type='content'
        )
        
        if success:
            print("✅ Document update sent successfully")
            print("📍 Updated document ID: streaming_test_001")
            return True
        else:
            print("❌ Failed to send document update")
            return False
            
    except Exception as e:
        print(f"❌ Error testing document update: {e}")
        return False

async def test_batch_sending():
    """Test batch document sending."""
    
    print("\n📦 Testing batch document sending...")
    
    try:
        from src.prod_rag.streaming.kafka_producer import get_kafka_producer
        producer = get_kafka_producer()
        
        # Create batch of documents
        batch_documents = []
        for i in range(1, 6):  # 5 documents
            doc = {
                'document_id': f'batch_doc_{i:03d}',
                'content': f'''
                Title: Batch Document #{i}
                Created: {datetime.now().isoformat()}
                
                This is document #{i} in a batch processing test. 
                
                Batch processing allows multiple documents to be sent and 
                processed efficiently together, reducing overhead and 
                improving throughput.
                
                Document Details:
                - Document number: {i} of 5
                - Batch ID: demo_batch_001
                - Processing type: Batch streaming
                - Content type: Plain text
                
                This tests the system's ability to handle multiple documents
                simultaneously while maintaining order and consistency.
                ''',
                'metadata': {
                    'filename': f'batch_doc_{i:03d}.txt',
                    'title': f'Batch Document #{i}',
                    'batch_id': 'demo_batch_001',
                    'batch_position': i,
                    'total_in_batch': 5,
                    'source': 'batch_test',
                    'file_type': 'txt',
                    'tags': ['batch', 'test', 'streaming'],
                    'created_at': datetime.now().isoformat()
                }
            }
            batch_documents.append(doc)
        
        # Send batch
        result = await producer.send_batch_documents(
            documents=batch_documents,
            batch_id='demo_batch_001'
        )
        
        print(f"📊 Batch processing result:")
        print(f"  - Total documents: {result['total_documents']}")
        print(f"  - Successfully sent: {result['sent_successfully']}")
        print(f"  - Failed: {result['failed']}")
        print(f"  - Success rate: {result['success_rate']:.1%}")
        
        return result['success_rate'] > 0.8  # 80% success rate
        
    except Exception as e:
        print(f"❌ Error testing batch sending: {e}")
        return False

async def main():
    """Run all streaming tests."""
    
    print("🧪 Kafka Streaming Test Suite")
    print("=" * 50)
    
    test_results = {}
    
    # Test 1: Basic document sending
    print("\n🔧 Test 1: Basic Document Sending")
    test_results['basic_sending'] = await test_kafka_streaming()
    
    # Test 2: Document updates
    print("\n🔧 Test 2: Document Updates")
    test_results['document_updates'] = await test_document_update()
    
    # Test 3: Batch processing
    print("\n🔧 Test 3: Batch Processing")
    test_results['batch_processing'] = await test_batch_sending()
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Test Results Summary:")
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name.replace('_', ' ').title()}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Streaming pipeline is working correctly.")
        print("\nNext steps:")
        print("1. Start the streaming consumer to process these documents")
        print("2. Query the API to verify documents are searchable")
        print("3. Monitor Grafana dashboards for streaming metrics")
    else:
        print(f"\n⚠️  {total - passed} tests failed. Check the error messages above.")
        print("Common issues:")
        print("- Kafka not running or not accessible")
        print("- Network connectivity issues")
        print("- Missing dependencies or configuration")
    
    return passed == total

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        exit(1)
