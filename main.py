#!/usr/bin/env python3
"""
Main entry point for the Production RAG Pipeline.
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.prod_rag.api.main import app
from src.prod_rag.core.config import get_settings
from src.prod_rag.data.ingestion import get_ingestion_pipeline


async def main():
    """Main function for CLI operations."""
    parser = argparse.ArgumentParser(description="Production RAG Pipeline")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Server command
    server_parser = subparsers.add_parser("serve", help="Start the API server")
    server_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    server_parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    server_parser.add_argument("--workers", type=int, default=1, help="Number of workers")
    server_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest documents")
    ingest_parser.add_argument("files", nargs="+", help="Files to ingest")
    ingest_parser.add_argument("--batch-size", type=int, default=5, help="Batch size for processing")
    
    # Health check command
    health_parser = subparsers.add_parser("health", help="Check system health")
    
    # Initialize command
    init_parser = subparsers.add_parser("init", help="Initialize the system")
    
    args = parser.parse_args()
    
    if args.command == "serve":
        import uvicorn
        uvicorn.run(
            "src.prod_rag.api.main:app",
            host=args.host,
            port=args.port,
            workers=args.workers,
            reload=args.reload
        )
    
    elif args.command == "ingest":
        print(f"🔄 Ingesting {len(args.files)} files...")
        
        pipeline = await get_ingestion_pipeline()
        responses = await pipeline.batch_ingest_files(
            file_paths=args.files,
            max_concurrent=args.batch_size
        )
        
        successful = sum(1 for r in responses if r.status.value == "completed")
        total_chunks = sum(r.chunks_created for r in responses)
        
        print(f"✅ Ingestion completed:")
        print(f"  - Successful: {successful}/{len(args.files)}")
        print(f"  - Total chunks created: {total_chunks}")
        
        for response in responses:
            if response.status.value != "completed":
                print(f"  ❌ Failed: {response.message}")
    
    elif args.command == "health":
        print("🔍 Checking system health...")
        
        try:
            from src.prod_rag.core.rag_engine import get_rag_engine
            
            rag_engine = await get_rag_engine()
            health = await rag_engine.health_check()
            
            print(f"Overall status: {health['status']}")
            print("Service statuses:")
            for service, status in health.get('services', {}).items():
                emoji = "✅" if status == "healthy" else "❌"
                print(f"  {emoji} {service}: {status}")
        
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            sys.exit(1)
    
    elif args.command == "init":
        print("🔧 Initializing system...")
        
        try:
            from src.prod_rag.core.rag_engine import get_rag_engine
            from src.prod_rag.data.ingestion import get_ingestion_pipeline
            
            print("  - Initializing RAG engine...")
            await get_rag_engine()
            
            print("  - Initializing ingestion pipeline...")
            await get_ingestion_pipeline()
            
            print("✅ System initialized successfully!")
        
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            sys.exit(1)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
