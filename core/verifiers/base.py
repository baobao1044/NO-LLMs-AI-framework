from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    error: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    verifier_name: str | None = None
    verifier_version: str | None = None
    verifier_stage_failed: str | None = None


class Verifier(Protocol):
    verifier_name: str
    verifier_version: str

    def verify(self, source_file: Path) -> VerificationResult:
        ...

    def task_payload_snapshot(self) -> tuple[dict[str, Any], bool]:
        ...

    def replay_config(self) -> dict[str, Any]:
        ...
