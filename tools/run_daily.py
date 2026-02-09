#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.agent import AgentLoop
from core.logger import JsonlLogger
from core.task import CodeTask
from core.verifier import FunctionCase, build_composite_function_verifier, build_ts_composite_verifier
from tools.create_run_pack import create_run_pack
from tools.generate_tasks import generate_tasks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic daily pipeline within budget.")
    parser.add_argument("--config", type=Path, default=Path("configs/daily_config.json"))
    parser.add_argument("--date", type=str, default=None, help="UTC date YYYYMMDD")
    return parser.parse_args()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _daily_seed(config: dict[str, Any], day: str) -> int:
    base = int(config.get("seed_base", 123))
    if str(config.get("seed_daily_mode", "date-derived")) == "fixed":
        return base
    return base + int(day)


def _normalize_generated(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task["task_id"],
        "language": task.get("language", "py"),
        "prompt": task["prompt"],
        "target_file": task["target_file"],
        "function_name": task["function_name"],
        "signature": task.get("signature"),
        "testcases": task["testcases"],
        "attempts": task["attempts"],
    }


def _normalize_golden(entry: dict[str, Any]) -> dict[str, Any]:
    language = str(entry.get("language") or "py")
    if "verifier" in entry:
        return {
            "task_id": str(entry["task_id"]),
            "language": language,
            "prompt": str(entry["prompt"]),
            "target_file": str(entry.get("target_file") or f"{entry['task_id']}.py"),
            "function_name": str(entry["verifier"]["function_name"]),
            "signature": None,
            "testcases": [
                {"inputs": case["args"], "expected": case["expected"]}
                for case in entry["verifier"]["cases"]
            ],
            "attempts": list(entry["attempts"]),
        }

    return {
        "task_id": str(entry["task_id"]),
        "language": language,
        "prompt": str(entry["prompt"]),
        "target_file": str(entry.get("target_file") or ("src/solution.ts" if language == "ts" else f"{entry['task_id']}.py")),
        "function_name": str(entry["function_name"]),
        "signature": entry.get("signature"),
        "testcases": list(entry["testcases"]),
        "attempts": list(entry["attempts"]),
    }


def _build_verifier(entry: dict[str, Any]) -> object:
    language = str(entry.get("language") or "py")
    if language == "ts":
        return build_ts_composite_verifier(
            function_name=entry["function_name"],
            testcases=entry["testcases"],
            signature=entry.get("signature"),
            timeout_seconds=2.0,
            tsc_timeout_seconds=20.0,
        )

    cases = [FunctionCase(args=tuple(case["inputs"]), expected=case["expected"]) for case in entry["testcases"]]
    return build_composite_function_verifier(
        function_name=entry["function_name"],
        cases=cases,
        timeout_seconds=1.0,
    )


def _collect_run_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    run_state: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(events, start=1):
        run_id = str(event.get("run_id") or f"legacy_run_{index}")
        language = str(event.get("language") or "py")
        state = run_state.setdefault(run_id, {"language": language, "done": False, "attempts": 0})
        state["language"] = language
        state["done"] = state["done"] or bool(event.get("passed"))
        state["attempts"] = max(state["attempts"], int(event.get("attempt_index") or 0))

    rows = list(run_state.values())
    by_lang: dict[str, list[bool]] = {}
    for row in rows:
        by_lang.setdefault(row["language"], []).append(row["done"])

    return {
        "run_count": len(rows),
        "pass_rate_by_language": {
            language: round(sum(1 for v in values if v) / len(values), 6) if values else 0.0
            for language, values in sorted(by_lang.items())
        },
        "mean_attempts": round(sum(row["attempts"] for row in rows) / len(rows), 6) if rows else 0.0,
    }


def main() -> int:
    args = parse_args()
    config = _load_json(args.config)
    day = args.date or _today()
    seed = _daily_seed(config=config, day=day)

    run_pack = create_run_pack(
        day,
        metadata={
            "seed": seed,
            "config": str(args.config),
            "policy": "daily",
            "budget": {
                "max_tasks_per_day": int(config.get("max_tasks_per_day", 12)),
                "max_attempts_per_task": int(config.get("max_attempts_per_task", 2)),
                "max_total_seconds": float(config.get("max_total_seconds", 90)),
            },
        },
    )

    generated_count = int(config.get("generated_task_count", 8))
    max_tasks = int(config.get("max_tasks_per_day", 12))
    max_attempts = int(config.get("max_attempts_per_task", 2))
    max_total_seconds = float(config.get("max_total_seconds", 90))
    languages_enabled = list(config.get("languages_enabled", ["ts", "py"]))

    entries: list[dict[str, Any]] = []

    if "py" in languages_enabled:
        golden_py = _load_json(Path("configs/golden_set.json"))
        entries.extend(_normalize_golden(entry) for entry in golden_py.get("tasks", []))
    if "ts" in languages_enabled:
        golden_ts = _load_json(Path("configs/ts_golden_set.json"))
        entries.extend(_normalize_golden(entry) for entry in golden_ts.get("tasks", []))

    lang_count = max(1, len(languages_enabled))
    base = generated_count // lang_count
    remainder = generated_count % lang_count
    for idx, language in enumerate(languages_enabled):
        count = base + (1 if idx < remainder else 0)
        if count <= 0:
            continue
        templates_key = "ts_templates" if language == "ts" else "py_templates"
        templates = list(config.get(templates_key, []))
        if not templates:
            continue
        generated_tasks = generate_tasks(
            seed=seed + idx,
            count=count,
            templates=templates,
            tag=str(config.get("generated_tag", "generated")),
        )
        generated_tasks = [task for task in generated_tasks if task.get("language") == language]
        entries.extend(_normalize_generated(task) for task in generated_tasks)

    entries.sort(key=lambda item: (str(item.get("language")), str(item.get("task_id"))))

    log_file = run_pack["log_file"]
    logger = JsonlLogger(log_file)

    started = perf_counter()
    executed = 0
    for entry in entries:
        if executed >= max_tasks:
            break
        if (perf_counter() - started) >= max_total_seconds:
            break

        attempts = list(entry.get("attempts") or [])[:max_attempts]
        if not attempts:
            continue
        verifier = _build_verifier(entry)

        task = CodeTask(
            task_id=entry["task_id"],
            prompt=entry["prompt"],
            target_file=run_pack["run_dir"] / str(entry["target_file"]),
            attempts=attempts,
            language=str(entry.get("language") or "py"),
        )
        AgentLoop().run(task=task, verifier=verifier, logger=logger)
        executed += 1

    records: list[dict[str, Any]] = []
    with log_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "date": day,
        "seed": seed,
        "executed_tasks": executed,
        "budget": {
            "max_tasks_per_day": max_tasks,
            "max_attempts_per_task": max_attempts,
            "max_total_seconds": max_total_seconds,
            "elapsed_seconds": round(perf_counter() - started, 6),
        },
        **_collect_run_summary(records),
    }

    reports_day_dir = Path("reports") / day
    reports_day_dir.mkdir(parents=True, exist_ok=True)
    summary_file = reports_day_dir / "daily_summary.json"
    summary_file.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")

    merged_log = Path("logs") / "agent_runs.jsonl"
    merged_log.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(log_file, merged_log)

    print(f"run_pack_log={log_file}")
    print(f"reports_day_dir={reports_day_dir}")
    print(f"daily_summary={summary_file}")
    print(f"active_log={merged_log}")
    print(f"executed_tasks={executed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
