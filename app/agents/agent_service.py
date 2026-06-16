from __future__ import annotations



import json

import sqlite3

import uuid

from collections.abc import Iterator

from typing import Any



from langchain_core.messages import AIMessage, HumanMessage

from langchain_ollama import ChatOllama

from langgraph.checkpoint.sqlite import SqliteSaver

from langgraph.prebuilt import create_react_agent



from app.agents.audit import AuditStore

from app.agents.hitl import ApprovalStore

from app.agents.prompts import AGENT_SYSTEM_PROMPT

from app.agents.tools import build_tools

from app.config import Settings, get_settings

from app.services.ingest import IngestService

from app.services.order_report import OrderReportGenerator

from app.services.postgres_business_store import PostgresBusinessStore

from app.services.postgres_query import PostgresQueryService

from app.services.report_writer import ReportWriter

from app.services.retrieval import RetrievalService

from app.services.shell_executor import ShellExecutor

from app.services.table_schema import TableSchemaService

from app.services.task_registry import TaskRegistry





class AgentService:

    def __init__(

        self,

        retrieval_service: RetrievalService,

        business_store: PostgresBusinessStore,

        ingest_service: IngestService,

        llm: ChatOllama,

        settings: Settings | None = None,

    ) -> None:

        self.settings = settings or get_settings()

        self.retrieval_service = retrieval_service

        self.business_store = business_store

        self.ingest_service = ingest_service

        self.llm = llm



        self.schema_service = TableSchemaService(business_store, self.settings)

        self.data_query = PostgresQueryService(

            business_store, self.schema_service, self.settings

        )

        self.report_writer = ReportWriter(ingest_service, self.settings)

        self.order_report_generator = OrderReportGenerator(business_store, self.settings)

        self.task_registry = TaskRegistry(self.settings)

        self.shell_executor = ShellExecutor(self.settings)



        self.settings.agent_session_db_path.parent.mkdir(parents=True, exist_ok=True)

        self.settings.agent_audit_db_path.parent.mkdir(parents=True, exist_ok=True)

        self.audit_store = AuditStore(str(self.settings.agent_audit_db_path))

        self.approval_store = ApprovalStore(str(self.settings.agent_audit_db_path))



        self._register_task_handlers()

        self._checkpointer = self._build_checkpointer()

        self._graph = None



    def _register_task_handlers(self) -> None:

        def ingest_directory(params: dict[str, Any]) -> dict[str, Any]:

            fp, ca, skipped = self.ingest_service.ingest_directory(

                force=bool(params.get("force"))

            )

            return {

                "success": True,

                "data": {

                    "files_processed": fp,

                    "chunks_added": ca,

                    "skipped": skipped,

                },

            }



        def sync_orders(params: dict[str, Any]) -> dict[str, Any]:

            from datetime import datetime



            start = datetime.fromisoformat(str(params["from_date"]).replace("Z", "+00:00"))

            end = datetime.fromisoformat(str(params["to_date"]).replace("Z", "+00:00"))

            path, count = self.order_report_generator.generate_report_file(start, end)

            chunks, source = self.ingest_service.ingest_file(path, force=True)

            return {

                "success": True,

                "data": {"order_count": count, "path": str(path)},

                "report_path": str(path),

                "chunks_added": chunks,

                "source": source,

            }



        self.task_registry.set_handler("ingest_directory", ingest_directory)

        self.task_registry.set_handler("sync_orders_to_rag", sync_orders)



    def _build_checkpointer(self) -> SqliteSaver:

        conn = sqlite3.connect(

            str(self.settings.agent_session_db_path), check_same_thread=False

        )

        return SqliteSaver(conn)



    def _get_graph(self, session_id: str, run_id: str, pending_shell: dict[str, Any]):

        tools = build_tools(

            retrieval_service=self.retrieval_service,

            schema_service=self.schema_service,

            data_query=self.data_query,

            report_writer=self.report_writer,

            order_report_generator=self.order_report_generator,

            ingest_service=self.ingest_service,

            task_registry=self.task_registry,

            shell_executor=self.shell_executor,

            approval_store=self.approval_store,

            audit_store=self.audit_store,

            get_health=self._health_payload,

            session_id=session_id,

            run_id=run_id,

            pending_shell=pending_shell,

        )

        model = self.llm.bind_tools(tools)

        return create_react_agent(

            model,

            tools,

            prompt=AGENT_SYSTEM_PROMPT,

            checkpointer=self._checkpointer,

        )



    def _config(self, session_id: str) -> dict:

        return {

            "configurable": {"thread_id": session_id},

            "recursion_limit": self.settings.agent_max_iterations,

        }



    def _health_payload(self) -> dict[str, Any]:

        return {

            "agent_enabled": self.settings.agent_enabled,

            "agent_model": self.settings.effective_agent_model,

            "postgres_available": self.business_store.is_available,

        }



    def chat(self, session_id: str, message: str) -> dict[str, Any]:

        run_id = str(uuid.uuid4())

        pending_shell: dict[str, Any] = {}

        graph = self._get_graph(session_id, run_id, pending_shell)

        result = graph.invoke(

            {"messages": [HumanMessage(content=message)]},

            config=self._config(session_id),

        )

        ai_message = result["messages"][-1]

        answer = ai_message.content if isinstance(ai_message.content, str) else str(ai_message.content)

        return {

            "session_id": session_id,

            "run_id": run_id,

            "answer": answer,

            "pending_approval": pending_shell or None,

        }



    def stream(

        self, session_id: str, message: str

    ) -> tuple[str, Iterator[dict[str, Any]], dict[str, Any]]:

        run_id = str(uuid.uuid4())

        pending_shell: dict[str, Any] = {}

        graph = self._get_graph(session_id, run_id, pending_shell)



        def event_iterator() -> Iterator[dict[str, Any]]:

            inputs = {"messages": [HumanMessage(content=message)]}

            config = self._config(session_id)

            for event in graph.stream(inputs, config=config, stream_mode="messages"):

                if isinstance(event, tuple) and len(event) == 2:

                    msg, _meta = event

                    if isinstance(msg, AIMessage) and msg.content:

                        text = msg.content if isinstance(msg.content, str) else str(msg.content)

                        if text:

                            yield {"event": "token", "data": {"text": text}}

                elif isinstance(event, dict):

                    for _node, data in event.items():

                        if "messages" in data:

                            for msg in data["messages"]:

                                if isinstance(msg, AIMessage) and msg.tool_calls:

                                    for tc in msg.tool_calls:

                                        yield {

                                            "event": "tool_start",

                                            "data": {

                                                "tool": tc.get("name"),

                                                "input": tc.get("args"),

                                            },

                                        }

            if pending_shell:

                yield {

                    "event": "approval_required",

                    "data": pending_shell,

                }

            yield {

                "event": "done",

                "data": {

                    "session_id": session_id,

                    "run_id": run_id,

                    "pending_approval": pending_shell or None,

                },

            }



        return run_id, event_iterator(), pending_shell



    def get_history(self, session_id: str) -> list[dict]:

        graph = self._get_graph(session_id, "history", {})

        state = graph.get_state(self._config(session_id))

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

        self._checkpointer.delete_thread(session_id)



    def list_runs(self, session_id: str) -> list[dict[str, Any]]:

        return self.audit_store.list_runs(session_id)



    def list_pending_approvals(self) -> list[dict[str, Any]]:

        return self.approval_store.list_pending()



    def approve_shell(self, approval_id: str, *, approved: bool) -> dict[str, Any]:

        record = self.approval_store.resolve(approval_id, approved=approved)

        if not approved:

            return {"status": "rejected", "approval_id": approval_id}

        result = self.shell_executor.execute(record["command"])

        self.audit_store.log(

            run_id=record["run_id"],

            session_id=record["session_id"],

            event_type="shell",

            tool_name="run_shell_command",

            input_json={"command": record["command"]},

            output_preview=json.dumps(result, ensure_ascii=False)[:2000],

            duration_ms=result.get("duration_ms"),

            success=result.get("success", False),

        )

        return {"status": "approved", "approval_id": approval_id, "result": result}

