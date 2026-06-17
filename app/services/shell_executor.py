from __future__ import annotations

import json
import re
import shlex
import subprocess
import time
from pathlib import Path

from app.config import Settings, get_settings

BLOCKED_PATTERNS = [
    re.compile(r"\.\./"),
    re.compile(r"/etc/", re.I),
    re.compile(r"system32", re.I),
    re.compile(r"&&|\|\||;|`|>|<"),
]


class ShellExecutor:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _resolve_cwd(self) -> Path:
        cwd = self.settings.agent_shell_cwd.resolve()
        cwd.mkdir(parents=True, exist_ok=True)
        return cwd

    def _check_allowlist(self, command: str) -> None:
        if self.settings.agent_shell_mode != "allowlist":
            return
        patterns = self.settings.agent_shell_allowlist_patterns
        if not patterns:
            return
        if not any(re.search(p, command) for p in patterns):
            raise ValueError(f"Command not in allowlist: {command}")

    def _check_blocked(self, command: str) -> None:
        for pattern in BLOCKED_PATTERNS:
            if pattern.search(command):
                raise ValueError("Command contains blocked path pattern")

    def execute(self, command: str) -> dict:
        if not self.settings.agent_shell_enabled:
            raise RuntimeError("Shell execution is disabled")

        command = command.strip()
        if not command:
            raise ValueError("Empty command")
        if len(command) > 2000:
            raise ValueError("Command too long")

        self._check_blocked(command)
        self._check_allowlist(command)
        cmd_args = shlex.split(command, posix=True)
        if not cmd_args:
            raise ValueError("Empty command")

        cwd = self._resolve_cwd()
        start = time.perf_counter()
        try:
            completed = subprocess.run(
                cmd_args,
                shell=False,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=self.settings.agent_shell_timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Command timed out after {self.settings.agent_shell_timeout}s") from exc

        duration_ms = int((time.perf_counter() - start) * 1000)
        stdout = (completed.stdout or "")[:8000]
        stderr = (completed.stderr or "")[:8000]
        return {
            "command": command,
            "exit_code": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "duration_ms": duration_ms,
            "success": completed.returncode == 0,
        }
