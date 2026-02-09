#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare daily A/B summaries and emit recommendation.")
    parser.add_argument("--a", type=Path, required=True, help="Path to baseline daily_summary.json")
    parser.add_argument("--b", type=Path, required=True, help="Path to proposer-enabled daily_summary.json")
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    parser.add_argument("--min-solve-rate-gain", type=float, default=0.0)
    parser.add_argument("--max-timeout-increase", type=float, default=0.0)
    parser.add_argument("--max-flaky-increase", type=int, default=0)
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _language_delta(a: dict[str, Any], b: dict[str, Any]) -> dict[str, dict[str, float]]:
    pa = a.get("pass_rate_by_language", {})
    pb = b.get("pass_rate_by_language", {})
    out: dict[str, dict[str, float]] = {}
    for language in sorted(set(pa) | set(pb)):
        before = float(pa.get(language, 0.0))
        after = float(pb.get(language, 0.0))
        out[language] = {
            "before": before,
            "after": after,
            "delta": round(after - before, 6),
        }
    return out


def _normalize_signature(item: Any) -> str:
    if isinstance(item, dict):
        language = str(item.get("language") or "all")
        signature = str(item.get("error_signature") or "")
        return f"{language}:{signature}"
    return str(item)


def compare(
    *,
    summary_a: dict[str, Any],
    summary_b: dict[str, Any],
    min_solve_rate_gain: float,
    max_timeout_increase: float,
    max_flaky_increase: int,
) -> dict[str, Any]:
    solve_a = float(summary_a.get("overall_pass_rate", 0.0))
    solve_b = float(summary_b.get("overall_pass_rate", 0.0))
    solve_delta = round(solve_b - solve_a, 6)

    cov_a = float(summary_a.get("signature_coverage", 0.0))
    cov_b = float(summary_b.get("signature_coverage", 0.0))
    cov_delta = round(cov_b - cov_a, 6)

    timeout_a = float(summary_a.get("timeout_rate", 0.0))
    timeout_b = float(summary_b.get("timeout_rate", 0.0))
    timeout_delta = round(timeout_b - timeout_a, 6)

    flaky_a = int(summary_a.get("flaky_groups_count", 0))
    flaky_b = int(summary_b.get("flaky_groups_count", 0))
    flaky_delta = flaky_b - flaky_a

    uncovered_a = {_normalize_signature(item) for item in summary_a.get("top_uncovered_signatures", [])}
    uncovered_b = {_normalize_signature(item) for item in summary_b.get("top_uncovered_signatures", [])}

    top_uncovered_delta = {
        "added": sorted(uncovered_b - uncovered_a),
        "removed": sorted(uncovered_a - uncovered_b),
        "added_count": len(uncovered_b - uncovered_a),
        "removed_count": len(uncovered_a - uncovered_b),
    }

    budget_b = summary_b.get("proposer_budget_spent") or {"calls": 0, "seconds": 0.0}
    attempts_saved_a = int(summary_a.get("attempts_saved_by_patchers_approx", 0))
    attempts_saved_b = int(summary_b.get("attempts_saved_by_patchers_approx", 0))
    proposer_calls = int(budget_b.get("calls", 0))
    proposer_seconds = float(budget_b.get("seconds", 0.0))
    solve_gain_per_call = 0.0
    if proposer_calls > 0:
        solve_gain_per_call = solve_delta / proposer_calls

    enable = (
        solve_delta >= min_solve_rate_gain
        and timeout_delta <= max_timeout_increase
        and flaky_delta <= max_flaky_increase
    )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "solve_rate": {
            "before": solve_a,
            "after": solve_b,
            "delta": solve_delta,
        },
        "pass_rate_by_language": _language_delta(summary_a, summary_b),
        "signature_coverage": {
            "before": cov_a,
            "after": cov_b,
            "delta": cov_delta,
        },
        "signature_coverage_delta": cov_delta,
        "top_uncovered_delta": top_uncovered_delta,
        "timeout_rate": {
            "before": timeout_a,
            "after": timeout_b,
            "delta": timeout_delta,
        },
        "flaky_groups_count": {
            "before": flaky_a,
            "after": flaky_b,
            "delta": flaky_delta,
        },
        "attempts_saved_by_patchers": {
            "before": attempts_saved_a,
            "after": attempts_saved_b,
            "delta": attempts_saved_b - attempts_saved_a,
        },
        "attempts_saved_by_patchers_delta": attempts_saved_b - attempts_saved_a,
        "cost": {
            "proposer_calls": proposer_calls,
            "proposer_seconds": proposer_seconds,
            "calls_by_proposer": dict(sorted((budget_b.get("calls_by_proposer") or {}).items())),
            "solve_gain_per_call": round(solve_gain_per_call, 8),
        },
        "decision": {
            "enable_proposer": enable,
            "criteria": {
                "min_solve_rate_gain": min_solve_rate_gain,
                "max_timeout_increase": max_timeout_increase,
                "max_flaky_increase": max_flaky_increase,
            },
            "reason": (
                "enable proposer" if enable else "keep proposer disabled"
            ),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# A/B Compare")
    lines.append("")

    solve = payload["solve_rate"]
    lines.append(
        f"- solve_rate: {solve['before']:.6f} -> {solve['after']:.6f} (delta {solve['delta']:+.6f})"
    )

    cov = payload["signature_coverage"]
    lines.append(
        f"- signature_coverage: {cov['before']:.6f} -> {cov['after']:.6f} (delta {cov['delta']:+.6f})"
    )

    timeout = payload["timeout_rate"]
    lines.append(
        f"- timeout_rate: {timeout['before']:.6f} -> {timeout['after']:.6f} (delta {timeout['delta']:+.6f})"
    )

    flaky = payload["flaky_groups_count"]
    lines.append(
        f"- flaky_groups_count: {flaky['before']} -> {flaky['after']} (delta {flaky['delta']:+d})"
    )

    uncovered = payload["top_uncovered_delta"]
    lines.append(
        f"- top_uncovered delta: added={uncovered['added_count']} removed={uncovered['removed_count']}"
    )

    patch_delta = payload["attempts_saved_by_patchers"]
    lines.append(
        f"- attempts_saved_by_patchers: {patch_delta['before']} -> {patch_delta['after']} (delta {patch_delta['delta']:+d})"
    )

    cost = payload["cost"]
    lines.append(
        f"- proposer cost: calls={cost['proposer_calls']} seconds={cost['proposer_seconds']:.6f} solve_gain_per_call={cost['solve_gain_per_call']:.8f}"
    )

    decision = payload["decision"]
    lines.append(f"- decision: {decision['reason']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    summary_a = _load(args.a)
    summary_b = _load(args.b)
    payload = compare(
        summary_a=summary_a,
        summary_b=summary_b,
        min_solve_rate_gain=float(args.min_solve_rate_gain),
        max_timeout_increase=float(args.max_timeout_increase),
        max_flaky_increase=int(args.max_flaky_increase),
    )

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(render_markdown(payload), encoding="utf-8")

    print(f"ab_compare_json={args.out_json}")
    print(f"ab_compare_md={args.out_md}")
    print(f"enable_proposer={payload['decision']['enable_proposer']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
