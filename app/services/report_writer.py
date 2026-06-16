from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.services.ingest import IngestService


def _slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "-", text.strip())
    return text.lower()[:60] or "report"


def _render_kpi(data: dict[str, Any]) -> str:
    lines = ["| 指标 | 数值 |", "|------|------|"]
    for key, value in data.items():
        lines.append(f"| {key} | {value} |")
    return "\n".join(lines)


def _render_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "（无数据）"
    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(lines)


class ReportWriter:
    def __init__(
        self,
        ingest_service: IngestService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.ingest_service = ingest_service

    def render_section(self, heading: str, content_type: str, data: Any) -> str:
        parts = [f"## {heading}", ""]
        if content_type == "text":
            parts.append(str(data))
        elif content_type == "kpi" and isinstance(data, dict):
            parts.append(_render_kpi(data))
        elif content_type == "markdown_table" and isinstance(data, list):
            parts.append(_render_table(data))
        elif content_type == "bullet_list" and isinstance(data, list):
            parts.extend(f"- {item}" for item in data)
        elif content_type == "json_block":
            parts.append("```json")
            parts.append(json.dumps(data, ensure_ascii=False, indent=2))
            parts.append("```")
        else:
            parts.append("```json")
            parts.append(json.dumps(data, ensure_ascii=False, indent=2))
            parts.append("```")
        parts.append("")
        return "\n".join(parts)

    def generate(
        self,
        title: str,
        sections: list[dict[str, Any]],
        *,
        source_collection: str | None = None,
        output_subdir: str = "reports",
        ingest_to_rag: bool = True,
    ) -> dict[str, Any]:
        generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = [
            f"# {title}",
            "",
            f"> **生成时间**：{generated_at}",
        ]
        if source_collection:
            lines.append(f"> **数据来源**：PostgreSQL `{source_collection}`")
        lines.extend(["", "---", ""])

        for section in sections:
            lines.append(
                self.render_section(
                    section.get("heading", "章节"),
                    section.get("content_type", "json_block"),
                    section.get("data"),
                )
            )

        content = "\n".join(lines)
        date_label = datetime.now(UTC).strftime("%Y-%m-%d")
        slug = _slugify(title)
        out_dir = self.settings.data_dir / output_subdir
        if source_collection:
            out_dir = out_dir / source_collection
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{slug}_{date_label}.md"
        path.write_text(content, encoding="utf-8")

        chunks_added = 0
        source = str(path.resolve())
        if ingest_to_rag and self.ingest_service:
            chunks_added, source = self.ingest_service.ingest_file(path, force=True)

        return {
            "path": str(path),
            "source": source,
            "sections_count": len(sections),
            "chunks_added": chunks_added,
            "ingested": ingest_to_rag,
        }
