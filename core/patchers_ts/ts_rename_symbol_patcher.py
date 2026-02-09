from __future__ import annotations

import re

from core.patchers.base import PatchContext, PatchResult


class TsRenameSymbolPatcher:
    id = "ts_rename_symbol_patcher"

    _RENAME_RE = re.compile(
        r"Cannot find name '([A-Za-z_][A-Za-z0-9_]*)'\. Did you mean '([A-Za-z_][A-Za-z0-9_]*)'"
    )

    def can_apply(self, ctx: PatchContext) -> bool:
        if ctx.language != "ts":
            return False
        combined = (ctx.error_signature or "") + " " + (ctx.error_message or "")
        return "TS2552" in combined or "Did you mean" in combined

    def apply(self, ctx: PatchContext) -> PatchResult | None:
        combined = (ctx.error_signature or "") + " " + (ctx.error_message or "")
        match = self._RENAME_RE.search(combined)
        if not match:
            return None

        missing = match.group(1)
        replacement = match.group(2)
        pattern = re.compile(rf"\b{re.escape(missing)}\b")
        patched, count = pattern.subn(replacement, ctx.code, count=1)
        if count == 0 or patched == ctx.code:
            return None

        return PatchResult(
            patched_code=patched,
            patcher_id=self.id,
            patch_summary=f"renamed symbol {missing} -> {replacement}",
        )
