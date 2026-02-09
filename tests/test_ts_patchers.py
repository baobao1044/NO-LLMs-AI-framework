import unittest

from core.patchers import PatchContext
from core.patchers_ts import (
    TsAddReturnPatcher,
    TsExportPatcher,
    TsFixTypeAnnotationPatcher,
    TsMissingImportPatcher,
    TsRenameSymbolPatcher,
)


class TsPatchersTests(unittest.TestCase):
    def test_export_patcher(self) -> None:
        patcher = TsExportPatcher()
        ctx = PatchContext(
            task_id="ts_export",
            prompt="",
            code="function add(a: number, b: number): number {\n  return a + b;\n}\n",
            failure_type="assertion_fail",
            error_signature="AssertionError: missing callable 'add'",
            error_message="missing callable 'add'",
            task_payload={"function_name": "add"},
            language="ts",
        )

        result = patcher.apply(ctx)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("export function add", result.patched_code)

    def test_missing_import_patcher(self) -> None:
        patcher = TsMissingImportPatcher()
        ctx = PatchContext(
            task_id="ts_import",
            prompt="",
            code="export function load(pathname: string): string {\n  return readFileSync(pathname, 'utf-8');\n}\n",
            failure_type="ts_name_error",
            error_signature="TS2304:Cannot find name 'readFileSync'.",
            error_message="Cannot find name 'readFileSync'.",
            task_payload={"function_name": "load"},
            language="ts",
        )

        result = patcher.apply(ctx)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn('const { readFileSync } = require("fs");', result.patched_code)

    def test_fix_type_annotation_patcher(self) -> None:
        patcher = TsFixTypeAnnotationPatcher()
        ctx = PatchContext(
            task_id="ts_types",
            prompt="",
            code="export function add(a, b) {\n  return a + b;\n}\n",
            failure_type="ts_type_error",
            error_signature="TS7006:Parameter 'a' implicitly has an 'any' type.",
            error_message="Parameter 'a' implicitly has an 'any' type.",
            task_payload={
                "function_name": "add",
                "signature": "(a: number, b: number) => number",
            },
            language="ts",
        )

        result = patcher.apply(ctx)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("function add(a: number, b: number): number", result.patched_code)

    def test_rename_symbol_patcher(self) -> None:
        patcher = TsRenameSymbolPatcher()
        ctx = PatchContext(
            task_id="ts_rename",
            prompt="",
            code="export function add(a: number, b: number): number {\n  return ad + b;\n}\n",
            failure_type="ts_name_error",
            error_signature="TS2552:Cannot find name 'ad'. Did you mean 'a'?",
            error_message="Cannot find name 'ad'. Did you mean 'a'?",
            task_payload={"function_name": "add"},
            language="ts",
        )

        result = patcher.apply(ctx)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("return a + b", result.patched_code)

    def test_add_return_patcher(self) -> None:
        patcher = TsAddReturnPatcher()
        ctx = PatchContext(
            task_id="ts_return",
            prompt="",
            code="export function add(a: number, b: number): number {\n  const out = a + b;\n}\n",
            failure_type="assertion_fail",
            error_signature="AssertionError: case 1 mismatch: expected=5 actual=undefined",
            error_message="case 1 mismatch: expected=5 actual=undefined",
            task_payload={
                "function_name": "add",
                "testcases": [{"inputs": [2, 3], "expected": 5}],
            },
            language="ts",
        )

        result = patcher.apply(ctx)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("return a + b;", result.patched_code)


if __name__ == "__main__":
    unittest.main()
