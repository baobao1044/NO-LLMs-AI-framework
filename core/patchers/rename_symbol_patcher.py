from __future__ import annotations

import ast
import re

from .base import PatchContext, PatchResult


class RenameSymbolPatcher:
    id = "rename_symbol_patcher"

    _NAME_RE = re.compile(r"name '([A-Za-z_][A-Za-z0-9_]*)' is not defined")

    def can_apply(self, ctx: PatchContext) -> bool:
        signature = (ctx.error_signature or "") + " " + (ctx.error_message or "")
        return "NameError" in signature

    def apply(self, ctx: PatchContext) -> PatchResult | None:
        combined = (ctx.error_signature or "") + " " + (ctx.error_message or "")
        match = self._NAME_RE.search(combined)
        if not match:
            return None
        missing = match.group(1)

        try:
            tree = ast.parse(ctx.code)
        except SyntaxError:
            return None

        symbols = sorted(self._collect_symbols(tree))
        if missing in symbols:
            return None

        best = None
        for symbol in symbols:
            distance = self._levenshtein(missing, symbol)
            if distance > 2:
                continue
            key = (distance, len(symbol), symbol)
            if best is None or key < best[0]:
                best = (key, symbol)

        if best is None:
            return None
        replacement = best[1]

        pattern = re.compile(rf"\b{re.escape(missing)}\b")
        patched, count = pattern.subn(replacement, ctx.code, count=1)
        if count == 0 or patched == ctx.code:
            return None

        return PatchResult(
            patched_code=patched,
            patcher_id=self.id,
            patch_summary=f"renamed symbol {missing} -> {replacement}",
        )

    def _collect_symbols(self, tree: ast.AST) -> set[str]:
        symbols: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                symbols.add(node.name)
                for arg in node.args.args:
                    symbols.add(arg.arg)
            elif isinstance(node, ast.ClassDef):
                symbols.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        symbols.add(target.id)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    symbols.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    symbols.add(alias.asname or alias.name)
        return symbols

    def _levenshtein(self, a: str, b: str) -> int:
        if a == b:
            return 0
        if not a:
            return len(b)
        if not b:
            return len(a)
        prev = list(range(len(b) + 1))
        for i, char_a in enumerate(a, start=1):
            curr = [i]
            for j, char_b in enumerate(b, start=1):
                ins = curr[j - 1] + 1
                delete = prev[j] + 1
                sub = prev[j - 1] + (0 if char_a == char_b else 1)
                curr.append(min(ins, delete, sub))
            prev = curr
        return prev[-1]
