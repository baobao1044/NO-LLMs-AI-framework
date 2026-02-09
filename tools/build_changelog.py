#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append date sections to CHANGELOG using daily/progress reports.")
    parser.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    parser.add_argument("--progress-glob", type=str, default="reports/progress_*.md")
    parser.add_argument("--daily-glob", type=str, default="reports/*/daily_summary*.json")
    parser.add_argument("--backlog-selected", type=Path, default=Path("configs/backlog_selected.json"))
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_date_key(raw: str) -> str:
    if re.fullmatch(r"\d{8}", raw):
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    raise ValueError(f"unsupported date key: {raw}")


def _extract_date_from_progress(path: Path) -> str | None:
    match = re.search(r"progress_(\d{8})\.md$", path.name)
    if not match:
        return None
    return _normalize_date_key(match.group(1))


def _extract_patchers_from_progress(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    patchers: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped == "## Patchers Added":
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section and stripped.startswith("- "):
            value = stripped[2:].strip()
            if value and value != "none":
                patchers.append(value)

    return patchers


def _extract_patchers_from_backlog(path: Path) -> list[str]:
    if not path.exists():
        return []

    payload = _load_json(path)
    out: list[str] = []
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        language = str(item.get("language") or "all")
        category = str(item.get("suggested_category") or "other")
        signature = str(item.get("error_signature") or "")
        descriptor = f"{language}:{category}:{signature}" if signature else f"{language}:{category}"
        out.append(descriptor)

    deduped = sorted(set(out))
    return deduped


def _extract_daily_date(path: Path, payload: dict[str, Any]) -> str:
    for candidate in [str(payload.get("date") or ""), path.parent.name]:
        if not candidate:
            continue
        try:
            return _normalize_date_key(candidate)
        except ValueError:
            continue

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return today


def _daily_rank(path: Path) -> int:
    name = path.name
    if name == "daily_summary.json":
        return 3
    if name == "daily_summary_B.json":
        return 2
    if name == "daily_summary_A.json":
        return 1
    return 0


def _pass_rate_deltas(payload: dict[str, Any]) -> dict[str, float]:
    by_lang = payload.get("pass_rate_by_language", {})
    out: dict[str, float] = {}
    if not isinstance(by_lang, dict):
        return out

    for language, value in by_lang.items():
        if isinstance(value, dict) and "delta" in value:
            out[str(language)] = float(value.get("delta") or 0.0)
        elif isinstance(value, (int, float)):
            out[str(language)] = 0.0
    return out


def _pass_rate_deltas_from_ab(payload: dict[str, Any]) -> dict[str, float]:
    by_lang = payload.get("pass_rate_by_language", {})
    if not isinstance(by_lang, dict):
        return {}
    out: dict[str, float] = {}
    for language, value in by_lang.items():
        if isinstance(value, dict):
            out[str(language)] = float(value.get("delta") or 0.0)
    return out


def _signature_coverage_delta(payload: dict[str, Any]) -> float:
    value = payload.get("signature_coverage")
    if isinstance(value, dict):
        return float(value.get("delta") or 0.0)
    if isinstance(value, (int, float)):
        return 0.0
    return 0.0


def _signature_coverage_delta_from_ab(payload: dict[str, Any]) -> float:
    sig = payload.get("signature_coverage")
    if not isinstance(sig, dict):
        return 0.0
    return float(sig.get("delta") or 0.0)


def _normalize_uncovered_item(item: Any) -> str:
    if isinstance(item, dict):
        language = str(item.get("language") or "all")
        signature = str(item.get("error_signature") or "")
        return f"{language}:{signature}"
    return str(item)


def _top_uncovered_delta(payload: dict[str, Any]) -> tuple[int, int]:
    top_uncovered = payload.get("top_uncovered")
    if not isinstance(top_uncovered, dict):
        return 0, 0

    before = {_normalize_uncovered_item(item) for item in top_uncovered.get("before", [])}
    after = {_normalize_uncovered_item(item) for item in top_uncovered.get("after", [])}
    added = len(after - before)
    removed = len(before - after)
    return added, removed


def _top_uncovered_delta_from_ab(payload: dict[str, Any]) -> tuple[int, int]:
    top = payload.get("top_uncovered_delta")
    if not isinstance(top, dict):
        return 0, 0
    return int(top.get("added_count") or 0), int(top.get("removed_count") or 0)


def _replay_notes(day: str, replay_path: Path | None = None) -> str:
    if replay_path is None:
        yyyymmdd = day.replace("-", "")
        replay_path = Path("reports") / yyyymmdd / "replay_metrics.json"
    if not replay_path.exists():
        return "replay=unknown"

    payload = _load_json(replay_path)
    replay_match = int(payload.get("replay_match") or 0)
    replay_eligible = int(payload.get("replay_eligible") or 0)
    env_mismatch = int(payload.get("env_fingerprint_mismatch_count") or 0)
    mismatch = replay_eligible - replay_match
    return (
        f"replay={replay_match}/{replay_eligible} "
        f"mismatch={mismatch} env_fingerprint_mismatch={env_mismatch}"
    )


def _replay_notes_ab(report_dir: Path) -> str:
    path_a = report_dir / "replay_metrics_A.json"
    path_b = report_dir / "replay_metrics_B.json"
    if not path_a.exists() or not path_b.exists():
        return _replay_notes(report_dir.name, replay_path=report_dir / "replay_metrics.json")

    payload_a = _load_json(path_a)
    payload_b = _load_json(path_b)
    mismatch_a = int(payload_a.get("replay_eligible", 0)) - int(payload_a.get("replay_match", 0))
    mismatch_b = int(payload_b.get("replay_eligible", 0)) - int(payload_b.get("replay_match", 0))
    env_a = int(payload_a.get("env_fingerprint_mismatch_count", 0))
    env_b = int(payload_b.get("env_fingerprint_mismatch_count", 0))
    return (
        "replay_A="
        f"{payload_a.get('replay_match', 0)}/{payload_a.get('replay_eligible', 0)} mismatch={mismatch_a} env={env_a}; "
        "replay_B="
        f"{payload_b.get('replay_match', 0)}/{payload_b.get('replay_eligible', 0)} mismatch={mismatch_b} env={env_b}"
    )


def build_section(
    day: str,
    daily_payload: dict[str, Any],
    ab_payload: dict[str, Any] | None,
    patchers: list[str],
    replay_note: str,
) -> str:
    pass_delta = _pass_rate_deltas_from_ab(ab_payload) if ab_payload is not None else _pass_rate_deltas(daily_payload)
    pass_delta_str = ", ".join(
        f"{language}:{delta:+.6f}" for language, delta in sorted(pass_delta.items())
    )
    if not pass_delta_str:
        pass_delta_str = "none"

    signature_delta = (
        _signature_coverage_delta_from_ab(ab_payload)
        if ab_payload is not None
        else _signature_coverage_delta(daily_payload)
    )
    uncovered_added, uncovered_removed = (
        _top_uncovered_delta_from_ab(ab_payload) if ab_payload is not None else _top_uncovered_delta(daily_payload)
    )

    regress_note = str(daily_payload.get("regress_status") or "unknown")
    quality_note = str(daily_payload.get("quality_status") or "unknown")
    proposer_note = "proposer_budget=unknown"
    if ab_payload is not None:
        cost = ab_payload.get("cost", {})
        proposer_note = (
            "proposer_budget="
            f"calls={int(cost.get('proposer_calls', 0))} "
            f"seconds={float(cost.get('proposer_seconds', 0.0)):.6f} "
            f"solve_gain_per_call={float(cost.get('solve_gain_per_call', 0.0)):.8f}"
        )
    elif isinstance(daily_payload.get("proposer_budget_spent"), dict):
        budget = daily_payload["proposer_budget_spent"]
        proposer_note = (
            "proposer_budget="
            f"calls={int(budget.get('calls', 0))} "
            f"seconds={float(budget.get('seconds', 0.0)):.6f}"
        )
    lines: list[str] = []
    lines.append(f"## [{day}]")
    lines.append("")
    lines.append(f"- pass_rate_by_language delta: {pass_delta_str}")
    lines.append(f"- signature_coverage delta: {signature_delta:+.6f}")
    lines.append(f"- top_uncovered delta: added={uncovered_added}, removed={uncovered_removed}")
    if patchers:
        lines.append(f"- patchers added: {', '.join(sorted(set(patchers)))}")
    else:
        lines.append("- patchers added: none")
    lines.append(f"- notes: regress={regress_note}; quality={quality_note}; {replay_note}; {proposer_note}")
    lines.append("")
    return "\n".join(lines)


def append_sections(changelog: Path, sections: dict[str, str]) -> tuple[int, Path]:
    if changelog.exists():
        content = changelog.read_text(encoding="utf-8")
    else:
        content = "# Changelog\n\nAll notable changes to this project will be documented in this file.\n\n"

    existing_days = set(re.findall(r"^## \[(\d{4}-\d{2}-\d{2})\]$", content, flags=re.MULTILINE))
    to_append = [sections[day] for day in sorted(sections) if day not in existing_days]

    if not to_append:
        changelog.parent.mkdir(parents=True, exist_ok=True)
        changelog.write_text(content, encoding="utf-8")
        return 0, changelog

    if not content.endswith("\n"):
        content += "\n"
    if not content.endswith("\n\n"):
        content += "\n"

    content += "\n".join(to_append)
    changelog.parent.mkdir(parents=True, exist_ok=True)
    changelog.write_text(content, encoding="utf-8")
    return len(to_append), changelog


def main() -> int:
    args = parse_args()

    progress_patchers: dict[str, list[str]] = {}
    for raw_path in sorted(glob.glob(args.progress_glob)):
        path = Path(raw_path)
        date_key = _extract_date_from_progress(path)
        if date_key is None:
            continue
        progress_patchers[date_key] = _extract_patchers_from_progress(path)

    backlog_patchers = _extract_patchers_from_backlog(args.backlog_selected)

    selected_daily_by_day: dict[str, tuple[Path, dict[str, Any]]] = {}
    for raw_path in sorted(glob.glob(args.daily_glob)):
        path = Path(raw_path)
        daily_payload = _load_json(path)
        day = _extract_daily_date(path, daily_payload)
        current = selected_daily_by_day.get(day)
        if current is None or _daily_rank(path) > _daily_rank(current[0]):
            selected_daily_by_day[day] = (path, daily_payload)

    sections: dict[str, str] = {}
    for day, (path, daily_payload) in sorted(selected_daily_by_day.items()):
        patchers = progress_patchers.get(day) or backlog_patchers
        ab_path = path.parent / "ab_compare.json"
        ab_payload = _load_json(ab_path) if ab_path.exists() else None
        replay_note = _replay_notes_ab(path.parent) if ab_payload is not None else _replay_notes(
            day,
            replay_path=path.parent / "replay_metrics.json",
        )
        sections[day] = build_section(
            day=day,
            daily_payload=daily_payload,
            ab_payload=ab_payload,
            patchers=patchers,
            replay_note=replay_note,
        )

    appended_count, out_path = append_sections(args.changelog, sections)
    print(f"changelog={out_path}")
    print(f"sections_appended={appended_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
