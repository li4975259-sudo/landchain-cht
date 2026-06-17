#!/usr/bin/env python3
"""Run a lightweight regression checklist for recent hardening changes."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> int:
    print(f"$ {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=str(ROOT))
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LandChain regression checks")
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip unit tests",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Optional app log path; if set, run perf summary parser",
    )
    args = parser.parse_args()

    steps: list[tuple[str, list[str]]] = []
    if not args.skip_tests:
        steps.append(
            (
                "unit tests",
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
            )
        )
    if args.log_file:
        steps.append(
            (
                "perf summary parser",
                [
                    sys.executable,
                    "scripts/perf_log_summary.py",
                    "--log-file",
                    str(args.log_file),
                ],
            )
        )

    if not steps:
        print("Nothing to run. Use default options or pass --log-file.")
        return 0

    for name, cmd in steps:
        print(f"\n== {name} ==")
        code = _run(cmd)
        if code != 0:
            print(f"\nRegression check failed at: {name}", file=sys.stderr)
            return code

    print("\nAll regression checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
