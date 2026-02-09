from __future__ import annotations

import re

from core.patchers.base import PatchContext, PatchResult


class TsFixTypeAnnotationPatcher:
    id = "ts_fix_type_annotation_patcher"

    _FUNC_RE_TEMPLATE = r"^(\s*)(export\s+)?function\s+{name}\s*\([^)]*\)\s*(?::\s*[^\s{{]+)?\s*\{{"

    def can_apply(self, ctx: PatchContext) -> bool:
        if ctx.language != "ts":
            return False
        signature = (ctx.error_signature or "") + " " + (ctx.error_message or "")
        return "TS7006" in signature or "TS2322" in signature or ctx.failure_type == "ts_type_error"

    def apply(self, ctx: PatchContext) -> PatchResult | None:
        payload = ctx.task_payload or {}
        function_name = str(payload.get("function_name") or "")
        signature = payload.get("signature")
        if not function_name or not isinstance(signature, str):
            return None

        parsed = self._parse_signature(signature)
        if parsed is None:
            return None
        params, return_type = parsed
        pattern = re.compile(self._FUNC_RE_TEMPLATE.format(name=re.escape(function_name)))

        lines = ctx.code.splitlines()
        for idx, line in enumerate(lines):
            match = pattern.match(line)
            if not match:
                continue
            indent = match.group(1)
            exported = "export " if match.group(2) else ""
            replacement = f"{indent}{exported}function {function_name}({params}): {return_type} {{"
            if replacement == line:
                return None
            lines[idx] = replacement
            trailing = "\n" if ctx.code.endswith("\n") else ""
            return PatchResult(
                patched_code="\n".join(lines) + trailing,
                patcher_id=self.id,
                patch_summary=f"updated type annotations for '{function_name}'",
            )

        return None

    def _parse_signature(self, signature: str) -> tuple[str, str] | None:
        match = re.match(r"^\((?P<params>.*)\)\s*=>\s*(?P<ret>.+)$", signature.strip())
        if not match:
            return None
        params = " ".join(match.group("params").split())
        ret = " ".join(match.group("ret").split())
        if not params and not ret:
            return None
        return params, ret
