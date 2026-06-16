from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import yaml

from app.config import Settings, get_settings


@dataclass
class TaskParamSpec:
    name: str
    type: str = "string"
    required: bool = False
    description: str = ""
    values: list[str] = field(default_factory=list)


@dataclass
class TaskDefinition:
    name: str
    description: str
    category: str = "general"
    script: str | None = None
    handler: Callable[..., dict[str, Any]] | None = None
    params: list[TaskParamSpec] = field(default_factory=list)
    output_mode: str = "json"
    timeout: int = 60


class TaskRegistry:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._tasks: dict[str, TaskDefinition] = {}
        self._load_builtin_tasks()
        self._load_yaml_tasks()

    def _load_builtin_tasks(self) -> None:
        self.register(
            TaskDefinition(
                name="health_check",
                description="检查 Ollama、Qdrant、PostgreSQL 等服务可达性",
                category="ops",
                handler=self._health_check,
                params=[],
            )
        )

    def _load_yaml_tasks(self) -> None:
        path = self.settings.agent_tasks_path
        if not path.exists():
            return
        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            return
        tasks = data.get("tasks", data) if isinstance(data, dict) else {}
        if not isinstance(tasks, dict):
            return
        for name, spec in tasks.items():
            if not isinstance(spec, dict):
                continue
            params = []
            for pname, pspec in (spec.get("params") or {}).items():
                if isinstance(pspec, dict):
                    params.append(
                        TaskParamSpec(
                            name=pname,
                            type=pspec.get("type", "string"),
                            required=bool(pspec.get("required", False)),
                            description=pspec.get("description", ""),
                            values=list(pspec.get("values") or []),
                        )
                    )
            self.register(
                TaskDefinition(
                    name=name,
                    description=spec.get("description", name),
                    category=spec.get("category", "stats"),
                    script=spec.get("script"),
                    params=params,
                    output_mode=spec.get("output_mode", "json"),
                    timeout=int(spec.get("timeout", self.settings.agent_task_timeout)),
                )
            )

    def register(self, task: TaskDefinition) -> None:
        self._tasks[task.name] = task

    def list_tasks(
        self,
        category: str | None = None,
        keyword: str | None = None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for task in self._tasks.values():
            if category and category != "all" and task.category != category:
                continue
            hay = f"{task.name} {task.description}".lower()
            if keyword and keyword.lower() not in hay:
                continue
            items.append(
                {
                    "name": task.name,
                    "description": task.description,
                    "category": task.category,
                    "params_schema": [
                        {
                            "name": p.name,
                            "type": p.type,
                            "required": p.required,
                            "description": p.description,
                            "values": p.values,
                        }
                        for p in task.params
                    ],
                    "output_mode": task.output_mode,
                }
            )
        return sorted(items, key=lambda x: x["name"])

    def _resolve_date(self, value: Any) -> str:
        if value is None:
            raise ValueError("date parameter is required")
        text = str(value).strip().lower()
        tz = ZoneInfo(self.settings.agent_timezone)
        today = datetime.now(tz).date()
        if text in {"today", "今日"}:
            return today.isoformat()
        if text in {"yesterday", "昨日", "昨天"}:
            return date.fromordinal(today.toordinal() - 1).isoformat()
        return str(value)

    def _validate_params(self, task: TaskDefinition, params: dict[str, Any]) -> dict[str, Any]:
        resolved = dict(params or {})
        for spec in task.params:
            if spec.name not in resolved or resolved[spec.name] in (None, ""):
                if spec.required:
                    raise ValueError(f"Missing required parameter: {spec.name}")
            elif spec.type == "date":
                resolved[spec.name] = self._resolve_date(resolved[spec.name])
            elif spec.type == "int":
                resolved[spec.name] = int(resolved[spec.name])
            elif spec.type == "bool":
                resolved[spec.name] = bool(resolved[spec.name])
            elif spec.type == "enum" and spec.values:
                if str(resolved[spec.name]) not in spec.values:
                    raise ValueError(f"Invalid enum value for {spec.name}")
        return resolved

    def run(self, task_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        task = self._tasks.get(task_name)
        if not task:
            raise ValueError(f"Unknown task: {task_name}")

        resolved = self._validate_params(task, params or {})
        start = time.perf_counter()

        if task.handler:
            result = task.handler(resolved)
        elif task.script:
            result = self._run_script(task, resolved)
        else:
            raise ValueError(f"Task '{task_name}' has no handler or script")

        duration_ms = int((time.perf_counter() - start) * 1000)
        result["duration_ms"] = duration_ms
        result["task"] = task_name
        return result

    def _run_script(self, task: TaskDefinition, params: dict[str, Any]) -> dict[str, Any]:
        script_path = Path(task.script or "")
        if not script_path.is_absolute():
            script_path = Path.cwd() / script_path
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")

        cmd = [sys.executable, str(script_path), "--output", "json"]
        for key, value in params.items():
            cmd.extend([f"--{key.replace('_', '-')}", str(value)])

        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=task.timeout,
            cwd=str(Path.cwd()),
        )
        stdout = (completed.stdout or "").strip()
        if not stdout:
            raise RuntimeError(completed.stderr or "Script produced no output")

        last_line = stdout.splitlines()[-1]
        payload = json.loads(last_line)
        if not payload.get("success", False):
            raise RuntimeError(payload.get("error") or "Script failed")
        return payload

    def _health_check(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": True,
            "data": {"message": "Use get_system_health tool for detailed status"},
        }

    def set_handler(self, name: str, handler: Callable[..., dict[str, Any]]) -> None:
        if name in self._tasks:
            self._tasks[name].handler = handler
