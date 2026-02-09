from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PatchContext:
    task_id: str
    prompt: str
    code: str
    failure_type: str | None
    error_signature: str | None
    error_message: str | None
    task_payload: dict
    language: str = "py"


@dataclass(frozen=True)
class PatchResult:
    patched_code: str
    patcher_id: str
    patch_summary: str


class Patcher(Protocol):
    id: str

    def can_apply(self, ctx: PatchContext) -> bool:
        ...

    def apply(self, ctx: PatchContext) -> PatchResult | None:
        ...
