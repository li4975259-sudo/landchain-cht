from __future__ import annotations

import re

ORDER_ID_PATTERN = re.compile(r"\bO\d+\b", re.IGNORECASE)
MODEL_PATTERN = re.compile(r"\b[A-Z]{1,3}[-_]?\d{2,}[A-Z0-9-]*\b")
LONG_NUMBER_PATTERN = re.compile(r"\b\d{6,}\b")
QUOTED_PATTERN = re.compile(r"[「『\"']([^「『\"']{2,})[」』\"']")


def extract_keywords(text: str) -> list[str]:
    """Extract ID-like tokens and quoted phrases from query or chunk text."""
    if not text.strip():
        return []

    found: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        normalized = value.strip()
        if not normalized or len(normalized) < 2:
            return
        key = normalized.lower()
        if key in seen:
            return
        seen.add(key)
        found.append(normalized)

    for pattern in (ORDER_ID_PATTERN, MODEL_PATTERN, LONG_NUMBER_PATTERN):
        for match in pattern.finditer(text):
            add(match.group(0))

    for match in QUOTED_PATTERN.finditer(text):
        add(match.group(1))

    return found
