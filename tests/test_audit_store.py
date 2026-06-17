import os
import tempfile
import unittest
from pathlib import Path

from app.agents.audit import AuditStore


class AuditStoreTests(unittest.TestCase):
    def test_log_persists_standardized_fields(self) -> None:
        fd, raw_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        Path(raw_path).unlink(missing_ok=True)
        db_path = Path(raw_path)
        try:
            store = AuditStore(str(db_path))
            store.log(
                run_id="run-1",
                session_id="session-1",
                event_type="tool_end",
                tool_name="query_data",
                input_json={"action": "count"},
                output_preview='{"success": true}',
                duration_ms=12,
                success=True,
                actor="agent",
                source="tool",
                result_summary="success=true",
                resolved_by="ops",
            )
            runs = store.list_runs("session-1")
            self.assertEqual(len(runs), 1)
            row = runs[0]
            self.assertEqual(row["actor"], "agent")
            self.assertEqual(row["source"], "tool")
            self.assertEqual(row["result_summary"], "success=true")
            self.assertEqual(row["resolved_by"], "ops")
        finally:
            try:
                db_path.unlink(missing_ok=True)
            except PermissionError:
                pass


if __name__ == "__main__":
    unittest.main()
