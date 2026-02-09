import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ScaffoldPatcherTests(unittest.TestCase):
    def test_creates_files_with_expected_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            script = Path(__file__).resolve().parents[1] / "tools" / "scaffold_patcher.py"

            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--language",
                    "ts",
                    "--category",
                    "type_fix",
                    "--signature",
                    "TS2322:",
                    "--name",
                    "ts_fix_ts2322",
                    "--out-dir",
                    str(root / "core" / "patchers_ts"),
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)

            patcher_file = root / "core" / "patchers_ts" / "ts_fix_ts2322_patcher.py"
            test_file = root / "tests" / "test_ts_fix_ts2322_patcher.py"
            self.assertTrue(patcher_file.exists())
            self.assertTrue(test_file.exists())

            patcher_content = patcher_file.read_text(encoding="utf-8")
            self.assertIn('PATCHER_ID = "ts_fix_ts2322_patcher"', patcher_content)
            self.assertIn('"TS2322:" in combined', patcher_content)
            self.assertIn("class TsFixTs2322Patcher", patcher_content)

            test_content = test_file.read_text(encoding="utf-8")
            self.assertIn("PatchContext", test_content)
            self.assertIn("ts_fix_ts2322_patcher", test_content)

    def test_refuses_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            script = Path(__file__).resolve().parents[1] / "tools" / "scaffold_patcher.py"
            cmd = [
                sys.executable,
                str(script),
                "--language",
                "py",
                "--category",
                "syntax_fix",
                "--name",
                "py_fix_syntax",
                "--out-dir",
                str(root / "core" / "patchers"),
            ]
            first = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)
            second = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0)
            self.assertEqual(second.returncode, 1)
            self.assertIn("refusing to overwrite", second.stdout)

    def test_force_keeps_content_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            script = Path(__file__).resolve().parents[1] / "tools" / "scaffold_patcher.py"
            cmd = [
                sys.executable,
                str(script),
                "--language",
                "py",
                "--category",
                "name_or_import",
                "--signature",
                "NameError:",
                "--name",
                "py_name_fix",
                "--out-dir",
                str(root / "core" / "patchers"),
            ]
            proc1 = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)
            self.assertEqual(proc1.returncode, 0)
            patcher_file = root / "core" / "patchers" / "py_name_fix_patcher.py"
            before = patcher_file.read_text(encoding="utf-8")

            proc2 = subprocess.run(cmd + ["--force"], cwd=root, capture_output=True, text=True, check=False)
            self.assertEqual(proc2.returncode, 0)
            after = patcher_file.read_text(encoding="utf-8")
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
