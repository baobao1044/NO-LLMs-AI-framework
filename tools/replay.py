#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.verifier import CompositeVerifier, FunctionVerifier, TsCompositeVerifier
from core.env_fingerprint import get_env_fingerprint


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay event logs and verify determinism.")
    parser.add_argument("log_file", type=Path, help="Path to JSONL event log.")
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional JSON output path for replay metrics.",
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


def _event_language(event: dict[str, Any]) -> str:
    language = event.get("language")
    if isinstance(language, str) and language:
        return language
    verifier_name = str(event.get("verifier_name") or "")
    if verifier_name.startswith("ts_"):
        return "ts"
    return "py"


def build_verifier(event: dict[str, Any]) -> object:
    payload = event["task_payload"]
    verifier_name = event.get("verifier_name")
    config = event.get("verifier_config") or {}
    language = _event_language(event)

    if language == "ts" or verifier_name == "ts_composite":
        timeout_seconds = float(config.get("timeout_seconds", 2.0))
        tsc_timeout_seconds = float(config.get("tsc_timeout_seconds", 20.0))
        return TsCompositeVerifier.from_task_payload(
            payload=payload,
            timeout_seconds=timeout_seconds,
            tsc_timeout_seconds=tsc_timeout_seconds,
        )

    if verifier_name == "composite_verifier":
        timeout_seconds = float(config.get("timeout_seconds", 1.0))
        return CompositeVerifier.from_task_payload(
            payload=payload,
            timeout_seconds=timeout_seconds,
        )

    return FunctionVerifier.from_task_payload(
        payload=payload,
        verifier_name=event.get("verifier_name", "function_verifier"),
        verifier_version=event.get("verifier_version", "unknown"),
    )


def _replay_target_file(base_dir: Path, index: int, event: dict[str, Any]) -> Path:
    language = _event_language(event)
    run_dir = base_dir / f"event_{index}"
    if language == "ts":
        return run_dir / "src" / "solution.ts"
    return run_dir / "replay_candidate.py"


def replay_records(records: list[dict]) -> tuple[int, dict[str, Any]]:
    if not records:
        metrics = {
            "records": 0,
            "replay_eligible": 0,
            "replay_match": 0,
            "replay_match_rate": 100.0,
            "unreplayable_lossy": 0,
            "timeout_rate": 0.0,
            "top_error_signature": [],
            "flaky_keys": [],
            "flaky_groups": [],
            "mismatch_samples": [],
        }
        return 0, metrics

    total = 0
    eligible = 0
    matched = 0
    unreplayable_lossy = 0
    timeout_count = 0
    mismatches: list[dict] = []
    signature_counts: Counter[str] = Counter()
    replay_outcomes = defaultdict(set)
    group_outcomes = defaultdict(set)
    current_env_fingerprint = get_env_fingerprint()
    env_fingerprint_mismatch_count = 0

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        for index, event in enumerate(records, start=1):
            total += 1
            logged_fingerprint = event.get("env_fingerprint")
            if isinstance(logged_fingerprint, dict) and logged_fingerprint != current_env_fingerprint:
                env_fingerprint_mismatch_count += 1
            if not event.get("passed"):
                signature = event.get("error_signature") or "UNKNOWN"
                signature_counts[signature] += 1

            task_payload = event.get("task_payload")
            code = event.get("code")
            if event.get("payload_is_lossy") is True:
                unreplayable_lossy += 1
                continue
            if not isinstance(task_payload, dict) or not isinstance(code, str):
                mismatches.append(
                    {
                        "index": index,
                        "run_id": event.get("run_id"),
                        "task_id": event.get("task_id"),
                        "logged_passed": bool(event.get("passed")),
                        "replayed_passed": False,
                    }
                )
                continue

            eligible += 1
            replay_file = _replay_target_file(tmp_root, index=index, event=event)
            replay_file.parent.mkdir(parents=True, exist_ok=True)
            replay_file.write_text(code, encoding="utf-8")

            verifier = build_verifier(event)
            replay_result = verifier.verify(replay_file)

            if replay_result.error_type == "TimeoutError" or replay_result.verifier_stage_failed == "timeout":
                timeout_count += 1

            if replay_result.passed == bool(event["passed"]):
                matched += 1
            else:
                mismatches.append(
                    {
                        "index": index,
                        "run_id": event.get("run_id"),
                        "task_id": event.get("task_id"),
                        "logged_passed": bool(event["passed"]),
                        "replayed_passed": replay_result.passed,
                    }
                )

            replay_key = (
                str(event.get("language") or _event_language(event)),
                str(event.get("task_hash")),
                str(event.get("artifact_hash")),
                str(event.get("verifier_name")),
                str(event.get("verifier_version")),
            )
            replay_outcomes[replay_key].add(replay_result.passed)

            group_key = (
                str(event.get("language") or _event_language(event)),
                str(event.get("failure_type")),
                str(event.get("error_signature")),
                str(event.get("verifier_stage_failed")),
            )
            group_outcomes[group_key].add(replay_result.passed)

    pct = 100.0 if eligible == 0 else (matched / eligible) * 100.0
    timeout_rate = 0.0 if eligible == 0 else (timeout_count / eligible) * 100.0
    flaky_keys = [key for key, outcomes in replay_outcomes.items() if len(outcomes) > 1]
    flaky_groups = [key for key, outcomes in group_outcomes.items() if len(outcomes) > 1]
    flaky_groups_sorted = sorted(flaky_groups, key=lambda item: (item[0], item[1], item[2], item[3]))

    metrics = {
        "records": total,
        "replay_eligible": eligible,
        "replay_match": matched,
        "replay_match_rate": round(pct, 4),
        "unreplayable_lossy": unreplayable_lossy,
        "timeout_rate": round(timeout_rate, 4),
        "top_error_signature": [
            {"error_signature": signature, "count": count}
            for signature, count in signature_counts.most_common(20)
        ],
        "flaky_keys": [list(item) for item in sorted(flaky_keys)],
        "flaky_groups": [
            {
                "language": item[0],
                "failure_type": item[1],
                "error_signature": item[2],
                "verifier_stage_failed": item[3],
            }
            for item in flaky_groups_sorted
        ],
        "mismatch_samples": mismatches[:20],
        "env_fingerprint_current": current_env_fingerprint,
        "env_fingerprint_mismatch_count": env_fingerprint_mismatch_count,
    }
    return (1 if mismatches else 0), metrics


def print_metrics(metrics: dict[str, Any]) -> None:
    print(f"records={metrics['records']}")
    print(f"replay_eligible={metrics['replay_eligible']}")
    print(
        "replay_match="
        f"{metrics['replay_match']}/{metrics['replay_eligible']} ({metrics['replay_match_rate']:.2f}%)"
    )
    print(f"unreplayable_lossy={metrics['unreplayable_lossy']}")
    print(f"timeout_rate={metrics['timeout_rate']:.2f}%")
    print(f"env_fingerprint_mismatch_count={metrics.get('env_fingerprint_mismatch_count', 0)}")
    if metrics.get("env_fingerprint_mismatch_count", 0) > 0:
        print("warning=env_fingerprint_mismatch_detected")

    top_signatures = metrics.get("top_error_signature", [])
    if top_signatures:
        print("top_error_signature:")
        for item in top_signatures:
            print(f"  {item['count']:>5}  {item['error_signature']}")
    else:
        print("top_error_signature=none")

    if metrics.get("flaky_keys"):
        print("flaky_keys:")
        for key in metrics["flaky_keys"]:
            print(
                f"  language={key[0]} task_hash={key[1]} artifact_hash={key[2]} verifier={key[3]}@{key[4]}"
            )
    else:
        print("flaky_keys=none")

    if metrics.get("flaky_groups"):
        print("flaky_groups:")
        for item in metrics["flaky_groups"]:
            print(
                "  "
                f"{item['language']} | {item['failure_type']} | "
                f"{item['verifier_stage_failed']} | {item['error_signature']}"
            )
    else:
        print("flaky_groups=none")

    if metrics.get("mismatch_samples"):
        print("mismatch_samples:")
        for item in metrics["mismatch_samples"]:
            print(
                "  "
                f"index={item['index']} run_id={item['run_id']} task_id={item['task_id']} "
                f"logged_passed={item['logged_passed']} replayed_passed={item['replayed_passed']}"
            )


def main() -> int:
    args = parse_args()
    records = load_records(args.log_file)
    code, metrics = replay_records(records)
    print_metrics(metrics)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(metrics, ensure_ascii=True, indent=2), encoding="utf-8")
        print(f"json_out={args.json_out}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
