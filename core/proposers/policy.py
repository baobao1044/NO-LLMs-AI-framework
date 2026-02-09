from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProposerPolicy:
    enabled: bool = False
    allowed_languages: tuple[str, ...] = ("ts", "py")
    max_calls_per_task: int = 1
    max_calls_per_day: int = 20
    max_total_seconds_per_day: float = 30.0
    only_for_uncovered_signatures: bool = True
    uncovered_source: str = "configs/uncovered_signatures.json"
    timeout_seconds: float = 2.0


def load_proposer_policy(path: Path = Path("configs/proposer_policy.json")) -> ProposerPolicy:
    if not path.exists():
        return ProposerPolicy()

    payload = json.loads(path.read_text(encoding="utf-8"))
    return ProposerPolicy(
        enabled=bool(payload.get("enabled", False)),
        allowed_languages=tuple(str(item) for item in payload.get("allowed_languages", ["ts", "py"])),
        max_calls_per_task=int(payload.get("max_calls_per_task", 1)),
        max_calls_per_day=int(payload.get("max_calls_per_day", 20)),
        max_total_seconds_per_day=float(payload.get("max_total_seconds_per_day", 30.0)),
        only_for_uncovered_signatures=bool(payload.get("only_for_uncovered_signatures", True)),
        uncovered_source=str(payload.get("uncovered_source", "configs/uncovered_signatures.json")),
        timeout_seconds=float(payload.get("timeout_seconds", 2.0)),
    )


def load_uncovered_signatures(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()

    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items")
    if not isinstance(items, list):
        return set()

    signatures: set[tuple[str, str]] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        signature = item.get("error_signature")
        if not signature:
            continue
        language = str(item.get("language") or "all")
        signatures.add((language, str(signature)))
    return signatures


def is_signature_uncovered(
    *,
    language: str,
    error_signature: str | None,
    uncovered_signatures: set[tuple[str, str]],
) -> bool:
    if not error_signature:
        return False
    if (language, error_signature) in uncovered_signatures:
        return True
    if ("all", error_signature) in uncovered_signatures:
        return True
    return False


def budget_snapshot_dict(
    *,
    calls_day: int,
    seconds_day: float,
    calls_task: int,
) -> dict[str, Any]:
    return {
        "calls_day": calls_day,
        "seconds_day": round(seconds_day, 6),
        "calls_task": calls_task,
    }
