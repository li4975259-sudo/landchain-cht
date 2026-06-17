from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any


class AuditStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_audit_log (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    tool_name TEXT,
                    input_json TEXT,
                    output_preview TEXT,
                    duration_ms INTEGER,
                    success INTEGER,
                    error TEXT,
                    actor TEXT,
                    source TEXT,
                    result_summary TEXT,
                    resolved_by TEXT,
                    created_at REAL NOT NULL
                )
                """
            )
            # Backward-compatible migrations for existing DB files.
            for column_sql in (
                "ALTER TABLE agent_audit_log ADD COLUMN actor TEXT",
                "ALTER TABLE agent_audit_log ADD COLUMN source TEXT",
                "ALTER TABLE agent_audit_log ADD COLUMN result_summary TEXT",
                "ALTER TABLE agent_audit_log ADD COLUMN resolved_by TEXT",
            ):
                try:
                    conn.execute(column_sql)
                except sqlite3.OperationalError:
                    pass
            conn.commit()

    def log(
        self,
        *,
        run_id: str,
        session_id: str,
        event_type: str,
        tool_name: str | None = None,
        input_json: dict[str, Any] | None = None,
        output_preview: str | None = None,
        duration_ms: int | None = None,
        success: bool = True,
        error: str | None = None,
        actor: str = "system",
        source: str = "agent",
        result_summary: str | None = None,
        resolved_by: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_audit_log
                (id, run_id, session_id, event_type, tool_name, input_json, output_preview,
                 duration_ms, success, error, actor, source, result_summary, resolved_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    run_id,
                    session_id,
                    event_type,
                    tool_name,
                    json.dumps(input_json or {}, ensure_ascii=False),
                    (output_preview or "")[:4000],
                    duration_ms,
                    1 if success else 0,
                    error,
                    actor,
                    source,
                    (result_summary or "")[:512],
                    resolved_by,
                    time.time(),
                ),
            )
            conn.commit()

    def list_runs(self, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT run_id, event_type, tool_name, input_json, output_preview,
                       duration_ms, success, error, actor, source, result_summary,
                       resolved_by, created_at
                FROM agent_audit_log
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]
