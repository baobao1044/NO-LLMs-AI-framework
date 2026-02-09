#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.agent import AgentLoop
from core.logger import JsonlLogger
from core.proposers.codex_proposer import CodexProposer, CodexProposerConfig
from core.proposers.policy import ProposerPolicy, load_proposer_policy, load_uncovered_signatures
from core.proposers.runtime import ProposerRuntime
from core.task import CodeTask
from core.verifier import FunctionCase, build_composite_function_verifier, build_ts_composite_verifier
from tools.collect_quality_metrics import build_metrics as build_quality_metrics
from tools.create_run_pack import create_run_pack
from tools.generate_tasks import generate_tasks
from tools.replay import replay_records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic daily pipeline within budget.")
    parser.add_argument("--config", type=Path, default=Path("configs/daily_config.json"))
    parser.add_argument("--date", type=str, default=None, help="UTC date YYYYMMDD")
    parser.add_argument(
        "--ab",
        action="store_true",
        help="Run dual mode: baseline A (proposer disabled) and B (proposer enabled).",
    )
    parser.add_argument(
        "--proposer-policy",
        type=Path,
        default=Path("configs/proposer_policy.json"),
        help="Proposer policy file used for single run or AB mode B.",
    )
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
        "target_file": str(
            entry.get("target_file") or ("src/solution.ts" if language == "ts" else f"{entry['task_id']}.py")
        ),
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

    run_count = len(rows)
    pass_count = sum(1 for row in rows if row["done"])
    overall_pass_rate = (pass_count / run_count) if run_count else 0.0

    return {
        "run_count": run_count,
        "overall_pass_rate": round(overall_pass_rate, 6),
        "pass_rate_by_language": {
            language: round(sum(1 for v in values if v) / len(values), 6) if values else 0.0
            for language, values in sorted(by_lang.items())
        },
        "mean_attempts": round(sum(row["attempts"] for row in rows) / len(rows), 6) if rows else 0.0,
    }


def _build_entries(config: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    generated_count = int(config.get("generated_task_count", 8))
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
    return entries


def _load_records(log_file: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with log_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _build_runtime(policy: ProposerPolicy) -> ProposerRuntime:
    uncovered = load_uncovered_signatures(Path(policy.uncovered_source))
    proposer = None
    if policy.enabled:
        proposer = CodexProposer(CodexProposerConfig(timeout_seconds=policy.timeout_seconds))
    return ProposerRuntime(policy=policy, proposer=proposer, uncovered_signatures=uncovered)


def _collect_proposer_spend(records: list[dict[str, Any]]) -> dict[str, Any]:
    calls = 0
    seconds_day = 0.0
    by_id: dict[str, int] = {}
    for event in records:
        if not bool(event.get("proposer_used")):
            continue
        calls += 1
        proposer_id = str(event.get("proposer_id") or "unknown")
        by_id[proposer_id] = by_id.get(proposer_id, 0) + 1
        budget = event.get("proposer_budget_spent")
        if isinstance(budget, dict):
            seconds_day = max(seconds_day, float(budget.get("seconds_day") or 0.0))

    return {
        "calls": calls,
        "seconds": round(seconds_day, 6),
        "calls_by_proposer": dict(sorted(by_id.items())),
    }


def _run_mode(
    *,
    day: str,
    mode_suffix: str | None,
    config_path: Path,
    seed: int,
    entries: list[dict[str, Any]],
    max_tasks: int,
    max_attempts: int,
    max_total_seconds: float,
    proposer_policy: ProposerPolicy,
) -> dict[str, Any]:
    run_key = day if mode_suffix is None else f"{day}_{mode_suffix}"
    run_pack = create_run_pack(
        run_key,
        metadata={
            "seed": seed,
            "config": str(config_path),
            "policy": "daily",
            "mode": mode_suffix or "single",
            "proposer_policy": {
                "enabled": proposer_policy.enabled,
                "allowed_languages": list(proposer_policy.allowed_languages),
                "max_calls_per_task": proposer_policy.max_calls_per_task,
                "max_calls_per_day": proposer_policy.max_calls_per_day,
                "max_total_seconds_per_day": proposer_policy.max_total_seconds_per_day,
                "only_for_uncovered_signatures": proposer_policy.only_for_uncovered_signatures,
                "uncovered_source": proposer_policy.uncovered_source,
                "timeout_seconds": proposer_policy.timeout_seconds,
            },
            "budget": {
                "max_tasks_per_day": max_tasks,
                "max_attempts_per_task": max_attempts,
                "max_total_seconds": max_total_seconds,
            },
        },
    )

    logger = JsonlLogger(run_pack["log_file"])
    runtime = _build_runtime(proposer_policy)
    agent = AgentLoop(proposer_runtime=runtime)

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
        agent.run(task=task, verifier=verifier, logger=logger)
        executed += 1

    records = _load_records(run_pack["log_file"])
    quality_metrics = build_quality_metrics(records=records, source_log=run_pack["log_file"])
    _, replay_metrics = replay_records(records)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "date": day,
        "mode": mode_suffix or "single",
        "seed": seed,
        "executed_tasks": executed,
        "proposer_enabled": proposer_policy.enabled,
        "budget": {
            "max_tasks_per_day": max_tasks,
            "max_attempts_per_task": max_attempts,
            "max_total_seconds": max_total_seconds,
            "elapsed_seconds": round(perf_counter() - started, 6),
        },
        **_collect_run_summary(records),
        "signature_coverage": quality_metrics.get("signature_coverage", 0.0),
        "top_uncovered_signatures": quality_metrics.get("top_uncovered_signatures", []),
        "timeout_rate": quality_metrics.get("timeout_rate", 0.0),
        "flaky_groups_count": quality_metrics.get("flaky_groups_count", 0),
        "replay_match": replay_metrics.get("replay_match", 0),
        "replay_eligible": replay_metrics.get("replay_eligible", 0),
        "replay_match_rate": replay_metrics.get("replay_match_rate", 0.0),
        "env_fingerprint_mismatch_count": replay_metrics.get("env_fingerprint_mismatch_count", 0),
        "proposer_budget_spent": _collect_proposer_spend(records),
    }

    reports_dir = Path("reports") / run_key
    reports_dir.mkdir(parents=True, exist_ok=True)
    summary_file = reports_dir / "daily_summary.json"
    summary_file.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")

    return {
        "run_key": run_key,
        "run_pack": run_pack,
        "records": records,
        "summary": summary,
        "summary_file": summary_file,
    }


def main() -> int:
    args = parse_args()
    config = _load_json(args.config)
    day = args.date or _today()
    seed = _daily_seed(config=config, day=day)

    max_tasks = int(config.get("max_tasks_per_day", 12))
    max_attempts = int(config.get("max_attempts_per_task", 2))
    max_total_seconds = float(config.get("max_total_seconds", 90))
    entries = _build_entries(config=config, seed=seed)

    proposer_policy = load_proposer_policy(args.proposer_policy)

    if args.ab:
        result_a = _run_mode(
            day=day,
            mode_suffix="A",
            config_path=args.config,
            seed=seed,
            entries=entries,
            max_tasks=max_tasks,
            max_attempts=max_attempts,
            max_total_seconds=max_total_seconds,
            proposer_policy=replace(proposer_policy, enabled=False),
        )
        result_b = _run_mode(
            day=day,
            mode_suffix="B",
            config_path=args.config,
            seed=seed,
            entries=entries,
            max_tasks=max_tasks,
            max_attempts=max_attempts,
            max_total_seconds=max_total_seconds,
            proposer_policy=replace(proposer_policy, enabled=True),
        )

        active_log = Path("logs") / "agent_runs.jsonl"
        active_log.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(result_b["run_pack"]["log_file"], active_log)

        print(f"run_pack_log_A={result_a['run_pack']['log_file']}")
        print(f"run_pack_log_B={result_b['run_pack']['log_file']}")
        print(f"daily_summary_A={result_a['summary_file']}")
        print(f"daily_summary_B={result_b['summary_file']}")
        print(f"active_log={active_log}")
        print(f"executed_tasks_A={result_a['summary']['executed_tasks']}")
        print(f"executed_tasks_B={result_b['summary']['executed_tasks']}")
        return 0

    result = _run_mode(
        day=day,
        mode_suffix=None,
        config_path=args.config,
        seed=seed,
        entries=entries,
        max_tasks=max_tasks,
        max_attempts=max_attempts,
        max_total_seconds=max_total_seconds,
        proposer_policy=proposer_policy,
    )

    active_log = Path("logs") / "agent_runs.jsonl"
    active_log.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(result["run_pack"]["log_file"], active_log)

    print(f"run_pack_log={result['run_pack']['log_file']}")
    print(f"reports_day_dir={Path('reports') / day}")
    print(f"daily_summary={result['summary_file']}")
    print(f"active_log={active_log}")
    print(f"executed_tasks={result['summary']['executed_tasks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
