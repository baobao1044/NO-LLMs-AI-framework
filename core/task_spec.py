from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def is_json_only(value: Any) -> bool:
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, list):
        return all(is_json_only(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and is_json_only(item) for key, item in value.items())
    return False


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    prompt: str
    target_file: str
    function_name: str
    testcases: list[dict[str, Any]]
    difficulty: str
    language: str = "py"
    signature: str | None = None
    constraints: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    attempts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if not is_json_only(payload):
            raise ValueError("TaskSpec payload must be JSON-only")
        return payload
