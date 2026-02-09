from __future__ import annotations

import re
from dataclasses import dataclass

from .error_classifier_ts import classify_tsc_output
from .verifier import VerificationResult


@dataclass(frozen=True)
class ClassifiedFailure:
    failure_type: str | None
    error_signature: str | None


def classify_failure(result: VerificationResult, language: str = "py") -> ClassifiedFailure:
    if result.passed:
        return ClassifiedFailure(failure_type=None, error_signature=None)

    if language == "ts":
        return _classify_failure_ts(result)
    return _classify_failure_py(result)


def _classify_failure_ts(result: VerificationResult) -> ClassifiedFailure:
    error_type = (result.error_type or "").strip()
    message = (result.error_message or result.error or "").strip()
    message_lower = message.lower()
    stage = (result.verifier_stage_failed or "").strip()

    if error_type == "TimeoutError" or "timeout" in message_lower or stage == "timeout":
        return ClassifiedFailure(
            failure_type="timeout",
            error_signature=f"TimeoutError:{_short_message(message)}",
        )

    if re.fullmatch(r"TS\d{4}", error_type):
        diagnostic = classify_tsc_output(f"error {error_type}: {message}")
        return ClassifiedFailure(
            failure_type=diagnostic.failure_type,
            error_signature=diagnostic.error_signature,
        )

    if error_type == "AssertionError" or stage == "unit_test":
        failure_type = "assertion_fail" if "mismatch" in message_lower or error_type == "AssertionError" else "runtime_error"
        return ClassifiedFailure(
            failure_type=failure_type,
            error_signature=f"{error_type or 'RuntimeError'}:{_short_message(message)}",
        )

    if stage in {"tsc", "build"}:
        return ClassifiedFailure(
            failure_type="ts_compile_error",
            error_signature=f"{error_type or 'TS0000'}:{_short_message(message)}",
        )

    return ClassifiedFailure(
        failure_type="runtime_error",
        error_signature=f"{error_type or 'RuntimeError'}:{_short_message(message)}",
    )


def _classify_failure_py(result: VerificationResult) -> ClassifiedFailure:
    error_type = (result.error_type or "UnknownError").strip()
    message = (result.error_message or result.error or "").strip()
    message_lower = message.lower()

    if error_type == "SyntaxError":
        failure_type = "syntax_error"
    elif error_type in {"ModuleNotFoundError", "ImportError"}:
        failure_type = "import_error"
    elif error_type == "TimeoutError" or "timeout" in message_lower:
        failure_type = "timeout"
    elif error_type == "AssertionError" or "mismatch" in message_lower:
        failure_type = "assertion_fail"
    else:
        failure_type = "runtime_error"

    signature = f"{error_type}:{_short_message(message)}"
    return ClassifiedFailure(failure_type=failure_type, error_signature=signature)


def _short_message(message: str, max_len: int = 140) -> str:
    cleaned = " ".join(message.split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3] + "..."
