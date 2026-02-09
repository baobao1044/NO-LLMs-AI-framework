from __future__ import annotations

from .base import PatchContext, PatchResult


class AddReturnPatcher:
    id = "add_return_patcher"

    def can_apply(self, ctx: PatchContext) -> bool:
        if ctx.failure_type != "assertion_fail":
            return False
        signature = (ctx.error_signature or "") + " " + (ctx.error_message or "")
        return "actual=None" in signature.replace(" ", "")

    def apply(self, ctx: PatchContext) -> PatchResult | None:
        payload = ctx.task_payload or {}
        function_name = payload.get("function_name")
        cases = payload.get("cases", [])
        if not function_name or not isinstance(cases, list):
            return None

        expr = self._infer_return_expression(function_name=function_name, cases=cases)
        if expr is None:
            return None

        lines = ctx.code.splitlines()
        header_idx = None
        header_indent = 0
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(f"def {function_name}("):
                header_idx = idx
                header_indent = len(line) - len(line.lstrip(" "))
                break
        if header_idx is None:
            return None

        next_idx = header_idx + 1
        body_idx = None
        while next_idx < len(lines):
            if not lines[next_idx].strip():
                next_idx += 1
                continue
            indent = len(lines[next_idx]) - len(lines[next_idx].lstrip(" "))
            if indent <= header_indent:
                break
            body_idx = next_idx
            break

        if body_idx is not None and lines[body_idx].strip() == "pass":
            lines[body_idx] = " " * (header_indent + 4) + f"return {expr}"
        else:
            insert_idx = header_idx + 1
            while insert_idx < len(lines):
                if not lines[insert_idx].strip():
                    insert_idx += 1
                    continue
                indent = len(lines[insert_idx]) - len(lines[insert_idx].lstrip(" "))
                if indent <= header_indent:
                    break
                insert_idx += 1
            lines.insert(insert_idx, " " * (header_indent + 4) + f"return {expr}")

        patched = "\n".join(lines) + ("\n" if ctx.code.endswith("\n") else "")
        return PatchResult(
            patched_code=patched,
            patcher_id=self.id,
            patch_summary=f"added return {expr}",
        )

    def _infer_return_expression(self, function_name: str, cases: list[dict]) -> str | None:
        values = []
        for case in cases:
            args = case.get("args")
            expected = case.get("expected")
            if not isinstance(args, list):
                return None
            values.append((args, expected))

        if not values:
            return None

        if all(
            len(args) == 2
            and isinstance(args[0], (int, float))
            and isinstance(args[1], (int, float))
            and isinstance(expected, (int, float))
            for args, expected in values
        ):
            if all(abs((args[0] + args[1]) - expected) < 1e-9 for args, expected in values):
                return "a + b"
            if all(abs((args[0] * args[1]) - expected) < 1e-9 for args, expected in values):
                return "a * b"

        if all(
            len(args) == 1
            and isinstance(args[0], (int, float))
            and isinstance(expected, (int, float))
            for args, expected in values
        ):
            if all(abs((args[0] + 1) - expected) < 1e-9 for args, expected in values):
                return "x + 1"

        # Very constrained fallback for common "add" task.
        if function_name == "add":
            return "a + b"
        return None
