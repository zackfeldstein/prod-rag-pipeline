"""
Kafka consumer for processing streaming document data in real-time.
"""

import json
import logging
from typing import Dict, Any, Optional, Callable, Awaitable
import asyncio
from datetime import datetime

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from ..core.config import get_settings
from ..data.ingestion import get_ingestion_pipeline
from ..models.schemas import IngestionRequest, DocumentMetadata, DocumentType

logger = logging.getLogger(__name__)


class KafkaDocumentConsumer:
    """Kafka consumer for processing streaming documents."""
    
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.consumer = None
        self.ingestion_pipeline = None
        self.running = False
        
        self.topic_handlers = {
            'rag-documents': self._handle_document_create,
            'rag-document-updates': self._handle_document_update,
            'rag-document-deletions': self._handle_document_deletion,
            'rag-metadata-updates': self._handle_metadata_update
        }
    
    async def initialize(self):
        """Initialize consumer and ingestion pipeline."""
        try:
            # Initialize ingestion pipeline
            self.ingestion_pipeline = await get_ingestion_pipeline()
            
            # Initialize Kafka consumer
            self.consumer = KafkaConsumer(
                *self.topic_handlers.keys(),
                bootstrap_servers=['localhost:9092'],
                group_id='rag-document-processor',
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                auto_offset_reset='latest',  # Start from latest messages
                enable_auto_commit=True,
                auto_commit_interval_ms=5000,
                max_poll_records=100,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000
            )
            
            logger.info("Kafka consumer initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Kafka consumer: {e}")
            raise
    
    async def start_consuming(self):
        """Start consuming messages from Kafka topics."""
        if not self.consumer:
            await self.initialize()
        
        self.running = True
        logger.info("Starting Kafka consumer...")
        
        try:
            while self.running:
                # Poll for messages
                message_batch = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.consumer.poll,
                    1000  # timeout in ms
                )
                
                if message_batch:
                    await self._process_message_batch(message_batch)
                
                # Small delay to prevent tight loop
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error in consumer loop: {e}")
            raise
        finally:
            self.running = False
    
    async def stop_consuming(self):
        """Stop consuming messages."""
        self.running = False
        if self.consumer:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.consumer.close
                )
                logger.info("Kafka consumer stopped")
            except Exception as e:
                logger.error(f"Error stopping consumer: {e}")
    
    async def _process_message_batch(self, message_batch: Dict):
        """Process a batch of messages."""
        for topic_partition, messages in message_batch.items():
            topic = topic_partition.topic
            
            if topic in self.topic_handlers:
                handler = self.topic_handlers[topic]
                
                for message in messages:
                    try:
                        await handler(message)
                    except Exception as e:
                        logger.error(f"Error processing message from {topic}: {e}")
                        # Continue processing other messages
                        continue
    
    async def _handle_document_create(self, message):
        """Handle document creation events."""
        try:
            data = message.value
            document_id = data.get('document_id')
            document_data = data.get('data', {})
            
            logger.info(f"Processing document creation: {document_id}")
            
            # Extract document content and metadata
            content = document_data.get('content', '')
            if not content:
                logger.warning(f"No content found for document {document_id}")
                return
            
            # Create metadata
            metadata_dict = document_data.get('metadata', {})
            metadata = DocumentMetadata(
                filename=metadata_dict.get('filename', f"{document_id}.txt"),
                file_size=len(content),
                file_type=DocumentType(metadata_dict.get('file_type', 'txt')),
                title=metadata_dict.get('title', document_id),
                author=metadata_dict.get('author'),
                source_url=metadata_dict.get('source_url'),
                tags=metadata_dict.get('tags', ['streaming', 'kafka'])
            )
            
            # Create ingestion request
            request = IngestionRequest(
                file_content=content,
                metadata=metadata,
                process_immediately=True
            )
            
            # Ingest document
            response = await self.ingestion_pipeline.ingest_document(request)
            
            if response.status.value == "completed":
                logger.info(
                    f"Document {document_id} ingested successfully: "
                    f"{response.chunks_created} chunks created"
                )
            else:
                logger.error(f"Document {document_id} ingestion failed: {response.message}")
                
        except Exception as e:
            logger.error(f"Error handling document creation: {e}")
            raise
    
    async def _handle_document_update(self, message):
        """Handle document update events."""
        try:
            data = message.value
            document_id = data.get('document_id')
            update_type = data.get('update_type', 'content')
            updates = data.get('data', {})
            
            logger.info(f"Processing document update: {document_id} ({update_type})")
            
            if update_type == 'content':
                # For content updates, we need to re-ingest the document
                content = updates.get('content', '')
                if content:
                    # Delete existing document chunks
                    from ..core.rag_engine import get_rag_engine
                    rag_engine = await get_rag_engine()
                    await rag_engine.delete_document(document_id)
                    
                    # Re-ingest with new content
                    metadata_dict = updates.get('metadata', {})
                    metadata = DocumentMetadata(
                        filename=metadata_dict.get('filename', f"{document_id}.txt"),
                        file_size=len(content),
                        file_type=DocumentType(metadata_dict.get('file_type', 'txt')),
                        title=metadata_dict.get('title', document_id),
                        tags=metadata_dict.get('tags', ['streaming', 'kafka', 'updated'])
                    )
                    
                    request = IngestionRequest(
                        file_content=content,
                        metadata=metadata,
                        process_immediately=True
                    )
                    
                    response = await self.ingestion_pipeline.ingest_document(request)
                    logger.info(f"Document {document_id} re-ingested: {response.status}")
            
            elif update_type == 'metadata':
                # Handle metadata-only updates
                logger.info(f"Metadata update for document {document_id}")
                # In a full implementation, you'd update metadata in your document store
                
        except Exception as e:
            logger.error(f"Error handling document update: {e}")
            raise
    
    async def _handle_document_deletion(self, message):
        """Handle document deletion events."""
        try:
            data = message.value
            document_id = data.get('document_id')
            
            logger.info(f"Processing document deletion: {document_id}")
            
            # Delete document from RAG system
            from ..core.rag_engine import get_rag_engine
            rag_engine = await get_rag_engine()
            
            result = await rag_engine.delete_document(document_id)
            
            if result['status'] == 'success':
                logger.info(
                    f"Document {document_id} deleted successfully: "
                    f"{result['chunks_deleted']} chunks removed"
                )
            else:
                logger.error(f"Document {document_id} deletion failed: {result['message']}")
                
        except Exception as e:
            logger.error(f"Error handling document deletion: {e}")
            raise
    
    async def _handle_metadata_update(self, message):
        """Handle metadata update events."""
        try:
            data = message.value
            document_id = data.get('document_id')
            metadata = data.get('metadata', {})
            
            logger.info(f"Processing metadata update: {document_id}")
            
            # In a full implementation, you'd update metadata in your document store
            # For now, we'll just log the update
            logger.info(f"Metadata update for {document_id}: {metadata}")
            
        except Exception as e:
            logger.error(f"Error handling metadata update: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Kafka consumer."""
        try:
            if not self.consumer:
                return {
                    'status': 'not_initialized',
                    'consumer_active': False
                }
            
            # Get consumer metrics
            assignment = self.consumer.assignment()
            subscription = self.consumer.subscription()
            
            return {
                'status': 'healthy',
                'consumer_active': self.running,
                'assigned_partitions': len(assignment),
                'subscribed_topics': list(subscription),
                'topics_handled': list(self.topic_handlers.keys())
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'consumer_active': False
            }
    
    async def get_consumer_stats(self) -> Dict[str, Any]:
        """Get detailed consumer statistics."""
        try:
            if not self.consumer:
                return {'error': 'Consumer not initialized'}
            
            # Get consumer group metadata
            coordinator = self.consumer.coordinator()
            assignment = self.consumer.assignment()
            
            stats = {
                'consumer_group': 'rag-document-processor',
                'coordinator': str(coordinator) if coordinator else None,
                'assigned_partitions': len(assignment),
                'partition_details': [],
                'subscription': list(self.consumer.subscription()),
                'running': self.running
            }
            
            # Get partition details
            for tp in assignment:
                try:
                    position = self.consumer.position(tp)
                    stats['partition_details'].append({
                        'topic': tp.topic,
                        'partition': tp.partition,
                        'current_position': position
                    })
                except Exception as e:
                    stats['partition_details'].append({
                        'topic': tp.topic,
                        'partition': tp.partition,
                        'error': str(e)
                    })
            
            return stats
            
        except Exception as e:
            return {'error': str(e)}


# Global consumer instance
_kafka_consumer: Optional[KafkaDocumentConsumer] = None


async def get_kafka_consumer() -> KafkaDocumentConsumer:
    """Get or create the global Kafka consumer instance."""
    global _kafka_consumer
    
    if _kafka_consumer is None:
        _kafka_consumer = KafkaDocumentConsumer()
        await _kafka_consumer.initialize()
    
    return _kafka_consumer


async def start_streaming_consumer():
    """Start the streaming consumer as a background task."""
    consumer = await get_kafka_consumer()
    await consumer.start_consuming()
