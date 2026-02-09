#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GroupKey:
    language: str
    failure_type: str
    error_signature: str
    verifier_stage_failed: str


_STAGE_WEIGHT = {
    "tsc": 1.3,
    "build": 1.2,
    "syntax": 1.1,
    "timeout": 1.25,
    "unit_test": 1.0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build coverage-driven patch backlog from event logs.")
    parser.add_argument("--log", type=Path, required=True, help="Path to JSONL event log.")
    parser.add_argument("--language", choices=["all", "py", "ts"], default="all", help="Language filter.")
    parser.add_argument("--top-k", type=int, default=50, help="Maximum backlog items.")
    parser.add_argument("--min-count", type=int, default=3, help="Minimum records per signature group.")
    parser.add_argument(
        "--solve-rate-threshold",
        type=float,
        default=0.85,
        help="Low-solve threshold using [0,1] solve rate.",
    )
    parser.add_argument(
        "--patch-success-threshold",
        type=float,
        default=0.5,
        help="Low patch success threshold using [0,1] patch success rate.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Backlog JSON output path. Default: configs/patch_backlog_<language>.json",
    )
    return parser.parse_args()


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _truncate(value: Any, max_len: int) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _event_language(record: dict[str, Any]) -> str:
    language = record.get("language")
    if isinstance(language, str) and language:
        return language
    verifier_name = str(record.get("verifier_name") or "")
    if verifier_name.startswith("ts_"):
        return "ts"
    return "py"


def _group_key(record: dict[str, Any]) -> GroupKey | None:
    failure_type = record.get("failure_type")
    error_signature = record.get("error_signature")
    verifier_stage = record.get("verifier_stage_failed")
    if not failure_type or not error_signature:
        return None
    return GroupKey(
        language=_event_language(record),
        failure_type=str(failure_type),
        error_signature=str(error_signature),
        verifier_stage_failed=str(verifier_stage or "UNKNOWN"),
    )


def _is_patch_success_event(events: list[dict[str, Any]], failed_event: dict[str, Any]) -> bool:
    run_id = failed_event.get("run_id")
    artifact_hash = failed_event.get("artifact_hash")
    attempt_index = failed_event.get("attempt_index")
    if not run_id or not artifact_hash:
        return False
    for event in events:
        if event.get("run_id") != run_id:
            continue
        if event.get("attempt_index") != attempt_index:
            continue
        if event.get("parent_artifact_hash") != artifact_hash:
            continue
        if event.get("passed"):
            return True
    return False


def _suggested_category(group: GroupKey) -> str:
    signature = group.error_signature.upper()
    failure = group.failure_type.lower()
    stage = group.verifier_stage_failed.lower()

    if "TIMEOUT" in signature or "timeout" in failure or stage == "timeout":
        return "performance_or_infinite_loop"
    if any(token in signature for token in ["TS2322", "TS2345", "TS236", "TS7006"]) or "type" in failure:
        return "type_fix"
    if any(token in signature for token in ["TS2304", "TS2307", "TS2552"]) or failure in {
        "ts_name_error",
        "import_error",
    }:
        return "name_or_import"
    if (
        "SYNTAX" in signature
        or failure in {"syntax_error", "ts_syntax_error"}
        or any(token in signature for token in ["TS100", "TS1109", "TS1128", "TS1136", "TS1160"])
    ):
        return "syntax_fix"
    if "MISSING CALLABLE" in signature or "EXPORT" in signature or "TS2459" in signature:
        return "export_fix"
    return "other"


def _priority_score(count_total: int, solve_rate: float, stage: str) -> float:
    stage_weight = _STAGE_WEIGHT.get(stage.lower(), 1.0)
    base = float(count_total) * (1.0 - solve_rate)
    return round(base * stage_weight, 6)


def build_backlog(
    records: list[dict[str, Any]],
    language: str,
    top_k: int,
    min_count: int,
    solve_rate_threshold: float,
    patch_success_threshold: float,
) -> list[dict[str, Any]]:
    filtered = [
        record for record in records if language == "all" or _event_language(record) == language
    ]

    run_solved: dict[str, bool] = defaultdict(bool)
    for record in filtered:
        run_id = record.get("run_id")
        if not run_id:
            continue
        run_solved[str(run_id)] = run_solved[str(run_id)] or bool(record.get("passed"))

    grouped_records: dict[GroupKey, list[dict[str, Any]]] = defaultdict(list)
    for record in filtered:
        key = _group_key(record)
        if key is None:
            continue
        grouped_records[key].append(record)

    rows: list[dict[str, Any]] = []
    for key, events in grouped_records.items():
        events_sorted = sorted(
            events,
            key=lambda item: (
                str(item.get("run_id", "")),
                int(item.get("attempt_index", 0)),
                str(item.get("artifact_hash", "")),
            ),
        )
        count_total = len(events_sorted)
        if count_total < min_count:
            continue

        count_solved = sum(1 for event in events_sorted if run_solved.get(str(event.get("run_id")), False))
        patch_hits = sum(1 for event in events_sorted if event.get("patcher_id") is not None)
        patch_applied = [
            event for event in events_sorted if event.get("patch_applied") and event.get("patcher_id") is not None
        ]
        patch_success = sum(1 for event in patch_applied if _is_patch_success_event(filtered, event))

        solve_rate = count_solved / count_total if count_total else 0.0
        patch_hit_rate = patch_hits / count_total if count_total else 0.0
        patch_success_rate = patch_success / len(patch_applied) if patch_applied else 0.0

        is_uncovered = patch_hit_rate == 0.0 or patch_success_rate < patch_success_threshold
        is_low_solve = solve_rate < solve_rate_threshold
        if not (is_uncovered or is_low_solve):
            continue

        examples: list[dict[str, Any]] = []
        seen_artifacts: set[str] = set()
        for event in events_sorted:
            artifact_hash = str(event.get("artifact_hash") or "")
            if artifact_hash in seen_artifacts:
                continue
            seen_artifacts.add(artifact_hash)
            examples.append(
                {
                    "task_id": event.get("task_id"),
                    "prompt": _truncate(event.get("task_prompt"), 160),
                    "code": _truncate(event.get("code"), 320),
                    "error_message": _truncate(event.get("error_message") or event.get("error"), 180),
                    "artifact_hash": event.get("artifact_hash"),
                    "parent_artifact_hash": event.get("parent_artifact_hash"),
                }
            )
            if len(examples) >= 3:
                break

        rows.append(
            {
                "language": key.language,
                "failure_type": key.failure_type,
                "error_signature": key.error_signature,
                "verifier_stage_failed": key.verifier_stage_failed,
                "count_total": count_total,
                "solve_rate": round(solve_rate, 6),
                "patch_hit_rate": round(patch_hit_rate, 6),
                "patch_success_rate": round(patch_success_rate, 6),
                "suggested_category": _suggested_category(key),
                "priority_score": _priority_score(
                    count_total=count_total,
                    solve_rate=solve_rate,
                    stage=key.verifier_stage_failed,
                ),
                "examples": examples,
            }
        )

    rows.sort(
        key=lambda item: (
            -item["priority_score"],
            -item["count_total"],
            item["language"],
            item["failure_type"],
            item["error_signature"],
            item["verifier_stage_failed"],
        )
    )
    return rows[:top_k]


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Patch Backlog")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- source_log: {payload['source_log']}")
    lines.append(f"- language_filter: {payload['language_filter']}")
    lines.append(f"- total_candidates: {payload['total_candidates']}")
    lines.append(f"- backlog_items: {len(payload['items'])}")
    lines.append("")
    lines.append("## Top Priorities")
    lines.append("")

    for item in payload["items"]:
        lines.append(
            "- "
            f"priority={item['priority_score']:.4f} | {item['language']} | {item['failure_type']} | "
            f"{item['verifier_stage_failed']} | {item['error_signature']} "
            f"(count={item['count_total']}, solve={item['solve_rate']:.3f}, "
            f"patch_hit={item['patch_hit_rate']:.3f}, patch_success={item['patch_success_rate']:.3f}, "
            f"category={item['suggested_category']})"
        )
        for example in item["examples"][:2]:
            lines.append(
                "  "
                f"task_id={example['task_id']} artifact_hash={example['artifact_hash']} "
                f"parent={example['parent_artifact_hash']}"
            )
            lines.append(f"  error={example['error_message']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    records = load_records(args.log)
    items = build_backlog(
        records=records,
        language=args.language,
        top_k=args.top_k,
        min_count=args.min_count,
        solve_rate_threshold=args.solve_rate_threshold,
        patch_success_threshold=args.patch_success_threshold,
    )

    out_path = args.out
    if out_path is None:
        out_path = Path(f"configs/patch_backlog_{args.language}.json")

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_log": str(args.log),
        "language_filter": args.language,
        "top_k": args.top_k,
        "min_count": args.min_count,
        "solve_rate_threshold": args.solve_rate_threshold,
        "patch_success_threshold": args.patch_success_threshold,
        "total_candidates": len(items),
        "items": items,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    report_dir = Path("reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    md_path = report_dir / f"patch_backlog_{today}.md"
    md_path.write_text(render_markdown(payload), encoding="utf-8")

    print(f"backlog_json={out_path}")
    print(f"backlog_md={md_path}")
    print(f"items={len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
