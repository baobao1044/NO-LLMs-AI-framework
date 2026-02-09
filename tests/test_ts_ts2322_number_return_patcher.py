import unittest

from core.patchers.base import PatchContext
from core.patchers_ts.ts_ts2322_number_return_patcher import TsTs2322NumberReturnPatcher


class TsTs2322NumberReturnPatcherTests(unittest.TestCase):
    def test_can_apply_for_ts2322_number_mismatch(self) -> None:
        patcher = TsTs2322NumberReturnPatcher()
        ctx = PatchContext(
            task_id="ts2322_case",
            prompt="",
            code='export function to_number(): number {\n  return "42";\n}\n',
            failure_type="ts_type_error",
            error_signature="TS2322:Type 'string' is not assignable to type 'number'.",
            error_message="Type 'string' is not assignable to type 'number'.",
            task_payload={"function_name": "to_number"},
            language="ts",
        )

        self.assertTrue(patcher.can_apply(ctx))

    def test_apply_wraps_return_literal(self) -> None:
        patcher = TsTs2322NumberReturnPatcher()
        ctx = PatchContext(
            task_id="ts2322_apply",
            prompt="",
            code='export function to_number(): number {\n  return "12";\n}\n',
            failure_type="ts_type_error",
            error_signature="TS2322:Type 'string' is not assignable to type 'number'.",
            error_message="Type 'string' is not assignable to type 'number'.",
            task_payload={"function_name": "to_number"},
            language="ts",
        )

        result = patcher.apply(ctx)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn('return Number("12");', result.patched_code)
        self.assertEqual(result.patcher_id, "ts_ts2322_number_return_patcher")


if __name__ == "__main__":
    unittest.main()
