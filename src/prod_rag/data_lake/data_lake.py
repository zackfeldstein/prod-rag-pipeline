"""
Data Lake Manager for organizing and managing data across different zones.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from datetime import datetime
import json
import asyncio
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError
import pandas as pd

from ..core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class DataAsset:
    """Represents a data asset in the data lake."""
    path: str
    zone: str
    format: str
    size_bytes: int
    created_at: datetime
    metadata: Dict[str, Any]
    tags: List[str]
    source: str
    version: str = "1.0"


class DataLakeManager:
    """Manages data lake operations across raw, processed, and curated zones."""
    
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.s3_client = None
        self.bucket_name = "datalake"
        
        # Data lake zones
        self.zones = {
            "raw": "raw-data",
            "processed": "processed-data", 
            "curated": "curated-data",
            "documents": "documents",
            "models": "models"
        }
        
        self._initialize_s3()
    
    def _initialize_s3(self):
        """Initialize S3/MinIO client."""
        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=f"http://{self.settings.minio_endpoint}",
                aws_access_key_id=self.settings.minio_access_key,
                aws_secret_access_key=self.settings.minio_secret_key,
                region_name='us-east-1'
            )
            logger.info("S3/MinIO client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
    async def store_data(
        self,
        data: Union[bytes, str, pd.DataFrame],
        zone: str,
        key: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        source: str = "unknown"
    ) -> DataAsset:
        """
        Store data in the specified zone of the data lake.
        
        Args:
            data: Data to store (bytes, string, or DataFrame)
            zone: Target zone (raw, processed, curated, documents, models)
            key: Object key/path in the zone
            metadata: Additional metadata
            tags: Tags for the data asset
            source: Source system identifier
            
        Returns:
            DataAsset object representing the stored data
        """
        if zone not in self.zones:
            raise ValueError(f"Invalid zone: {zone}. Valid zones: {list(self.zones.keys())}")
        
        bucket_name = self.zones[zone]
        full_key = f"{zone}/{key}"
        
        try:
            # Convert data to bytes if needed
            if isinstance(data, pd.DataFrame):
                # Store as parquet for efficient analytics
                buffer = data.to_parquet(index=False)
                data_bytes = buffer
                format_type = "parquet"
            elif isinstance(data, str):
                data_bytes = data.encode('utf-8')
                format_type = "text"
            else:
                data_bytes = data
                format_type = "binary"
            
            # Prepare metadata
            object_metadata = {
                'source': source,
                'zone': zone,
                'format': format_type,
                'created_at': datetime.utcnow().isoformat(),
                'tags': ','.join(tags or []),
                **(metadata or {})
            }
            
            # Store in S3/MinIO
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._upload_to_s3,
                bucket_name,
                full_key,
                data_bytes,
                object_metadata
            )
            
            # Create DataAsset
            asset = DataAsset(
                path=f"s3://{bucket_name}/{full_key}",
                zone=zone,
                format=format_type,
                size_bytes=len(data_bytes),
                created_at=datetime.utcnow(),
                metadata=metadata or {},
                tags=tags or [],
                source=source
            )
            
            logger.info(f"Stored data asset: {asset.path}")
            return asset
            
        except Exception as e:
            logger.error(f"Failed to store data in {zone}/{key}: {e}")
            raise
    
    def _upload_to_s3(self, bucket: str, key: str, data: bytes, metadata: Dict[str, str]):
        """Upload data to S3/MinIO synchronously."""
        self.s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            Metadata=metadata
        )
    
    async def load_data(
        self,
        zone: str,
        key: str,
        format_type: Optional[str] = None
    ) -> Union[bytes, str, pd.DataFrame]:
        """
        Load data from the data lake.
        
        Args:
            zone: Source zone
            key: Object key
            format_type: Expected format (auto-detected if None)
            
        Returns:
            Loaded data in appropriate format
        """
        if zone not in self.zones:
            raise ValueError(f"Invalid zone: {zone}")
        
        bucket_name = self.zones[zone]
        full_key = f"{zone}/{key}"
        
        try:
            # Download from S3/MinIO
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                self._download_from_s3,
                bucket_name,
                full_key
            )
            
            data_bytes = response['Body'].read()
            metadata = response.get('Metadata', {})
            
            # Determine format
            if not format_type:
                format_type = metadata.get('format', 'binary')
            
            # Convert based on format
            if format_type == 'parquet':
                import io
                return pd.read_parquet(io.BytesIO(data_bytes))
            elif format_type == 'text':
                return data_bytes.decode('utf-8')
            elif format_type == 'json':
                return json.loads(data_bytes.decode('utf-8'))
            else:
                return data_bytes
                
        except Exception as e:
            logger.error(f"Failed to load data from {zone}/{key}: {e}")
            raise
    
    def _download_from_s3(self, bucket: str, key: str):
        """Download data from S3/MinIO synchronously."""
        return self.s3_client.get_object(Bucket=bucket, Key=key)
    
    async def list_assets(
        self,
        zone: Optional[str] = None,
        prefix: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[DataAsset]:
        """
        List data assets in the data lake.
        
        Args:
            zone: Filter by zone
            prefix: Filter by key prefix
            tags: Filter by tags
            
        Returns:
            List of DataAsset objects
        """
        assets = []
        
        zones_to_search = [zone] if zone else list(self.zones.keys())
        
        for zone_name in zones_to_search:
            if zone_name not in self.zones:
                continue
                
            bucket_name = self.zones[zone_name]
            search_prefix = f"{zone_name}/"
            if prefix:
                search_prefix += prefix
            
            try:
                # List objects in S3/MinIO
                objects = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._list_s3_objects,
                    bucket_name,
                    search_prefix
                )
                
                for obj in objects:
                    # Get object metadata
                    metadata_response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self._get_s3_metadata,
                        bucket_name,
                        obj['Key']
                    )
                    
                    obj_metadata = metadata_response.get('Metadata', {})
                    obj_tags = obj_metadata.get('tags', '').split(',') if obj_metadata.get('tags') else []
                    
                    # Filter by tags if specified
                    if tags and not any(tag in obj_tags for tag in tags):
                        continue
                    
                    asset = DataAsset(
                        path=f"s3://{bucket_name}/{obj['Key']}",
                        zone=zone_name,
                        format=obj_metadata.get('format', 'unknown'),
                        size_bytes=obj['Size'],
                        created_at=obj['LastModified'],
                        metadata=obj_metadata,
                        tags=obj_tags,
                        source=obj_metadata.get('source', 'unknown')
                    )
                    assets.append(asset)
                    
            except Exception as e:
                logger.error(f"Failed to list assets in zone {zone_name}: {e}")
        
        return assets
    
    def _list_s3_objects(self, bucket: str, prefix: str):
        """List S3 objects synchronously."""
        response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        return response.get('Contents', [])
    
    def _get_s3_metadata(self, bucket: str, key: str):
        """Get S3 object metadata synchronously."""
        return self.s3_client.head_object(Bucket=bucket, Key=key)
    
    async def delete_asset(self, zone: str, key: str) -> bool:
        """
        Delete a data asset.
        
        Args:
            zone: Zone containing the asset
            key: Asset key
            
        Returns:
            True if deleted successfully
        """
        if zone not in self.zones:
            raise ValueError(f"Invalid zone: {zone}")
        
        bucket_name = self.zones[zone]
        full_key = f"{zone}/{key}"
        
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.s3_client.delete_object,
                {'Bucket': bucket_name, 'Key': full_key}
            )
            
            logger.info(f"Deleted asset: {zone}/{key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete asset {zone}/{key}: {e}")
            return False
    
    async def promote_data(
        self,
        source_zone: str,
        target_zone: str,
        key: str,
        transformation_func=None
    ) -> DataAsset:
        """
        Promote data from one zone to another (e.g., raw -> processed).
        
        Args:
            source_zone: Source zone
            target_zone: Target zone
            key: Data key
            transformation_func: Optional transformation function
            
        Returns:
            New DataAsset in target zone
        """
        # Load data from source zone
        data = await self.load_data(source_zone, key)
        
        # Apply transformation if provided
        if transformation_func:
            data = transformation_func(data)
        
        # Store in target zone
        return await self.store_data(
            data=data,
            zone=target_zone,
            key=key,
            metadata={'promoted_from': source_zone},
            source=f"promotion_from_{source_zone}"
        )
    
    async def get_zone_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for each zone."""
        stats = {}
        
        for zone_name, bucket_name in self.zones.items():
            try:
                assets = await self.list_assets(zone=zone_name)
                
                total_size = sum(asset.size_bytes for asset in assets)
                formats = {}
                sources = {}
                
                for asset in assets:
                    formats[asset.format] = formats.get(asset.format, 0) + 1
                    sources[asset.source] = sources.get(asset.source, 0) + 1
                
                stats[zone_name] = {
                    'total_assets': len(assets),
                    'total_size_bytes': total_size,
                    'total_size_mb': round(total_size / (1024 * 1024), 2),
                    'formats': formats,
                    'sources': sources
                }
                
            except Exception as e:
                logger.error(f"Failed to get stats for zone {zone_name}: {e}")
                stats[zone_name] = {'error': str(e)}
        
        return stats
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on data lake."""
        try:
            # Test S3 connection
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.s3_client.list_buckets
            )
            
            # Get zone statistics
            stats = await self.get_zone_statistics()
            
            return {
                'status': 'healthy',
                'zones': list(self.zones.keys()),
                'statistics': stats,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }


# Global data lake manager instance
_data_lake_manager: Optional[DataLakeManager] = None


def get_data_lake_manager() -> DataLakeManager:
    """Get or create the global data lake manager instance."""
    global _data_lake_manager
    
    if _data_lake_manager is None:
        _data_lake_manager = DataLakeManager()
    
    return _data_lake_manager
