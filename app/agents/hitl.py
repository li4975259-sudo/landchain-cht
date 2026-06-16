from __future__ import annotations

import sqlite3
import time
import uuid
from typing import Any


class ApprovalStore:
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
                CREATE TABLE IF NOT EXISTS pending_approvals (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    command TEXT NOT NULL,
                    reason TEXT,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    resolved_at REAL,
                    resolved_by TEXT
                )
                """
            )
            conn.commit()

    def create(
        self,
        *,
        session_id: str,
        run_id: str,
        tool_name: str,
        command: str,
        reason: str = "",
    ) -> dict[str, Any]:
        approval_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO pending_approvals
                (id, session_id, run_id, tool_name, command, reason, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (approval_id, session_id, run_id, tool_name, command, reason, time.time()),
            )
            conn.commit()
        return {
            "approval_id": approval_id,
            "session": session_id,
            "run_id": run_id,
            "tool_name": tool_name,
            "command": command,
            "reason": reason,
            "status": "pending",
        }

    def resolve(self, approval_id: str, *, approved: bool, resolved_by: str = "user") -> dict[str, Any]:
        status = "approved" if approved else "rejected"
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE pending_approvals
                SET status = ?, resolved_at = ?, resolved_by = ?
                WHERE id = ? AND status = 'pending'
                """,
                (status, time.time(), resolved_by, approval_id),
            )
            row = conn.execute(
                "SELECT * FROM pending_approvals WHERE id = ?", (approval_id,)
            ).fetchone()
            conn.commit()
        if row is None:
            raise ValueError(f"Approval not found or already resolved: {approval_id}")
        return dict(row)

    def get(self, approval_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM pending_approvals WHERE id = ?", (approval_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_pending(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pending_approvals WHERE status = 'pending' ORDER BY created_at ASC"
            ).fetchall()
        return [dict(row) for row in rows]
