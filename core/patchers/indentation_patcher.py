from __future__ import annotations

import re

from .base import PatchContext, PatchResult


class IndentationPatcher:
    id = "indentation_patcher"

    _HEADER_RE = re.compile(r"^\s*(def|if|for|while|elif|else|try|except|finally|class)\b.*:\s*$")

    def can_apply(self, ctx: PatchContext) -> bool:
        msg = (ctx.error_message or "") + " " + (ctx.error_signature or "")
        return "IndentationError" in msg

    def apply(self, ctx: PatchContext) -> PatchResult | None:
        original = ctx.code
        lines = [line.replace("\t", "    ") for line in original.splitlines()]
        changed = lines != original.splitlines()

        for idx, line in enumerate(lines[:-1]):
            if not self._HEADER_RE.match(line):
                continue

            header_indent = len(line) - len(line.lstrip(" "))
            next_idx = idx + 1
            while next_idx < len(lines) and not lines[next_idx].strip():
                next_idx += 1
            if next_idx >= len(lines):
                continue

            next_line = lines[next_idx]
            next_indent = len(next_line) - len(next_line.lstrip(" "))
            if next_indent <= header_indent:
                stripped = next_line.lstrip(" ")
                lines[next_idx] = (" " * (header_indent + 4)) + stripped
                changed = True
                break

        if not changed:
            return None

        trailing = "\n" if original.endswith("\n") else ""
        return PatchResult(
            patched_code="\n".join(lines) + trailing,
            patcher_id=self.id,
            patch_summary="normalized indentation around block header",
        )
