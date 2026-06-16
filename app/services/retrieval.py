from pathlib import Path



from langchain_core.documents import Document



from app.config import Settings, get_settings

from app.models.schemas import SourceCitation

from app.services.chunk_expand import ChunkExpandService

from app.services.hybrid_retrieval import HybridRetrievalService

from app.services.keyword_extract import extract_keywords

from app.services.query_rewrite import QueryRewriteService

from app.services.rerank import RerankService

from app.services.vectorstore import VectorStoreService





def _format_doc_prefix(doc: Document) -> str:

    filename = doc.metadata.get("filename") or Path(str(doc.metadata.get("source", ""))).name

    heading_path = doc.metadata.get("heading_path")

    if heading_path:

        return f"[来源: {filename} | 章节: {heading_path}]"

    if filename:

        return f"[来源: {filename}]"

    return "[来源: 未知]"





def format_docs(docs: list[Document]) -> str:

    if not docs:

        return "（无相关上下文）"

    parts = [f"{_format_doc_prefix(doc)}\n{doc.page_content}" for doc in docs]

    return "\n\n".join(parts)





def extract_sources(docs: list[Document]) -> list[str]:

    seen: set[str] = set()

    sources: list[str] = []

    for doc in docs:

        source = doc.metadata.get("source")

        if source and source not in seen:

            seen.add(source)

            sources.append(source)

    return sources





def extract_citations(docs: list[Document]) -> list[SourceCitation]:

    citations: list[SourceCitation] = []

    for doc in docs:

        source = str(doc.metadata.get("source", ""))

        filename = doc.metadata.get("filename") or Path(source).name

        chunk_index = doc.metadata.get("chunk_index")

        heading_path = doc.metadata.get("heading_path")

        citations.append(

            SourceCitation(

                source=source,

                filename=filename,

                heading_path=heading_path,

                chunk_index=chunk_index if chunk_index is not None else None,

            )

        )

    return citations





class RetrievalService:

    def __init__(

        self,

        vectorstore: VectorStoreService,

        rerank_service: RerankService,

        query_rewrite_service: QueryRewriteService | None = None,

        hybrid_retrieval_service: HybridRetrievalService | None = None,

        chunk_expand_service: ChunkExpandService | None = None,

        settings: Settings | None = None,

    ) -> None:

        self.vectorstore = vectorstore

        self.rerank_service = rerank_service

        self.settings = settings or get_settings()

        self.query_rewrite_service = query_rewrite_service or QueryRewriteService(

            settings=self.settings

        )

        self.hybrid_retrieval_service = hybrid_retrieval_service or HybridRetrievalService(

            vectorstore,

            self.settings,

        )

        self.chunk_expand_service = chunk_expand_service or ChunkExpandService(

            vectorstore,

            self.settings,

        )



    def retrieve(self, query: str, top_k: int | None = None) -> list[Document]:

        final_k = top_k if top_k is not None else self.settings.top_k

        candidate_k = max(final_k, self.settings.retrieve_k)

        if self.rerank_service.enabled:

            candidate_k = max(candidate_k, final_k * 2)



        rewritten_query = self.query_rewrite_service.rewrite(query)

        keywords = extract_keywords(query) + extract_keywords(rewritten_query)

        deduped_keywords = list(dict.fromkeys(keywords))



        candidates = self.hybrid_retrieval_service.recall(

            rewritten_query,

            k=candidate_k,

            keywords=deduped_keywords,

        )

        ranked = self.rerank_service.rerank(rewritten_query, candidates, top_k=final_k)

        return self.chunk_expand_service.expand(ranked)


