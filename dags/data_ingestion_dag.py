"""
Apache Airflow DAG for data ingestion pipeline.
This DAG orchestrates the complete data lifecycle from sources to RAG-ready format.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.sensors.filesystem import FileSensor
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.models import Variable
from airflow.utils.task_group import TaskGroup

import pandas as pd
import json
import sys
import os

# Add project root to Python path
sys.path.append('/opt/airflow/dags')
sys.path.append('/app/src')

# Default arguments for the DAG
default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'catchup': False,
}

# DAG definition
dag = DAG(
    'data_ingestion_pipeline',
    default_args=default_args,
    description='Complete data ingestion pipeline for RAG system',
    schedule_interval=timedelta(hours=6),  # Run every 6 hours
    max_active_runs=1,
    tags=['data-ingestion', 'rag', 'etl'],
)

# Configuration from Airflow Variables
DATA_SOURCES_CONFIG = Variable.get("data_sources_config", default_var={}, deserialize_json=True)
QUALITY_CHECKS_CONFIG = Variable.get("quality_checks_config", default_var={}, deserialize_json=True)


def extract_from_s3(**context) -> str:
    """Extract data from S3 sources."""
    from src.prod_rag.data_lake.connectors import create_connector
    from src.prod_rag.data_lake.data_lake import get_data_lake_manager
    
    print("Starting S3 data extraction...")
    
    s3_config = DATA_SOURCES_CONFIG.get('s3', {})
    if not s3_config:
        print("No S3 configuration found, skipping...")
        return "skipped"
    
    try:
        # Create S3 connector
        connector = create_connector('s3', s3_config)
        
        # Validate connection
        if not connector.validate_connection():
            raise Exception("S3 connection validation failed")
        
        # Ingest data to raw zone
        result = connector.ingest_to_data_lake(
            zone='raw',
            batch_size=1000
        )
        
        print(f"S3 extraction completed: {result}")
        
        # Store result in XCom
        context['task_instance'].xcom_push(key='s3_extraction_result', value=result)
        
        return "success"
        
    except Exception as e:
        print(f"S3 extraction failed: {e}")
        raise


def extract_from_database(**context) -> str:
    """Extract data from database sources."""
    from src.prod_rag.data_lake.connectors import create_connector
    
    print("Starting database data extraction...")
    
    db_config = DATA_SOURCES_CONFIG.get('database', {})
    if not db_config:
        print("No database configuration found, skipping...")
        return "skipped"
    
    try:
        # Create database connector
        connector = create_connector('database', db_config)
        
        # Validate connection
        if not connector.validate_connection():
            raise Exception("Database connection validation failed")
        
        # Ingest data to raw zone
        result = connector.ingest_to_data_lake(
            zone='raw',
            batch_size=5000
        )
        
        print(f"Database extraction completed: {result}")
        
        # Store result in XCom
        context['task_instance'].xcom_push(key='db_extraction_result', value=result)
        
        return "success"
        
    except Exception as e:
        print(f"Database extraction failed: {e}")
        raise


def extract_from_apis(**context) -> str:
    """Extract data from API sources."""
    from src.prod_rag.data_lake.connectors import create_connector
    
    print("Starting API data extraction...")
    
    api_config = DATA_SOURCES_CONFIG.get('api', {})
    if not api_config:
        print("No API configuration found, skipping...")
        return "skipped"
    
    try:
        # Create API connector
        connector = create_connector('api', api_config)
        
        # Validate connection
        if not connector.validate_connection():
            raise Exception("API connection validation failed")
        
        # Ingest data to raw zone
        result = connector.ingest_to_data_lake(
            zone='raw',
            batch_size=500
        )
        
        print(f"API extraction completed: {result}")
        
        # Store result in XCom
        context['task_instance'].xcom_push(key='api_extraction_result', value=result)
        
        return "success"
        
    except Exception as e:
        print(f"API extraction failed: {e}")
        raise


def validate_raw_data(**context) -> str:
    """Validate data quality in raw zone."""
    from src.prod_rag.data_lake.data_lake import get_data_lake_manager
    
    print("Starting raw data validation...")
    
    data_lake = get_data_lake_manager()
    
    try:
        # Get recent raw data assets
        assets = data_lake.list_assets(zone='raw')
        
        # Filter assets from this DAG run
        execution_date = context['execution_date']
        recent_assets = [
            asset for asset in assets
            if asset.created_at.date() == execution_date.date()
        ]
        
        if not recent_assets:
            print("No recent assets found to validate")
            return "no_data"
        
        validation_results = []
        
        for asset in recent_assets:
            try:
                # Load data for validation
                data = data_lake.load_data('raw', asset.path.split('/')[-1])
                
                if isinstance(data, pd.DataFrame):
                    # Basic data quality checks
                    checks = {
                        'asset_path': asset.path,
                        'row_count': len(data),
                        'column_count': len(data.columns),
                        'null_percentage': (data.isnull().sum().sum() / data.size) * 100,
                        'duplicate_rows': data.duplicated().sum(),
                        'memory_usage_mb': data.memory_usage(deep=True).sum() / (1024 * 1024)
                    }
                    
                    validation_results.append(checks)
                    
            except Exception as e:
                print(f"Failed to validate asset {asset.path}: {e}")
                continue
        
        print(f"Validation completed for {len(validation_results)} assets")
        
        # Store validation results
        context['task_instance'].xcom_push(key='validation_results', value=validation_results)
        
        return "success"
        
    except Exception as e:
        print(f"Data validation failed: {e}")
        raise


def process_raw_data(**context) -> str:
    """Process raw data and move to processed zone."""
    from src.prod_rag.data_lake.data_lake import get_data_lake_manager
    
    print("Starting data processing...")
    
    data_lake = get_data_lake_manager()
    
    try:
        # Get validation results from previous task
        validation_results = context['task_instance'].xcom_pull(
            task_ids='validate_raw_data',
            key='validation_results'
        )
        
        if not validation_results:
            print("No validation results found")
            return "no_data"
        
        processed_assets = []
        
        for result in validation_results:
            asset_path = result['asset_path']
            asset_key = asset_path.split('/')[-1]
            
            try:
                # Load raw data
                raw_data = data_lake.load_data('raw', asset_key)
                
                if isinstance(raw_data, pd.DataFrame):
                    # Data processing pipeline
                    processed_data = _process_dataframe(raw_data)
                    
                    # Store in processed zone
                    processed_key = f"processed_{asset_key}"
                    processed_asset = data_lake.store_data(
                        data=processed_data,
                        zone='processed',
                        key=processed_key,
                        metadata={
                            'original_asset': asset_path,
                            'processing_timestamp': datetime.utcnow().isoformat(),
                            'row_count': len(processed_data),
                            'processing_applied': ['deduplication', 'null_handling', 'standardization']
                        },
                        tags=['processed', 'cleaned'],
                        source='data_processing_pipeline'
                    )
                    
                    processed_assets.append(processed_asset.path)
                    
            except Exception as e:
                print(f"Failed to process asset {asset_path}: {e}")
                continue
        
        print(f"Processing completed for {len(processed_assets)} assets")
        
        # Store processing results
        context['task_instance'].xcom_push(key='processed_assets', value=processed_assets)
        
        return "success"
        
    except Exception as e:
        print(f"Data processing failed: {e}")
        raise


def _process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply data processing transformations to DataFrame."""
    # Remove duplicates
    df = df.drop_duplicates()
    
    # Handle missing values
    # For numeric columns, fill with median
    numeric_columns = df.select_dtypes(include=['number']).columns
    df[numeric_columns] = df[numeric_columns].fillna(df[numeric_columns].median())
    
    # For text columns, fill with empty string
    text_columns = df.select_dtypes(include=['object']).columns
    df[text_columns] = df[text_columns].fillna('')
    
    # Standardize text columns (lowercase, strip whitespace)
    for col in text_columns:
        df[col] = df[col].astype(str).str.lower().str.strip()
    
    # Add processing metadata
    df['processed_at'] = datetime.utcnow().isoformat()
    
    return df


def curate_data(**context) -> str:
    """Curate processed data for RAG ingestion."""
    from src.prod_rag.data_lake.data_lake import get_data_lake_manager
    
    print("Starting data curation...")
    
    data_lake = get_data_lake_manager()
    
    try:
        # Get processed assets from previous task
        processed_assets = context['task_instance'].xcom_pull(
            task_ids='process_raw_data',
            key='processed_assets'
        )
        
        if not processed_assets:
            print("No processed assets found")
            return "no_data"
        
        curated_assets = []
        
        for asset_path in processed_assets:
            asset_key = asset_path.split('/')[-1]
            
            try:
                # Load processed data
                processed_data = data_lake.load_data('processed', asset_key)
                
                if isinstance(processed_data, pd.DataFrame):
                    # Curation pipeline
                    curated_data = _curate_dataframe(processed_data)
                    
                    # Store in curated zone
                    curated_key = f"curated_{asset_key}"
                    curated_asset = data_lake.store_data(
                        data=curated_data,
                        zone='curated',
                        key=curated_key,
                        metadata={
                            'source_asset': asset_path,
                            'curation_timestamp': datetime.utcnow().isoformat(),
                            'row_count': len(curated_data),
                            'ready_for_rag': True
                        },
                        tags=['curated', 'rag_ready'],
                        source='data_curation_pipeline'
                    )
                    
                    curated_assets.append(curated_asset.path)
                    
            except Exception as e:
                print(f"Failed to curate asset {asset_path}: {e}")
                continue
        
        print(f"Curation completed for {len(curated_assets)} assets")
        
        # Store curation results
        context['task_instance'].xcom_push(key='curated_assets', value=curated_assets)
        
        return "success"
        
    except Exception as e:
        print(f"Data curation failed: {e}")
        raise


def _curate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply curation transformations for RAG readiness."""
    # Identify text columns that could be documents
    text_columns = df.select_dtypes(include=['object']).columns
    
    # Create document-ready format
    curated_data = []
    
    for idx, row in df.iterrows():
        # Combine text fields into document content
        text_parts = []
        metadata = {}
        
        for col in df.columns:
            if col in text_columns and len(str(row[col])) > 50:  # Substantial text content
                text_parts.append(f"{col}: {row[col]}")
            else:
                metadata[col] = row[col]
        
        if text_parts:
            document = {
                'content': '\n'.join(text_parts),
                'metadata': metadata,
                'document_id': f"doc_{idx}",
                'source_row': idx
            }
            curated_data.append(document)
    
    return pd.DataFrame(curated_data)


def ingest_to_rag(**context) -> str:
    """Ingest curated data into RAG system."""
    print("Starting RAG ingestion...")
    
    try:
        # Get curated assets from previous task
        curated_assets = context['task_instance'].xcom_pull(
            task_ids='curate_data',
            key='curated_assets'
        )
        
        if not curated_assets:
            print("No curated assets found")
            return "no_data"
        
        # This would integrate with your RAG ingestion pipeline
        # For now, we'll simulate the process
        
        from src.prod_rag.data.ingestion import get_ingestion_pipeline
        from src.prod_rag.data_lake.data_lake import get_data_lake_manager
        
        data_lake = get_data_lake_manager()
        ingestion_pipeline = get_ingestion_pipeline()
        
        total_documents = 0
        total_chunks = 0
        
        for asset_path in curated_assets:
            asset_key = asset_path.split('/')[-1]
            
            try:
                # Load curated data
                curated_data = data_lake.load_data('curated', asset_key)
                
                if isinstance(curated_data, pd.DataFrame):
                    # Process each document
                    for _, row in curated_data.iterrows():
                        if 'content' in row and row['content']:
                            # Create ingestion request
                            from src.prod_rag.models.schemas import IngestionRequest, DocumentMetadata, DocumentType
                            
                            metadata = DocumentMetadata(
                                filename=f"{row.get('document_id', 'unknown')}.txt",
                                file_size=len(str(row['content'])),
                                file_type=DocumentType.TXT,
                                title=row.get('document_id'),
                                source_url=f"data_lake://curated/{asset_key}",
                                tags=['data_lake', 'curated']
                            )
                            
                            request = IngestionRequest(
                                file_content=str(row['content']),
                                metadata=metadata,
                                process_immediately=True
                            )
                            
                            # Ingest document
                            response = ingestion_pipeline.ingest_document(request)
                            
                            total_documents += 1
                            total_chunks += response.chunks_created
                            
            except Exception as e:
                print(f"Failed to ingest asset {asset_path}: {e}")
                continue
        
        result = {
            'total_documents_ingested': total_documents,
            'total_chunks_created': total_chunks,
            'assets_processed': len(curated_assets)
        }
        
        print(f"RAG ingestion completed: {result}")
        
        # Store ingestion results
        context['task_instance'].xcom_push(key='rag_ingestion_result', value=result)
        
        return "success"
        
    except Exception as e:
        print(f"RAG ingestion failed: {e}")
        raise


def generate_pipeline_report(**context) -> str:
    """Generate pipeline execution report."""
    print("Generating pipeline report...")
    
    try:
        # Collect results from all tasks
        s3_result = context['task_instance'].xcom_pull(
            task_ids='extract_from_s3',
            key='s3_extraction_result'
        )
        
        db_result = context['task_instance'].xcom_pull(
            task_ids='extract_from_database', 
            key='db_extraction_result'
        )
        
        api_result = context['task_instance'].xcom_pull(
            task_ids='extract_from_apis',
            key='api_extraction_result'
        )
        
        validation_results = context['task_instance'].xcom_pull(
            task_ids='validate_raw_data',
            key='validation_results'
        )
        
        rag_result = context['task_instance'].xcom_pull(
            task_ids='ingest_to_rag',
            key='rag_ingestion_result'
        )
        
        # Create comprehensive report
        report = {
            'pipeline_execution': {
                'dag_id': context['dag'].dag_id,
                'execution_date': context['execution_date'].isoformat(),
                'start_time': context['task_instance'].start_date.isoformat(),
                'end_time': datetime.utcnow().isoformat()
            },
            'extraction_results': {
                's3': s3_result,
                'database': db_result,
                'api': api_result
            },
            'validation_summary': {
                'assets_validated': len(validation_results) if validation_results else 0,
                'total_rows': sum(r.get('row_count', 0) for r in validation_results or []),
                'total_columns': sum(r.get('column_count', 0) for r in validation_results or [])
            },
            'rag_ingestion': rag_result,
            'pipeline_status': 'completed'
        }
        
        print(f"Pipeline report: {json.dumps(report, indent=2)}")
        
        # Store report in data lake
        from src.prod_rag.data_lake.data_lake import get_data_lake_manager
        
        data_lake = get_data_lake_manager()
        
        report_key = f"pipeline_reports/{context['execution_date'].strftime('%Y%m%d_%H%M%S')}_report.json"
        data_lake.store_data(
            data=json.dumps(report, indent=2),
            zone='processed',
            key=report_key,
            metadata={'report_type': 'pipeline_execution'},
            tags=['report', 'pipeline'],
            source='airflow_pipeline'
        )
        
        return "success"
        
    except Exception as e:
        print(f"Report generation failed: {e}")
        raise


# Task definitions
with TaskGroup('data_extraction', dag=dag) as extraction_group:
    extract_s3_task = PythonOperator(
        task_id='extract_from_s3',
        python_callable=extract_from_s3,
        dag=dag,
    )
    
    extract_db_task = PythonOperator(
        task_id='extract_from_database',
        python_callable=extract_from_database,
        dag=dag,
    )
    
    extract_api_task = PythonOperator(
        task_id='extract_from_apis',
        python_callable=extract_from_apis,
        dag=dag,
    )

validate_task = PythonOperator(
    task_id='validate_raw_data',
    python_callable=validate_raw_data,
    dag=dag,
)

process_task = PythonOperator(
    task_id='process_raw_data',
    python_callable=process_raw_data,
    dag=dag,
)

curate_task = PythonOperator(
    task_id='curate_data',
    python_callable=curate_data,
    dag=dag,
)

rag_ingest_task = PythonOperator(
    task_id='ingest_to_rag',
    python_callable=ingest_to_rag,
    dag=dag,
)

report_task = PythonOperator(
    task_id='generate_pipeline_report',
    python_callable=generate_pipeline_report,
    dag=dag,
)

# Task dependencies
extraction_group >> validate_task >> process_task >> curate_task >> rag_ingest_task >> report_task
