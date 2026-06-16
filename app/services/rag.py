from collections.abc import Iterator

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from app.config import Settings, get_settings
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
        chain = self._chitchat_prompt | self.llm | self._parser
        return chain.invoke({"question": question})

    def _answer_rag(self, question: str, top_k: int | None = None) -> dict:
        docs = self.retrieval_service.retrieve(question, top_k=top_k)
        context = format_docs(docs)
        chain = self._rag_prompt | self.llm | self._parser
        answer = chain.invoke({"context": context, "question": question})
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
        if is_chitchat(question, self.settings):
            chain = self._chitchat_prompt | self.llm | self._parser
            token_stream = chain.stream({"question": question})
            return token_stream, [], [], 0, "chitchat"

        docs = self.retrieval_service.retrieve(question, top_k=top_k)
        context = format_docs(docs)
        sources = extract_sources(docs)
        citations = extract_citations(docs)
        chain = self._rag_prompt | self.llm | self._parser
        token_stream = chain.stream({"context": context, "question": question})
        return token_stream, sources, citations, len(docs), "rag"
