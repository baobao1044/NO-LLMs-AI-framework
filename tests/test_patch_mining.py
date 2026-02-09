import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.patch_mining import build_report


class PatchMiningTests(unittest.TestCase):
    def _write_fixture_log(self, path: Path) -> None:
        records = [
            {
                "run_id": "r1",
                "attempt_index": 1,
                "task_id": "t1",
                "task_prompt": "add prompt",
                "code": "def add(a,b):\n    return a-b\n",
                "passed": False,
                "failure_type": "assertion_fail",
                "error_signature": "AssertionError: mismatch add",
                "verifier_stage_failed": "unit_test",
                "error_message": "mismatch",
                "artifact_hash": "a1",
                "parent_artifact_hash": None,
                "patcher_id": None,
                "patch_applied": False,
            },
            {
                "run_id": "r1",
                "attempt_index": 2,
                "task_id": "t1",
                "task_prompt": "add prompt",
                "code": "def add(a,b):\n    return a+b\n",
                "passed": True,
                "failure_type": None,
                "error_signature": None,
                "verifier_stage_failed": None,
                "error_message": None,
                "artifact_hash": "a2",
                "parent_artifact_hash": None,
                "patcher_id": None,
                "patch_applied": False,
            },
            {
                "run_id": "r2",
                "attempt_index": 1,
                "task_id": "t2",
                "task_prompt": "syntax prompt",
                "code": "def add(a,b)\n    return a+b\n",
                "passed": False,
                "failure_type": "syntax_error",
                "error_signature": "SyntaxError: expected ':'",
                "verifier_stage_failed": "syntax",
                "error_message": "expected ':'",
                "artifact_hash": "s1",
                "parent_artifact_hash": None,
                "patcher_id": "syntax_fix_patcher",
                "patch_applied": True,
            },
            {
                "run_id": "r2",
                "attempt_index": 1,
                "task_id": "t2",
                "task_prompt": "syntax prompt",
                "code": "def add(a,b):\n    return a+b\n",
                "passed": True,
                "failure_type": None,
                "error_signature": None,
                "verifier_stage_failed": None,
                "error_message": None,
                "artifact_hash": "s2",
                "parent_artifact_hash": "s1",
                "patcher_id": "syntax_fix_patcher",
                "patch_applied": True,
            },
            {
                "run_id": "r3",
                "attempt_index": 1,
                "task_id": "t3",
                "task_prompt": "syntax prompt 2",
                "code": "def inc(x)\n    return x+1\n",
                "passed": False,
                "failure_type": "syntax_error",
                "error_signature": "SyntaxError: expected ':'",
                "verifier_stage_failed": "syntax",
                "error_message": "expected ':'",
                "artifact_hash": "s3",
                "parent_artifact_hash": None,
                "patcher_id": "syntax_fix_patcher",
                "patch_applied": True,
            },
            {
                "run_id": "r3",
                "attempt_index": 1,
                "task_id": "t3",
                "task_prompt": "syntax prompt 2",
                "code": "def inc(x):\n    return x+1\n",
                "passed": True,
                "failure_type": None,
                "error_signature": None,
                "verifier_stage_failed": None,
                "error_message": None,
                "artifact_hash": "s4",
                "parent_artifact_hash": "s3",
                "patcher_id": "syntax_fix_patcher",
                "patch_applied": True,
            },
        ]
        with path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    def test_grouping_metrics_and_ordering_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            log_file = root / "events.jsonl"
            self._write_fixture_log(log_file)
            records = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()]

            report1 = build_report(records=records, top_k=10, min_count=1)
            report2 = build_report(records=records, top_k=10, min_count=1)
            self.assertEqual(report1["groups_by_count"], report2["groups_by_count"])
            self.assertEqual(report1["groups_by_low_solve_rate"], report2["groups_by_low_solve_rate"])

            self.assertGreaterEqual(len(report1["groups_by_count"]), 2)
            first_group = report1["groups_by_count"][0]
            self.assertEqual(first_group["group_key"]["failure_type"], "syntax_error")
            self.assertEqual(first_group["count_total"], 2)
            self.assertGreater(first_group["patch_hit_rate"], 0.0)

    def test_report_files_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            log_file = root / "events.jsonl"
            self._write_fixture_log(log_file)
            script = Path(__file__).resolve().parents[1] / "tools" / "patch_mining.py"

            proc = subprocess.run(
                [sys.executable, str(script), "--log", str(log_file), "--top-k", "5", "--min-count", "1"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            reports_dir = root / "reports"
            md_files = sorted(reports_dir.glob("patch_mining_*.md"))
            json_files = sorted(reports_dir.glob("patch_mining_*.json"))
            self.assertEqual(len(md_files), 1)
            self.assertEqual(len(json_files), 1)
            payload = json.loads(json_files[0].read_text(encoding="utf-8"))
            self.assertIn("summary", payload)
            self.assertIn("coverage", payload)


if __name__ == "__main__":
    unittest.main()
