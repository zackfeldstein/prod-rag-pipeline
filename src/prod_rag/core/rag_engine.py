"""
Core RAG engine implementation using LangChain and Milvus.
"""

import asyncio
import logging
import time
from typing import List, Optional, Dict, Any
from datetime import datetime

from langchain.llms.base import LLM
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.schema import BaseRetriever, Document
from langchain.callbacks.manager import CallbackManagerForRetrieverRun

from .config import Settings, get_settings
from .embeddings import get_embedding_manager, EmbeddingManager
from .vector_store import get_vector_store_manager, VectorStoreManager
from ..models.schemas import (
    QuerySchema, 
    ResponseSchema, 
    SearchResult,
    ChunkSchema
)
from ..utils.cache import CacheManager
from ..utils.metrics import MetricsCollector

logger = logging.getLogger(__name__)


class MilvusRetriever(BaseRetriever):
    """Custom LangChain retriever using Milvus vector store."""
    
    def __init__(
        self,
        vector_store: VectorStoreManager,
        embedding_manager: EmbeddingManager,
        k: int = 5,
        similarity_threshold: float = 0.7
    ):
        super().__init__()
        self.vector_store = vector_store
        self.embedding_manager = embedding_manager
        self.k = k
        self.similarity_threshold = similarity_threshold
    
    async def aget_relevant_documents(
        self, 
        query: str, 
        *, 
        run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """Asynchronously retrieve relevant documents."""
        try:
            # Generate query embedding
            query_embedding = await self.embedding_manager.encode_single(query)
            
            # Search vector store
            search_results = await self.vector_store.search(
                query_embedding=query_embedding,
                limit=self.k,
                similarity_threshold=self.similarity_threshold
            )
            
            # Convert to LangChain Documents
            documents = []
            for result in search_results:
                doc = Document(
                    page_content=result.content,
                    metadata={
                        "id": result.id,
                        "document_id": result.document_id,
                        "chunk_index": result.chunk_index,
                        "score": result.score,
                        **result.metadata
                    }
                )
                documents.append(doc)
            
            return documents
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {e}")
            return []
    
    def _get_relevant_documents(
        self, 
        query: str, 
        *, 
        run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """Synchronous wrapper for async retrieval."""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(
            self.aget_relevant_documents(query, run_manager=run_manager)
        )


class SimpleLocalLLM(LLM):
    """Simple local LLM implementation for demonstration."""
    
    model_name: str = "local-llm"
    temperature: float = 0.7
    max_length: int = 512
    
    @property
    def _llm_type(self) -> str:
        return "simple_local"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate response using a simple rule-based approach.
        In production, replace this with actual LLM inference.
        """
        # Simple response generation for demonstration
        # In production, replace with actual model inference
        context_parts = prompt.split("Context:")
        if len(context_parts) > 1:
            context = context_parts[1].split("Question:")[0].strip()
            question = context_parts[1].split("Question:")[1].strip() if "Question:" in context_parts[1] else ""
            
            if context and question:
                return f"Based on the provided context, {question.lower()} can be answered using the information about {context[:100]}..."
        
        return "I need more specific information to provide a detailed answer."


class RAGEngine:
    """Production RAG engine with LangChain integration."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.embedding_manager: Optional[EmbeddingManager] = None
        self.vector_store: Optional[VectorStoreManager] = None
        self.retriever: Optional[MilvusRetriever] = None
        self.llm: Optional[LLM] = None
        self.chain: Optional[LLMChain] = None
        self.cache: Optional[CacheManager] = None
        self.metrics: Optional[MetricsCollector] = None
        self.initialized = False
        
        # RAG prompt template
        self.prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""You are a helpful AI assistant. Use the following context to answer the question.
If you cannot answer the question based on the context, say so clearly.

Context:
{context}

Question: {question}

Answer:"""
        )
    
    async def initialize(self) -> None:
        """Initialize all RAG components."""
        if self.initialized:
            return
        
        try:
            logger.info("Initializing RAG engine...")
            
            # Initialize components
            self.embedding_manager = await get_embedding_manager()
            self.vector_store = await get_vector_store_manager()
            
            # Initialize cache and metrics
            self.cache = CacheManager(self.settings)
            self.metrics = MetricsCollector()
            
            # Create retriever
            self.retriever = MilvusRetriever(
                vector_store=self.vector_store,
                embedding_manager=self.embedding_manager,
                k=5,
                similarity_threshold=self.settings.similarity_threshold if hasattr(self.settings, 'similarity_threshold') else 0.7
            )
            
            # Initialize LLM (using simple implementation for now)
            self.llm = SimpleLocalLLM(
                temperature=self.settings.llm_temperature,
                max_length=self.settings.llm_max_length
            )
            
            # Create LangChain
            self.chain = LLMChain(
                llm=self.llm,
                prompt=self.prompt_template
            )
            
            self.initialized = True
            logger.info("RAG engine initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG engine: {e}")
            raise
    
    async def query(self, query_request: QuerySchema) -> ResponseSchema:
        """
        Process a RAG query and return a response.
        
        Args:
            query_request: Query request containing question and parameters
            
        Returns:
            RAG response with answer and sources
        """
        if not self.initialized:
            await self.initialize()
        
        start_time = time.time()
        query_text = query_request.query
        
        try:
            # Check cache first
            if self.cache and self.settings.enable_cache:
                cached_response = await self.cache.get(query_text)
                if cached_response:
                    logger.info("Returning cached response")
                    self.metrics.record_cache_hit()
                    return ResponseSchema.parse_obj(cached_response)
            
            # Retrieve relevant documents
            logger.info(f"Processing query: {query_text}")
            
            # Generate query embedding
            query_embedding = await self.embedding_manager.encode_single(query_text)
            
            # Search for relevant chunks
            search_results = await self.vector_store.search(
                query_embedding=query_embedding,
                limit=query_request.max_results,
                similarity_threshold=query_request.similarity_threshold
            )
            
            if not search_results:
                # No relevant documents found
                response = ResponseSchema(
                    query=query_text,
                    answer="I couldn't find relevant information to answer your question.",
                    sources=[],
                    confidence_score=0.0,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    model_info={
                        "embedding_model": self.settings.embedding_model,
                        "llm_model": self.settings.llm_model_name
                    }
                )
            else:
                # Combine context from retrieved documents
                context = "\n\n".join([result.content for result in search_results])
                
                # Generate response using LLM
                llm_response = await self._generate_response(context, query_text)
                
                # Calculate confidence score based on retrieval scores
                avg_score = sum(result.score for result in search_results) / len(search_results)
                
                response = ResponseSchema(
                    query=query_text,
                    answer=llm_response,
                    sources=search_results,
                    confidence_score=float(avg_score),
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    model_info={
                        "embedding_model": self.settings.embedding_model,
                        "llm_model": self.settings.llm_model_name
                    }
                )
            
            # Cache the response
            if self.cache and self.settings.enable_cache:
                await self.cache.set(
                    query_text, 
                    response.dict(), 
                    ttl=self.settings.cache_ttl
                )
            
            # Record metrics
            self.metrics.record_query(
                processing_time=response.processing_time_ms,
                num_sources=len(response.sources),
                confidence_score=response.confidence_score
            )
            
            logger.info(f"Query processed in {response.processing_time_ms}ms")
            return response
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            
            # Return error response
            return ResponseSchema(
                query=query_text,
                answer=f"An error occurred while processing your query: {str(e)}",
                sources=[],
                confidence_score=0.0,
                processing_time_ms=int((time.time() - start_time) * 1000),
                model_info={
                    "embedding_model": self.settings.embedding_model,
                    "llm_model": self.settings.llm_model_name
                }
            )
    
    async def _generate_response(self, context: str, question: str) -> str:
        """Generate response using LLM with given context and question."""
        try:
            # Run LLM chain in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self.chain.run,
                {"context": context, "question": question}
            )
            return response
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return "I encountered an error while generating the response."
    
    async def add_documents(self, chunks: List[ChunkSchema]) -> Dict[str, Any]:
        """
        Add document chunks to the vector store.
        
        Args:
            chunks: List of document chunks to add
            
        Returns:
            Result summary
        """
        if not self.initialized:
            await self.initialize()
        
        try:
            start_time = time.time()
            
            # Generate embeddings for chunks that don't have them
            chunks_to_embed = [chunk for chunk in chunks if not chunk.embedding]
            if chunks_to_embed:
                texts = [chunk.content for chunk in chunks_to_embed]
                embeddings = await self.embedding_manager.encode_texts(texts)
                
                for chunk, embedding in zip(chunks_to_embed, embeddings):
                    chunk.embedding = embedding
            
            # Insert into vector store
            inserted_ids = await self.vector_store.insert_chunks(chunks)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            logger.info(f"Added {len(chunks)} chunks in {processing_time}ms")
            
            return {
                "status": "success",
                "chunks_added": len(chunks),
                "processing_time_ms": processing_time,
                "inserted_ids": inserted_ids
            }
            
        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            return {
                "status": "error",
                "message": str(e),
                "chunks_added": 0
            }
    
    async def delete_document(self, document_id: str) -> Dict[str, Any]:
        """
        Delete all chunks for a specific document.
        
        Args:
            document_id: Document ID to delete
            
        Returns:
            Deletion result
        """
        if not self.initialized:
            await self.initialize()
        
        try:
            deleted_count = await self.vector_store.delete_by_document_id(document_id)
            
            # Clear related cache entries
            if self.cache:
                await self.cache.clear_pattern(f"*{document_id}*")
            
            return {
                "status": "success",
                "document_id": document_id,
                "chunks_deleted": deleted_count
            }
            
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "chunks_deleted": 0
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow(),
            "services": {}
        }
        
        try:
            # Check embedding service
            if self.embedding_manager:
                embedding_health = await self.embedding_manager.health_check()
                health_status["services"]["embeddings"] = embedding_health["status"]
            else:
                health_status["services"]["embeddings"] = "not_initialized"
            
            # Check vector store
            if self.vector_store:
                vector_health = await self.vector_store.health_check()
                health_status["services"]["vector_store"] = vector_health["status"]
            else:
                health_status["services"]["vector_store"] = "not_initialized"
            
            # Check cache
            if self.cache:
                cache_health = await self.cache.health_check()
                health_status["services"]["cache"] = cache_health["status"]
            else:
                health_status["services"]["cache"] = "not_initialized"
            
            # Overall status
            if any(status != "healthy" for status in health_status["services"].values()):
                health_status["status"] = "degraded"
            
        except Exception as e:
            logger.error(f"Health check error: {e}")
            health_status["status"] = "error"
            health_status["error"] = str(e)
        
        return health_status
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        if self.metrics:
            return self.metrics.get_metrics()
        return {}
    
    async def close(self) -> None:
        """Clean up resources."""
        try:
            if self.vector_store:
                await self.vector_store.close()
            
            if self.cache:
                await self.cache.close()
            
            logger.info("RAG engine closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing RAG engine: {e}")


# Global RAG engine instance
_rag_engine: Optional[RAGEngine] = None


async def get_rag_engine() -> RAGEngine:
    """Get or create the global RAG engine instance."""
    global _rag_engine
    
    if _rag_engine is None:
        _rag_engine = RAGEngine()
        await _rag_engine.initialize()
    
    return _rag_engine
