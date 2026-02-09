#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build uncovered signature list for proposer gating.")
    parser.add_argument("--backlog", type=Path, default=Path("configs/patch_backlog_all.json"))
    parser.add_argument("--stats", type=Path, default=None)
    parser.add_argument("--top-k", type=int, default=100)
    parser.add_argument("--out", type=Path, default=Path("configs/uncovered_signatures.json"))
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _from_backlog(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = _load(path)
    rows: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "language": str(item.get("language") or "all"),
                "error_signature": str(item.get("error_signature") or ""),
                "verifier_stage_failed": str(item.get("verifier_stage_failed") or ""),
                "count": int(item.get("count_total") or 0),
            }
        )
    return [row for row in rows if row["error_signature"]]


def _from_stats(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = _load(path)
    rows: list[dict[str, Any]] = []
    for item in payload.get("top_uncovered_signatures", []):
        if not isinstance(item, dict):
            continue
        signature = str(item.get("error_signature") or "")
        if not signature:
            continue
        rows.append(
            {
                "language": str(item.get("language") or "all"),
                "error_signature": signature,
                "verifier_stage_failed": "",
                "count": int(item.get("count") or 0),
            }
        )
    return rows


def build_items(backlog_rows: list[dict[str, Any]], stats_rows: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}

    for row in backlog_rows + stats_rows:
        key = (row["language"], row["error_signature"], row["verifier_stage_failed"])
        existing = merged.get(key)
        if existing is None or int(row["count"]) > int(existing["count"]):
            merged[key] = dict(row)

    items = list(merged.values())
    items.sort(
        key=lambda row: (
            -int(row["count"]),
            row["language"],
            row["error_signature"],
            row["verifier_stage_failed"],
        )
    )
    return items[:top_k]


def main() -> int:
    args = parse_args()
    backlog_rows = _from_backlog(args.backlog)
    stats_rows = _from_stats(args.stats) if args.stats is not None else []

    items = build_items(backlog_rows=backlog_rows, stats_rows=stats_rows, top_k=args.top_k)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "backlog": str(args.backlog),
            "stats": str(args.stats) if args.stats is not None else None,
        },
        "top_k": args.top_k,
        "items": items,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"uncovered_out={args.out}")
    print(f"items={len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
