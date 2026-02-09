from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CodeTask:
    """A minimal coding task executed by fixed attempts, no reasoning required."""

    task_id: str
    prompt: str
    target_file: Path
    attempts: list[str]
    language: str = "py"
