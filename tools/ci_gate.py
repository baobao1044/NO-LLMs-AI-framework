#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CI governance gate across test/regress/quality/replay.")
    parser.add_argument("--policy", type=Path, default=Path("configs/governance_policy.json"))
    parser.add_argument("--quality-baseline", type=Path, default=Path("configs/patcher_quality_baseline.json"))
    parser.add_argument("--quality-out", type=Path, default=Path("reports/ci_quality_metrics.json"))
    parser.add_argument("--replay-out", type=Path, default=Path("reports/ci_replay_metrics.json"))
    parser.add_argument("--log", type=Path, default=Path("logs/agent_runs.jsonl"))
    parser.add_argument(
        "--skip-commands",
        action="store_true",
        help="Evaluate policy using existing output files without running make commands.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run(command: list[str]) -> int:
    print("command=" + " ".join(command))
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip())
    return proc.returncode


def evaluate_governance(
    *,
    policy: dict[str, Any],
    quality_baseline: dict[str, Any],
    quality_current: dict[str, Any],
    replay_metrics: dict[str, Any],
) -> tuple[bool, list[str]]:
    failures: list[str] = []

    max_pass_rate_drop_allowed = float(policy.get("max_pass_rate_drop_allowed", 0.0))
    max_replay_mismatch_allowed = int(policy.get("max_replay_mismatch_allowed", 0))
    max_env_fingerprint_mismatch_allowed = int(policy.get("max_env_fingerprint_mismatch_allowed", 0))

    baseline_pass = float(quality_baseline.get("overall_pass_rate", 0.0))
    current_pass = float(quality_current.get("overall_pass_rate", 0.0))
    pass_rate_drop = baseline_pass - current_pass
    if pass_rate_drop > max_pass_rate_drop_allowed:
        failures.append(
            "pass_rate_drop_exceeded: "
            f"drop={pass_rate_drop:.6f} allowed={max_pass_rate_drop_allowed:.6f} "
            f"baseline={baseline_pass:.6f} current={current_pass:.6f}"
        )

    replay_match = int(replay_metrics.get("replay_match", 0))
    replay_eligible = int(replay_metrics.get("replay_eligible", 0))
    replay_mismatch = replay_eligible - replay_match
    if replay_mismatch > max_replay_mismatch_allowed:
        failures.append(
            "replay_mismatch_exceeded: "
            f"mismatch={replay_mismatch} allowed={max_replay_mismatch_allowed} "
            f"match={replay_match} eligible={replay_eligible}"
        )

    env_mismatch = int(replay_metrics.get("env_fingerprint_mismatch_count", 0))
    if env_mismatch > max_env_fingerprint_mismatch_allowed:
        failures.append(
            "env_fingerprint_mismatch_exceeded: "
            f"mismatch={env_mismatch} allowed={max_env_fingerprint_mismatch_allowed}"
        )

    return len(failures) == 0, failures


def main() -> int:
    args = parse_args()

    if not args.skip_commands:
        command_groups = [
            ["make", "test"],
            ["make", "regress"],
            ["make", "quality"],
            [
                "python3",
                "-c",
                (
                    "from pathlib import Path; "
                    "p = Path('logs/agent_runs.jsonl'); "
                    "p.parent.mkdir(parents=True, exist_ok=True); "
                    "p.write_text('', encoding='utf-8')"
                ),
            ],
            ["python3", "examples/add_task_demo.py"],
            ["python3", "tools/replay.py", str(args.log), "--json-out", str(args.replay_out)],
            [
                "python3",
                "tools/collect_quality_metrics.py",
                "--log",
                str(args.log),
                "--out",
                str(args.quality_out),
                "--allow-missing",
            ],
        ]
        for command in command_groups:
            code = _run(command)
            if code != 0:
                print("ci_gate=FAIL")
                print("reason=command_failed")
                return code

    policy = _load_json(args.policy)
    quality_baseline = _load_json(args.quality_baseline)
    quality_current = _load_json(args.quality_out)
    replay_metrics = _load_json(args.replay_out)

    ok, failures = evaluate_governance(
        policy=policy,
        quality_baseline=quality_baseline,
        quality_current=quality_current,
        replay_metrics=replay_metrics,
    )

    if not ok:
        print("ci_gate=FAIL")
        for failure in failures:
            print(failure)
        return 1

    print("ci_gate=PASS")
    print("reasons=none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
