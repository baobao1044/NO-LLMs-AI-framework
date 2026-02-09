#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.agent import AgentLoop
from core.logger import JsonlLogger
from core.task import CodeTask
from core.verifier import FunctionCase, build_composite_function_verifier, build_ts_composite_verifier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run golden set and gate regressions.")
    parser.add_argument(
        "--from-log",
        type=Path,
        default=None,
        help="Optional JSONL log path to compute metrics directly.",
    )
    parser.add_argument(
        "--golden-set",
        type=Path,
        default=Path("configs/golden_set.json"),
        help="Golden task set JSON file.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("configs/regression_baseline.json"),
        help="Baseline metrics JSON file.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Write baseline from current run (requires explicit flag).",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--pass-rate-drop",
        type=float,
        default=0.0,
        help="Allowed absolute drop in pass rate percentage.",
    )
    parser.add_argument(
        "--attempts-increase",
        type=float,
        default=0.0,
        help="Allowed absolute increase in mean attempts.",
    )
    parser.add_argument(
        "--failure-spike",
        type=int,
        default=0,
        help="Allowed absolute spike per failure_type count.",
    )
    parser.add_argument(
        "--flaky-quarantine",
        type=Path,
        default=None,
        help="Optional flaky group quarantine config to ignore in failure counts.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    language = str(entry.get("language") or "py")
    if language not in {"py", "ts"}:
        raise ValueError(f"unsupported language={language} for task_id={entry.get('task_id')}")

    if "verifier" in entry:
        verifier_payload = entry["verifier"]
        function_name = verifier_payload["function_name"]
        testcases = [{"inputs": case["args"], "expected": case["expected"]} for case in verifier_payload["cases"]]
        signature = None
    else:
        function_name = entry["function_name"]
        testcases = [{"inputs": case["inputs"], "expected": case["expected"]} for case in entry["testcases"]]
        signature = entry.get("signature")

    attempts = list(entry.get("attempts") or [])
    if not attempts:
        raise ValueError(f"missing attempts for task_id={entry.get('task_id')}")

    timeout_seconds = float(entry.get("timeout_seconds", 1.0 if language == "py" else 2.0))
    tsc_timeout_seconds = float(entry.get("tsc_timeout_seconds", 20.0))
    target_file = str(entry.get("target_file") or (f"{entry['task_id']}.py" if language == "py" else "src/solution.ts"))

    return {
        "task_id": str(entry["task_id"]),
        "prompt": str(entry["prompt"]),
        "language": language,
        "attempts": attempts,
        "target_file": target_file,
        "function_name": str(function_name),
        "signature": signature,
        "testcases": testcases,
        "timeout_seconds": timeout_seconds,
        "tsc_timeout_seconds": tsc_timeout_seconds,
    }


def _build_task(entry: dict[str, Any], root: Path) -> tuple[CodeTask, object]:
    normalized = _normalize_entry(entry)
    language = normalized["language"]

    if language == "ts":
        verifier = build_ts_composite_verifier(
            function_name=normalized["function_name"],
            testcases=list(normalized["testcases"]),
            signature=normalized["signature"],
            timeout_seconds=normalized["timeout_seconds"],
            tsc_timeout_seconds=normalized["tsc_timeout_seconds"],
        )
    else:
        cases = [
            FunctionCase(args=tuple(case["inputs"]), expected=case["expected"])
            for case in normalized["testcases"]
        ]
        verifier = build_composite_function_verifier(
            function_name=normalized["function_name"],
            cases=cases,
            timeout_seconds=normalized["timeout_seconds"],
        )

    task = CodeTask(
        task_id=normalized["task_id"],
        prompt=normalized["prompt"],
        target_file=root / normalized["target_file"],
        attempts=normalized["attempts"],
        language=language,
    )
    return task, verifier


def _load_flaky_quarantine(path: Path | None) -> set[tuple[str, str, str, str]]:
    if path is None:
        return set()
    if not path.exists():
        return set()
    payload = _load_json(path)
    out: set[tuple[str, str, str, str]] = set()
    for item in payload.get("flaky_groups", []):
        out.add(
            (
                str(item.get("language") or "py"),
                str(item.get("failure_type") or ""),
                str(item.get("error_signature") or ""),
                str(item.get("verifier_stage_failed") or ""),
            )
        )
    return out


def _collect_metrics(
    events: list[dict],
    run_results: list[dict],
    flaky_quarantine: set[tuple[str, str, str, str]] | None = None,
) -> dict[str, Any]:
    if flaky_quarantine is None:
        flaky_quarantine = set()

    run_count = len(run_results)
    pass_count = sum(1 for result in run_results if result["done"])
    mean_attempts = sum(result["attempts_used"] for result in run_results) / run_count if run_count else 0.0

    failure_counts: dict[str, int] = {}
    failure_counts_by_language: dict[str, dict[str, int]] = {}
    for event in events:
        if event.get("passed"):
            continue
        failure_type = str(event.get("failure_type") or "UNKNOWN")
        language = str(event.get("language") or "py")
        group_key = (
            language,
            failure_type,
            str(event.get("error_signature") or ""),
            str(event.get("verifier_stage_failed") or ""),
        )
        if group_key in flaky_quarantine:
            continue
        failure_counts[failure_type] = failure_counts.get(failure_type, 0) + 1
        lang_bucket = failure_counts_by_language.setdefault(language, {})
        lang_bucket[failure_type] = lang_bucket.get(failure_type, 0) + 1

    language_runs: dict[str, list[dict[str, Any]]] = {}
    for result in run_results:
        language_runs.setdefault(result["language"], []).append(result)

    run_count_by_language: dict[str, int] = {}
    pass_rate_by_language: dict[str, float] = {}
    mean_attempts_by_language: dict[str, float] = {}
    for language, rows in sorted(language_runs.items()):
        run_count_by_language[language] = len(rows)
        pass_count_lang = sum(1 for row in rows if row["done"])
        pass_rate_by_language[language] = round((pass_count_lang / len(rows)) * 100.0 if rows else 0.0, 4)
        mean_attempts_by_language[language] = round(
            sum(row["attempts_used"] for row in rows) / len(rows) if rows else 0.0,
            4,
        )

    task_metrics: list[dict[str, Any]] = []
    for result in run_results:
        task_metrics.append(
            {
                "task_id": result["task_id"],
                "language": result["language"],
                "done": result["done"],
                "attempts_used": result["attempts_used"],
            }
        )

    pass_rate = (pass_count / run_count) * 100.0 if run_count else 0.0
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_count": run_count,
        "pass_rate": round(pass_rate, 4),
        "mean_attempts": round(mean_attempts, 4),
        "failure_type_counts": failure_counts,
        "run_count_by_language": run_count_by_language,
        "pass_rate_by_language": pass_rate_by_language,
        "mean_attempts_by_language": mean_attempts_by_language,
        "failure_type_counts_by_language": failure_counts_by_language,
        "tasks": task_metrics,
    }


def _read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _run_golden_set(
    golden_set_path: Path,
    flaky_quarantine: set[tuple[str, str, str, str]] | None = None,
) -> dict[str, Any]:
    golden = _load_json(golden_set_path)
    entries = golden["tasks"]

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        log_file = root / "events.jsonl"
        logger = JsonlLogger(log_file)
        run_results: list[dict] = []

        for entry in entries:
            task, verifier = _build_task(entry, root=root)
            result = AgentLoop().run(task=task, verifier=verifier, logger=logger)
            run_results.append(
                {
                    "task_id": task.task_id,
                    "language": task.language,
                    "done": result.done,
                    "attempts_used": result.attempts_used,
                }
            )

        events = _read_jsonl(log_file)
        return _collect_metrics(events=events, run_results=run_results, flaky_quarantine=flaky_quarantine)


def _run_from_log(
    log_path: Path,
    flaky_quarantine: set[tuple[str, str, str, str]] | None = None,
) -> dict[str, Any]:
    events = _read_jsonl(log_path)
    run_state: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(events, start=1):
        run_id = str(event.get("run_id") or f"legacy_run_{index}")
        language = str(event.get("language") or "py")
        state = run_state.setdefault(
            run_id,
            {
                "task_id": event.get("task_id"),
                "language": language,
                "done": False,
                "attempts_used": 0,
            },
        )
        state["language"] = language
        state["task_id"] = event.get("task_id")
        state["done"] = state["done"] or bool(event.get("passed"))
        state["attempts_used"] = max(state["attempts_used"], int(event.get("attempt_index") or 0))

    run_results = [
        {
            "task_id": state["task_id"],
            "language": state["language"],
            "done": state["done"],
            "attempts_used": state["attempts_used"],
        }
        for _, state in sorted(run_state.items())
    ]
    return _collect_metrics(events=events, run_results=run_results, flaky_quarantine=flaky_quarantine)


def _compare(
    baseline: dict[str, Any],
    current: dict[str, Any],
    pass_rate_drop: float,
    attempts_increase: float,
    failure_spike: int,
) -> list[str]:
    failures: list[str] = []

    baseline_pass_rate = float(baseline.get("pass_rate", 0.0))
    current_pass_rate = float(current.get("pass_rate", 0.0))
    if baseline_pass_rate - current_pass_rate > pass_rate_drop:
        failures.append(
            "pass_rate regression: "
            f"baseline={baseline_pass_rate:.4f} current={current_pass_rate:.4f} "
            f"allowed_drop={pass_rate_drop:.4f}"
        )

    baseline_attempts = float(baseline.get("mean_attempts", 0.0))
    current_attempts = float(current.get("mean_attempts", 0.0))
    if current_attempts - baseline_attempts > attempts_increase:
        failures.append(
            "mean_attempts regression: "
            f"baseline={baseline_attempts:.4f} current={current_attempts:.4f} "
            f"allowed_increase={attempts_increase:.4f}"
        )

    base_failures: dict[str, int] = baseline.get("failure_type_counts", {})
    curr_failures: dict[str, int] = current.get("failure_type_counts", {})
    keys = set(base_failures) | set(curr_failures)
    for key in sorted(keys):
        base_count = int(base_failures.get(key, 0))
        curr_count = int(curr_failures.get(key, 0))
        if curr_count - base_count > failure_spike:
            failures.append(
                "failure_type regression: "
                f"type={key} baseline={base_count} current={curr_count} "
                f"allowed_spike={failure_spike}"
            )

    base_pass_by_lang: dict[str, float] = baseline.get("pass_rate_by_language", {})
    curr_pass_by_lang: dict[str, float] = current.get("pass_rate_by_language", {})
    for language in sorted(set(base_pass_by_lang) | set(curr_pass_by_lang)):
        base_value = float(base_pass_by_lang.get(language, 0.0))
        curr_value = float(curr_pass_by_lang.get(language, 0.0))
        if base_value - curr_value > pass_rate_drop:
            failures.append(
                "pass_rate regression by language: "
                f"language={language} baseline={base_value:.4f} current={curr_value:.4f} "
                f"allowed_drop={pass_rate_drop:.4f}"
            )

    base_attempts_by_lang: dict[str, float] = baseline.get("mean_attempts_by_language", {})
    curr_attempts_by_lang: dict[str, float] = current.get("mean_attempts_by_language", {})
    for language in sorted(set(base_attempts_by_lang) | set(curr_attempts_by_lang)):
        base_value = float(base_attempts_by_lang.get(language, 0.0))
        curr_value = float(curr_attempts_by_lang.get(language, 0.0))
        if curr_value - base_value > attempts_increase:
            failures.append(
                "mean_attempts regression by language: "
                f"language={language} baseline={base_value:.4f} current={curr_value:.4f} "
                f"allowed_increase={attempts_increase:.4f}"
            )

    base_failure_by_lang: dict[str, dict[str, int]] = baseline.get("failure_type_counts_by_language", {})
    curr_failure_by_lang: dict[str, dict[str, int]] = current.get("failure_type_counts_by_language", {})
    for language in sorted(set(base_failure_by_lang) | set(curr_failure_by_lang)):
        base_bucket = base_failure_by_lang.get(language, {})
        curr_bucket = curr_failure_by_lang.get(language, {})
        for failure_type in sorted(set(base_bucket) | set(curr_bucket)):
            base_count = int(base_bucket.get(failure_type, 0))
            curr_count = int(curr_bucket.get(failure_type, 0))
            if curr_count - base_count > failure_spike:
                failures.append(
                    "failure_type regression by language: "
                    f"language={language} type={failure_type} baseline={base_count} current={curr_count} "
                    f"allowed_spike={failure_spike}"
                )

    return failures


def _baseline_diff_summary(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    previous_pass = float(previous.get("pass_rate", 0.0))
    current_pass = float(current.get("pass_rate", 0.0))
    previous_attempts = float(previous.get("mean_attempts", 0.0))
    current_attempts = float(current.get("mean_attempts", 0.0))

    return {
        "pass_rate": {
            "before": round(previous_pass, 4),
            "after": round(current_pass, 4),
            "delta": round(current_pass - previous_pass, 4),
        },
        "mean_attempts": {
            "before": round(previous_attempts, 4),
            "after": round(current_attempts, 4),
            "delta": round(current_attempts - previous_attempts, 4),
        },
        "failure_type_counts_before": previous.get("failure_type_counts", {}),
        "failure_type_counts_after": current.get("failure_type_counts", {}),
        "pass_rate_by_language_before": previous.get("pass_rate_by_language", {}),
        "pass_rate_by_language_after": current.get("pass_rate_by_language", {}),
    }


def main() -> int:
    args = parse_args()
    if args.write_baseline and not args.update_baseline:
        print("warning=--write-baseline is deprecated, use --update-baseline")
        args.update_baseline = True

    flaky_quarantine = _load_flaky_quarantine(args.flaky_quarantine)
    if args.from_log is not None:
        metrics = _run_from_log(args.from_log, flaky_quarantine=flaky_quarantine)
    else:
        metrics = _run_golden_set(args.golden_set, flaky_quarantine=flaky_quarantine)
    print(
        f"current pass_rate={metrics['pass_rate']:.4f} "
        f"mean_attempts={metrics['mean_attempts']:.4f}"
    )
    print(f"current pass_rate_by_language={json.dumps(metrics['pass_rate_by_language'], sort_keys=True)}")
    print(f"current mean_attempts_by_language={json.dumps(metrics['mean_attempts_by_language'], sort_keys=True)}")
    print(f"current failure_type_counts={json.dumps(metrics['failure_type_counts'], sort_keys=True)}")

    if args.update_baseline:
        previous_baseline: dict[str, Any] = {}
        if args.baseline.exists():
            previous_baseline = _load_json(args.baseline)
        diff_summary = _baseline_diff_summary(previous_baseline, metrics)
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(metrics, ensure_ascii=True, indent=2), encoding="utf-8")
        print("baseline_update=enabled")
        print(f"baseline_file={args.baseline}")
        print(f"baseline_diff_summary={json.dumps(diff_summary, ensure_ascii=True, sort_keys=True)}")
        return 0

    baseline = _load_json(args.baseline)
    failures = _compare(
        baseline=baseline,
        current=metrics,
        pass_rate_drop=args.pass_rate_drop,
        attempts_increase=args.attempts_increase,
        failure_spike=args.failure_spike,
    )
    if failures:
        print("regression=FAIL")
        for item in failures:
            print(item)
        return 1

    print("regression=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
