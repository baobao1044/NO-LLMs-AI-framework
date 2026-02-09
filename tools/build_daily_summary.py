#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build daily summary JSON from before/after metrics.")
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _delta(before: float, after: float) -> float:
    return round(after - before, 6)


def main() -> int:
    args = parse_args()
    before = _load(args.before)
    after = _load(args.after)

    pass_before = before.get("pass_rate_by_language", {})
    pass_after = after.get("pass_rate_by_language", {})
    pass_rate_by_language = {
        language: {
            "before": float(pass_before.get(language, 0.0)),
            "after": float(pass_after.get(language, 0.0)),
            "delta": _delta(float(pass_before.get(language, 0.0)), float(pass_after.get(language, 0.0))),
        }
        for language in sorted(set(pass_before) | set(pass_after))
    }

    cov_before = float(before.get("signature_coverage", 0.0))
    cov_after = float(after.get("signature_coverage", 0.0))

    patcher_before = before.get("patcher_success_rate_by_id", {})
    patcher_after = after.get("patcher_success_rate_by_id", {})
    patcher_success_delta = {
        patcher: {
            "before": float(patcher_before.get(patcher, 0.0)),
            "after": float(patcher_after.get(patcher, 0.0)),
            "delta": _delta(float(patcher_before.get(patcher, 0.0)), float(patcher_after.get(patcher, 0.0))),
        }
        for patcher in sorted(set(patcher_before) | set(patcher_after))
    }

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "before_source": str(args.before),
        "after_source": str(args.after),
        "pass_rate_by_language": pass_rate_by_language,
        "signature_coverage": {
            "before": cov_before,
            "after": cov_after,
            "delta": _delta(cov_before, cov_after),
        },
        "top_uncovered": {
            "before": before.get("top_uncovered_signatures", []),
            "after": after.get("top_uncovered_signatures", []),
        },
        "patcher_success_delta": patcher_success_delta,
        "timeout_rate": {
            "before": float(before.get("timeout_rate", 0.0)),
            "after": float(after.get("timeout_rate", 0.0)),
            "delta": _delta(float(before.get("timeout_rate", 0.0)), float(after.get("timeout_rate", 0.0))),
        },
        "flaky_groups_count": {
            "before": int(before.get("flaky_groups_count", 0)),
            "after": int(after.get("flaky_groups_count", 0)),
            "delta": int(after.get("flaky_groups_count", 0)) - int(before.get("flaky_groups_count", 0)),
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"daily_summary_out={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
