import tempfile
import unittest
from pathlib import Path

from core.verifier import FunctionCase, build_composite_function_verifier


class VerifierPipelineTests(unittest.TestCase):
    def test_composite_reports_syntax_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "candidate.py"
            source.write_text("def add(a, b)\n    return a + b\n", encoding="utf-8")
            verifier = build_composite_function_verifier(
                function_name="add",
                cases=[FunctionCase(args=(1, 2), expected=3)],
                timeout_seconds=0.2,
            )
            result = verifier.verify(source)
            self.assertFalse(result.passed)
            self.assertEqual(result.verifier_stage_failed, "syntax")

    def test_composite_reports_timeout_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "candidate.py"
            source.write_text(
                "def spin(x):\n"
                "    while True:\n"
                "        pass\n",
                encoding="utf-8",
            )
            verifier = build_composite_function_verifier(
                function_name="spin",
                cases=[FunctionCase(args=(1,), expected=1)],
                timeout_seconds=0.1,
            )
            result = verifier.verify(source)
            self.assertFalse(result.passed)
            self.assertEqual(result.verifier_stage_failed, "timeout")

    def test_composite_passes_and_has_no_failed_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "candidate.py"
            source.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
            verifier = build_composite_function_verifier(
                function_name="add",
                cases=[FunctionCase(args=(1, 2), expected=3)],
                timeout_seconds=0.2,
            )
            result = verifier.verify(source)
            self.assertTrue(result.passed)
            self.assertIsNone(result.verifier_stage_failed)


if __name__ == "__main__":
    unittest.main()
