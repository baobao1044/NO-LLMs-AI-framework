from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass(frozen=True)
class DeltaInfo:
    changed_lines_count: int
    changed_line_numbers: list[int]
    delta_summary: str


def compute_delta(before: str, after: str, line_cap: int = 20) -> DeltaInfo:
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines)
    changed: list[int] = []

    for tag, _, _, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        for line_no in range(j1 + 1, j2 + 1):
            changed.append(line_no)

    unique = sorted(set(changed))
    capped = unique[:line_cap]
    count = len(unique)
    if count == 0:
        summary = "no line changes"
    else:
        preview = ",".join(str(x) for x in capped[:8])
        suffix = "..." if len(capped) > 8 else ""
        summary = f"changed_lines={count}; sample={preview}{suffix}"
    if len(summary) > 200:
        summary = summary[:197] + "..."
    return DeltaInfo(
        changed_lines_count=count,
        changed_line_numbers=capped,
        delta_summary=summary,
    )
