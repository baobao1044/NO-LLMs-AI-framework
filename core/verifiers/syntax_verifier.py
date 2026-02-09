from __future__ import annotations

import ast
from pathlib import Path

from .base import VerificationResult


class SyntaxVerifier:
    verifier_name = "syntax_verifier"
    verifier_version = "1.0.0"

    def verify(self, source_file: Path) -> VerificationResult:
        source = source_file.read_text(encoding="utf-8")
        try:
            ast.parse(source, filename=str(source_file))
        except SyntaxError as exc:
            message = str(exc)
            return VerificationResult(
                passed=False,
                error=f"SyntaxError: {message}",
                error_type=type(exc).__name__,
                error_message=message,
                verifier_name=self.verifier_name,
                verifier_version=self.verifier_version,
                verifier_stage_failed="syntax",
            )
        return VerificationResult(
            passed=True,
            verifier_name=self.verifier_name,
            verifier_version=self.verifier_version,
            verifier_stage_failed=None,
        )

    def task_payload_snapshot(self) -> tuple[dict, bool]:
        return {}, False

    def replay_config(self) -> dict:
        return {"kind": "syntax"}
