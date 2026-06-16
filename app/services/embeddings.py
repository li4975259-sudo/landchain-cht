from __future__ import annotations

import logging
from typing import Any

from langchain_core.embeddings import Embeddings
from qdrant_client.http import models as rest

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
DENSE_DIM = 1024


def lexical_weights_to_sparse(lexical_weights: dict[Any, float]) -> rest.SparseVector:
    indices: list[int] = []
    values: list[float] = []
    for token_id, weight in lexical_weights.items():
        indices.append(int(token_id))
        values.append(float(weight))
    return rest.SparseVector(indices=indices, values=values)


class BGEM3EmbeddingService(Embeddings):
    """Dense + sparse embeddings via FlagEmbedding BGEM3FlagModel."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._model: Any = None
        self._load_failed = False

    @property
    def available(self) -> bool:
        return not self._load_failed

    def _get_model(self) -> Any:
        if self._load_failed:
            raise RuntimeError("BGEM3 embedding model previously failed to load")
        if self._model is None:
            try:
                from FlagEmbedding import BGEM3FlagModel

                use_fp16 = self.settings.embed_device != "cpu"
                self._model = BGEM3FlagModel(
                    self.settings.embed_model,
                    use_fp16=use_fp16,
                    device=self.settings.embed_device,
                )
            except Exception:
                self._load_failed = True
                logger.exception(
                    "Failed to load embedding model %s",
                    self.settings.embed_model,
                )
                raise
        return self._model

    def _encode_batch(self, texts: list[str]) -> tuple[list[list[float]], list[rest.SparseVector]]:
        if not texts:
            return [], []

        model = self._get_model()
        output = model.encode(
            texts,
            batch_size=12,
            max_length=8192,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense_vectors = [vector.tolist() for vector in output["dense_vecs"]]
        sparse_vectors = [
            lexical_weights_to_sparse(weights)
            for weights in output["lexical_weights"]
        ]
        return dense_vectors, sparse_vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        dense_vectors, _ = self._encode_batch(texts)
        return dense_vectors

    def embed_query(self, text: str) -> list[float]:
        dense_vectors, _ = self._encode_batch([text])
        return dense_vectors[0]

    def encode_with_sparse(
        self,
        texts: list[str],
    ) -> tuple[list[list[float]], list[rest.SparseVector]]:
        return self._encode_batch(texts)

    def encode_query_with_sparse(self, text: str) -> tuple[list[float], rest.SparseVector]:
        dense_vectors, sparse_vectors = self._encode_batch([text])
        return dense_vectors[0], sparse_vectors[0]


def create_embedding_service(settings: Settings | None = None) -> BGEM3EmbeddingService:
    return BGEM3EmbeddingService(settings)
