from __future__ import annotations

from core.patchers.base import PatchContext, PatchResult, Patcher

from .ts_add_return_patcher import TsAddReturnPatcher
from .ts_export_patcher import TsExportPatcher
from .ts_fix_type_annotation_patcher import TsFixTypeAnnotationPatcher
from .ts_missing_import_patcher import TsMissingImportPatcher
from .ts_rename_symbol_patcher import TsRenameSymbolPatcher
from .ts_ts2322_number_return_patcher import TsTs2322NumberReturnPatcher


def patchers_in_priority_ts() -> list[Patcher]:
    return [
        TsExportPatcher(),
        TsRenameSymbolPatcher(),
        TsMissingImportPatcher(),
        TsTs2322NumberReturnPatcher(),
        TsFixTypeAnnotationPatcher(),
        TsAddReturnPatcher(),
    ]


def apply_first_ts(ctx: PatchContext) -> PatchResult | None:
    for patcher in patchers_in_priority_ts():
        if not patcher.can_apply(ctx):
            continue
        result = patcher.apply(ctx)
        if result is not None:
            return result
    return None
