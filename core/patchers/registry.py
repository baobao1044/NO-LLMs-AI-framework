from __future__ import annotations

from core.patchers_ts import apply_first_ts, patchers_in_priority_ts

from .add_return_patcher import AddReturnPatcher
from .base import PatchContext, PatchResult, Patcher
from .indentation_patcher import IndentationPatcher
from .missing_import_patcher import MissingImportPatcher
from .rename_symbol_patcher import RenameSymbolPatcher
from .syntax_fix_patcher import SyntaxFixPatcher


def patchers_in_priority(language: str = "py") -> list[Patcher]:
    if language == "ts":
        return patchers_in_priority_ts()

    return [
        SyntaxFixPatcher(),
        IndentationPatcher(),
        MissingImportPatcher(),
        RenameSymbolPatcher(),
        AddReturnPatcher(),
    ]


def apply_first(ctx: PatchContext, language: str | None = None) -> PatchResult | None:
    selected_language = language or ctx.language
    if selected_language == "ts":
        return apply_first_ts(ctx)

    for patcher in patchers_in_priority(language=selected_language):
        if not patcher.can_apply(ctx):
            continue
        result = patcher.apply(ctx)
        if result is not None:
            return result
    return None
