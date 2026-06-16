import sqlite3
from collections.abc import Iterator
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langchain_ollama import ChatOllama
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from app.config import Settings, get_settings
from app.services.intent import is_chitchat
from app.services.retrieval import (
    RetrievalService,
    extract_citations,
    extract_sources,
    format_docs,
)

RAG_SYSTEM_PROMPT = (
    "你是知识库助手。请结合对话历史与以下检索上下文回答用户问题。"
    "如果上下文中没有相关信息，请明确回答「知识库中未找到相关内容」。"
    "不要编造上下文中不存在的信息。\n\n检索上下文：\n{context}"
)

CHITCHAT_SYSTEM_PROMPT = (
    "你是 LandChain 智能助手，语气自然、友好、简洁。"
    "用户可能在打招呼、闲聊、开玩笑或表达情绪，请结合对话历史像正常对话一样回应。"
    "不要假装检索了知识库，也不要引用不存在的订单或文档。"
)


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    context: str
    sources: list[str]
    citations: list[dict]
    chunks_used: int
    mode: str


def _retrieval_query(messages: list[BaseMessage]) -> str:
    human_messages = [msg.content for msg in messages if isinstance(msg, HumanMessage)]
    if not human_messages:
        return ""
    latest = human_messages[-1]
    if len(human_messages) >= 2 and len(latest) <= 30:
        return f"{human_messages[-2]}\n{latest}"
    return latest


def _latest_human_message(messages: list[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


class ChatGraphService:
    def __init__(
        self,
        retrieval_service: RetrievalService,
        llm: ChatOllama,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.retrieval_service = retrieval_service
        self.llm = llm
        self._parser = StrOutputParser()
        self._rag_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", RAG_SYSTEM_PROMPT),
                MessagesPlaceholder("history"),
            ]
        )
        self._chitchat_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", CHITCHAT_SYSTEM_PROMPT),
                MessagesPlaceholder("history"),
            ]
        )
        self._graph = self._build_graph()

    def _build_checkpointer(self) -> SqliteSaver:
        self.settings.session_db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.settings.session_db_path), check_same_thread=False)
        return SqliteSaver(conn)

    def _route_intent(self, state: ChatState) -> Literal["retrieve", "chitchat"]:
        message = _latest_human_message(state["messages"])
        if is_chitchat(message, self.settings):
            return "chitchat"
        return "retrieve"

    def _retrieve(
        self,
        messages: list[BaseMessage],
        config: RunnableConfig | None = None,
    ) -> dict:
        top_k = None
        if config:
            top_k = config.get("configurable", {}).get("top_k")
        query = _retrieval_query(messages)
        docs = self.retrieval_service.retrieve(query, top_k=top_k)
        return {
            "context": format_docs(docs),
            "sources": extract_sources(docs),
            "citations": [c.model_dump() for c in extract_citations(docs)],
            "chunks_used": len(docs),
            "mode": "rag",
        }

    def _retrieve_node(self, state: ChatState, config: RunnableConfig) -> dict:
        return self._retrieve(state["messages"], config)

    def _generate_node(self, state: ChatState) -> dict:
        chain = self._rag_prompt | self.llm | self._parser
        answer = chain.invoke(
            {
                "context": state.get("context", "（无相关上下文）"),
                "history": state["messages"],
            }
        )
        return {"messages": [AIMessage(content=answer)]}

    def _chitchat_node(self, state: ChatState) -> dict:
        chain = self._chitchat_prompt | self.llm | self._parser
        answer = chain.invoke({"history": state["messages"]})
        return {
            "messages": [AIMessage(content=answer)],
            "context": "",
            "sources": [],
            "citations": [],
            "chunks_used": 0,
            "mode": "chitchat",
        }

    def _build_graph(self):
        graph = StateGraph(ChatState)
        graph.add_node("retrieve", self._retrieve_node)
        graph.add_node("generate", self._generate_node)
        graph.add_node("chitchat", self._chitchat_node)
        graph.add_conditional_edges(
            START,
            self._route_intent,
            {"retrieve": "retrieve", "chitchat": "chitchat"},
        )
        graph.add_edge("retrieve", "generate")
        graph.add_edge("generate", END)
        graph.add_edge("chitchat", END)
        return graph.compile(checkpointer=self._build_checkpointer())

    def _config(self, session_id: str, top_k: int | None = None) -> dict:
        configurable: dict = {"thread_id": session_id}
        if top_k is not None:
            configurable["top_k"] = top_k
        return {"configurable": configurable}

    def chat(
        self,
        session_id: str,
        message: str,
        top_k: int | None = None,
    ) -> dict:
        result = self._graph.invoke(
            {"messages": [HumanMessage(content=message)]},
            config=self._config(session_id, top_k),
        )
        ai_message = result["messages"][-1]
        return {
            "session_id": session_id,
            "answer": ai_message.content,
            "sources": result.get("sources", []),
            "citations": result.get("citations", []),
            "chunks_used": result.get("chunks_used", 0),
            "mode": result.get("mode", "rag"),
        }

    def stream(
        self,
        session_id: str,
        message: str,
        top_k: int | None = None,
    ) -> tuple[Iterator[str], list[str], list[dict], int, str]:
        config = self._config(session_id, top_k)
        snapshot = self._graph.get_state(config)
        history = list(snapshot.values.get("messages", []))
        pending_messages = history + [HumanMessage(content=message)]

        if is_chitchat(message, self.settings):
            chain = self._chitchat_prompt | self.llm | self._parser
            token_stream = chain.stream({"history": pending_messages})
            retrieve_result = {
                "context": "",
                "sources": [],
                "citations": [],
                "chunks_used": 0,
                "mode": "chitchat",
            }
        else:
            retrieve_result = self._retrieve(pending_messages, config)
            chain = self._rag_prompt | self.llm | self._parser
            token_stream = chain.stream(
                {
                    "context": retrieve_result["context"],
                    "history": pending_messages,
                }
            )

        mode = retrieve_result.get("mode", "rag")

        def wrapped_stream() -> Iterator[str]:
            full_answer = ""
            for token in token_stream:
                full_answer += token
                yield token
            self._graph.update_state(
                config,
                {
                    "messages": [
                        HumanMessage(content=message),
                        AIMessage(content=full_answer),
                    ],
                    **retrieve_result,
                },
            )

        return (
            wrapped_stream(),
            retrieve_result["sources"],
            retrieve_result["citations"],
            retrieve_result["chunks_used"],
            mode,
        )

    def get_history(self, session_id: str) -> list[dict]:
        state = self._graph.get_state(self._config(session_id))
        if not state.values:
            return []

        history: list[dict] = []
        for msg in state.values.get("messages", []):
            if isinstance(msg, HumanMessage):
                history.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                history.append({"role": "assistant", "content": msg.content})
        return history

    def clear_session(self, session_id: str) -> None:
        self._graph.checkpointer.delete_thread(session_id)
