"""Streaming data components for real-time ingestion."""

from .kafka_consumer import KafkaDocumentConsumer
from .kafka_producer import KafkaDocumentProducer
from .stream_processor import StreamProcessor

__all__ = [
    "KafkaDocumentConsumer",
    "KafkaDocumentProducer", 
    "StreamProcessor",
]
