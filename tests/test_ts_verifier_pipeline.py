import tempfile
import unittest
from pathlib import Path

from core.verifier import build_ts_composite_verifier


class TsVerifierPipelineTests(unittest.TestCase):
    def _make_source(self, root: Path, code: str) -> Path:
        source = root / "src" / "solution.ts"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(code, encoding="utf-8")
        return source

    def _build_verifier(self):
        return build_ts_composite_verifier(
            function_name="add",
            signature="(a: number, b: number) => number",
            testcases=[
                {"inputs": [2, 3], "expected": 5},
                {"inputs": [-1, 7], "expected": 6},
            ],
            timeout_seconds=2.0,
            tsc_timeout_seconds=20.0,
        )

    def test_fails_fast_on_tsc_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = self._make_source(
                root,
                "export function add(a: number, b: number): number {\n  return a + ;\n}\n",
            )
            verifier = self._build_verifier()

            result = verifier.verify(source)

            self.assertFalse(result.passed)
            self.assertEqual(result.verifier_stage_failed, "tsc")
            self.assertTrue(str(result.error_type).startswith("TS"))

    def test_fails_on_unit_test_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = self._make_source(
                root,
                "export function add(a: number, b: number): number {\n  return a - b;\n}\n",
            )
            verifier = self._build_verifier()

            result = verifier.verify(source)

            self.assertFalse(result.passed)
            self.assertEqual(result.verifier_stage_failed, "unit_test")
            self.assertEqual(result.error_type, "AssertionError")

    def test_passes_when_code_is_correct(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = self._make_source(
                root,
                "export function add(a: number, b: number): number {\n  return a + b;\n}\n",
            )
            verifier = self._build_verifier()

            result = verifier.verify(source)

            self.assertTrue(result.passed)
            self.assertIsNone(result.verifier_stage_failed)


if __name__ == "__main__":
    unittest.main()
