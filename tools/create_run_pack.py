#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create date-scoped run pack layout.")
    parser.add_argument("--date", type=str, default=None, help="UTC date in YYYYMMDD (default: today UTC).")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--task-config", type=str, default="")
    parser.add_argument("--policy", type=str, default="")
    parser.add_argument("--budget", type=str, default="")
    parser.add_argument("--metadata-out", type=Path, default=None)
    return parser.parse_args()


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def create_run_pack(
    date_yyyymmdd: str,
    metadata: dict[str, Any] | None = None,
    reset_log: bool = True,
) -> dict[str, Path]:
    run_dir = Path("runs") / date_yyyymmdd
    report_dir = Path("reports") / date_yyyymmdd
    run_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    log_file = run_dir / "agent_runs.jsonl"
    metadata_file = run_dir / "metadata.json"
    if metadata is None:
        metadata = {}
    metadata_payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "date": date_yyyymmdd,
        **metadata,
    }
    metadata_file.write_text(json.dumps(metadata_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    if reset_log:
        log_file.write_text("", encoding="utf-8")
    elif not log_file.exists():
        log_file.write_text("", encoding="utf-8")

    return {
        "run_dir": run_dir,
        "report_dir": report_dir,
        "log_file": log_file,
        "metadata_file": metadata_file,
    }


def main() -> int:
    args = parse_args()
    day = args.date or _today_utc()
    metadata: dict[str, Any] = {
        "seed": args.seed,
        "task_config": args.task_config,
        "policy": args.policy,
        "budget": args.budget,
    }
    paths = create_run_pack(day, metadata=metadata)
    if args.metadata_out is not None:
        args.metadata_out.parent.mkdir(parents=True, exist_ok=True)
        args.metadata_out.write_text(paths["metadata_file"].read_text(encoding="utf-8"), encoding="utf-8")

    print(f"run_dir={paths['run_dir']}")
    print(f"report_dir={paths['report_dir']}")
    print(f"log_file={paths['log_file']}")
    print(f"metadata_file={paths['metadata_file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
