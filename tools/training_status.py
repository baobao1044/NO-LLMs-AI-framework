#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATUS = ROOT / "reports" / "training_247_status.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show concise 24/7 training status.")
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS)
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    status = _load_json(args.status_file)
    if status is None:
        print(f"status_file_missing={args.status_file}")
        return 1

    total = int(status.get("total_cycles") or 0)
    ok = int(status.get("successful_cycles") or 0)
    ok_rate = (ok / total) if total else 0.0
    last_cycle = status.get("last_cycle") if isinstance(status.get("last_cycle"), dict) else {}
    cycle_key = str(last_cycle.get("cycle_key") or "")
    reports_dir = ROOT / "reports" / cycle_key if cycle_key else None
    ab_compare = reports_dir / "ab_compare.json" if reports_dir else None

    print(f"updated_utc={status.get('updated_utc')}")
    print(f"pid={status.get('pid')}")
    print(f"running={status.get('running')}")
    print(f"state={status.get('state')}")
    print(f"current_step={status.get('current_step')}")
    print(f"total_cycles={total}")
    print(f"successful_cycles={ok}")
    print(f"success_rate={ok_rate:.4f}")
    print(f"consecutive_failures={status.get('consecutive_failures')}")
    print(f"last_cycle_key={cycle_key}")
    print(f"last_cycle_ok={status.get('last_cycle_ok')}")
    print(f"last_cycle_elapsed_seconds={status.get('last_cycle_elapsed_seconds')}")
    print(f"sleep_seconds={status.get('sleep_seconds')}")
    if status.get("next_cycle_in_seconds") is not None:
        print(f"next_cycle_in_seconds={status.get('next_cycle_in_seconds')}")
    if ab_compare and ab_compare.exists():
        payload = _load_json(ab_compare) or {}
        solve_delta = (
            payload.get("solve_rate", {}).get("delta")
            if isinstance(payload.get("solve_rate"), dict)
            else payload.get("solve_rate_delta")
        )
        print(f"latest_ab_compare={ab_compare}")
        print(f"latest_solve_rate_delta={solve_delta}")
        print(f"latest_proposer_calls={payload.get('cost', {}).get('proposer_calls') if isinstance(payload.get('cost'), dict) else None}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
