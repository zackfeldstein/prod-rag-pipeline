"""
Text processing utilities for document ingestion.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
import tiktoken

logger = logging.getLogger(__name__)


class TextProcessor:
    """Handles text processing and chunking for RAG pipeline."""
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        encoding_name: str = "cl100k_base"
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding_name = encoding_name
        
        # Initialize tokenizer
        try:
            self.tokenizer = tiktoken.get_encoding(encoding_name)
        except Exception as e:
            logger.warning(f"Failed to load tokenizer {encoding_name}: {e}")
            self.tokenizer = None
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=self._token_length if self.tokenizer else len,
            separators=["\n\n", "\n", " ", ""]
        )
    
    def _token_length(self, text: str) -> int:
        """Calculate token length using tiktoken."""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        return len(text)
    
    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text content.
        
        Args:
            text: Raw text content
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep punctuation
        text = re.sub(r'[^\w\s\.,!?;:\-\(\)\[\]\'\"]+', '', text)
        
        # Remove multiple consecutive punctuation
        text = re.sub(r'([.!?]){2,}', r'\1', text)
        
        # Normalize quotes
        text = re.sub(r'[""''`]', '"', text)
        text = re.sub(r'['']', "'", text)
        
        # Strip and ensure single spaces
        text = ' '.join(text.split())
        
        return text.strip()
    
    def extract_metadata_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract metadata from text content.
        
        Args:
            text: Text content
            
        Returns:
            Dictionary of extracted metadata
        """
        metadata = {}
        
        # Word count
        words = text.split()
        metadata['word_count'] = len(words)
        
        # Character count
        metadata['char_count'] = len(text)
        
        # Token count (if tokenizer available)
        if self.tokenizer:
            metadata['token_count'] = self._token_length(text)
        
        # Paragraph count
        paragraphs = text.split('\n\n')
        metadata['paragraph_count'] = len([p for p in paragraphs if p.strip()])
        
        # Sentence count (rough estimate)
        sentences = re.split(r'[.!?]+', text)
        metadata['sentence_count'] = len([s for s in sentences if s.strip()])
        
        # Language hints (simple heuristics)
        metadata['language_hints'] = self._detect_language_hints(text)
        
        return metadata
    
    def _detect_language_hints(self, text: str) -> Dict[str, Any]:
        """Detect language hints from text."""
        hints = {}
        
        # Common English words
        english_words = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
        english_count = sum(1 for word in english_words if word in text.lower())
        hints['english_word_count'] = english_count
        
        # Special characters that might indicate specific languages
        if re.search(r'[àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]', text):
            hints['has_accented_chars'] = True
        
        if re.search(r'[А-Яа-я]', text):
            hints['has_cyrillic'] = True
            
        if re.search(r'[一-龯]', text):
            hints['has_chinese'] = True
        
        return hints
    
    def chunk_text(
        self, 
        text: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Split text into chunks with metadata.
        
        Args:
            text: Text to chunk
            metadata: Additional metadata to include
            
        Returns:
            List of chunk dictionaries
        """
        if not text.strip():
            return []
        
        # Clean the text
        cleaned_text = self.clean_text(text)
        
        # Create document for splitting
        doc = Document(page_content=cleaned_text, metadata=metadata or {})
        
        # Split into chunks
        chunks = self.text_splitter.split_documents([doc])
        
        # Convert to dictionaries with additional metadata
        chunk_dicts = []
        for i, chunk in enumerate(chunks):
            chunk_metadata = {
                **(metadata or {}),
                'chunk_index': i,
                'chunk_size': len(chunk.page_content),
                'chunk_token_count': self._token_length(chunk.page_content),
                **self.extract_metadata_from_text(chunk.page_content)
            }
            
            chunk_dict = {
                'content': chunk.page_content,
                'metadata': chunk_metadata,
                'chunk_index': i
            }
            
            chunk_dicts.append(chunk_dict)
        
        logger.info(f"Created {len(chunk_dicts)} chunks from text")
        return chunk_dicts
    
    def chunk_document(
        self,
        content: str,
        document_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Chunk a complete document with proper metadata handling.
        
        Args:
            content: Document content
            document_metadata: Document-level metadata
            
        Returns:
            List of chunk dictionaries
        """
        # Extract content metadata
        content_metadata = self.extract_metadata_from_text(content)
        
        # Combine with document metadata
        combined_metadata = {
            **document_metadata,
            **content_metadata,
            'total_chunks': 0  # Will be updated after chunking
        }
        
        # Create chunks
        chunks = self.chunk_text(content, combined_metadata)
        
        # Update total chunks count in each chunk
        for chunk in chunks:
            chunk['metadata']['total_chunks'] = len(chunks)
        
        return chunks
    
    def validate_chunk_size(self, text: str, max_tokens: Optional[int] = None) -> bool:
        """
        Validate if text fits within chunk size limits.
        
        Args:
            text: Text to validate
            max_tokens: Maximum allowed tokens (defaults to chunk_size)
            
        Returns:
            True if text fits within limits
        """
        if not max_tokens:
            max_tokens = self.chunk_size
        
        token_count = self._token_length(text)
        return token_count <= max_tokens
    
    def estimate_chunks(self, text: str) -> int:
        """
        Estimate number of chunks that will be created from text.
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated number of chunks
        """
        if not text:
            return 0
        
        # Simple estimation based on token count
        token_count = self._token_length(text)
        effective_chunk_size = self.chunk_size - self.chunk_overlap
        
        estimated_chunks = max(1, (token_count + effective_chunk_size - 1) // effective_chunk_size)
        return estimated_chunks
    
    def get_processing_stats(self, text: str) -> Dict[str, Any]:
        """
        Get comprehensive processing statistics for text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Processing statistics
        """
        stats = {
            'original_length': len(text),
            'cleaned_length': len(self.clean_text(text)),
            'estimated_chunks': self.estimate_chunks(text),
            'token_count': self._token_length(text),
            'processing_settings': {
                'chunk_size': self.chunk_size,
                'chunk_overlap': self.chunk_overlap,
                'encoding': self.encoding_name
            }
        }
        
        # Add content metadata
        stats.update(self.extract_metadata_from_text(text))
        
        return stats
