from __future__ import annotations

import logging

from langchain_core.documents import Document

from app.config import Settings, get_settings
from app.services.vectorstore import VectorStoreService

logger = logging.getLogger(__name__)


class ChunkExpandService:
    def __init__(
        self,
        vectorstore: VectorStoreService,
        settings: Settings | None = None,
    ) -> None:
        self.vectorstore = vectorstore
        self.settings = settings or get_settings()

    def expand(self, documents: list[Document]) -> list[Document]:
        if not documents or not self.settings.neighbor_expand_enabled:
            return documents

        merged: dict[str, Document] = {}
        order: list[str] = []

        def add_doc(doc: Document) -> None:
            chunk_id = str(doc.metadata.get("chunk_id", ""))
            if not chunk_id or chunk_id in merged:
                return
            merged[chunk_id] = doc
            order.append(chunk_id)

        for doc in documents:
            add_doc(doc)
            source = doc.metadata.get("source")
            chunk_index = doc.metadata.get("chunk_index")
            if source is None or chunk_index is None:
                continue
            try:
                index = int(chunk_index)
            except (TypeError, ValueError):
                continue

            neighbors = self.vectorstore.fetch_neighbor_chunks(
                source=str(source),
                chunk_index=index,
                window=self.settings.neighbor_window,
            )
            for neighbor in neighbors:
                add_doc(neighbor)
                if len(order) >= self.settings.expand_max_chunks:
                    break
            if len(order) >= self.settings.expand_max_chunks:
                break

        expanded = [merged[chunk_id] for chunk_id in order[: self.settings.expand_max_chunks]]
        expanded.sort(
            key=lambda doc: (
                str(doc.metadata.get("source", "")),
                int(doc.metadata.get("chunk_index", 0) or 0),
            )
        )
        if len(expanded) != len(documents):
            logger.debug(
                "Neighbor expansion: %s -> %s chunks",
                len(documents),
                len(expanded),
            )
        return expanded
