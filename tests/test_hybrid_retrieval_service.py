import unittest

from langchain_core.documents import Document

from app.config import Settings
from app.services.hybrid_retrieval import HybridRetrievalService


class _VectorStoreStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    def hybrid_search(self, query: str, keywords: list[str], k: int) -> list[Document]:
        self.calls.append(("hybrid", query, k))
        return []

    def dense_search(self, query: str, k: int) -> list[Document]:
        self.calls.append(("dense", query, k))
        return [Document(page_content="dense", metadata={"chunk_id": "d1"})]

    def keyword_search(self, keywords: list[str], k: int) -> list[Document]:
        self.calls.append(("keyword", ",".join(keywords), k))
        return [Document(page_content="kw", metadata={"chunk_id": "k1"})]


class HybridRetrievalServiceTests(unittest.TestCase):
    def test_falls_back_to_keyword_search_when_hybrid_empty(self) -> None:
        store = _VectorStoreStub()
        service = HybridRetrievalService(store, Settings(hybrid_enabled=True))
        docs = service.recall("query", k=3, keywords=["order"])
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["chunk_id"], "k1")
        self.assertEqual(store.calls[0][0], "hybrid")
        self.assertEqual(store.calls[1][0], "keyword")

    def test_uses_dense_search_when_hybrid_disabled(self) -> None:
        store = _VectorStoreStub()
        service = HybridRetrievalService(store, Settings(hybrid_enabled=False))
        docs = service.recall("query", k=2, keywords=["order"])
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["chunk_id"], "d1")
        self.assertEqual(store.calls[0][0], "dense")


if __name__ == "__main__":
    unittest.main()
