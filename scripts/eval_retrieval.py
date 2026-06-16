#!/usr/bin/env python3
"""Evaluate retrieval quality against a golden query set."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.config import get_settings
from app.services.chunk_expand import ChunkExpandService
from app.services.embeddings import create_embedding_service
from app.services.hybrid_retrieval import HybridRetrievalService
from app.services.query_rewrite import QueryRewriteService
from app.services.rerank import RerankService
from app.services.retrieval import RetrievalService
from app.services.vectorstore import VectorStoreService


@dataclass
class GoldenQuery:
    query: str
    expected_sources: list[str]
    expected_keywords: list[str]
    category: str = "general"


def load_golden(path: Path) -> list[GoldenQuery]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        GoldenQuery(
            query=item["query"],
            expected_sources=item.get("expected_sources", []),
            expected_keywords=item.get("expected_keywords", []),
            category=item.get("category", "general"),
        )
        for item in raw
    ]


def _source_match(doc_source: str, expected: str) -> bool:
    return expected.lower() in doc_source.lower() or doc_source.lower() in expected.lower()


def _is_relevant(docs, item: GoldenQuery) -> bool:
    for doc in docs:
        source = str(doc.metadata.get("source", ""))
        filename = str(doc.metadata.get("filename", ""))
        content = doc.page_content
        for expected_source in item.expected_sources:
            if _source_match(source, expected_source) or _source_match(filename, expected_source):
                return True
        for keyword in item.expected_keywords:
            if keyword.lower() in content.lower():
                return True
    return False


def _first_relevant_rank(docs, item: GoldenQuery) -> int | None:
    for rank, doc in enumerate(docs, start=1):
        source = str(doc.metadata.get("source", ""))
        filename = str(doc.metadata.get("filename", ""))
        content = doc.page_content
        for expected_source in item.expected_sources:
            if _source_match(source, expected_source) or _source_match(filename, expected_source):
                return rank
        for keyword in item.expected_keywords:
            if keyword.lower() in content.lower():
                return rank
    return None


def build_retrieval_service() -> RetrievalService:
    settings = get_settings()
    embeddings = create_embedding_service(settings)
    vectorstore = VectorStoreService(embeddings, settings)
    rerank_service = RerankService(settings)
    return RetrievalService(
        vectorstore,
        rerank_service,
        query_rewrite_service=QueryRewriteService(settings=settings),
        hybrid_retrieval_service=HybridRetrievalService(vectorstore, settings),
        chunk_expand_service=ChunkExpandService(vectorstore, settings),
        settings=settings,
    )


def evaluate(items: list[GoldenQuery], top_k: int) -> dict:
    retrieval = build_retrieval_service()
    recall_hits = 0
    mrr_total = 0.0
    empty_count = 0
    by_category: dict[str, dict[str, float | int]] = {}

    for item in items:
        docs = retrieval.retrieve(item.query, top_k=top_k)
        if not docs:
            empty_count += 1
        relevant = _is_relevant(docs, item)
        if relevant:
            recall_hits += 1
        rank = _first_relevant_rank(docs, item)
        if rank is not None:
            mrr_total += 1.0 / rank

        bucket = by_category.setdefault(
            item.category,
            {"count": 0, "recall_hits": 0, "empty": 0},
        )
        bucket["count"] = int(bucket["count"]) + 1
        if relevant:
            bucket["recall_hits"] = int(bucket["recall_hits"]) + 1
        if not docs:
            bucket["empty"] = int(bucket["empty"]) + 1

    total = len(items) or 1
    return {
        "total": len(items),
        "top_k": top_k,
        "recall_at_k": recall_hits / total,
        "mrr": mrr_total / total,
        "empty_rate": empty_count / total,
        "by_category": by_category,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval against golden queries")
    parser.add_argument(
        "--golden",
        type=Path,
        default=ROOT / "data" / "eval" / "golden_queries.json",
        help="Path to golden query JSON",
    )
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write JSON report to this path",
    )
    args = parser.parse_args()

    if not args.golden.exists():
        print(f"Golden set not found: {args.golden}")
        return 1

    items = load_golden(args.golden)
    report = evaluate(items, top_k=args.top_k)

    print(f"Golden queries: {report['total']}")
    print(f"Recall@{report['top_k']}: {report['recall_at_k']:.3f}")
    print(f"MRR: {report['mrr']:.3f}")
    print(f"Empty rate: {report['empty_rate']:.3f}")
    print("By category:")
    for category, stats in report["by_category"].items():
        count = int(stats["count"]) or 1
        recall = int(stats["recall_hits"]) / count
        empty = int(stats["empty"]) / count
        print(f"  {category}: recall={recall:.3f} empty={empty:.3f} n={count}")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report written to {args.report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
