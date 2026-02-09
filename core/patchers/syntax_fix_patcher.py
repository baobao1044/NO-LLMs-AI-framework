from __future__ import annotations

import re

from .base import PatchContext, PatchResult


class SyntaxFixPatcher:
    id = "syntax_fix_patcher"

    _HEADER_RE = re.compile(
        r"^(\s*)(def|if|for|while|elif|else|try|except|finally|class)\b[^#]*$"
    )

    def can_apply(self, ctx: PatchContext) -> bool:
        return (ctx.failure_type == "syntax_error") or ("SyntaxError" in (ctx.error_signature or ""))

    def apply(self, ctx: PatchContext) -> PatchResult | None:
        message = (ctx.error_message or "").lower()

        if "expected ':'" in message:
            patched = self._append_missing_colon(ctx.code)
            if patched != ctx.code:
                return PatchResult(
                    patched_code=patched,
                    patcher_id=self.id,
                    patch_summary="added missing ':' on a block header",
                )

        if "unterminated string" in message or "eol while scanning string literal" in message:
            patched = self._close_unterminated_quote(ctx.code)
            if patched != ctx.code:
                return PatchResult(
                    patched_code=patched,
                    patcher_id=self.id,
                    patch_summary="closed unmatched quote on one line",
                )

        return None

    def _append_missing_colon(self, code: str) -> str:
        lines = code.splitlines()
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.endswith(":"):
                continue
            if self._HEADER_RE.match(line):
                lines[idx] = line + ":"
                break
        trailing = "\n" if code.endswith("\n") else ""
        return "\n".join(lines) + trailing

    def _close_unterminated_quote(self, code: str) -> str:
        lines = code.splitlines()
        for idx, line in enumerate(lines):
            single_count = line.count("'") - line.count("\\'")
            if single_count % 2 == 1:
                lines[idx] = line + "'"
                break
            double_count = line.count('"') - line.count('\\"')
            if double_count % 2 == 1:
                lines[idx] = line + '"'
                break
        trailing = "\n" if code.endswith("\n") else ""
        return "\n".join(lines) + trailing
