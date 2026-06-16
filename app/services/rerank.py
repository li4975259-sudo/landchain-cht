import logging

from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_core.documents import Document

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class RerankService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._model: HuggingFaceCrossEncoder | None = None
        self._load_failed = False

    @property
    def enabled(self) -> bool:
        return self.settings.rerank_enabled and not self._load_failed

    def _get_model(self) -> HuggingFaceCrossEncoder:
        if self._load_failed:
            raise RuntimeError("Rerank model previously failed to load")
        if self._model is None:
            try:
                self._model = HuggingFaceCrossEncoder(
                    model_name=self.settings.rerank_model,
                    model_kwargs={"device": self.settings.embed_device},
                )
            except Exception:
                self._load_failed = True
                logger.exception(
                    "Failed to load rerank model %s; falling back to vector order",
                    self.settings.rerank_model,
                )
                raise
        return self._model

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int | None = None,
    ) -> list[Document]:
        if not documents:
            return []

        final_k = top_k if top_k is not None else self.settings.top_k
        min_score = self.settings.rerank_min_score

        if not self.settings.rerank_enabled:
            return documents[:final_k]

        try:
            model = self._get_model()
            pairs = [(query, doc.page_content) for doc in documents]
            scores = list(model.score(pairs))
            ranked = sorted(
                zip(scores, documents, strict=True),
                key=lambda item: item[0],
                reverse=True,
            )
            filtered = [doc for score, doc in ranked if score >= min_score]
            if not filtered:
                logger.info(
                    "All rerank scores below threshold %.2f; returning empty results",
                    min_score,
                )
                return []
            return filtered[:final_k]
        except Exception:
            if not self._load_failed:
                self._load_failed = True
            logger.exception("Rerank failed; returning vector retrieval order")
            return documents[:final_k]
