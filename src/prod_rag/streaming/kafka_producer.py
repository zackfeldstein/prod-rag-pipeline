"""
Kafka producer for streaming document data to the RAG pipeline.
"""

import json
import logging
from typing import Dict, Any, Optional, List
import asyncio
from datetime import datetime

from kafka import KafkaProducer
from kafka.errors import KafkaError

from ..core.config import get_settings

logger = logging.getLogger(__name__)


class KafkaDocumentProducer:
    """Kafka producer for streaming documents to RAG pipeline."""
    
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.producer = None
        self.topic_config = {
            'documents': 'rag-documents',
            'updates': 'rag-document-updates',
            'deletions': 'rag-document-deletions',
            'metadata': 'rag-metadata-updates'
        }
    
    def _initialize_producer(self):
        """Initialize Kafka producer."""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=['localhost:9092'],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',  # Wait for all replicas to acknowledge
                retries=3,
                batch_size=16384,
                linger_ms=10,
                buffer_memory=33554432,
                compression_type='gzip'
            )
            logger.info("Kafka producer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            raise
    
    async def send_document(
        self,
        document_data: Dict[str, Any],
        document_id: Optional[str] = None,
        partition_key: Optional[str] = None
    ) -> bool:
        """
        Send a document to the documents topic for ingestion.
        
        Args:
            document_data: Document content and metadata
            document_id: Optional document ID for keying
            partition_key: Optional partition key for distribution
            
        Returns:
            True if sent successfully
        """
        if not self.producer:
            self._initialize_producer()
        
        try:
            # Prepare message
            message = {
                'event_type': 'document_create',
                'timestamp': datetime.utcnow().isoformat(),
                'document_id': document_id or f"doc_{datetime.utcnow().timestamp()}",
                'data': document_data
            }
            
            # Use document_id as key for partitioning if not specified
            key = partition_key or document_id
            
            # Send to Kafka
            future = self.producer.send(
                topic=self.topic_config['documents'],
                key=key,
                value=message
            )
            
            # Wait for send to complete
            await asyncio.get_event_loop().run_in_executor(
                None, 
                future.get,
                60  # timeout in seconds
            )
            
            logger.info(f"Document sent to Kafka: {document_id}")
            return True
            
        except KafkaError as e:
            logger.error(f"Kafka error sending document: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending document to Kafka: {e}")
            return False
    
    async def send_document_update(
        self,
        document_id: str,
        updates: Dict[str, Any],
        update_type: str = "content"
    ) -> bool:
        """
        Send a document update event.
        
        Args:
            document_id: ID of document to update
            updates: Update data
            update_type: Type of update (content, metadata, etc.)
            
        Returns:
            True if sent successfully
        """
        if not self.producer:
            self._initialize_producer()
        
        try:
            message = {
                'event_type': 'document_update',
                'timestamp': datetime.utcnow().isoformat(),
                'document_id': document_id,
                'update_type': update_type,
                'data': updates
            }
            
            future = self.producer.send(
                topic=self.topic_config['updates'],
                key=document_id,
                value=message
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None, 
                future.get,
                60
            )
            
            logger.info(f"Document update sent to Kafka: {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending document update: {e}")
            return False
    
    async def send_document_deletion(self, document_id: str) -> bool:
        """
        Send a document deletion event.
        
        Args:
            document_id: ID of document to delete
            
        Returns:
            True if sent successfully
        """
        if not self.producer:
            self._initialize_producer()
        
        try:
            message = {
                'event_type': 'document_delete',
                'timestamp': datetime.utcnow().isoformat(),
                'document_id': document_id
            }
            
            future = self.producer.send(
                topic=self.topic_config['deletions'],
                key=document_id,
                value=message
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None, 
                future.get,
                60
            )
            
            logger.info(f"Document deletion sent to Kafka: {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending document deletion: {e}")
            return False
    
    async def send_metadata_update(
        self,
        document_id: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Send metadata update for a document.
        
        Args:
            document_id: Document ID
            metadata: New metadata
            
        Returns:
            True if sent successfully
        """
        if not self.producer:
            self._initialize_producer()
        
        try:
            message = {
                'event_type': 'metadata_update',
                'timestamp': datetime.utcnow().isoformat(),
                'document_id': document_id,
                'metadata': metadata
            }
            
            future = self.producer.send(
                topic=self.topic_config['metadata'],
                key=document_id,
                value=message
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None, 
                future.get,
                60
            )
            
            logger.info(f"Metadata update sent to Kafka: {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending metadata update: {e}")
            return False
    
    async def send_batch_documents(
        self,
        documents: List[Dict[str, Any]],
        batch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a batch of documents efficiently.
        
        Args:
            documents: List of document data
            batch_id: Optional batch identifier
            
        Returns:
            Batch processing results
        """
        if not self.producer:
            self._initialize_producer()
        
        batch_id = batch_id or f"batch_{datetime.utcnow().timestamp()}"
        sent_count = 0
        failed_count = 0
        
        try:
            # Send documents in batch
            for i, doc_data in enumerate(documents):
                doc_id = doc_data.get('document_id', f"{batch_id}_doc_{i}")
                
                success = await self.send_document(
                    document_data=doc_data,
                    document_id=doc_id,
                    partition_key=batch_id
                )
                
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
            
            # Flush producer to ensure all messages are sent
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.producer.flush
            )
            
            result = {
                'batch_id': batch_id,
                'total_documents': len(documents),
                'sent_successfully': sent_count,
                'failed': failed_count,
                'success_rate': sent_count / len(documents) if documents else 0
            }
            
            logger.info(f"Batch processing completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in batch document sending: {e}")
            return {
                'batch_id': batch_id,
                'total_documents': len(documents),
                'sent_successfully': sent_count,
                'failed': failed_count + (len(documents) - sent_count),
                'error': str(e)
            }
    
    def close(self):
        """Close the Kafka producer."""
        if self.producer:
            try:
                self.producer.flush()
                self.producer.close()
                logger.info("Kafka producer closed")
            except Exception as e:
                logger.error(f"Error closing Kafka producer: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Kafka producer."""
        try:
            if not self.producer:
                self._initialize_producer()
            
            # Test message send
            test_message = {
                'event_type': 'health_check',
                'timestamp': datetime.utcnow().isoformat(),
                'test': True
            }
            
            future = self.producer.send(
                topic='health-check',  # Use a test topic
                value=test_message
            )
            
            # Wait for confirmation
            await asyncio.get_event_loop().run_in_executor(
                None,
                future.get,
                10  # Short timeout for health check
            )
            
            return {
                'status': 'healthy',
                'producer_active': True,
                'topics_configured': list(self.topic_config.values())
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'producer_active': False
            }


# Global producer instance
_kafka_producer: Optional[KafkaDocumentProducer] = None


def get_kafka_producer() -> KafkaDocumentProducer:
    """Get or create the global Kafka producer instance."""
    global _kafka_producer
    
    if _kafka_producer is None:
        _kafka_producer = KafkaDocumentProducer()
    
    return _kafka_producer
