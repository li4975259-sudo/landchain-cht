#!/usr/bin/env python3
"""CLI to ingest documents from the data/ directory into Qdrant."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.config import get_settings
from app.services.embeddings import create_embedding_service
from app.services.ingest import IngestService
from app.services.vectorstore import VectorStoreService


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest documents into the RAG vector store")
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Directory to scan (default: DATA_DIR from settings)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest all files regardless of mtime index",
    )
    args = parser.parse_args()

    settings = get_settings()
    embeddings = create_embedding_service(settings)
    vectorstore = VectorStoreService(embeddings, settings)
    vectorstore.ensure_collection()
    ingest_service = IngestService(vectorstore, settings)

    target_dir = args.dir or settings.data_dir
    files_processed, chunks_added, skipped = ingest_service.ingest_directory(
        target_dir,
        force=args.force,
    )

    print(f"Directory: {target_dir.resolve()}")
    print(f"Files processed: {files_processed}")
    print(f"Chunks added: {chunks_added}")
    print(f"Total vector chunks: {vectorstore.count()}")
    if skipped:
        print("Skipped:")
        for item in skipped:
            print(f"  - {item}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
