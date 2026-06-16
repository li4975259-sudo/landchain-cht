#!/usr/bin/env python3
"""Shared helpers for agent task scripts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo


def parse_args(extra: list[tuple[str, dict[str, Any]]] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="today")
    parser.add_argument("--output", choices=["json", "markdown"], default="json")
    parser.add_argument("--out", default=None, help="Output markdown path when --output markdown")
    if extra:
        for flag, kwargs in extra:
            parser.add_argument(flag, **kwargs)
    return parser.parse_args()


def resolve_date(value: str, tz_name: str = "Asia/Shanghai") -> date:
    text = value.strip().lower()
    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date()
    if text in {"today", "今日"}:
        return today
    if text in {"yesterday", "昨日", "昨天"}:
        return date.fromordinal(today.toordinal() - 1)
    return date.fromisoformat(text)


def emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def fail(task: str, message: str) -> None:
    emit_json({"success": False, "task": task, "error": message})
    sys.exit(1)
