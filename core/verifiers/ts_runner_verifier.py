from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .base import VerificationResult
from .ts_project import ensure_ts_project


class TsRunnerVerifier:
    verifier_name = "ts_runner_verifier"
    verifier_version = "1.0.0"

    def __init__(
        self,
        function_name: str,
        testcases: list[dict[str, Any]],
        timeout_seconds: float = 2.0,
    ) -> None:
        self.function_name = function_name
        self.testcases = testcases
        self.timeout_seconds = timeout_seconds
        self.max_output_kb = 32

    def verify(self, source_file: Path) -> VerificationResult:
        project_root = ensure_ts_project(source_file)
        payload = {
            "function_name": self.function_name,
            "testcases": self.testcases,
        }
        (project_root / "task_payload.json").write_text(
            json.dumps(payload, ensure_ascii=True),
            encoding="utf-8",
        )

        try:
            proc = subprocess.run(
                ["node", "dist/runner.js"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return VerificationResult(
                passed=False,
                error=f"TimeoutError: runner exceeded {self.timeout_seconds:.3f}s",
                error_type="TimeoutError",
                error_message=f"runner exceeded {self.timeout_seconds:.3f}s",
                verifier_name=self.verifier_name,
                verifier_version=self.verifier_version,
                verifier_stage_failed="timeout",
            )

        stdout = self._truncate_output((proc.stdout or "").strip())
        if not stdout:
            return VerificationResult(
                passed=False,
                error="RuntimeError: empty runner output",
                error_type="RuntimeError",
                error_message="empty runner output",
                verifier_name=self.verifier_name,
                verifier_version=self.verifier_version,
                verifier_stage_failed="unit_test",
            )

        try:
            payload_out = json.loads(stdout)
        except json.JSONDecodeError:
            merged = self._truncate_output("\n".join(part for part in [proc.stdout, proc.stderr] if part).strip())
            message = "invalid runner JSON output"
            if merged:
                message = f"{message}: {merged.splitlines()[0]}"
            return VerificationResult(
                passed=False,
                error=f"RuntimeError: {message}",
                error_type="RuntimeError",
                error_message=message,
                verifier_name=self.verifier_name,
                verifier_version=self.verifier_version,
                verifier_stage_failed="unit_test",
            )

        if bool(payload_out.get("passed")):
            return VerificationResult(
                passed=True,
                verifier_name=self.verifier_name,
                verifier_version=self.verifier_version,
                verifier_stage_failed=None,
            )

        error_type = str(payload_out.get("error_type") or "AssertionError")
        error_message = str(payload_out.get("error_message") or "unit test failed")
        return VerificationResult(
            passed=False,
            error=f"{error_type}: {error_message}",
            error_type=error_type,
            error_message=error_message,
            verifier_name=self.verifier_name,
            verifier_version=self.verifier_version,
            verifier_stage_failed="unit_test",
        )

    def task_payload_snapshot(self) -> tuple[dict, bool]:
        return {
            "function_name": self.function_name,
            "testcases": self.testcases,
        }, False

    def replay_config(self) -> dict:
        return {
            "kind": "ts_runner",
            "timeout_seconds": self.timeout_seconds,
        }

    def _truncate_output(self, text: str) -> str:
        max_bytes = self.max_output_kb * 1024
        encoded = text.encode("utf-8", errors="replace")
        if len(encoded) <= max_bytes:
            return text
        truncated = encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()
        return truncated + " ...[truncated]"
