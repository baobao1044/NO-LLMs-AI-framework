from .registry import apply_first_ts, patchers_in_priority_ts
from .ts_add_return_patcher import TsAddReturnPatcher
from .ts_export_patcher import TsExportPatcher
from .ts_fix_type_annotation_patcher import TsFixTypeAnnotationPatcher
from .ts_missing_import_patcher import TsMissingImportPatcher
from .ts_rename_symbol_patcher import TsRenameSymbolPatcher
from .ts_ts2322_number_return_patcher import TsTs2322NumberReturnPatcher

__all__ = [
    "TsAddReturnPatcher",
    "TsExportPatcher",
    "TsFixTypeAnnotationPatcher",
    "TsMissingImportPatcher",
    "TsRenameSymbolPatcher",
    "TsTs2322NumberReturnPatcher",
    "apply_first_ts",
    "patchers_in_priority_ts",
]
