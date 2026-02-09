#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report duplicates in a JSONL log by deterministic key.")
    parser.add_argument("log_file", type=Path)
    parser.add_argument("--json-out", type=Path, default=None)
    return parser.parse_args()


def _dedup_key(record: dict[str, Any]) -> tuple[str, str, int, str, str]:
    return (
        str(record.get("task_hash") or ""),
        str(record.get("artifact_hash") or ""),
        int(record.get("attempt_index") or 0),
        str(record.get("verifier_stage_failed") or ""),
        str(record.get("error_signature") or ""),
    )


def main() -> int:
    args = parse_args()
    counts: Counter[tuple[str, str, int, str, str]] = Counter()
    total = 0
    with args.log_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            total += 1
            counts[_dedup_key(json.loads(line))] += 1

    duplicate_keys = {key: count for key, count in counts.items() if count > 1}
    duplicate_records = sum(count - 1 for count in duplicate_keys.values())
    payload = {
        "source_log": str(args.log_file),
        "total_records": total,
        "unique_records": len(counts),
        "duplicate_records": duplicate_records,
        "duplicate_ratio": round((duplicate_records / total) if total else 0.0, 6),
        "top_duplicate_keys": [
            {
                "task_hash": key[0],
                "artifact_hash": key[1],
                "attempt_index": key[2],
                "verifier_stage_failed": key[3],
                "error_signature": key[4],
                "count": count,
            }
            for key, count in sorted(duplicate_keys.items(), key=lambda item: (-item[1], item[0]))[:20]
        ],
    }

    print(f"total_records={payload['total_records']}")
    print(f"unique_records={payload['unique_records']}")
    print(f"duplicate_records={payload['duplicate_records']}")
    print(f"duplicate_ratio={payload['duplicate_ratio']:.6f}")

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        print(f"json_out={args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
