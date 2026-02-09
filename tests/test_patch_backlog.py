import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.build_patch_backlog import build_backlog


class PatchBacklogTests(unittest.TestCase):
    def _fixture_records(self) -> list[dict]:
        records: list[dict] = []

        # Group A: TS2322 type errors, unsolved, no patch hit.
        for run_id in ["ts_a1", "ts_a2", "ts_a3"]:
            records.append(
                {
                    "run_id": run_id,
                    "attempt_index": 1,
                    "language": "ts",
                    "task_id": f"task_{run_id}",
                    "task_prompt": "fix type",
                    "code": "export function f(x: number): number { return 'x' as any; }",
                    "passed": False,
                    "failure_type": "ts_type_error",
                    "error_signature": "TS2322:Type 'string' is not assignable to type 'number'.",
                    "verifier_stage_failed": "tsc",
                    "error_message": "Type 'string' is not assignable to type 'number'.",
                    "artifact_hash": f"a_{run_id}",
                    "parent_artifact_hash": None,
                    "patcher_id": None,
                    "patch_applied": False,
                }
            )

        # Group B: Python syntax errors, partially solved via second attempt in two runs.
        for run_id, solved in [("py_b1", False), ("py_b2", False), ("py_b3", True), ("py_b4", True)]:
            artifact = f"b_{run_id}_1"
            records.append(
                {
                    "run_id": run_id,
                    "attempt_index": 1,
                    "language": "py",
                    "task_id": f"task_{run_id}",
                    "task_prompt": "fix syntax",
                    "code": "def add(a, b)\n    return a + b\n",
                    "passed": False,
                    "failure_type": "syntax_error",
                    "error_signature": "SyntaxError:expected ':'",
                    "verifier_stage_failed": "syntax",
                    "error_message": "expected ':'",
                    "artifact_hash": artifact,
                    "parent_artifact_hash": None,
                    "patcher_id": None,
                    "patch_applied": False,
                }
            )
            if solved:
                records.append(
                    {
                        "run_id": run_id,
                        "attempt_index": 2,
                        "language": "py",
                        "task_id": f"task_{run_id}",
                        "task_prompt": "fix syntax",
                        "code": "def add(a, b):\n    return a + b\n",
                        "passed": True,
                        "failure_type": None,
                        "error_signature": None,
                        "verifier_stage_failed": None,
                        "error_message": None,
                        "artifact_hash": f"b_{run_id}_2",
                        "parent_artifact_hash": artifact,
                        "patcher_id": None,
                        "patch_applied": False,
                    }
                )

        return records

    def test_priority_and_category_are_stable(self) -> None:
        records = self._fixture_records()
        rows1 = build_backlog(
            records=records,
            language="all",
            top_k=10,
            min_count=1,
            solve_rate_threshold=0.95,
            patch_success_threshold=0.5,
        )
        rows2 = build_backlog(
            records=records,
            language="all",
            top_k=10,
            min_count=1,
            solve_rate_threshold=0.95,
            patch_success_threshold=0.5,
        )
        self.assertEqual(rows1, rows2)
        self.assertGreaterEqual(len(rows1), 2)

        self.assertEqual(rows1[0]["language"], "ts")
        self.assertEqual(rows1[0]["suggested_category"], "type_fix")
        self.assertEqual(rows1[1]["language"], "py")
        self.assertEqual(rows1[1]["suggested_category"], "syntax_fix")

    def test_cli_writes_json_and_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            log_file = root / "events.jsonl"
            out_file = root / "patch_backlog_all.json"
            reports_dir = root / "reports"

            with log_file.open("w", encoding="utf-8") as handle:
                for record in self._fixture_records():
                    handle.write(json.dumps(record, ensure_ascii=True) + "\n")

            script = Path(__file__).resolve().parents[1] / "tools" / "build_patch_backlog.py"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--log",
                    str(log_file),
                    "--language",
                    "all",
                    "--top-k",
                    "10",
                    "--min-count",
                    "1",
                    "--out",
                    str(out_file),
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertTrue(out_file.exists())

            payload = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertIn("items", payload)
            self.assertGreaterEqual(len(payload["items"]), 2)

            md_files = list(reports_dir.glob("patch_backlog_*.md"))
            self.assertEqual(len(md_files), 1)


if __name__ == "__main__":
    unittest.main()
