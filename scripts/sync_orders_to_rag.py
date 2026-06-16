#!/usr/bin/env python3
"""Generate order statistics markdown from PostgreSQL and ingest into RAG."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.config import get_settings
from app.services.ingest import IngestService
from app.services.embeddings import create_embedding_service
from app.services.ingest import IngestService
from app.services.order_report import OrderReportGenerator
from app.services.postgres_business_store import PostgresBusinessStore
from app.services.vectorstore import VectorStoreService


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate order report markdown from PostgreSQL and ingest into RAG",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Business collection name (default: POSTGRES_BUSINESS_COLLECTION)",
    )
    parser.add_argument(
        "--from",
        dest="from_time",
        help="Start of created_at range (ISO-8601, e.g. 2025-01-01T00:00:00Z)",
    )
    parser.add_argument(
        "--to",
        dest="to_time",
        help="End of created_at range (ISO-8601)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for generated markdown (default: data/orders)",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Existing markdown file to ingest (used with --ingest-only)",
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Only generate markdown, do not ingest into RAG",
    )
    parser.add_argument(
        "--ingest-only",
        action="store_true",
        help="Only ingest an existing markdown file, skip PostgreSQL query",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count matched orders only, do not write files or ingest",
    )
    args = parser.parse_args()

    settings = get_settings()
    collection = args.collection or settings.postgres_business_collection
    output_dir = args.output_dir or (settings.data_dir / "orders")

    if args.ingest_only:
        if args.file is None:
            print("--ingest-only requires --file", file=sys.stderr)
            return 1
        report_path = args.file.resolve()
        if not report_path.is_file():
            print(f"File not found: {report_path}", file=sys.stderr)
            return 1
    else:
        if not args.from_time or not args.to_time:
            print("--from and --to are required unless --ingest-only is set", file=sys.stderr)
            return 1

        start = parse_datetime(args.from_time)
        end = parse_datetime(args.to_time)

        business_store = PostgresBusinessStore(settings)
        if not business_store.is_available:
            print("PostgreSQL business store is unavailable", file=sys.stderr)
            return 1

        generator = OrderReportGenerator(business_store, settings)

        if args.dry_run:
            orders = generator.fetch_orders(start, end, collection=collection)
            print(f"Collection: {collection}")
            print(f"Time range: {start.isoformat()} .. {end.isoformat()}")
            print(f"Matched orders: {len(orders)}")
            print("Dry run — no files written")
            return 0

        report_path, order_count = generator.generate_report_file(
            start,
            end,
            collection=collection,
            output_dir=output_dir,
        )
        print(f"Collection: {collection}")
        print(f"Time range: {start.isoformat()} .. {end.isoformat()}")
        print(f"Orders processed: {order_count}")
        print(f"Report written: {report_path}")

        if args.generate_only:
            return 0

    embeddings = create_embedding_service(settings)
    vectorstore = VectorStoreService(embeddings, settings)
    vectorstore.ensure_collection()
    ingest_service = IngestService(vectorstore, settings)

    try:
        chunks_added, source = ingest_service.ingest_file(report_path, force=True)
    except Exception as exc:
        print(f"Ingest failed: {exc}", file=sys.stderr)
        return 1

    print(f"Ingested: {report_path}")
    print(f"Chunks added: {chunks_added}")
    print(f"Source: {source}")
    print(f"Total vector chunks: {vectorstore.count()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
