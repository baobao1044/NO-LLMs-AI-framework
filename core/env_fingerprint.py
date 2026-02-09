from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path
from typing import Any


def _run_command(cmd: list[str], timeout_seconds: float = 2.0) -> str | None:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except Exception:
        return None

    if proc.returncode != 0:
        return None
    value = (proc.stdout or proc.stderr or "").strip()
    return value or None


def _git_commit() -> str | None:
    repo_root = Path(__file__).resolve().parents[1]
    value = _run_command(["git", "rev-parse", "HEAD"], timeout_seconds=1.0)
    if value is None:
        return None
    if len(value) == 40:
        return value
    return None


def get_env_fingerprint() -> dict[str, Any]:
    python_version = platform.python_version()
    node_version = _run_command(["node", "-v"]) or "unknown"
    tsc_version = _run_command(["tsc", "-v"]) or "unknown"

    return {
        "python_version": python_version,
        "node_version": node_version,
        "tsc_version": tsc_version,
        "platform": platform.platform(),
        "git_commit": _git_commit(),
    }
