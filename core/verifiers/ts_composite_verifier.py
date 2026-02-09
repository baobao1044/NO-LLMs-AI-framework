from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import VerificationResult
from .ts_runner_verifier import TsRunnerVerifier
from .tsc_verifier import TscVerifier


class TsCompositeVerifier:
    verifier_name = "ts_composite"
    verifier_version = "1.0.0"

    def __init__(
        self,
        function_name: str,
        testcases: list[dict[str, Any]],
        signature: str | None = None,
        timeout_seconds: float = 2.0,
        tsc_timeout_seconds: float = 20.0,
    ) -> None:
        self.function_name = function_name
        self.testcases = testcases
        self.signature = signature
        self.timeout_seconds = timeout_seconds
        self.tsc_timeout_seconds = tsc_timeout_seconds

        self.tsc_verifier = TscVerifier(
            no_emit=True,
            stage_name="tsc",
            timeout_seconds=tsc_timeout_seconds,
        )
        self.build_verifier = TscVerifier(
            no_emit=False,
            stage_name="build",
            timeout_seconds=tsc_timeout_seconds,
        )
        self.runner_verifier = TsRunnerVerifier(
            function_name=function_name,
            testcases=testcases,
            timeout_seconds=timeout_seconds,
        )

    def verify(self, source_file: Path) -> VerificationResult:
        tsc_result = self.tsc_verifier.verify(source_file)
        if not tsc_result.passed:
            return self._as_pipeline_result(tsc_result, "tsc")

        build_result = self.build_verifier.verify(source_file)
        if not build_result.passed:
            return self._as_pipeline_result(build_result, "build")

        runner_result = self.runner_verifier.verify(source_file)
        if not runner_result.passed:
            return self._as_pipeline_result(runner_result, runner_result.verifier_stage_failed or "unit_test")

        return VerificationResult(
            passed=True,
            verifier_name=self.verifier_name,
            verifier_version=self.verifier_version,
            verifier_stage_failed=None,
        )

    def task_payload_snapshot(self) -> tuple[dict[str, Any], bool]:
        return {
            "language": "ts",
            "function_name": self.function_name,
            "signature": self.signature,
            "testcases": self.testcases,
        }, False

    def replay_config(self) -> dict[str, Any]:
        return {
            "kind": "ts_composite",
            "timeout_seconds": self.timeout_seconds,
            "tsc_timeout_seconds": self.tsc_timeout_seconds,
        }

    @staticmethod
    def from_task_payload(
        payload: dict[str, Any],
        timeout_seconds: float = 2.0,
        tsc_timeout_seconds: float = 20.0,
    ) -> "TsCompositeVerifier":
        return TsCompositeVerifier(
            function_name=str(payload["function_name"]),
            testcases=list(payload["testcases"]),
            signature=payload.get("signature"),
            timeout_seconds=timeout_seconds,
            tsc_timeout_seconds=tsc_timeout_seconds,
        )

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


def build_ts_composite_verifier(
    function_name: str,
    testcases: list[dict[str, Any]],
    signature: str | None = None,
    timeout_seconds: float = 2.0,
    tsc_timeout_seconds: float = 20.0,
) -> TsCompositeVerifier:
    return TsCompositeVerifier(
        function_name=function_name,
        testcases=testcases,
        signature=signature,
        timeout_seconds=timeout_seconds,
        tsc_timeout_seconds=tsc_timeout_seconds,
    )
