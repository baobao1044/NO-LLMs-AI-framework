#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build flaky quarantine config from replay metrics.")
    parser.add_argument("--replay-metrics", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("configs/flaky_quarantine.json"))
    return parser.parse_args()


def _normalize_item(item: dict[str, Any]) -> dict[str, str]:
    return {
        "language": str(item.get("language") or "py"),
        "failure_type": str(item.get("failure_type") or ""),
        "error_signature": str(item.get("error_signature") or ""),
        "verifier_stage_failed": str(item.get("verifier_stage_failed") or ""),
    }


def main() -> int:
    args = parse_args()
    payload = json.loads(args.replay_metrics.read_text(encoding="utf-8"))
    raw = payload.get("flaky_groups") or []
    normalized = sorted(
        {
            (
                str(item.get("language") or "py"),
                str(item.get("failure_type") or ""),
                str(item.get("error_signature") or ""),
                str(item.get("verifier_stage_failed") or ""),
            )
            for item in raw
        }
    )

    out_payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_replay_metrics": str(args.replay_metrics),
        "flaky_groups_count": len(normalized),
        "flaky_groups": [
            {
                "language": item[0],
                "failure_type": item[1],
                "error_signature": item[2],
                "verifier_stage_failed": item[3],
            }
            for item in normalized
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out_payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"quarantine_out={args.out}")
    print(f"flaky_groups_count={len(normalized)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
