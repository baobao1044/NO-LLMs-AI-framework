from __future__ import annotations

import re

from core.patchers.base import PatchContext, PatchResult


class TsExportPatcher:
    id = "ts_export_patcher"

    def can_apply(self, ctx: PatchContext) -> bool:
        if ctx.language != "ts":
            return False
        message = (ctx.error_message or "") + " " + (ctx.error_signature or "")
        if "missing callable" in message:
            return True
        function_name = str((ctx.task_payload or {}).get("function_name") or "")
        return bool(function_name and re.search(rf"\bfunction\s+{re.escape(function_name)}\s*\(", ctx.code))

    def apply(self, ctx: PatchContext) -> PatchResult | None:
        function_name = str((ctx.task_payload or {}).get("function_name") or "")
        if not function_name:
            return None

        exported_pattern = re.compile(rf"^\s*export\s+function\s+{re.escape(function_name)}\s*\(")
        if any(exported_pattern.search(line) for line in ctx.code.splitlines()):
            return None

        pattern = re.compile(rf"^(\s*)function\s+({re.escape(function_name)}\s*\()")
        lines = ctx.code.splitlines()
        for idx, line in enumerate(lines):
            patched = pattern.sub(r"\1export function \2", line, count=1)
            if patched != line:
                lines[idx] = patched
                trailing = "\n" if ctx.code.endswith("\n") else ""
                return PatchResult(
                    patched_code="\n".join(lines) + trailing,
                    patcher_id=self.id,
                    patch_summary=f"exported function '{function_name}'",
                )

        return None
