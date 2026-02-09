from __future__ import annotations

from pathlib import Path

from .base import VerificationResult
from .function_verifier import FunctionCase, FunctionVerifier
from .syntax_verifier import SyntaxVerifier
from .timeout_verifier import TimeoutVerifier


class CompositeVerifier:
    verifier_name = "composite_verifier"
    verifier_version = "1.0.0"

    def __init__(
        self,
        unit_verifier: FunctionVerifier,
        timeout_seconds: float = 1.0,
    ) -> None:
        self.syntax_verifier = SyntaxVerifier()
        self.timeout_verifier = TimeoutVerifier(
            unit_verifier=unit_verifier,
            timeout_seconds=timeout_seconds,
        )
        self.unit_verifier = unit_verifier
        self.timeout_seconds = timeout_seconds

    def verify(self, source_file: Path) -> VerificationResult:
        syntax_result = self.syntax_verifier.verify(source_file)
        if not syntax_result.passed:
            return self._as_pipeline_result(syntax_result, stage_default="syntax")

        timeout_result = self.timeout_verifier.verify(source_file)
        if not timeout_result.passed:
            stage = timeout_result.verifier_stage_failed or "unit_test"
            return self._as_pipeline_result(timeout_result, stage_default=stage)

        return VerificationResult(
            passed=True,
            verifier_name=self.verifier_name,
            verifier_version=self.verifier_version,
            verifier_stage_failed=None,
        )

    def task_payload_snapshot(self) -> tuple[dict, bool]:
        return self.unit_verifier.task_payload_snapshot()

    def replay_config(self) -> dict:
        return {
            "kind": "composite",
            "timeout_seconds": self.timeout_seconds,
        }

    @staticmethod
    def from_task_payload(
        payload: dict,
        timeout_seconds: float = 1.0,
    ) -> "CompositeVerifier":
        unit_verifier = FunctionVerifier.from_task_payload(
            payload=payload,
            verifier_name="function_verifier",
            verifier_version="1.1.0",
        )
        return CompositeVerifier(unit_verifier=unit_verifier, timeout_seconds=timeout_seconds)

    def _as_pipeline_result(self, result: VerificationResult, stage_default: str) -> VerificationResult:
        return VerificationResult(
            passed=False,
            error=result.error,
            error_type=result.error_type,
            error_message=result.error_message,
            verifier_name=self.verifier_name,
            verifier_version=self.verifier_version,
            verifier_stage_failed=result.verifier_stage_failed or stage_default,
        )


def build_composite_function_verifier(
    function_name: str,
    cases: list[FunctionCase],
    timeout_seconds: float = 1.0,
) -> CompositeVerifier:
    unit = FunctionVerifier(
        function_name=function_name,
        cases=cases,
    )
    return CompositeVerifier(unit_verifier=unit, timeout_seconds=timeout_seconds)
