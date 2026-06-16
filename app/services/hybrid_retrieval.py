from __future__ import annotations

import logging

from langchain_core.documents import Document

from app.config import Settings, get_settings
from app.services.keyword_extract import extract_keywords
from app.services.vectorstore import VectorStoreService

logger = logging.getLogger(__name__)


class HybridRetrievalService:
    def __init__(
        self,
        vectorstore: VectorStoreService,
        settings: Settings | None = None,
    ) -> None:
        self.vectorstore = vectorstore
        self.settings = settings or get_settings()

    def recall(self, query: str, k: int, keywords: list[str] | None = None) -> list[Document]:
        keyword_list = keywords if keywords is not None else extract_keywords(query)
        if self.settings.hybrid_enabled:
            docs = self.vectorstore.hybrid_search(query, keyword_list, k=k)
        else:
            docs = self.vectorstore.dense_search(query, k=k)

        if docs:
            return docs

        if keyword_list:
            logger.debug("Hybrid recall empty; trying keyword-only search")
            return self.vectorstore.keyword_search(keyword_list, k=k)

        return []
