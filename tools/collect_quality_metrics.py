#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect quality metrics from agent event log.")
    parser.add_argument("--log", type=Path, required=True, help="Path to JSONL event log.")
    parser.add_argument("--out", type=Path, required=True, help="Output metrics JSON path.")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Write zero metrics when log file is missing.",
    )
    return parser.parse_args()


def _event_language(record: dict[str, Any]) -> str:
    language = record.get("language")
    if isinstance(language, str) and language:
        return language
    verifier_name = str(record.get("verifier_name") or "")
    if verifier_name.startswith("ts_"):
        return "ts"
    return "py"


def _zero_metrics(source_log: Path) -> dict[str, Any]:
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_log": str(source_log),
        "records": 0,
        "runs": 0,
        "overall_pass_rate": 0.0,
        "pass_rate_by_language": {},
        "timeout_rate": 0.0,
        "flaky_groups_count": 0,
        "signature_coverage": 0.0,
        "signature_coverage_by_language": {},
        "top_uncovered_signatures": [],
        "patcher_activity_by_id": {},
        "patcher_success_rate_by_id": {},
    }


def load_records(path: Path, allow_missing: bool) -> list[dict[str, Any]]:
    if not path.exists():
        if allow_missing:
            return []
        raise FileNotFoundError(f"log file not found: {path}")

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def build_metrics(records: list[dict[str, Any]], source_log: Path) -> dict[str, Any]:
    if not records:
        return _zero_metrics(source_log=source_log)

    run_state: dict[str, dict[str, Any]] = {}
    run_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_fail_signatures: Counter[tuple[str, str]] = Counter()
    covered_signatures: set[tuple[str, str]] = set()
    signatures_by_lang: dict[str, set[str]] = defaultdict(set)
    covered_by_lang: dict[str, set[str]] = defaultdict(set)

    timeout_failures = 0
    flaky_groups: dict[tuple[str, str, str, str], set[bool]] = defaultdict(set)

    patch_attempts: Counter[str] = Counter()
    patch_successes: Counter[str] = Counter()

    for index, event in enumerate(records, start=1):
        run_id = str(event.get("run_id") or f"legacy_run_{index}")
        language = _event_language(event)
        run_events[run_id].append(event)

        state = run_state.setdefault(run_id, {"language": language, "passed": False})
        state["language"] = language
        state["passed"] = state["passed"] or bool(event.get("passed"))

        failure_type = event.get("failure_type")
        error_signature = event.get("error_signature")
        stage = str(event.get("verifier_stage_failed") or "UNKNOWN")
        if failure_type and error_signature:
            key = (language, str(error_signature))
            all_fail_signatures[key] += 1
            signatures_by_lang[language].add(str(error_signature))
            if event.get("patcher_id") is not None:
                covered_signatures.add(key)
                covered_by_lang[language].add(str(error_signature))

            group_key = (language, str(failure_type), str(error_signature), stage)
            flaky_groups[group_key].add(bool(event.get("passed")))

        if event.get("error_type") == "TimeoutError" or event.get("verifier_stage_failed") == "timeout":
            timeout_failures += 1

        patcher_id = event.get("patcher_id")
        if event.get("patch_applied") and patcher_id and event.get("parent_artifact_hash"):
            patch_attempts[str(patcher_id)] += 1
            if event.get("passed"):
                patch_successes[str(patcher_id)] += 1

    run_count = len(run_state)
    pass_count = sum(1 for state in run_state.values() if state["passed"])
    overall_pass_rate = (pass_count / run_count) if run_count else 0.0

    pass_rate_by_language: dict[str, float] = {}
    by_lang: dict[str, list[bool]] = defaultdict(list)
    for state in run_state.values():
        by_lang[state["language"]].append(state["passed"])
    for language, rows in sorted(by_lang.items()):
        pass_rate_by_language[language] = sum(1 for value in rows if value) / len(rows)

    signature_total = len(all_fail_signatures)
    signature_coverage = (len(covered_signatures) / signature_total) if signature_total else 0.0
    signature_coverage_by_language: dict[str, float] = {}
    for language, signatures in sorted(signatures_by_lang.items()):
        total = len(signatures)
        covered = len(covered_by_lang.get(language, set()))
        signature_coverage_by_language[language] = (covered / total) if total else 0.0

    uncovered_candidates = [
        {
            "language": language,
            "error_signature": signature,
            "count": count,
        }
        for (language, signature), count in all_fail_signatures.items()
        if (language, signature) not in covered_signatures
    ]
    uncovered_candidates.sort(key=lambda row: (-row["count"], row["language"], row["error_signature"]))

    patcher_success_rate_by_id: dict[str, float] = {}
    for patcher_id, attempts in sorted(patch_attempts.items()):
        patcher_success_rate_by_id[patcher_id] = patch_successes.get(patcher_id, 0) / attempts

    flaky_groups_count = sum(1 for outcomes in flaky_groups.values() if len(outcomes) > 1)

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_log": str(source_log),
        "records": len(records),
        "runs": run_count,
        "overall_pass_rate": round(overall_pass_rate, 6),
        "pass_rate_by_language": {k: round(v, 6) for k, v in pass_rate_by_language.items()},
        "timeout_rate": round(timeout_failures / len(records), 6) if records else 0.0,
        "flaky_groups_count": flaky_groups_count,
        "signature_coverage": round(signature_coverage, 6),
        "signature_coverage_by_language": {
            k: round(v, 6) for k, v in signature_coverage_by_language.items()
        },
        "top_uncovered_signatures": uncovered_candidates[:20],
        "patcher_activity_by_id": dict(sorted(patch_attempts.items())),
        "patcher_success_rate_by_id": patcher_success_rate_by_id,
    }


def main() -> int:
    args = parse_args()
    records = load_records(args.log, allow_missing=args.allow_missing)
    metrics = build_metrics(records=records, source_log=args.log)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(metrics, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"metrics_out={args.out}")
    print(f"records={metrics['records']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
