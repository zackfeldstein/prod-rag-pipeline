"""
Data connectors for ingesting data from various sources into the data lake.
"""

import logging
from typing import Dict, List, Any, Optional, AsyncGenerator, Union
from abc import ABC, abstractmethod
import asyncio
from datetime import datetime
import json

import boto3
import asyncpg
import httpx
import pandas as pd
from sqlalchemy import create_engine
import pymongo

from ..core.config import get_settings
from .data_lake import DataLakeManager, get_data_lake_manager

logger = logging.getLogger(__name__)


class DataConnector(ABC):
    """Abstract base class for data connectors."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.data_lake = get_data_lake_manager()
    
    @abstractmethod
    async def extract_data(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Extract data from the source."""
        pass
    
    @abstractmethod
    async def validate_connection(self) -> bool:
        """Validate connection to the data source."""
        pass
    
    async def ingest_to_data_lake(
        self,
        zone: str = "raw",
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Ingest data from source to data lake.
        
        Args:
            zone: Target zone in data lake
            batch_size: Number of records per batch
            
        Returns:
            Ingestion summary
        """
        ingested_count = 0
        failed_count = 0
        assets_created = []
        
        try:
            batch = []
            async for record in self.extract_data():
                batch.append(record)
                
                if len(batch) >= batch_size:
                    try:
                        asset = await self._store_batch(batch, zone, ingested_count)
                        assets_created.append(asset)
                        ingested_count += len(batch)
                        batch = []
                    except Exception as e:
                        logger.error(f"Failed to store batch: {e}")
                        failed_count += len(batch)
                        batch = []
            
            # Store remaining records
            if batch:
                try:
                    asset = await self._store_batch(batch, zone, ingested_count)
                    assets_created.append(asset)
                    ingested_count += len(batch)
                except Exception as e:
                    logger.error(f"Failed to store final batch: {e}")
                    failed_count += len(batch)
            
            return {
                'status': 'completed',
                'records_ingested': ingested_count,
                'records_failed': failed_count,
                'assets_created': len(assets_created),
                'asset_paths': [asset.path for asset in assets_created]
            }
            
        except Exception as e:
            logger.error(f"Data ingestion failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'records_ingested': ingested_count,
                'records_failed': failed_count
            }
    
    async def _store_batch(
        self,
        batch: List[Dict[str, Any]],
        zone: str,
        batch_number: int
    ):
        """Store a batch of records in the data lake."""
        # Convert to DataFrame for efficient storage
        df = pd.DataFrame(batch)
        
        # Generate unique key
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        key = f"{self.config['source_name']}/{timestamp}_batch_{batch_number}.parquet"
        
        # Store in data lake
        return await self.data_lake.store_data(
            data=df,
            zone=zone,
            key=key,
            metadata={
                'source': self.config['source_name'],
                'batch_number': batch_number,
                'record_count': len(batch),
                'ingestion_timestamp': datetime.utcnow().isoformat()
            },
            tags=[self.config['source_name'], 'batch_ingestion'],
            source=self.config['source_name']
        )


class S3Connector(DataConnector):
    """Connector for Amazon S3 or S3-compatible storage."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.s3_client = boto3.client(
            's3',
            endpoint_url=config.get('endpoint_url'),
            aws_access_key_id=config['access_key'],
            aws_secret_access_key=config['secret_key'],
            region_name=config.get('region', 'us-east-1')
        )
    
    async def validate_connection(self) -> bool:
        """Validate S3 connection."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.s3_client.head_bucket,
                {'Bucket': self.config['bucket']}
            )
            return True
        except Exception as e:
            logger.error(f"S3 connection validation failed: {e}")
            return False
    
    async def extract_data(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Extract data from S3 objects."""
        bucket = self.config['bucket']
        prefix = self.config.get('prefix', '')
        
        try:
            # List objects
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                self.s3_client.list_objects_v2,
                {'Bucket': bucket, 'Prefix': prefix}
            )
            
            for obj in response.get('Contents', []):
                key = obj['Key']
                
                # Skip directories
                if key.endswith('/'):
                    continue
                
                try:
                    # Download object
                    object_response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self.s3_client.get_object,
                        {'Bucket': bucket, 'Key': key}
                    )
                    
                    content = object_response['Body'].read()
                    
                    # Yield record
                    yield {
                        'key': key,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'content': content,
                        'metadata': object_response.get('Metadata', {}),
                        'source_path': f"s3://{bucket}/{key}"
                    }
                    
                except Exception as e:
                    logger.error(f"Failed to process S3 object {key}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to list S3 objects: {e}")
            raise


class DatabaseConnector(DataConnector):
    """Connector for relational databases (PostgreSQL, MySQL, etc.)."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.connection_string = self._build_connection_string()
        self.engine = create_engine(self.connection_string)
    
    def _build_connection_string(self) -> str:
        """Build database connection string."""
        db_type = self.config['type']
        host = self.config['host']
        port = self.config['port']
        database = self.config['database']
        username = self.config['username']
        password = self.config['password']
        
        if db_type == 'postgresql':
            return f"postgresql://{username}:{password}@{host}:{port}/{database}"
        elif db_type == 'mysql':
            return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    async def validate_connection(self) -> bool:
        """Validate database connection."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._test_connection
            )
            return True
        except Exception as e:
            logger.error(f"Database connection validation failed: {e}")
            return False
    
    def _test_connection(self):
        """Test database connection synchronously."""
        with self.engine.connect() as conn:
            conn.execute("SELECT 1")
    
    async def extract_data(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Extract data from database tables."""
        tables = self.config.get('tables', [])
        query = self.config.get('query')
        
        if query:
            # Execute custom query
            async for record in self._execute_query(query):
                yield record
        else:
            # Extract from specified tables
            for table in tables:
                async for record in self._extract_table(table):
                    yield record
    
    async def _execute_query(self, query: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute SQL query and yield results."""
        try:
            df = await asyncio.get_event_loop().run_in_executor(
                None,
                pd.read_sql,
                query,
                self.engine
            )
            
            for _, row in df.iterrows():
                yield {
                    'table': 'custom_query',
                    'data': row.to_dict(),
                    'extracted_at': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
            raise
    
    async def _extract_table(self, table: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Extract data from a specific table."""
        try:
            chunk_size = self.config.get('chunk_size', 10000)
            
            # Get total row count
            count_query = f"SELECT COUNT(*) FROM {table}"
            total_rows = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: pd.read_sql(count_query, self.engine).iloc[0, 0]
            )
            
            # Extract in chunks
            for offset in range(0, total_rows, chunk_size):
                query = f"SELECT * FROM {table} LIMIT {chunk_size} OFFSET {offset}"
                
                df = await asyncio.get_event_loop().run_in_executor(
                    None,
                    pd.read_sql,
                    query,
                    self.engine
                )
                
                for _, row in df.iterrows():
                    yield {
                        'table': table,
                        'data': row.to_dict(),
                        'extracted_at': datetime.utcnow().isoformat()
                    }
                    
        except Exception as e:
            logger.error(f"Failed to extract table {table}: {e}")
            raise


class APIConnector(DataConnector):
    """Connector for REST APIs."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config['base_url']
        self.headers = config.get('headers', {})
        self.auth = config.get('auth')
    
    async def validate_connection(self) -> bool:
        """Validate API connection."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.base_url,
                    headers=self.headers,
                    auth=self.auth
                )
                return response.status_code < 400
        except Exception as e:
            logger.error(f"API connection validation failed: {e}")
            return False
    
    async def extract_data(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Extract data from API endpoints."""
        endpoints = self.config.get('endpoints', [])
        
        async with httpx.AsyncClient() as client:
            for endpoint in endpoints:
                async for record in self._extract_endpoint(client, endpoint):
                    yield record
    
    async def _extract_endpoint(
        self,
        client: httpx.AsyncClient,
        endpoint: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Extract data from a specific API endpoint."""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        page = 1
        page_size = self.config.get('page_size', 100)
        
        while True:
            try:
                # Handle pagination
                params = {
                    'page': page,
                    'limit': page_size,
                    **self.config.get('params', {})
                }
                
                response = await client.get(
                    url,
                    headers=self.headers,
                    auth=self.auth,
                    params=params
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Handle different response formats
                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict):
                    records = data.get('data', data.get('results', [data]))
                else:
                    records = [data]
                
                if not records:
                    break
                
                for record in records:
                    yield {
                        'endpoint': endpoint,
                        'data': record,
                        'extracted_at': datetime.utcnow().isoformat(),
                        'page': page
                    }
                
                # Check if there are more pages
                if len(records) < page_size:
                    break
                
                page += 1
                
            except Exception as e:
                logger.error(f"Failed to extract from endpoint {endpoint}: {e}")
                break


class MongoDBConnector(DataConnector):
    """Connector for MongoDB."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.connection_string = self._build_connection_string()
        self.client = None
    
    def _build_connection_string(self) -> str:
        """Build MongoDB connection string."""
        host = self.config['host']
        port = self.config['port']
        database = self.config['database']
        username = self.config.get('username')
        password = self.config.get('password')
        
        if username and password:
            return f"mongodb://{username}:{password}@{host}:{port}/{database}"
        else:
            return f"mongodb://{host}:{port}/{database}"
    
    async def validate_connection(self) -> bool:
        """Validate MongoDB connection."""
        try:
            self.client = pymongo.MongoClient(self.connection_string)
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.client.admin.command,
                'ping'
            )
            return True
        except Exception as e:
            logger.error(f"MongoDB connection validation failed: {e}")
            return False
    
    async def extract_data(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Extract data from MongoDB collections."""
        if not self.client:
            self.client = pymongo.MongoClient(self.connection_string)
        
        database_name = self.config['database']
        collections = self.config.get('collections', [])
        
        db = self.client[database_name]
        
        for collection_name in collections:
            collection = db[collection_name]
            
            # Get query filter
            query_filter = self.config.get('filter', {})
            
            try:
                cursor = collection.find(query_filter)
                
                async for document in self._iterate_cursor(cursor):
                    yield {
                        'collection': collection_name,
                        'data': document,
                        'extracted_at': datetime.utcnow().isoformat()
                    }
                    
            except Exception as e:
                logger.error(f"Failed to extract from collection {collection_name}: {e}")
                continue
    
    async def _iterate_cursor(self, cursor):
        """Iterate over MongoDB cursor asynchronously."""
        for document in cursor:
            # Convert ObjectId to string
            if '_id' in document:
                document['_id'] = str(document['_id'])
            yield document


class FileSystemConnector(DataConnector):
    """Connector for local file systems."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.root_path = Path(config['root_path'])
        self.file_patterns = config.get('file_patterns', ['*'])
    
    async def validate_connection(self) -> bool:
        """Validate file system access."""
        try:
            return self.root_path.exists() and self.root_path.is_dir()
        except Exception as e:
            logger.error(f"File system validation failed: {e}")
            return False
    
    async def extract_data(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Extract data from file system."""
        for pattern in self.file_patterns:
            for file_path in self.root_path.rglob(pattern):
                if file_path.is_file():
                    try:
                        # Read file content
                        content = await asyncio.get_event_loop().run_in_executor(
                            None,
                            file_path.read_bytes
                        )
                        
                        yield {
                            'file_path': str(file_path),
                            'file_name': file_path.name,
                            'file_size': file_path.stat().st_size,
                            'file_extension': file_path.suffix,
                            'content': content,
                            'modified_time': datetime.fromtimestamp(
                                file_path.stat().st_mtime
                            ).isoformat()
                        }
                        
                    except Exception as e:
                        logger.error(f"Failed to read file {file_path}: {e}")
                        continue


# Connector factory
def create_connector(connector_type: str, config: Dict[str, Any]) -> DataConnector:
    """Factory function to create data connectors."""
    connectors = {
        's3': S3Connector,
        'database': DatabaseConnector,
        'api': APIConnector,
        'mongodb': MongoDBConnector,
        'filesystem': FileSystemConnector
    }
    
    if connector_type not in connectors:
        raise ValueError(f"Unknown connector type: {connector_type}")
    
    return connectors[connector_type](config)
