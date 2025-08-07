"""
Document loaders for various file formats.
"""

import logging
from typing import Dict, Any, Optional, List
import asyncio
from pathlib import Path
import aiofiles
import io

# Document processing imports
import pypdf
from docx import Document as DocxDocument
import pandas as pd
from unstructured.partition.auto import partition
from unstructured.chunking.title import chunk_by_title
import markdown

from ..models.schemas import DocumentType, DocumentMetadata
from ..core.config import get_settings

logger = logging.getLogger(__name__)


class DocumentLoader:
    """Loads and processes documents from various sources and formats."""
    
    def __init__(self):
        self.settings = get_settings()
        self.max_file_size = self.settings.max_file_size_mb * 1024 * 1024  # Convert to bytes
    
    async def load_from_file(
        self, 
        file_path: str, 
        metadata: Optional[DocumentMetadata] = None
    ) -> Dict[str, Any]:
        """
        Load document from file path.
        
        Args:
            file_path: Path to the document file
            metadata: Optional metadata override
            
        Returns:
            Document content and metadata
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Check file size
        file_size = path.stat().st_size
        if file_size > self.max_file_size:
            raise ValueError(f"File too large: {file_size} bytes (max: {self.max_file_size})")
        
        # Determine file type
        file_type = self._determine_file_type(path)
        
        # Create metadata if not provided
        if metadata is None:
            metadata = DocumentMetadata(
                filename=path.name,
                file_size=file_size,
                file_type=file_type
            )
        
        # Load content based on file type
        try:
            content = await self._load_by_type(path, file_type)
            
            return {
                "content": content,
                "metadata": metadata,
                "file_path": str(path)
            }
            
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {e}")
            raise
    
    async def load_from_content(
        self,
        content: str,
        file_type: DocumentType,
        metadata: DocumentMetadata
    ) -> Dict[str, Any]:
        """
        Load document from content string.
        
        Args:
            content: Document content
            file_type: Type of document
            metadata: Document metadata
            
        Returns:
            Document content and metadata
        """
        try:
            # Process content based on type
            if file_type == DocumentType.MD:
                processed_content = self._process_markdown(content)
            elif file_type == DocumentType.HTML:
                processed_content = await self._process_html_content(content)
            else:
                processed_content = content
            
            return {
                "content": processed_content,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Error processing content: {e}")
            raise
    
    def _determine_file_type(self, path: Path) -> DocumentType:
        """Determine document type from file extension."""
        extension = path.suffix.lower()
        
        type_mapping = {
            '.pdf': DocumentType.PDF,
            '.docx': DocumentType.DOCX,
            '.txt': DocumentType.TXT,
            '.md': DocumentType.MD,
            '.markdown': DocumentType.MD,
            '.html': DocumentType.HTML,
            '.htm': DocumentType.HTML,
            '.csv': DocumentType.CSV,
            '.xlsx': DocumentType.XLSX,
            '.xls': DocumentType.XLSX
        }
        
        return type_mapping.get(extension, DocumentType.TXT)
    
    async def _load_by_type(self, path: Path, file_type: DocumentType) -> str:
        """Load content based on file type."""
        if file_type == DocumentType.PDF:
            return await self._load_pdf(path)
        elif file_type == DocumentType.DOCX:
            return await self._load_docx(path)
        elif file_type == DocumentType.TXT:
            return await self._load_text(path)
        elif file_type == DocumentType.MD:
            return await self._load_markdown(path)
        elif file_type == DocumentType.HTML:
            return await self._load_html(path)
        elif file_type == DocumentType.CSV:
            return await self._load_csv(path)
        elif file_type == DocumentType.XLSX:
            return await self._load_excel(path)
        else:
            # Fallback to text loading
            return await self._load_text(path)
    
    async def _load_pdf(self, path: Path) -> str:
        """Load PDF content."""
        def extract_pdf():
            with open(path, 'rb') as file:
                reader = pypdf.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
        
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, extract_pdf)
        return content.strip()
    
    async def _load_docx(self, path: Path) -> str:
        """Load DOCX content."""
        def extract_docx():
            doc = DocxDocument(path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, extract_docx)
        return content.strip()
    
    async def _load_text(self, path: Path) -> str:
        """Load plain text content."""
        try:
            async with aiofiles.open(path, 'r', encoding='utf-8') as file:
                content = await file.read()
                return content.strip()
        except UnicodeDecodeError:
            # Try with different encoding
            async with aiofiles.open(path, 'r', encoding='latin-1') as file:
                content = await file.read()
                return content.strip()
    
    async def _load_markdown(self, path: Path) -> str:
        """Load Markdown content and convert to text."""
        async with aiofiles.open(path, 'r', encoding='utf-8') as file:
            md_content = await file.read()
            return self._process_markdown(md_content)
    
    def _process_markdown(self, content: str) -> str:
        """Process markdown content."""
        # Convert markdown to HTML, then extract text
        html = markdown.markdown(content)
        # Simple HTML tag removal
        import re
        text = re.sub(r'<[^>]+>', '', html)
        return text.strip()
    
    async def _load_html(self, path: Path) -> str:
        """Load HTML content."""
        async with aiofiles.open(path, 'r', encoding='utf-8') as file:
            html_content = await file.read()
            return await self._process_html_content(html_content)
    
    async def _process_html_content(self, html_content: str) -> str:
        """Process HTML content to extract text."""
        def extract_html():
            # Use unstructured to parse HTML
            elements = partition(text=html_content, content_type="text/html")
            text_elements = [str(element) for element in elements]
            return "\n".join(text_elements)
        
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, extract_html)
        return content.strip()
    
    async def _load_csv(self, path: Path) -> str:
        """Load CSV content."""
        def process_csv():
            df = pd.read_csv(path)
            # Convert to readable text format
            text = f"CSV Data from {path.name}:\n\n"
            text += f"Columns: {', '.join(df.columns.tolist())}\n"
            text += f"Total rows: {len(df)}\n\n"
            
            # Add sample data (first 10 rows)
            sample_size = min(10, len(df))
            if sample_size > 0:
                text += "Sample data:\n"
                text += df.head(sample_size).to_string(index=False)
            
            return text
        
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, process_csv)
        return content
    
    async def _load_excel(self, path: Path) -> str:
        """Load Excel content."""
        def process_excel():
            # Read all sheets
            excel_file = pd.ExcelFile(path)
            text = f"Excel Data from {path.name}:\n\n"
            
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                text += f"Sheet: {sheet_name}\n"
                text += f"Columns: {', '.join(df.columns.tolist())}\n"
                text += f"Rows: {len(df)}\n"
                
                # Add sample data
                sample_size = min(5, len(df))
                if sample_size > 0:
                    text += "Sample data:\n"
                    text += df.head(sample_size).to_string(index=False)
                text += "\n\n"
            
            return text
        
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, process_excel)
        return content
    
    async def load_multiple_files(
        self, 
        file_paths: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Load multiple files concurrently.
        
        Args:
            file_paths: List of file paths to load
            
        Returns:
            List of document dictionaries
        """
        tasks = []
        for file_path in file_paths:
            task = self.load_from_file(file_path)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and log errors
        documents = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to load file {file_paths[i]}: {result}")
            else:
                documents.append(result)
        
        return documents
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats."""
        return [format_type.value for format_type in DocumentType]
    
    async def validate_file(self, file_path: str) -> Dict[str, Any]:
        """
        Validate a file for processing.
        
        Args:
            file_path: Path to file to validate
            
        Returns:
            Validation result
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                return {
                    "valid": False,
                    "error": "File does not exist"
                }
            
            file_size = path.stat().st_size
            if file_size > self.max_file_size:
                return {
                    "valid": False,
                    "error": f"File too large: {file_size} bytes (max: {self.max_file_size})"
                }
            
            file_type = self._determine_file_type(path)
            if file_type.value not in self.get_supported_formats():
                return {
                    "valid": False,
                    "error": f"Unsupported file type: {path.suffix}"
                }
            
            return {
                "valid": True,
                "file_type": file_type.value,
                "file_size": file_size,
                "filename": path.name
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }
