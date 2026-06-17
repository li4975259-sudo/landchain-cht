from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.agents.audit import AuditStore
    from app.agents.hitl import ApprovalStore
    from app.services.ingest import IngestService
    from app.services.order_report import OrderReportGenerator
    from app.services.postgres_query import PostgresQueryService
    from app.services.report_writer import ReportWriter
    from app.services.retrieval import RetrievalService
    from app.services.shell_executor import ShellExecutor
    from app.services.task_registry import TaskRegistry
    from app.services.table_schema import TableSchemaService


class ExploreDataInput(BaseModel):
    action: str = Field(description="list_collections | describe_collection | sample_records")
    collection: str | None = Field(default=None)
    limit: int = Field(default=5, ge=1, le=50)


class QueryDataInput(BaseModel):
    collection: str
    action: str = Field(
        description="get_by_id|count|list_by_date_range|filter_list|distinct_values|"
        "aggregate_by_field|aggregate_array_field|aggregate_numeric|aggregate_summary"
    )
    id_value: str | None = None
    id_field: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    time_field: str | None = None
    field: str | None = None
    op: str = "sum"
    filters: dict[str, Any] | None = None
    limit: int = 50
    skip: int = 0
    group_by: str | None = None


class SearchKnowledgeInput(BaseModel):
    query: str
    top_k: int = 4


class GenerateOrderReportInput(BaseModel):
    from_date: str
    to_date: str
    ingest_to_rag: bool = True
    collection: str | None = None


class ReportSectionInput(BaseModel):
    heading: str
    content_type: str = "json_block"
    data: Any = None


class GenerateMarkdownReportInput(BaseModel):
    title: str
    sections: list[dict[str, Any]]
    source_collection: str | None = None
    output_subdir: str = "reports"
    ingest_to_rag: bool = True


class IngestDocumentsInput(BaseModel):
    mode: str = Field(description="file | directory")
    path: str | None = None
    force: bool = False


class ListTasksInput(BaseModel):
    category: str | None = None
    keyword: str | None = None


class RunTaskInput(BaseModel):
    task_name: str
    params: dict[str, Any] | None = None
    ingest_report: bool = True


class RunShellInput(BaseModel):
    command: str
    reason: str = ""


def build_tools(
    *,
    retrieval_service: RetrievalService,
    schema_service: TableSchemaService,
    data_query: PostgresQueryService,
    report_writer: ReportWriter,
    order_report_generator: OrderReportGenerator,
    ingest_service: IngestService,
    task_registry: TaskRegistry,
    shell_executor: ShellExecutor,
    approval_store: ApprovalStore,
    audit_store: AuditStore,
    get_health: callable,
    session_id: str,
    run_id: str,
    pending_shell: dict[str, Any],
) -> list[StructuredTool]:
    def _summarize_result(result: Any) -> str:
        if isinstance(result, dict):
            if "success" in result:
                return f"success={result.get('success')}"
            keys = ",".join(list(result.keys())[:5])
            return f"dict_keys={keys}"
        if isinstance(result, list):
            return f"list_len={len(result)}"
        text = str(result)
        return text[:120]

    def _audit(tool_name: str, input_data: dict, fn):
        import time

        start = time.perf_counter()
        try:
            result = fn()
            out = json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
            audit_store.log(
                run_id=run_id,
                session_id=session_id,
                event_type="tool_end",
                tool_name=tool_name,
                input_json=input_data,
                output_preview=out[:2000],
                duration_ms=int((time.perf_counter() - start) * 1000),
                success=True,
                actor="agent",
                source="tool",
                result_summary=_summarize_result(result),
            )
            return out if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            audit_store.log(
                run_id=run_id,
                session_id=session_id,
                event_type="tool_end",
                tool_name=tool_name,
                input_json=input_data,
                output_preview=str(exc),
                duration_ms=int((time.perf_counter() - start) * 1000),
                success=False,
                error=str(exc),
                actor="agent",
                source="tool",
                result_summary="error",
            )
            return json.dumps(
                {"success": False, "tool": tool_name, "error": str(exc)},
                ensure_ascii=False,
            )

    def search_knowledge_base(query: str, top_k: int = 4) -> str:
        from app.services.retrieval import extract_citations, extract_sources, format_docs

        def fn():
            docs = retrieval_service.retrieve(query, top_k=top_k)
            return {
                "context": format_docs(docs)[:12000],
                "sources": extract_sources(docs),
                "citations": [c.model_dump() for c in extract_citations(docs)],
                "chunks_used": len(docs),
            }

        return _audit("search_knowledge_base", {"query": query, "top_k": top_k}, fn)

    def list_knowledge_sources() -> str:
        def fn():
            from app.config import get_settings

            settings = get_settings()
            index_path = settings.ingest_index_path
            if not index_path.exists():
                return {"sources": [], "count": 0}
            data = json.loads(index_path.read_text(encoding="utf-8"))
            return {"sources": list(data.keys()), "count": len(data)}

        return _audit("list_knowledge_sources", {}, fn)

    def explore_data(action: str, collection: str | None = None, limit: int = 5) -> str:
        def fn():
            if action == "list_collections":
                return {"collections": schema_service.list_collections()}
            if action == "describe_collection":
                if not collection:
                    raise ValueError("collection is required")
                return schema_service.describe_collection(collection)
            if action == "sample_records":
                if not collection:
                    raise ValueError("collection is required")
                return {"records": schema_service.sample_records(collection, limit=limit)}
            raise ValueError(f"Unknown explore action: {action}")

        return _audit("explore_data", {"action": action, "collection": collection}, fn)

    def query_data(
        collection: str,
        action: str,
        id_value: str | None = None,
        id_field: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        time_field: str | None = None,
        field: str | None = None,
        op: str = "sum",
        filters: dict[str, Any] | None = None,
        limit: int = 50,
        skip: int = 0,
        group_by: str | None = None,
    ) -> str:
        kwargs = {
            "collection": collection,
            "action": action,
            "id_value": id_value,
            "id_field": id_field,
            "from_date": from_date,
            "to_date": to_date,
            "time_field": time_field,
            "field": field,
            "op": op,
            "filters": filters,
            "limit": limit,
            "skip": skip,
            "group_by": group_by,
        }
        clean = {k: v for k, v in kwargs.items() if v is not None}

        def fn():
            return data_query.query(**clean)

        return _audit("query_data", clean, fn)

    def generate_order_report(
        from_date: str, to_date: str, ingest_to_rag: bool = True, collection: str | None = None
    ) -> str:
        def fn():
            from datetime import datetime

            start = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            end = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            path, count = order_report_generator.generate_report_file(
                start, end, collection=collection
            )
            chunks = 0
            source = str(path)
            if ingest_to_rag:
                chunks, source = ingest_service.ingest_file(path, force=True)
            return {"path": str(path), "order_count": count, "chunks_added": chunks, "source": source}

        return _audit(
            "generate_order_report",
            {"from_date": from_date, "to_date": to_date},
            fn,
        )

    def generate_markdown_report(
        title: str,
        sections: list[dict[str, Any]],
        source_collection: str | None = None,
        output_subdir: str = "reports",
        ingest_to_rag: bool = True,
    ) -> str:
        def fn():
            return report_writer.generate(
                title,
                sections,
                source_collection=source_collection,
                output_subdir=output_subdir,
                ingest_to_rag=ingest_to_rag,
            )

        return _audit("generate_markdown_report", {"title": title}, fn)

    def ingest_documents(mode: str, path: str | None = None, force: bool = False) -> str:
        def fn():
            from pathlib import Path

            from app.config import get_settings

            settings = get_settings()
            if mode == "directory":
                fp, ca, skipped = ingest_service.ingest_directory(force=force)
                return {"files_processed": fp, "chunks_added": ca, "skipped": skipped}
            if mode == "file":
                if not path:
                    raise ValueError("path is required for file mode")
                p = Path(path).resolve()
                allowed_roots = [settings.data_dir.resolve(), settings.upload_dir.resolve()]
                if not any(str(p).startswith(str(root)) for root in allowed_roots):
                    raise ValueError("path outside allowed directories")
                chunks, source = ingest_service.ingest_file(p, force=force)
                return {"chunks_added": chunks, "source": source}
            raise ValueError(f"Unknown ingest mode: {mode}")

        return _audit("ingest_documents", {"mode": mode, "path": path}, fn)

    def list_tasks(category: str | None = None, keyword: str | None = None) -> str:
        def fn():
            return {"tasks": task_registry.list_tasks(category=category, keyword=keyword)}

        return _audit("list_tasks", {"category": category, "keyword": keyword}, fn)

    def run_task(task_name: str, params: dict[str, Any] | None = None, ingest_report: bool = True) -> str:
        def fn():
            result = task_registry.run(task_name, params)
            report_path = result.get("report_path")
            if ingest_report and report_path:
                from pathlib import Path

                chunks, source = ingest_service.ingest_file(Path(report_path), force=True)
                result["chunks_added"] = chunks
                result["source"] = source
            return result

        return _audit("run_task", {"task_name": task_name, "params": params}, fn)

    def run_shell_command(command: str, reason: str = "") -> str:
        approval = approval_store.create(
            session_id=session_id,
            run_id=run_id,
            tool_name="run_shell_command",
            command=command,
            reason=reason,
        )
        pending_shell["approval_id"] = approval["approval_id"]
        pending_shell["command"] = command
        pending_shell["reason"] = reason
        audit_store.log(
            run_id=run_id,
            session_id=session_id,
            event_type="approval_requested",
            tool_name="run_shell_command",
            input_json={"command": command, "reason": reason},
            output_preview=f"approval_id={approval['approval_id']}",
            success=True,
            actor="agent",
            source="approval",
            result_summary="pending",
        )
        return json.dumps(
            {
                "status": "approval_required",
                "approval_id": approval["approval_id"],
                "command": command,
                "reason": reason,
                "message": "Shell command requires user approval. Wait for approval via API.",
            },
            ensure_ascii=False,
        )

    def get_system_health() -> str:
        def fn():
            return get_health()

        return _audit("get_system_health", {}, fn)

    return [
        StructuredTool.from_function(
            func=search_knowledge_base,
            name="search_knowledge_base",
            description="Search the knowledge base (RAG vector store)",
            args_schema=SearchKnowledgeInput,
        ),
        StructuredTool.from_function(
            func=list_knowledge_sources,
            name="list_knowledge_sources",
            description="List indexed knowledge base document sources",
        ),
        StructuredTool.from_function(
            func=explore_data,
            name="explore_data",
            description="Explore PostgreSQL business collections and schemas",
            args_schema=ExploreDataInput,
        ),
        StructuredTool.from_function(
            func=query_data,
            name="query_data",
            description="Query PostgreSQL business collections with safe structured actions",
            args_schema=QueryDataInput,
        ),
        StructuredTool.from_function(
            func=generate_order_report,
            name="generate_order_report",
            description="Generate order statistics markdown report",
            args_schema=GenerateOrderReportInput,
        ),
        StructuredTool.from_function(
            func=generate_markdown_report,
            name="generate_markdown_report",
            description="Generate a generic markdown report from structured sections",
            args_schema=GenerateMarkdownReportInput,
        ),
        StructuredTool.from_function(
            func=ingest_documents,
            name="ingest_documents",
            description="Ingest documents into the knowledge base",
            args_schema=IngestDocumentsInput,
        ),
        StructuredTool.from_function(
            func=list_tasks,
            name="list_tasks",
            description="List registered agent tasks and scripts",
            args_schema=ListTasksInput,
        ),
        StructuredTool.from_function(
            func=run_task,
            name="run_task",
            description="Run a registered task or analytics script",
            args_schema=RunTaskInput,
        ),
        StructuredTool.from_function(
            func=run_shell_command,
            name="run_shell_command",
            description="Run a shell command (requires user approval)",
            args_schema=RunShellInput,
        ),
        StructuredTool.from_function(
            func=get_system_health,
            name="get_system_health",
            description="Get system health status",
        ),
    ]
