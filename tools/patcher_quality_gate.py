#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gate patcher quality using before/after metrics.")
    parser.add_argument("--before", type=Path, required=True, help="Before metrics JSON.")
    parser.add_argument("--after", type=Path, required=True, help="After metrics JSON.")
    parser.add_argument("--max_pass_rate_drop", type=float, default=0.01)
    parser.add_argument("--max_timeout_increase", type=float, default=0.01)
    parser.add_argument("--max_flaky_increase", type=int, default=0)
    parser.add_argument("--min_coverage_gain", type=float, default=0.0)
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _suspected_patchers(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    before_activity: dict[str, int] = before.get("patcher_activity_by_id", {})
    after_activity: dict[str, int] = after.get("patcher_activity_by_id", {})
    before_success: dict[str, float] = before.get("patcher_success_rate_by_id", {})
    after_success: dict[str, float] = after.get("patcher_success_rate_by_id", {})

    suspects: list[str] = []
    for patcher_id in sorted(after_activity):
        delta_activity = int(after_activity.get(patcher_id, 0)) - int(before_activity.get(patcher_id, 0))
        if delta_activity <= 0:
            continue
        before_rate = float(before_success.get(patcher_id, 0.0))
        after_rate = float(after_success.get(patcher_id, 0.0))
        if patcher_id not in before_activity or after_rate < before_rate:
            suspects.append(patcher_id)
    return suspects


def evaluate(before: dict[str, Any], after: dict[str, Any], args: argparse.Namespace) -> tuple[bool, list[str], list[str]]:
    failures: list[str] = []

    before_pass = float(before.get("overall_pass_rate", 0.0))
    after_pass = float(after.get("overall_pass_rate", 0.0))
    if before_pass - after_pass > float(args.max_pass_rate_drop):
        failures.append(
            "overall_pass_rate regression: "
            f"before={before_pass:.6f} after={after_pass:.6f} allowed_drop={float(args.max_pass_rate_drop):.6f}"
        )

    before_timeout = float(before.get("timeout_rate", 0.0))
    after_timeout = float(after.get("timeout_rate", 0.0))
    if after_timeout - before_timeout > float(args.max_timeout_increase):
        failures.append(
            "timeout_rate regression: "
            f"before={before_timeout:.6f} after={after_timeout:.6f} allowed_increase={float(args.max_timeout_increase):.6f}"
        )

    before_flaky = int(before.get("flaky_groups_count", 0))
    after_flaky = int(after.get("flaky_groups_count", 0))
    if after_flaky - before_flaky > int(args.max_flaky_increase):
        failures.append(
            "flaky_groups regression: "
            f"before={before_flaky} after={after_flaky} allowed_increase={int(args.max_flaky_increase)}"
        )

    before_cov = float(before.get("signature_coverage", 0.0))
    after_cov = float(after.get("signature_coverage", 0.0))
    if after_cov - before_cov < float(args.min_coverage_gain):
        failures.append(
            "signature_coverage regression: "
            f"before={before_cov:.6f} after={after_cov:.6f} required_gain={float(args.min_coverage_gain):.6f}"
        )

    suspects = _suspected_patchers(before=before, after=after)
    return (len(failures) == 0), failures, suspects


def main() -> int:
    args = parse_args()
    before = _load(args.before)
    after = _load(args.after)
    ok, failures, suspects = evaluate(before=before, after=after, args=args)

    if ok:
        print("quality_gate=PASS")
        print("reasons=none")
        return 0

    print("quality_gate=FAIL")
    for reason in failures:
        print(reason)

    if suspects:
        print("suspected_patchers=" + ",".join(suspects))
    else:
        print("suspected_patchers=none")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
