#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge run logs with deterministic dedup.")
    parser.add_argument("inputs", nargs="+", help="Run pack folders, log files, or glob patterns.")
    parser.add_argument("--out", type=Path, default=Path("logs/merged.jsonl"))
    parser.add_argument("--prefer-pass", action="store_true", default=True)
    return parser.parse_args()


def _expand_inputs(inputs: list[str]) -> list[Path]:
    out: list[Path] = []
    for item in inputs:
        paths = [Path(p) for p in glob.glob(item)] if any(ch in item for ch in "*?[]") else [Path(item)]
        for path in paths:
            if path.is_dir():
                candidate = path / "agent_runs.jsonl"
                if candidate.exists():
                    out.append(candidate)
            elif path.is_file():
                out.append(path)
    unique = sorted({str(path.resolve()) for path in out})
    return [Path(path) for path in unique]


def _dedup_key(record: dict[str, Any]) -> tuple[str, str, int, str, str]:
    return (
        str(record.get("task_hash") or ""),
        str(record.get("artifact_hash") or ""),
        int(record.get("attempt_index") or 0),
        str(record.get("verifier_stage_failed") or ""),
        str(record.get("error_signature") or ""),
    )


def _event_sort_key(record: dict[str, Any]) -> tuple[str, str, int, str]:
    return (
        str(record.get("timestamp_utc") or ""),
        str(record.get("run_id") or ""),
        int(record.get("attempt_index") or 0),
        str(record.get("artifact_hash") or ""),
    )


def merge_records(paths: list[Path], prefer_pass: bool = True) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    all_records: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                all_records.append(json.loads(line))

    unique_map: dict[tuple[str, str, int, str, str], dict[str, Any]] = {}
    dup_count = 0
    for record in sorted(all_records, key=_event_sort_key):
        key = _dedup_key(record)
        current = unique_map.get(key)
        if current is None:
            unique_map[key] = record
            continue

        dup_count += 1
        if prefer_pass and (not bool(current.get("passed")) and bool(record.get("passed"))):
            unique_map[key] = record

    merged = sorted(unique_map.values(), key=_event_sort_key)
    summary = {
        "inputs": [str(path) for path in paths],
        "total_records": len(all_records),
        "unique_records": len(merged),
        "duplicate_records": dup_count,
        "duplicate_ratio": round((dup_count / len(all_records)) if all_records else 0.0, 6),
    }
    return merged, summary


def main() -> int:
    args = parse_args()
    paths = _expand_inputs(args.inputs)
    merged, summary = merge_records(paths=paths, prefer_pass=args.prefer_pass)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for record in merged:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    print(f"merged_out={args.out}")
    print(f"total_records={summary['total_records']}")
    print(f"unique_records={summary['unique_records']}")
    print(f"duplicate_records={summary['duplicate_records']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
