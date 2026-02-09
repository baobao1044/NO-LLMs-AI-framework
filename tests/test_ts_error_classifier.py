import unittest
from pathlib import Path

from core.error_classifier_ts import classify_tsc_output


class TsErrorClassifierTests(unittest.TestCase):
    def _read_fixture(self, name: str) -> str:
        root = Path(__file__).resolve().parent
        return (root / "fixtures" / "tsc_outputs" / name).read_text(encoding="utf-8")

    def test_maps_syntax_error(self) -> None:
        diagnostic = classify_tsc_output(self._read_fixture("syntax_error.txt"))
        self.assertEqual(diagnostic.failure_type, "ts_syntax_error")
        self.assertEqual(diagnostic.error_type, "TS1005")
        self.assertEqual(diagnostic.error_signature, "TS1005:';' expected.")

    def test_maps_type_error(self) -> None:
        diagnostic = classify_tsc_output(self._read_fixture("type_error.txt"))
        self.assertEqual(diagnostic.failure_type, "ts_type_error")
        self.assertEqual(diagnostic.error_type, "TS2322")
        self.assertIn("not assignable", diagnostic.error_signature)

    def test_maps_name_error(self) -> None:
        diagnostic = classify_tsc_output(self._read_fixture("name_error.txt"))
        self.assertEqual(diagnostic.failure_type, "ts_name_error")
        self.assertEqual(diagnostic.error_type, "TS2304")
        self.assertEqual(diagnostic.error_signature, "TS2304:Cannot find name 'missingVar'.")


if __name__ == "__main__":
    unittest.main()
