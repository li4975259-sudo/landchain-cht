import logging
import time
from collections.abc import Iterator

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from app.config import Settings, get_settings
from app.observability import get_request_id
from app.services.intent import is_chitchat
from app.services.retrieval import (
    RetrievalService,
    extract_citations,
    extract_sources,
    format_docs,
)

RAG_SYSTEM_PROMPT = (
    "你是知识库助手。请仅根据以下上下文回答用户问题。"
    "如果上下文中没有相关信息，请明确回答「知识库中未找到相关内容」。"
    "不要编造上下文中不存在的信息。\n\n上下文：\n{context}"
)

CHITCHAT_SYSTEM_PROMPT = (
    "你是 LandChain 智能助手，语气自然、友好、简洁。"
    "用户可能在打招呼、闲聊、开玩笑或表达情绪，请像正常对话一样回应。"
    "不要假装检索了知识库，也不要引用不存在的订单或文档。"
    "如果用户随后提出业务或资料问题，可以简短说明你可以帮助查询订单与文档。"
)

logger = logging.getLogger(__name__)


class RagService:
    def __init__(
        self,
        retrieval_service: RetrievalService,
        llm: ChatOllama,
        settings: Settings | None = None,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.llm = llm
        self.settings = settings or get_settings()
        self._rag_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", RAG_SYSTEM_PROMPT),
                ("human", "{question}"),
            ]
        )
        self._chitchat_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", CHITCHAT_SYSTEM_PROMPT),
                ("human", "{question}"),
            ]
        )
        self._parser = StrOutputParser()

    def _answer_chitchat(self, question: str) -> str:
        start = time.perf_counter()
        chain = self._chitchat_prompt | self.llm | self._parser
        answer = chain.invoke({"question": question})
        logger.info(
            "rag.chitchat.complete request_id=%s question_len=%s total_ms=%s",
            get_request_id(),
            len(question),
            int((time.perf_counter() - start) * 1000),
        )
        return answer

    def _answer_rag(self, question: str, top_k: int | None = None) -> dict:
        total_start = time.perf_counter()
        retrieval_start = time.perf_counter()
        docs = self.retrieval_service.retrieve(question, top_k=top_k)
        retrieval_ms = int((time.perf_counter() - retrieval_start) * 1000)
        context = format_docs(docs)
        chain = self._rag_prompt | self.llm | self._parser
        llm_start = time.perf_counter()
        answer = chain.invoke({"context": context, "question": question})
        llm_ms = int((time.perf_counter() - llm_start) * 1000)
        total_ms = int((time.perf_counter() - total_start) * 1000)
        logger.info(
            "rag.query.complete request_id=%s mode=rag chunks=%s retrieval_ms=%s llm_ms=%s total_ms=%s",
            get_request_id(),
            len(docs),
            retrieval_ms,
            llm_ms,
            total_ms,
        )
        return {
            "answer": answer,
            "sources": extract_sources(docs),
            "citations": extract_citations(docs),
            "chunks_used": len(docs),
            "mode": "rag",
        }

    def query(self, question: str, top_k: int | None = None) -> dict:
        if is_chitchat(question, self.settings):
            return {
                "answer": self._answer_chitchat(question),
                "sources": [],
                "citations": [],
                "chunks_used": 0,
                "mode": "chitchat",
            }
        return self._answer_rag(question, top_k=top_k)

    def stream(
        self,
        question: str,
        top_k: int | None = None,
    ) -> tuple[Iterator[str], list[str], list, int, str]:
        stream_start = time.perf_counter()
        if is_chitchat(question, self.settings):
            chain = self._chitchat_prompt | self.llm | self._parser
            token_stream = chain.stream({"question": question})

            def wrapped_chitchat_stream() -> Iterator[str]:
                token_count = 0
                for token in token_stream:
                    token_count += 1
                    yield token
                logger.info(
                    "rag.stream.complete request_id=%s mode=chitchat tokens=%s total_ms=%s",
                    get_request_id(),
                    token_count,
                    int((time.perf_counter() - stream_start) * 1000),
                )

            return wrapped_chitchat_stream(), [], [], 0, "chitchat"

        retrieval_start = time.perf_counter()
        docs = self.retrieval_service.retrieve(question, top_k=top_k)
        retrieval_ms = int((time.perf_counter() - retrieval_start) * 1000)
        context = format_docs(docs)
        sources = extract_sources(docs)
        citations = extract_citations(docs)
        chain = self._rag_prompt | self.llm | self._parser
        token_stream = chain.stream({"context": context, "question": question})

        def wrapped_rag_stream() -> Iterator[str]:
            token_count = 0
            for token in token_stream:
                token_count += 1
                yield token
            logger.info(
                "rag.stream.complete request_id=%s mode=rag chunks=%s retrieval_ms=%s tokens=%s total_ms=%s",
                get_request_id(),
                len(docs),
                retrieval_ms,
                token_count,
                int((time.perf_counter() - stream_start) * 1000),
            )

        return wrapped_rag_stream(), sources, citations, len(docs), "rag"
