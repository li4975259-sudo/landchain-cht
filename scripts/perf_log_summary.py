#!/usr/bin/env python3
"""Summarize API latency metrics from application logs."""

from __future__ import annotations

import argparse
import math
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

METRIC_PATTERN = re.compile(
    r"(?P<event>http\.(?:query|query_stream|chat|chat_stream|documents_upload|documents_ingest)\.complete)\s+"
    r".*?total_ms=(?P<total_ms>\d+)"
)
LINE_TS_PATTERN = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d{1,6})?)"
)


def percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil((p / 100.0) * len(ordered)) - 1))
    return ordered[index]


def _extract_line_datetime(line: str) -> datetime | None:
    match = LINE_TS_PATTERN.search(line)
    if not match:
        return None
    text = match.group("ts").replace(",", ".").replace(" ", "T")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def summarize_lines(
    lines: list[str],
    *,
    event_prefix: str = "http.",
    since: datetime | None = None,
) -> dict[str, dict[str, int | float]]:
    buckets: dict[str, list[int]] = defaultdict(list)
    for line in lines:
        if since is not None:
            line_dt = _extract_line_datetime(line)
            if line_dt is None or line_dt < since:
                continue
        match = METRIC_PATTERN.search(line)
        if not match:
            continue
        event = match.group("event")
        if event_prefix and not event.startswith(event_prefix):
            continue
        total_ms = int(match.group("total_ms"))
        buckets[event].append(total_ms)

    result: dict[str, dict[str, int | float]] = {}
    for event, values in sorted(buckets.items()):
        result[event] = {
            "count": len(values),
            "avg_ms": round(statistics.fmean(values), 2),
            "p50_ms": percentile(values, 50),
            "p95_ms": percentile(values, 95),
            "max_ms": max(values),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize HTTP latency metrics from LandChain logs"
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        required=True,
        help="Path to application log file",
    )
    parser.add_argument(
        "--event-prefix",
        default="http.",
        help="Only include events with this prefix (default: http.)",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Only include logs at/after this timestamp (e.g. 2026-06-17T18:30:00)",
    )
    args = parser.parse_args()

    log_path = args.log_file.resolve()
    if not log_path.is_file():
        print(f"Log file not found: {log_path}", file=sys.stderr)
        return 1

    since_dt: datetime | None = None
    if args.since:
        since_raw = str(args.since).replace(" ", "T")
        try:
            since_dt = datetime.fromisoformat(since_raw)
        except ValueError:
            print(f"Invalid --since value: {args.since}", file=sys.stderr)
            return 1

    lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    summary = summarize_lines(
        lines,
        event_prefix=args.event_prefix,
        since=since_dt,
    )
    if not summary:
        print("No latency metrics found in log file.")
        return 0

    print(f"Log file: {log_path}")
    print("")
    print("event,count,avg_ms,p50_ms,p95_ms,max_ms")
    for event, metric in summary.items():
        print(
            f"{event},{metric['count']},{metric['avg_ms']},{metric['p50_ms']},{metric['p95_ms']},{metric['max_ms']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
