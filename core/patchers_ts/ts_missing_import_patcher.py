from __future__ import annotations

import re

from core.patchers.base import PatchContext, PatchResult


class TsMissingImportPatcher:
    id = "ts_missing_import_patcher"

    _NAME_RE = re.compile(r"Cannot find name '([A-Za-z_][A-Za-z0-9_]*)'")
    _ALLOWLIST = {
        "fs": 'const fs = require("fs");',
        "path": 'const path = require("path");',
        "readFileSync": 'const { readFileSync } = require("fs");',
    }

    def can_apply(self, ctx: PatchContext) -> bool:
        if ctx.language != "ts":
            return False
        signature = (ctx.error_signature or "") + " " + (ctx.error_message or "")
        return "TS2304" in signature or "ts_name_error" in signature

    def apply(self, ctx: PatchContext) -> PatchResult | None:
        combined = (ctx.error_signature or "") + " " + (ctx.error_message or "")
        match = self._NAME_RE.search(combined)
        if not match:
            return None

        symbol = match.group(1)
        import_stmt = self._ALLOWLIST.get(symbol)
        if import_stmt is None:
            return None

        lines = ctx.code.splitlines()
        if any(line.strip() == import_stmt for line in lines):
            return None

        insert_idx = 0
        while insert_idx < len(lines):
            stripped = lines[insert_idx].strip()
            if not stripped or stripped.startswith("//"):
                insert_idx += 1
                continue
            break
        lines.insert(insert_idx, import_stmt)
        trailing = "\n" if ctx.code.endswith("\n") else ""
        return PatchResult(
            patched_code="\n".join(lines) + trailing,
            patcher_id=self.id,
            patch_summary=f"added import for '{symbol}'",
        )
