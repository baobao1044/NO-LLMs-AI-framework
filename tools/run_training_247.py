#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATUS_FILE = ROOT / "reports" / "training_247_status.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run continuous 24/7 training cycles with deterministic AB runs.")
    parser.add_argument("--config", type=Path, default=Path("configs/daily_training_full.json"))
    parser.add_argument("--policy-b", type=Path, default=Path("configs/proposer_policy_training_full.json"))
    parser.add_argument("--sleep-seconds", type=int, default=900)
    parser.add_argument("--ci-every", type=int, default=4, help="Run make ci every N successful cycles.")
    parser.add_argument("--max-consecutive-failures", type=int, default=3)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--skip-refresh", action="store_true")
    parser.add_argument("--skip-ci", action="store_true")
    return parser.parse_args()


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(cmd: list[str]) -> int:
    print(f"run={' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=ROOT, check=False)
    print(f"exit_code={proc.returncode}")
    return proc.returncode


def _cycle_id() -> str:
    # Numeric key keeps compatibility with seed derivation in run_daily.
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _write_status(payload: dict[str, Any]) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    pid = os.getpid()
    consecutive_failures = 0
    successful_cycles = 0
    total_cycles = 0

    while True:
        cycle_key = _cycle_id()
        total_cycles += 1
        started = time.time()

        cycle = {
            "cycle_key": cycle_key,
            "started_utc": _now_utc(),
            "config": str(args.config),
            "policy_b": str(args.policy_b),
            "steps": [],
        }

        steps: list[tuple[str, list[str]]] = [
            (
                "daily_ab",
                [
                    "python3",
                    "tools/run_daily.py",
                    "--config",
                    str(args.config),
                    "--date",
                    cycle_key,
                    "--ab",
                    "--proposer-policy-b",
                    str(args.policy_b),
                ],
            ),
            ("merge_logs", ["make", "merge-logs"]),
            ("dedup_report", ["make", "dedup-report"]),
        ]

        if not args.skip_refresh:
            steps.append(("refresh", ["make", "refresh"]))
        if not args.skip_ci and args.ci_every > 0 and ((successful_cycles + 1) % args.ci_every == 0):
            steps.append(("ci", ["make", "ci"]))

        cycle_ok = True
        for step_name, cmd in steps:
            _write_status(
                {
                    "updated_utc": _now_utc(),
                    "pid": pid,
                    "running": True,
                    "state": "running",
                    "current_step": step_name,
                    "total_cycles": total_cycles,
                    "successful_cycles": successful_cycles,
                    "consecutive_failures": consecutive_failures,
                    "sleep_seconds": args.sleep_seconds,
                    "ci_every": args.ci_every,
                    "max_consecutive_failures": args.max_consecutive_failures,
                    "last_cycle": cycle,
                }
            )
            code = _run(cmd)
            cycle["steps"].append({"name": step_name, "cmd": cmd, "exit_code": code})
            if code != 0:
                cycle_ok = False
                break

        elapsed = round(time.time() - started, 3)
        if cycle_ok:
            successful_cycles += 1
            consecutive_failures = 0
        else:
            consecutive_failures += 1

        status = {
            "updated_utc": _now_utc(),
            "pid": pid,
            "running": not args.once,
            "state": "completed" if args.once else ("sleeping" if cycle_ok else "failed"),
            "current_step": None,
            "total_cycles": total_cycles,
            "successful_cycles": successful_cycles,
            "consecutive_failures": consecutive_failures,
            "last_cycle_ok": cycle_ok,
            "last_cycle_elapsed_seconds": elapsed,
            "last_cycle": cycle,
            "sleep_seconds": args.sleep_seconds,
            "ci_every": args.ci_every,
            "max_consecutive_failures": args.max_consecutive_failures,
        }
        _write_status(status)

        if not cycle_ok and consecutive_failures >= args.max_consecutive_failures:
            print("status=STOP max consecutive failures reached")
            return 1

        if args.once:
            print(f"status={'PASS' if cycle_ok else 'FAIL'}")
            return 0 if cycle_ok else 1

        sleep_for = max(1, int(args.sleep_seconds))
        print(f"sleep_seconds={sleep_for}")
        _write_status(
            {
                **status,
                "updated_utc": _now_utc(),
                "running": True,
                "state": "sleeping",
                "next_cycle_in_seconds": sleep_for,
            }
        )
        time.sleep(sleep_for)


if __name__ == "__main__":
    raise SystemExit(main())
