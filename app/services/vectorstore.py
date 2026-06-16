import logging
from typing import Any
from uuid import uuid4

from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.hybrid.fusion import reciprocal_rank_fusion

from app.config import Settings, get_settings
from app.services.embeddings import (
    BGEM3EmbeddingService,
    DENSE_DIM,
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    create_embedding_service,
)

logger = logging.getLogger(__name__)

_CONTENT_FIELD = "content"
_LEGACY_VECTOR_DIM = 768


class VectorStoreService:
    def __init__(
        self,
        embeddings: BGEM3EmbeddingService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._embeddings = embeddings or create_embedding_service(self.settings)
        client_kwargs: dict[str, Any] = {"url": self.settings.qdrant_url}
        if self.settings.qdrant_api_key:
            client_kwargs["api_key"] = self.settings.qdrant_api_key
        self._client = QdrantClient(**client_kwargs)
        self._collection = self.settings.qdrant_collection

    @property
    def embeddings(self) -> BGEM3EmbeddingService:
        return self._embeddings

    def _collection_exists(self) -> bool:
        try:
            collections = self._client.get_collections().collections
            return any(item.name == self._collection for item in collections)
        except Exception:
            return False

    def _get_collection_info(self) -> rest.CollectionInfo | None:
        if not self._collection_exists():
            return None
        try:
            return self._client.get_collection(self._collection)
        except UnexpectedResponse:
            return None

    def is_hybrid_collection(self) -> bool:
        info = self._get_collection_info()
        if info is None:
            return False
        vectors = info.config.params.vectors
        if isinstance(vectors, dict):
            return DENSE_VECTOR_NAME in vectors
        return False

    def ensure_collection(self) -> None:
        if self._collection_exists():
            return

        if self.settings.hybrid_enabled:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config={
                    DENSE_VECTOR_NAME: rest.VectorParams(
                        size=DENSE_DIM,
                        distance=rest.Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    SPARSE_VECTOR_NAME: rest.SparseVectorParams(),
                },
            )
        else:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=rest.VectorParams(
                    size=DENSE_DIM,
                    distance=rest.Distance.COSINE,
                ),
            )

        self.ensure_payload_indexes()

    def ensure_payload_indexes(self) -> None:
        if not self._collection_exists():
            return

        index_specs = [
            ("source", rest.PayloadSchemaType.KEYWORD),
            ("chunk_id", rest.PayloadSchemaType.KEYWORD),
            ("keywords", rest.PayloadSchemaType.KEYWORD),
            ("content", rest.PayloadSchemaType.TEXT),
            ("chunk_index", rest.PayloadSchemaType.INTEGER),
        ]
        for field_name, field_schema in index_specs:
            try:
                self._client.create_payload_index(
                    collection_name=self._collection,
                    field_name=field_name,
                    field_schema=field_schema,
                )
            except UnexpectedResponse:
                logger.debug("Payload index may already exist for %s", field_name)
            except Exception:
                logger.exception("Failed to create payload index for %s", field_name)

    def ping(self) -> bool:
        try:
            self._client.get_collections()
            return True
        except Exception:
            logger.exception("Qdrant ping failed")
            return False

    def _build_payload(self, doc: Document, chunk_id: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            _CONTENT_FIELD: doc.page_content,
            "chunk_id": chunk_id,
        }
        for key, value in doc.metadata.items():
            if value is not None and key not in payload:
                payload[key] = value
        return payload

    def _point_from_doc(
        self,
        doc: Document,
        dense_vector: list[float],
        sparse_vector: rest.SparseVector | None,
        chunk_id: str,
    ) -> rest.PointStruct:
        payload = self._build_payload(doc, chunk_id)
        if self.settings.hybrid_enabled and sparse_vector is not None:
            vector: rest.VectorStruct = {
                DENSE_VECTOR_NAME: dense_vector,
                SPARSE_VECTOR_NAME: sparse_vector,
            }
        else:
            vector = dense_vector
        return rest.PointStruct(id=chunk_id, vector=vector, payload=payload)

    def add_documents(self, docs: list[Document]) -> list[str]:
        if not docs:
            return []

        texts = [doc.page_content for doc in docs]
        if self.settings.hybrid_enabled:
            dense_vectors, sparse_vectors = self._embeddings.encode_with_sparse(texts)
        else:
            dense_vectors = self._embeddings.embed_documents(texts)
            sparse_vectors = [None] * len(docs)

        self.ensure_collection()

        ids: list[str] = []
        points: list[rest.PointStruct] = []
        for doc, dense_vector, sparse_vector in zip(docs, dense_vectors, sparse_vectors, strict=True):
            chunk_id = str(doc.metadata.get("chunk_id") or uuid4())
            ids.append(chunk_id)
            points.append(
                self._point_from_doc(doc, dense_vector, sparse_vector, chunk_id)
            )

        self._client.upsert(collection_name=self._collection, points=points)
        return ids

    def delete_by_source(self, source: str) -> None:
        if not self._collection_exists():
            return
        try:
            self._client.delete(
                collection_name=self._collection,
                points_selector=rest.FilterSelector(
                    filter=rest.Filter(
                        must=[
                            rest.FieldCondition(
                                key="source",
                                match=rest.MatchValue(value=source),
                            )
                        ]
                    )
                ),
            )
        except UnexpectedResponse:
            logger.exception("Qdrant delete_by_source failed for source=%s", source)

    def count(self) -> int:
        info = self._get_collection_info()
        if info is None:
            return 0
        return int(info.points_count or 0)

    def _hit_to_document(self, hit: rest.ScoredPoint | rest.Record) -> Document:
        payload = dict(hit.payload or {})
        metadata = {key: value for key, value in payload.items() if key != _CONTENT_FIELD}
        chunk_id = metadata.get("chunk_id") or str(hit.id)
        metadata.setdefault("chunk_id", chunk_id)
        return Document(
            page_content=str(payload.get(_CONTENT_FIELD, "")),
            metadata=metadata,
        )

    def _legacy_similarity_search(self, query: str, k: int) -> list[Document]:
        query_vector = self._embeddings.embed_query(query)
        hits = self._client.search(
            collection_name=self._collection,
            query_vector=query_vector,
            limit=k,
            with_payload=True,
        )
        return [self._hit_to_document(hit) for hit in hits]

    def dense_search(self, query: str, k: int) -> list[Document]:
        if not self._collection_exists():
            return []

        info = self._get_collection_info()
        if not info or not info.points_count:
            return []

        if not self.is_hybrid_collection():
            return self._legacy_similarity_search(query, k)

        dense_vector = self._embeddings.embed_query(query)
        hits = self._client.search(
            collection_name=self._collection,
            query_vector=rest.NamedVector(name=DENSE_VECTOR_NAME, vector=dense_vector),
            limit=k,
            with_payload=True,
        )
        return [self._hit_to_document(hit) for hit in hits]

    def sparse_search(self, query: str, k: int) -> list[Document]:
        if not self._collection_exists() or not self.is_hybrid_collection():
            return []

        info = self._get_collection_info()
        if not info or not info.points_count:
            return []

        _, sparse_vector = self._embeddings.encode_query_with_sparse(query)
        hits = self._client.search(
            collection_name=self._collection,
            query_vector=rest.NamedSparseVector(
                name=SPARSE_VECTOR_NAME,
                vector=sparse_vector,
            ),
            limit=k,
            with_payload=True,
        )
        return [self._hit_to_document(hit) for hit in hits]

    def keyword_search(self, keywords: list[str], k: int) -> list[Document]:
        if not keywords or not self._collection_exists():
            return []

        info = self._get_collection_info()
        if not info or not info.points_count:
            return []

        should_conditions: list[rest.Condition] = []
        for keyword in keywords:
            should_conditions.append(
                rest.FieldCondition(
                    key=_CONTENT_FIELD,
                    match=rest.MatchText(text=keyword),
                )
            )
            should_conditions.append(
                rest.FieldCondition(
                    key="keywords",
                    match=rest.MatchValue(value=keyword),
                )
            )

        points, _ = self._client.scroll(
            collection_name=self._collection,
            scroll_filter=rest.Filter(should=should_conditions),
            limit=k,
            with_payload=True,
        )
        return [self._hit_to_document(point) for point in points]

    def _documents_to_scored_points(self, docs: list[Document]) -> list[rest.ScoredPoint]:
        scored: list[rest.ScoredPoint] = []
        for rank, doc in enumerate(docs):
            chunk_id = str(doc.metadata.get("chunk_id", ""))
            scored.append(
                rest.ScoredPoint(
                    id=chunk_id,
                    score=float(len(docs) - rank),
                    payload={
                        _CONTENT_FIELD: doc.page_content,
                        **doc.metadata,
                    },
                    version=0,
                )
            )
        return scored

    def hybrid_search(
        self,
        query: str,
        keywords: list[str],
        k: int,
    ) -> list[Document]:
        if not self._collection_exists():
            return []

        info = self._get_collection_info()
        if not info or not info.points_count:
            return []

        if not self.settings.hybrid_enabled or not self.is_hybrid_collection():
            return self.dense_search(query, k)

        scored_groups: list[list[rest.ScoredPoint]] = []

        dense_docs = self.dense_search(query, k)
        if dense_docs:
            scored_groups.append(self._documents_to_scored_points(dense_docs))

        sparse_docs = self.sparse_search(query, k)
        if sparse_docs:
            scored_groups.append(self._documents_to_scored_points(sparse_docs))

        if keywords:
            keyword_docs = self.keyword_search(keywords, k)
            if keyword_docs:
                scored_groups.append(self._documents_to_scored_points(keyword_docs))

        if not scored_groups:
            return []

        if len(scored_groups) == 1:
            return dense_docs or sparse_docs or self.keyword_search(keywords, k) or []

        merged = reciprocal_rank_fusion(scored_groups, limit=k)
        return [self._hit_to_document(point) for point in merged]

    def similarity_search(self, query: str, k: int | None = None) -> list[Document]:
        top_k = k if k is not None else self.settings.top_k
        return self.dense_search(query, top_k)

    def fetch_neighbor_chunks(
        self,
        source: str,
        chunk_index: int,
        window: int = 1,
    ) -> list[Document]:
        if not self._collection_exists() or window <= 0:
            return []

        low = max(0, chunk_index - window)
        high = chunk_index + window
        points, _ = self._client.scroll(
            collection_name=self._collection,
            scroll_filter=rest.Filter(
                must=[
                    rest.FieldCondition(
                        key="source",
                        match=rest.MatchValue(value=source),
                    ),
                    rest.FieldCondition(
                        key="chunk_index",
                        range=rest.Range(gte=low, lte=high),
                    ),
                ]
            ),
            limit=window * 2 + 1,
            with_payload=True,
        )
        documents = [self._hit_to_document(point) for point in points]
        documents.sort(key=lambda doc: int(doc.metadata.get("chunk_index", 0) or 0))
        return documents
