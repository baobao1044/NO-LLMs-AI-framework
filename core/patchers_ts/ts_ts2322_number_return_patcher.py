from __future__ import annotations

import re

from core.patchers.base import PatchContext, PatchResult


class TsTs2322NumberReturnPatcher:
    id = "ts_ts2322_number_return_patcher"

    _RETURN_LITERAL_RE = re.compile(r"return\s+([\"\'])(?P<value>[^\"\']*)([\"\'])\s*;")

    def can_apply(self, ctx: PatchContext) -> bool:
        if ctx.language != "ts":
            return False
        combined = ((ctx.error_signature or "") + " " + (ctx.error_message or "")).lower()
        if "ts2322" not in combined:
            return False
        if "not assignable to type 'number'" not in combined:
            return False
        return "return" in ctx.code

    def apply(self, ctx: PatchContext) -> PatchResult | None:
        match = self._RETURN_LITERAL_RE.search(ctx.code)
        if match is None:
            return None

        raw = match.group("value")
        replacement = f'return Number("{raw}");'
        patched = ctx.code[: match.start()] + replacement + ctx.code[match.end() :]
        if patched == ctx.code:
            return None

        return PatchResult(
            patched_code=patched,
            patcher_id=self.id,
            patch_summary="wrapped string literal return with Number(...) for TS2322",
        )
