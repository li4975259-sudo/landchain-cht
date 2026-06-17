import importlib.util
import unittest
from datetime import datetime
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[1]
    script_path = root / "scripts" / "perf_log_summary.py"
    spec = importlib.util.spec_from_file_location("perf_log_summary", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PerfLogSummaryTests(unittest.TestCase):
    def test_summarize_lines_extracts_metrics(self) -> None:
        mod = _load_module()
        lines = [
            "2026-01-01 INFO http.query.complete request_id=r1 total_ms=100",
            "2026-01-01 INFO http.query.complete request_id=r2 total_ms=300",
            "2026-01-01 INFO http.chat.complete request_id=r3 total_ms=200",
        ]
        summary = mod.summarize_lines(lines)
        self.assertIn("http.query.complete", summary)
        self.assertEqual(summary["http.query.complete"]["count"], 2)
        self.assertEqual(summary["http.query.complete"]["p50_ms"], 100)
        self.assertEqual(summary["http.query.complete"]["p95_ms"], 300)
        self.assertEqual(summary["http.chat.complete"]["max_ms"], 200)

    def test_summarize_lines_supports_event_prefix_filter(self) -> None:
        mod = _load_module()
        lines = [
            "2026-01-01 10:00:00 INFO http.query.complete request_id=r1 total_ms=100",
            "2026-01-01 10:00:01 INFO http.chat.complete request_id=r2 total_ms=200",
        ]
        summary = mod.summarize_lines(lines, event_prefix="http.chat")
        self.assertNotIn("http.query.complete", summary)
        self.assertIn("http.chat.complete", summary)

    def test_summarize_lines_supports_since_filter(self) -> None:
        mod = _load_module()
        lines = [
            "2026-01-01 10:00:00 INFO http.query.complete request_id=r1 total_ms=100",
            "2026-01-01 10:10:00 INFO http.query.complete request_id=r2 total_ms=300",
        ]
        summary = mod.summarize_lines(
            lines,
            since=datetime.fromisoformat("2026-01-01T10:05:00"),
        )
        self.assertEqual(summary["http.query.complete"]["count"], 1)
        self.assertEqual(summary["http.query.complete"]["max_ms"], 300)


if __name__ == "__main__":
    unittest.main()
