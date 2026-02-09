#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build date-stamped progress report from quality metrics.")
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--patchers", type=str, default="", help="Optional comma-separated patchers added.")
    parser.add_argument("--out", type=Path, default=None, help="Optional output markdown path.")
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt_pct(value: float) -> str:
    return f"{value * 100.0:.2f}%"


def _top_uncovered(payload: dict[str, Any], limit: int = 5) -> list[str]:
    rows = payload.get("top_uncovered_signatures", [])
    out: list[str] = []
    for row in rows[:limit]:
        out.append(f"{row.get('language')} | {row.get('error_signature')} ({row.get('count')})")
    return out


def render(before: dict[str, Any], after: dict[str, Any], patchers: list[str]) -> str:
    lines: list[str] = []
    lines.append("# Progress Report")
    lines.append("")
    lines.append(f"- generated_at_utc: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append("## Signature Coverage")
    lines.append("")
    before_cov_lang = before.get("signature_coverage_by_language", {})
    after_cov_lang = after.get("signature_coverage_by_language", {})
    for language in sorted(set(before_cov_lang) | set(after_cov_lang)):
        b = float(before_cov_lang.get(language, 0.0))
        a = float(after_cov_lang.get(language, 0.0))
        lines.append(f"- {language}: {_fmt_pct(b)} -> {_fmt_pct(a)}")

    lines.append("")
    lines.append("## Top Uncovered")
    lines.append("")
    lines.append("- before:")
    for item in _top_uncovered(before):
        lines.append(f"  - {item}")
    if not _top_uncovered(before):
        lines.append("  - none")

    lines.append("- after:")
    for item in _top_uncovered(after):
        lines.append(f"  - {item}")
    if not _top_uncovered(after):
        lines.append("  - none")

    lines.append("")
    lines.append("## Pass Rate By Language")
    lines.append("")
    before_pass = before.get("pass_rate_by_language", {})
    after_pass = after.get("pass_rate_by_language", {})
    for language in sorted(set(before_pass) | set(after_pass)):
        b = float(before_pass.get(language, 0.0))
        a = float(after_pass.get(language, 0.0))
        lines.append(f"- {language}: {_fmt_pct(b)} -> {_fmt_pct(a)}")

    lines.append("")
    lines.append("## Patchers Added")
    lines.append("")
    if patchers:
        for patcher in patchers:
            lines.append(f"- {patcher}")
    else:
        lines.append("- none")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    before = _load(args.before)
    after = _load(args.after)
    patchers = [item.strip() for item in args.patchers.split(",") if item.strip()]

    out_path = args.out
    if out_path is None:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        out_path = Path("reports") / f"progress_{today}.md"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(before=before, after=after, patchers=patchers), encoding="utf-8")
    print(f"progress_report={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
