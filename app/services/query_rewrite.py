from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

REWRITE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是检索 query 改写助手。将用户问题改写为适合文档检索的简洁查询句。"
            "要求：保留所有实体、编号、专有名词；口语改书面；不要回答问题；不要编造信息。"
            "只输出一条改写后的检索 query，不要解释。",
        ),
        ("human", "{query}"),
    ]
)


class QueryRewriteService:
    def __init__(
        self,
        llm: ChatOllama | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._llm = llm
        self._parser = StrOutputParser()

    def _get_llm(self) -> ChatOllama:
        if self._llm is None:
            self._llm = ChatOllama(
                model=self.settings.ollama_chat_model,
                base_url=self.settings.ollama_base_url,
                temperature=0,
            )
        return self._llm

    def _rewrite_sync(self, query: str) -> str:
        chain = REWRITE_PROMPT | self._get_llm() | self._parser
        rewritten = chain.invoke({"query": query}).strip()
        return rewritten or query

    def rewrite(self, query: str) -> str:
        if not self.settings.query_rewrite_enabled:
            return query

        text = query.strip()
        if not text:
            return query

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._rewrite_sync, text)
                rewritten = future.result(timeout=self.settings.query_rewrite_timeout)
                if rewritten and rewritten != text:
                    logger.debug("Query rewritten: %r -> %r", text, rewritten)
                return rewritten or text
        except TimeoutError:
            logger.warning("Query rewrite timed out; using original query")
            return query
        except Exception:
            logger.exception("Query rewrite failed; using original query")
            return query
