#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate offline curriculum from event logs.")
    parser.add_argument("log_file", type=Path, help="Path to JSONL event log.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("curriculum.json"),
        help="Output curriculum JSON path.",
    )
    parser.add_argument(
        "--mode",
        choices=["easy_to_hard", "focus_common_failures"],
        default="easy_to_hard",
        help="Task ordering strategy.",
    )
    parser.add_argument(
        "--language",
        choices=["py", "ts"],
        default=None,
        help="Optional language filter.",
    )
    return parser.parse_args()


def load_records(log_file: Path) -> list[dict]:
    records: list[dict] = []
    with log_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _entropy(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    value = 0.0
    for count in counts.values():
        p = count / total
        value -= p * math.log2(p)
    return value


def build_curriculum(records: list[dict], mode: str, language: str | None = None) -> list[dict[str, Any]]:
    run_state: dict[str, dict[str, Any]] = {}
    task_fail_types: dict[str, Counter[str]] = defaultdict(Counter)
    task_signatures: dict[str, Counter[str]] = defaultdict(Counter)
    task_identity: dict[str, tuple[str | None, str | None, str]] = {}

    for index, event in enumerate(records, start=1):
        event_language = str(event.get("language") or "py")
        if language is not None and event_language != language:
            continue

        run_id = event.get("run_id") or f"legacy_run_{index}"
        task_hash = event.get("task_hash") or f"legacy_task_{index}"
        key = f"{event_language}::{task_hash}::{event.get('task_id')}"
        task_identity[key] = (event.get("task_id"), task_hash, event_language)

        state = run_state.setdefault(
            run_id,
            {
                "task_key": key,
                "attempts": 0,
                "passed": False,
            },
        )
        state["attempts"] = max(state["attempts"], int(event.get("attempt_index", 0)))
        state["passed"] = state["passed"] or bool(event.get("passed"))

        if not event.get("passed"):
            failure_type = event.get("failure_type") or "UNKNOWN"
            signature = event.get("error_signature") or "UNKNOWN"
            task_fail_types[key][failure_type] += 1
            task_signatures[key][signature] += 1

    task_runs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for state in run_state.values():
        task_runs[state["task_key"]].append(state)

    rows: list[dict[str, Any]] = []
    for task_key, runs in task_runs.items():
        task_id, task_hash, task_language = task_identity[task_key]
        attempts = [run["attempts"] for run in runs]
        pass_count = sum(1 for run in runs if run["passed"])
        run_count = len(runs)
        pass_rate = (pass_count / run_count) * 100.0 if run_count else 0.0
        median_attempts = float(median(attempts)) if attempts else 0.0
        fail_entropy = _entropy(task_fail_types[task_key])
        top_sig = task_signatures[task_key].most_common(1)
        top_signature = top_sig[0][0] if top_sig else None
        top_signature_count = top_sig[0][1] if top_sig else 0

        difficulty_score = median_attempts + fail_entropy + (top_signature_count / max(run_count, 1))
        rows.append(
            {
                "task_id": task_id,
                "language": task_language,
                "task_hash": task_hash,
                "run_count": run_count,
                "pass_rate": round(pass_rate, 4),
                "median_attempts": round(median_attempts, 4),
                "failure_type_entropy": round(fail_entropy, 4),
                "top_error_signature": top_signature,
                "top_error_signature_count": top_signature_count,
                "difficulty_score": round(difficulty_score, 4),
            }
        )

    if mode == "easy_to_hard":
        rows.sort(
            key=lambda row: (
                row["difficulty_score"],
                row["median_attempts"],
                row["language"],
                row["task_id"] or "",
            )
        )
    else:
        rows.sort(
            key=lambda row: (
                -row["top_error_signature_count"],
                -row["failure_type_entropy"],
                -row["difficulty_score"],
                row["language"],
                row["task_id"] or "",
            )
        )
    return rows


def main() -> int:
    args = parse_args()
    records = load_records(args.log_file)
    tasks = build_curriculum(records, mode=args.mode, language=args.language)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_log": str(args.log_file),
        "mode": args.mode,
        "language": args.language,
        "task_count": len(tasks),
        "tasks": tasks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"task_count={len(tasks)}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
