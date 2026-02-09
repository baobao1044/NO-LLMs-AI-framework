#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select top backlog items using policy.")
    parser.add_argument("--backlog", type=Path, required=True, help="Path to backlog JSON.")
    parser.add_argument("--policy", type=Path, required=True, help="Path to backlog policy JSON.")
    parser.add_argument("--out", type=Path, required=True, help="Output selected backlog JSON.")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any) -> float:
    return float(value or 0.0)


def _safe_int(value: Any) -> int:
    return int(value or 0)


def _lang_rank(language: str, priority: list[str]) -> int:
    try:
        return priority.index(language)
    except ValueError:
        return len(priority)


def _stage_rank(stage: str, priority: list[str]) -> int:
    try:
        return priority.index(stage)
    except ValueError:
        return len(priority)


def _strategy_score(item: dict[str, Any], strategy: str) -> float:
    count_total = _safe_int(item.get("count_total"))
    solve_rate = _safe_float(item.get("solve_rate"))
    patch_hit_rate = _safe_float(item.get("patch_hit_rate"))
    patch_success_rate = _safe_float(item.get("patch_success_rate"))

    if strategy == "max_impact":
        return float(item.get("priority_score") or 0.0)

    if strategy == "max_leverage":
        leverage = count_total * (1.0 - solve_rate) * (1.0 + (1.0 - patch_hit_rate))
        if patch_hit_rate > 0:
            leverage *= (1.0 + (1.0 - patch_success_rate))
        return leverage

    if strategy == "max_coverage":
        uncovered_bonus = 1.0 if patch_hit_rate == 0.0 else (1.0 - patch_success_rate)
        return count_total * uncovered_bonus

    raise ValueError(f"unsupported strategy: {strategy}")


def select_items(backlog: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    strategy = str(policy.get("strategy") or "max_impact")
    language_priority = list(policy.get("language_priority") or ["ts", "py"])
    stage_priority = list(policy.get("stage_priority") or ["tsc", "unit_test", "timeout"])
    top_n = _safe_int(policy.get("top_n") or 3)
    min_count = _safe_int(policy.get("min_count") or 3)

    items = [
        dict(item)
        for item in backlog.get("items", [])
        if _safe_int(item.get("count_total")) >= min_count
    ]

    items.sort(
        key=lambda item: (
            -_strategy_score(item, strategy=strategy),
            _lang_rank(str(item.get("language") or ""), language_priority),
            _stage_rank(str(item.get("verifier_stage_failed") or ""), stage_priority),
            -_safe_int(item.get("count_total")),
            str(item.get("error_signature") or ""),
            str(item.get("failure_type") or ""),
        )
    )

    selected: list[dict[str, Any]] = []
    for item in items[:top_n]:
        selected.append(
            {
                "language": item.get("language"),
                "failure_type": item.get("failure_type"),
                "error_signature": item.get("error_signature"),
                "verifier_stage_failed": item.get("verifier_stage_failed"),
                "suggested_category": item.get("suggested_category"),
                "priority_score": item.get("priority_score"),
                "examples": list(item.get("examples") or []),
                "count_total": item.get("count_total"),
                "solve_rate": item.get("solve_rate"),
                "patch_hit_rate": item.get("patch_hit_rate"),
                "patch_success_rate": item.get("patch_success_rate"),
            }
        )
    return selected


def main() -> int:
    args = parse_args()
    backlog = load_json(args.backlog)
    policy = load_json(args.policy)
    selected = select_items(backlog=backlog, policy=policy)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_backlog": str(args.backlog),
        "source_policy": str(args.policy),
        "strategy": policy.get("strategy"),
        "top_n": policy.get("top_n"),
        "min_count": policy.get("min_count"),
        "items": selected,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"selected_out={args.out}")
    print(f"selected_items={len(selected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
