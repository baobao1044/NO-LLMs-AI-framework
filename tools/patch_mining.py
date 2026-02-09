#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mine patch opportunities from agent logs.")
    parser.add_argument("--log", type=Path, required=True, help="Path to JSONL event log.")
    parser.add_argument("--top-k", type=int, default=50, help="Top K groups in report.")
    parser.add_argument("--min-count", type=int, default=3, help="Minimum group count.")
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


def _group_key(record: dict[str, Any]) -> GroupKey | None:
    failure_type = record.get("failure_type")
    error_signature = record.get("error_signature")
    verifier_stage = record.get("verifier_stage_failed")
    if not failure_type or not error_signature:
        return None
    return GroupKey(
        language=str(record.get("language") or "py"),
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


def build_report(records: list[dict[str, Any]], top_k: int, min_count: int) -> dict[str, Any]:
    run_solved: dict[str, bool] = defaultdict(bool)
    run_language: dict[str, str] = {}
    for record in records:
        run_id = record.get("run_id")
        if not run_id:
            continue
        run_solved[run_id] = run_solved[run_id] or bool(record.get("passed"))
        run_language.setdefault(run_id, str(record.get("language") or "py"))

    grouped_records: dict[GroupKey, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = _group_key(record)
        if key is None:
            continue
        grouped_records[key].append(record)

    groups_out: list[dict[str, Any]] = []
    covered_signatures: set[str] = set()
    uncovered_counter: Counter[str] = Counter()
    patchable_signatures: set[tuple[str, str]] = set()
    fail_records = [record for record in records if _group_key(record) is not None]
    language_summary: dict[str, dict[str, int]] = defaultdict(lambda: {"eligible_records": 0, "solved_records": 0})

    for key, events in grouped_records.items():
        events_sorted = sorted(
            events,
            key=lambda item: (
                str(item.get("run_id", "")),
                int(item.get("attempt_index", 0)),
                str(item.get("artifact_hash", "")),
            ),
        )
        total = len(events_sorted)
        if total < min_count:
            continue

        count_solved = sum(1 for event in events_sorted if run_solved.get(str(event.get("run_id")), False))
        for event in events_sorted:
            language_summary[key.language]["eligible_records"] += 1
            if run_solved.get(str(event.get("run_id")), False):
                language_summary[key.language]["solved_records"] += 1
        patch_hit = sum(1 for event in events_sorted if event.get("patcher_id"))
        patch_applied_count = sum(1 for event in events_sorted if event.get("patch_applied") and event.get("patcher_id"))
        patch_success_count = sum(
            1
            for event in events_sorted
            if event.get("patch_applied")
            and event.get("patcher_id")
            and _is_patch_success_event(records, event)
        )

        patch_success_by_id: Counter[str] = Counter()
        for event in events_sorted:
            patcher_id = event.get("patcher_id")
            if not patcher_id:
                continue
            patchable_signatures.add((key.language, key.error_signature))
            if _is_patch_success_event(records, event):
                patch_success_by_id[str(patcher_id)] += 1

        if patch_hit > 0:
            covered_signatures.add(f"{key.language}::{key.error_signature}")
        else:
            uncovered_counter[f"{key.language}::{key.error_signature}"] += total

        examples = []
        seen_artifacts: set[str] = set()
        for event in events_sorted:
            artifact_hash = str(event.get("artifact_hash", ""))
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

        top_patchers = [
            {"patcher_id": patcher_id, "success_count": count}
            for patcher_id, count in sorted(
                patch_success_by_id.items(),
                key=lambda item: (-item[1], item[0]),
            )[:3]
        ]

        groups_out.append(
            {
                "group_key": {
                    "language": key.language,
                    "failure_type": key.failure_type,
                    "error_signature": key.error_signature,
                    "verifier_stage_failed": key.verifier_stage_failed,
                },
                "count_total": total,
                "count_solved": count_solved,
                "solve_rate": round((count_solved / total) * 100.0, 4),
                "patch_hit_rate": round((patch_hit / total) * 100.0, 4),
                "patch_success_rate": round(
                    (patch_success_count / patch_applied_count) * 100.0 if patch_applied_count else 0.0,
                    4,
                ),
                "top_patchers": top_patchers,
                "examples": examples,
                "patchers_tried": sorted(
                    {
                        str(event.get("patcher_id"))
                        for event in events_sorted
                        if event.get("patcher_id") is not None
                    }
                ),
            }
        )

    groups_out.sort(
        key=lambda item: (
            -item["count_total"],
            item["group_key"]["language"],
            item["group_key"]["failure_type"],
            item["group_key"]["error_signature"],
            item["group_key"]["verifier_stage_failed"],
        )
    )

    by_count = groups_out[:top_k]
    by_low_solve = sorted(
        groups_out,
        key=lambda item: (
            item["solve_rate"],
            -item["count_total"],
            item["group_key"]["language"],
            item["group_key"]["error_signature"],
        ),
    )[:top_k]

    all_signatures = {
        f"{str(record.get('language') or 'py')}::{str(record.get('error_signature'))}"
        for record in fail_records
        if record.get("error_signature")
    }
    uncovered_signatures = sorted(all_signatures - covered_signatures)
    overall_solved = sum(1 for record in fail_records if run_solved.get(str(record.get("run_id")), False))
    summary = {
        "total_records": len(records),
        "eligible_records": len(fail_records),
        "solved_records": overall_solved,
        "overall_solve_rate": round(
            (overall_solved / len(fail_records)) * 100.0 if fail_records else 0.0,
            4,
        ),
        "language_breakdown": {
            language: {
                "eligible_records": values["eligible_records"],
                "solved_records": values["solved_records"],
                "solve_rate": round(
                    (values["solved_records"] / values["eligible_records"]) * 100.0
                    if values["eligible_records"]
                    else 0.0,
                    4,
                ),
            }
            for language, values in sorted(language_summary.items())
        },
    }

    coverage = {
        "signatures_total": len(all_signatures),
        "signatures_covered_by_patcher": len(covered_signatures),
        "signatures_uncovered": len(uncovered_signatures),
        "coverage_rate": round((len(covered_signatures) / len(all_signatures)) * 100.0 if all_signatures else 0.0, 4),
        "top_uncovered_signatures": [
            {
                "language": signature.split("::", 1)[0],
                "error_signature": signature.split("::", 1)[1],
                "count": uncovered_counter.get(signature, 0),
            }
            for signature in sorted(
                uncovered_signatures,
                key=lambda sign: (-uncovered_counter.get(sign, 0), sign),
            )[:20]
        ],
    }

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "groups_by_count": by_count,
        "groups_by_low_solve_rate": by_low_solve,
        "coverage": coverage,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    summary = payload["summary"]
    coverage = payload["coverage"]
    lines.append("# Patch Mining Report")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- total_records: {summary['total_records']}")
    lines.append(f"- eligible_records: {summary['eligible_records']}")
    lines.append(f"- solved_records: {summary['solved_records']}")
    lines.append(f"- overall_solve_rate: {summary['overall_solve_rate']:.4f}%")
    if summary.get("language_breakdown"):
        lines.append("- language_breakdown:")
        for language, values in summary["language_breakdown"].items():
            lines.append(
                "  "
                f"{language}: eligible={values['eligible_records']} solved={values['solved_records']} "
                f"solve_rate={values['solve_rate']:.4f}%"
            )
    lines.append("")
    lines.append("## Top Groups By Count")
    lines.append("")
    for item in payload["groups_by_count"]:
        key = item["group_key"]
        lines.append(
            "- "
            f"{key['language']} | {key['failure_type']} | {key['verifier_stage_failed']} | {key['error_signature']} "
            f"(count={item['count_total']}, solve_rate={item['solve_rate']:.4f}%, "
            f"patch_hit_rate={item['patch_hit_rate']:.4f}%, "
            f"patch_success_rate={item['patch_success_rate']:.4f}%)"
        )
    lines.append("")
    lines.append("## Low Solve-Rate Groups")
    lines.append("")
    for item in payload["groups_by_low_solve_rate"]:
        key = item["group_key"]
        lines.append(
            "- "
            f"{key['language']} | {key['failure_type']} | {key['verifier_stage_failed']} | {key['error_signature']} "
            f"(count={item['count_total']}, solve_rate={item['solve_rate']:.4f}%)"
        )
    lines.append("")
    lines.append("## Suggested Patchers")
    lines.append("")
    for item in payload["groups_by_low_solve_rate"]:
        key = item["group_key"]
        lines.append(
            f"### {key['language']} | {key['failure_type']} | {key['verifier_stage_failed']} | {key['error_signature']}"
        )
        lines.append("")
        lines.append(f"- patchers_tried: {', '.join(item['patchers_tried']) if item['patchers_tried'] else 'none'}")
        if item["top_patchers"]:
            tops = ", ".join(
                f"{entry['patcher_id']}({entry['success_count']})" for entry in item["top_patchers"]
            )
        else:
            tops = "none"
        lines.append(f"- top_patchers: {tops}")
        lines.append("- notes: prioritize deterministic patcher for this signature group.")
        lines.append("- examples:")
        for example in item["examples"]:
            lines.append(
                "  "
                f"task_id={example['task_id']} artifact_hash={example['artifact_hash']} "
                f"parent={example['parent_artifact_hash']}"
            )
            lines.append(f"  prompt={example['prompt']}")
            lines.append(f"  error_message={example['error_message']}")
            lines.append(f"  code={example['code']}")
        lines.append("")

    lines.append("## Coverage")
    lines.append("")
    lines.append(f"- signatures_total: {coverage['signatures_total']}")
    lines.append(f"- signatures_covered_by_patcher: {coverage['signatures_covered_by_patcher']}")
    lines.append(f"- signatures_uncovered: {coverage['signatures_uncovered']}")
    lines.append(f"- coverage_rate: {coverage['coverage_rate']:.4f}%")
    lines.append("- top_uncovered_signatures:")
    for item in coverage["top_uncovered_signatures"]:
        lines.append(f"  - {item['language']} | {item['error_signature']} (count={item['count']})")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    records = load_records(args.log)
    payload = build_report(records=records, top_k=args.top_k, min_count=args.min_count)

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    report_dir = Path("reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"patch_mining_{today}.json"
    md_path = report_dir / f"patch_mining_{today}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(f"json_report={json_path}")
    print(f"md_report={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
