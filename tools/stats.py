#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print minimal analytics for event logs.")
    parser.add_argument("log_file", type=Path, help="Path to JSONL event log.")
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


def print_stats(records: list[dict]) -> None:
    if not records:
        print("records=0")
        return

    runs: dict[str, dict] = {}
    run_events: dict[str, list[dict]] = defaultdict(list)
    for index, event in enumerate(records, start=1):
        run_id = event.get("run_id") or f"legacy_run_{index}"
        language = str(event.get("language") or "py")
        run_events[run_id].append(event)
        state = runs.setdefault(
            run_id,
            {
                "task_id": event.get("task_id"),
                "task_hash": event.get("task_hash"),
                "language": language,
                "attempts": 0,
                "passed": False,
            },
        )
        state["language"] = language
        state["attempts"] = max(state["attempts"], int(event.get("attempt_index", 0)))
        state["passed"] = state["passed"] or bool(event.get("passed"))

    task_runs = defaultdict(list)
    language_runs: dict[str, list[bool]] = defaultdict(list)
    attempt_distribution: Counter[int] = Counter()
    attempts_by_task: dict[tuple[str | None, str | None], list[int]] = defaultdict(list)
    for run in runs.values():
        task_key = (run["task_id"], run["task_hash"])
        task_runs[task_key].append(run["passed"])
        language_runs[run["language"]].append(run["passed"])
        attempt_distribution[run["attempts"]] += 1
        attempts_by_task[task_key].append(run["attempts"])

    failure_breakdown: Counter[str] = Counter()
    signature_counts: Counter[str] = Counter()
    stage_breakdown: Counter[str] = Counter()
    signature_total: Counter[str] = Counter()
    signature_patch_hits: set[str] = set()
    patch_attempts: Counter[str] = Counter()
    patch_success: Counter[str] = Counter()

    for event in records:
        if event.get("passed"):
            pass
        else:
            failure_breakdown[event.get("failure_type") or "UNKNOWN"] += 1
            signature = event.get("error_signature") or "UNKNOWN"
            signature_counts[signature] += 1
            signature_total[signature] += 1
            stage_breakdown[event.get("verifier_stage_failed") or "UNKNOWN"] += 1

            if event.get("patcher_id"):
                signature_patch_hits.add(signature)

        patcher_id = event.get("patcher_id")
        if event.get("patch_applied") and patcher_id and event.get("parent_artifact_hash"):
            patch_attempts[patcher_id] += 1
            if event.get("passed"):
                patch_success[patcher_id] += 1

    solved_via_patcher = 0
    solved_via_new_attempt = 0
    unsolved_runs = 0
    estimated_attempts_saved_by_patchers = 0
    for run_id in sorted(run_events):
        events = sorted(
            run_events[run_id],
            key=lambda event: (int(event.get("attempt_index", 0)), str(event.get("timestamp_utc", ""))),
        )
        solved_event = next((event for event in events if event.get("passed")), None)
        if solved_event is None:
            unsolved_runs += 1
            continue

        if solved_event.get("patch_applied") and solved_event.get("parent_artifact_hash"):
            solved_via_patcher += 1
            estimated_attempts_saved_by_patchers += 1
        else:
            solved_via_new_attempt += 1

    all_signatures = set(signature_total.keys())
    covered_signatures = all_signatures & signature_patch_hits
    uncovered_signatures = all_signatures - covered_signatures
    signature_coverage = (len(covered_signatures) / len(all_signatures) * 100.0) if all_signatures else 0.0

    print(f"records={len(records)}")
    print(f"runs={len(runs)}")
    print("pass_rate_by_language:")
    for language, outcomes in sorted(language_runs.items()):
        total = len(outcomes)
        passed = sum(1 for outcome in outcomes if outcome)
        rate = (passed / total) * 100.0 if total else 0.0
        print(f"  language={language} pass_rate={rate:.2f}% ({passed}/{total})")

    print("pass_rate_by_task:")
    for (task_id, task_hash), outcomes in sorted(task_runs.items(), key=lambda item: item[0][0] or ""):
        total = len(outcomes)
        passed = sum(1 for outcome in outcomes if outcome)
        rate = (passed / total) * 100.0 if total else 0.0
        print(f"  task_id={task_id} task_hash={task_hash} pass_rate={rate:.2f}% ({passed}/{total})")

    print("attempt_distribution:")
    for attempts, count in sorted(attempt_distribution.items()):
        print(f"  attempts={attempts} runs={count}")

    print("median_attempts_per_task:")
    for (task_id, task_hash), attempts in sorted(attempts_by_task.items(), key=lambda item: item[0][0] or ""):
        print(f"  task_id={task_id} task_hash={task_hash} median_attempts={median(attempts):.2f}")

    print("failure_type_breakdown:")
    if failure_breakdown:
        for failure_type, count in failure_breakdown.most_common():
            print(f"  {failure_type}={count}")
    else:
        print("  none")

    print("verifier_stage_breakdown:")
    if stage_breakdown:
        for stage, count in stage_breakdown.most_common():
            print(f"  {stage}={count}")
    else:
        print("  none")

    print("top20_error_signature:")
    if signature_counts:
        for signature, count in signature_counts.most_common(20):
            print(f"  {count:>5}  {signature}")
    else:
        print("  none")

    print(f"signature_coverage={signature_coverage:.2f}% ({len(covered_signatures)}/{len(all_signatures)})")
    print("top_uncovered_signatures:")
    if uncovered_signatures:
        for signature in sorted(uncovered_signatures, key=lambda sign: (-signature_total[sign], sign))[:20]:
            print(f"  {signature_total[signature]:>5}  {signature}")
    else:
        print("  none")

    print("patch_success_rate_by_patcher:")
    if patch_attempts:
        for patcher_id, attempts in patch_attempts.most_common():
            success = patch_success.get(patcher_id, 0)
            rate = (success / attempts) * 100.0 if attempts else 0.0
            print(f"  patcher_id={patcher_id} success_rate={rate:.2f}% ({success}/{attempts})")
    else:
        print("  none")

    solved_total = solved_via_patcher + solved_via_new_attempt
    solved_patch_rate = (solved_via_patcher / solved_total) * 100.0 if solved_total else 0.0
    solved_attempt_rate = (solved_via_new_attempt / solved_total) * 100.0 if solved_total else 0.0
    print(
        "solved_mode_split:"
        f" via_patchers={solved_via_patcher} ({solved_patch_rate:.2f}%)"
        f" via_new_attempt={solved_via_new_attempt} ({solved_attempt_rate:.2f}%)"
        f" unsolved={unsolved_runs}"
    )
    print(f"attempts_saved_by_patchers_approx={estimated_attempts_saved_by_patchers}")


def main() -> int:
    args = parse_args()
    records = load_records(args.log_file)
    print_stats(records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
