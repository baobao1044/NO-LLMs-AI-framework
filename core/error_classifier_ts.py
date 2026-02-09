from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ClassifiedTsDiagnostic:
    failure_type: str
    error_type: str
    error_message: str
    error_signature: str


_DIAGNOSTIC_RE = re.compile(r"error\s+TS(?P<code>\d{4}):\s*(?P<message>.+)")
_ABS_PATH_RE = re.compile(r"(?:(?:[A-Za-z]:)?[/\\][^\s'\"]+)")
_LINE_COL_RE = re.compile(r"\(\d+,\d+\)")
_SYNTAX_CODES = {"1002", "1005", "1109", "1128", "1136", "1160"}
_TYPE_CODES = {"2322", "2345", "2362", "2363", "2365", "2367", "7006"}
_NAME_CODES = {"2304", "2307", "2552"}


def classify_tsc_output(output: str) -> ClassifiedTsDiagnostic:
    code, message = _first_diagnostic(output)
    normalized = _normalize_message(message)

    if code in _SYNTAX_CODES:
        failure_type = "ts_syntax_error"
    elif code in _TYPE_CODES:
        failure_type = "ts_type_error"
    elif code in _NAME_CODES:
        failure_type = "ts_name_error"
    else:
        failure_type = "ts_compile_error"

    error_type = f"TS{code}"
    return ClassifiedTsDiagnostic(
        failure_type=failure_type,
        error_type=error_type,
        error_message=normalized,
        error_signature=f"{error_type}:{_short_message(normalized)}",
    )


def _first_diagnostic(output: str) -> tuple[str, str]:
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _DIAGNOSTIC_RE.search(line)
        if match:
            return match.group("code"), match.group("message")

    fallback = _short_message(" ".join(output.split()))
    if not fallback:
        fallback = "unknown TypeScript compile error"
    return "0000", fallback


def _normalize_message(message: str) -> str:
    value = _LINE_COL_RE.sub("", message)
    value = _ABS_PATH_RE.sub("<path>", value)
    value = " ".join(value.split())
    return value


def _short_message(message: str, max_len: int = 140) -> str:
    if len(message) <= max_len:
        return message
    return message[: max_len - 3] + "..."
