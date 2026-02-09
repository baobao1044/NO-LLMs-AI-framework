from __future__ import annotations

import subprocess
from pathlib import Path

from core.error_classifier_ts import classify_tsc_output

from .base import VerificationResult
from .ts_project import ensure_ts_project


class TscVerifier:
    verifier_name = "tsc_verifier"
    verifier_version = "1.0.0"

    def __init__(
        self,
        no_emit: bool = True,
        stage_name: str = "tsc",
        timeout_seconds: float = 20.0,
    ) -> None:
        self.no_emit = no_emit
        self.stage_name = stage_name
        self.timeout_seconds = timeout_seconds
        self.max_output_kb = 32

    def verify(self, source_file: Path) -> VerificationResult:
        project_root = ensure_ts_project(source_file)
        cmd = [
            "npx",
            "--yes",
            "--package",
            "typescript@5.6.3",
            "tsc",
            "-p",
            "tsconfig.json",
        ]
        if self.no_emit:
            cmd.append("--noEmit")

        try:
            proc = subprocess.run(
                cmd,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return VerificationResult(
                passed=False,
                error=f"TimeoutError: tsc exceeded {self.timeout_seconds:.3f}s",
                error_type="TimeoutError",
                error_message=f"tsc exceeded {self.timeout_seconds:.3f}s",
                verifier_name=self.verifier_name,
                verifier_version=self.verifier_version,
                verifier_stage_failed="timeout",
            )

        if proc.returncode == 0:
            return VerificationResult(
                passed=True,
                verifier_name=self.verifier_name,
                verifier_version=self.verifier_version,
                verifier_stage_failed=None,
            )

        diagnostics = self._truncate_output("\n".join(part for part in [proc.stdout, proc.stderr] if part).strip())
        classified = classify_tsc_output(diagnostics)
        return VerificationResult(
            passed=False,
            error=f"{classified.error_type}: {classified.error_message}",
            error_type=classified.error_type,
            error_message=classified.error_message,
            verifier_name=self.verifier_name,
            verifier_version=self.verifier_version,
            verifier_stage_failed=self.stage_name,
        )

    def task_payload_snapshot(self) -> tuple[dict, bool]:
        return {}, False

    def replay_config(self) -> dict:
        return {
            "kind": "tsc",
            "no_emit": self.no_emit,
            "stage_name": self.stage_name,
            "timeout_seconds": self.timeout_seconds,
        }

    def _truncate_output(self, text: str) -> str:
        max_bytes = self.max_output_kb * 1024
        encoded = text.encode("utf-8", errors="replace")
        if len(encoded) <= max_bytes:
            return text
        truncated = encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()
        return truncated + " ...[truncated]"
