#!/usr/bin/env python3
"""Reindex all ingested documents into a hybrid Qdrant collection."""

from __future__ import annotations

import argparse
import json
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


def _load_sources(index_path: Path) -> list[Path]:
    if not index_path.exists():
        return []
    data = json.loads(index_path.read_text(encoding="utf-8"))
    return [Path(source) for source in data.keys()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Reindex documents into hybrid Qdrant collection")
    parser.add_argument(
        "--target-collection",
        default=None,
        help="Override QDRANT_COLLECTION for reindex target",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Directory to scan in addition to indexed sources",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-ingest even when mtime unchanged",
    )
    parser.add_argument(
        "--create-text-index",
        action="store_true",
        help="Ensure payload indexes (content TEXT, keywords, chunk_index)",
    )
    args = parser.parse_args()

    settings = get_settings()
    if args.target_collection:
        settings = settings.model_copy(update={"qdrant_collection": args.target_collection})

    embeddings = create_embedding_service(settings)
    vectorstore = VectorStoreService(embeddings, settings)
    vectorstore.ensure_collection()
    if args.create_text_index:
        vectorstore.ensure_payload_indexes()

    ingest_service = IngestService(vectorstore, settings)

    sources = _load_sources(settings.ingest_index_path)
    if args.dir:
        target_dir = args.dir.resolve()
        sources.extend(
            path
            for path in sorted(target_dir.rglob("*"))
            if path.is_file() and path.suffix.lower() in settings.allowed_extensions
        )

    unique_sources = list(dict.fromkeys(str(path.resolve()) for path in sources))
    files_processed = 0
    chunks_added = 0
    skipped: list[str] = []

    for source in unique_sources:
        path = Path(source)
        if not path.exists():
            skipped.append(f"{source} (missing)")
            continue
        try:
            added, _ = ingest_service.ingest_file(path, force=True)
            if added == 0:
                skipped.append(source)
            else:
                files_processed += 1
                chunks_added += added
        except Exception as exc:
            skipped.append(f"{source} ({exc})")

    print(f"Collection: {settings.qdrant_collection}")
    print(f"Hybrid enabled: {settings.hybrid_enabled}")
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
