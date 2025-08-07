"""
Production RAG Pipeline
A scalable, production-ready Retrieval Augmented Generation system.
"""

__version__ = "1.0.0"
__author__ = "RAG Team"
__email__ = "team@company.com"

from .core.config import Settings
from .core.rag_engine import RAGEngine
from .models.schemas import DocumentSchema, QuerySchema, ResponseSchema

__all__ = [
    "Settings",
    "RAGEngine", 
    "DocumentSchema",
    "QuerySchema",
    "ResponseSchema",
]
