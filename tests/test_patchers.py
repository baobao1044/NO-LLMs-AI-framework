import unittest

from core.patchers import PatchContext
from core.patchers.add_return_patcher import AddReturnPatcher
from core.patchers.indentation_patcher import IndentationPatcher
from core.patchers.missing_import_patcher import MissingImportPatcher
from core.patchers.rename_symbol_patcher import RenameSymbolPatcher
from core.patchers.syntax_fix_patcher import SyntaxFixPatcher


class PatcherUnitTests(unittest.TestCase):
    def test_syntax_fix_patcher_adds_colon(self) -> None:
        ctx = PatchContext(
            task_id="p1",
            prompt="add",
            code="def add(a, b)\n    return a + b\n",
            failure_type="syntax_error",
            error_signature="SyntaxError: expected ':'",
            error_message="expected ':'",
            task_payload={},
        )
        result = SyntaxFixPatcher().apply(ctx)
        self.assertIsNotNone(result)
        self.assertIn("def add(a, b):", result.patched_code)

    def test_indentation_patcher_indents_block(self) -> None:
        ctx = PatchContext(
            task_id="p2",
            prompt="add",
            code="def add(a, b):\nreturn a + b\n",
            failure_type="syntax_error",
            error_signature="IndentationError: expected an indented block",
            error_message="IndentationError: expected an indented block",
            task_payload={},
        )
        result = IndentationPatcher().apply(ctx)
        self.assertIsNotNone(result)
        self.assertIn("\n    return a + b", result.patched_code)

    def test_missing_import_patcher_adds_math(self) -> None:
        ctx = PatchContext(
            task_id="p3",
            prompt="area",
            code="def area(r):\n    return math.pi * r * r\n",
            failure_type="runtime_error",
            error_signature="NameError:name 'math' is not defined",
            error_message="name 'math' is not defined",
            task_payload={},
        )
        result = MissingImportPatcher().apply(ctx)
        self.assertIsNotNone(result)
        self.assertTrue(result.patched_code.startswith("import math\n"))

    def test_add_return_patcher_infers_expression(self) -> None:
        ctx = PatchContext(
            task_id="p4",
            prompt="add",
            code="def add(a, b):\n    pass\n",
            failure_type="assertion_fail",
            error_signature="AssertionError: case 1 mismatch: args=(1, 2), expected=3, actual=None",
            error_message="case mismatch actual=None",
            task_payload={
                "function_name": "add",
                "cases": [
                    {"args": [1, 2], "expected": 3},
                    {"args": [2, 3], "expected": 5},
                ],
            },
        )
        result = AddReturnPatcher().apply(ctx)
        self.assertIsNotNone(result)
        self.assertIn("return a + b", result.patched_code)

    def test_rename_symbol_patcher_renames_close_match(self) -> None:
        ctx = PatchContext(
            task_id="p5",
            prompt="value",
            code="def f(value):\n    return valu + 1\n",
            failure_type="runtime_error",
            error_signature="NameError:name 'valu' is not defined",
            error_message="name 'valu' is not defined",
            task_payload={},
        )
        result = RenameSymbolPatcher().apply(ctx)
        self.assertIsNotNone(result)
        self.assertIn("return value + 1", result.patched_code)


if __name__ == "__main__":
    unittest.main()
