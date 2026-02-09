import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.agent import AgentLoop
from core.logger import JsonlLogger
from core.task import CodeTask
from core.verifier import (
    FunctionCase,
    FunctionVerifier,
    build_composite_function_verifier,
    build_ts_composite_verifier,
)


class ToolsTests(unittest.TestCase):
    def test_replay_reports_full_match_with_patch_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            log_file = root / "events.jsonl"
            task = CodeTask(
                task_id="replay_t1",
                prompt="add(a,b)",
                target_file=root / "solution.py",
                attempts=["def add(a, b)\n    return a + b\n"],
            )
            verifier = FunctionVerifier(
                function_name="add",
                cases=[FunctionCase(args=(4, 5), expected=9)],
            )
            AgentLoop().run(task=task, verifier=verifier, logger=JsonlLogger(log_file))

            proc = subprocess.run(
                [sys.executable, "tools/replay.py", str(log_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("replay_eligible=2", proc.stdout)
            self.assertIn("replay_match=2/2 (100.00%)", proc.stdout)
            self.assertIn("unreplayable_lossy=0", proc.stdout)
            self.assertIn("env_fingerprint_mismatch_count=", proc.stdout)

    def test_replay_marks_lossy_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            log_file = root / "events.jsonl"
            marker = object()
            task = CodeTask(
                task_id="replay_lossy_t1",
                prompt="echo(x)",
                target_file=root / "solution.py",
                attempts=["def echo(x):\n    return x\n"],
            )
            verifier = FunctionVerifier(
                function_name="echo",
                cases=[FunctionCase(args=(marker,), expected=marker)],
            )
            AgentLoop().run(task=task, verifier=verifier, logger=JsonlLogger(log_file))

            proc = subprocess.run(
                [sys.executable, "tools/replay.py", str(log_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("replay_eligible=0", proc.stdout)
            self.assertIn("unreplayable_lossy=1", proc.stdout)

    def test_replay_json_out_has_timeout_rate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            log_file = root / "events.jsonl"
            metrics_out = root / "replay_metrics.json"
            task = CodeTask(
                task_id="replay_timeout_t1",
                prompt="spin(x)",
                target_file=root / "solution.py",
                attempts=["def spin(x):\n    while True:\n        pass\n"],
            )
            verifier = build_composite_function_verifier(
                function_name="spin",
                cases=[FunctionCase(args=(1,), expected=1)],
                timeout_seconds=0.1,
            )
            AgentLoop().run(task=task, verifier=verifier, logger=JsonlLogger(log_file))

            proc = subprocess.run(
                [sys.executable, "tools/replay.py", str(log_file), "--json-out", str(metrics_out)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertTrue(metrics_out.exists())
            payload = json.loads(metrics_out.read_text(encoding="utf-8"))
            self.assertGreater(payload["timeout_rate"], 0.0)
            self.assertIn("flaky_groups", payload)

    def test_replay_handles_ts_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            log_file = root / "events.jsonl"
            task = CodeTask(
                task_id="replay_ts_t1",
                prompt="add(a,b)",
                target_file=root / "src" / "solution.ts",
                attempts=["function add(a: number, b: number): number {\n  return a + b;\n}\n"],
                language="ts",
            )
            verifier = build_ts_composite_verifier(
                function_name="add",
                signature="(a: number, b: number) => number",
                testcases=[{"inputs": [1, 2], "expected": 3}],
            )
            AgentLoop().run(task=task, verifier=verifier, logger=JsonlLogger(log_file))

            proc = subprocess.run(
                [sys.executable, "tools/replay.py", str(log_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("replay_eligible=2", proc.stdout)
            self.assertIn("replay_match=2/2 (100.00%)", proc.stdout)

    def test_stats_reports_patch_analytics_and_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            log_file = root / "events.jsonl"
            task = CodeTask(
                task_id="stats_t1",
                prompt="add(a,b)",
                target_file=root / "solution.py",
                attempts=["def add(a, b)\n    return a + b\n"],
            )
            verifier = FunctionVerifier(
                function_name="add",
                cases=[FunctionCase(args=(1, 1), expected=2)],
            )
            AgentLoop().run(task=task, verifier=verifier, logger=JsonlLogger(log_file))

            proc = subprocess.run(
                [sys.executable, "tools/stats.py", str(log_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("failure_type_breakdown:", proc.stdout)
            self.assertIn("patch_success_rate_by_patcher:", proc.stdout)
            self.assertIn("syntax_fix_patcher", proc.stdout)
            self.assertIn("signature_coverage=", proc.stdout)
            self.assertIn("top_uncovered_signatures:", proc.stdout)
            self.assertIn("verifier_stage_breakdown:", proc.stdout)
            self.assertIn("median_attempts_per_task:", proc.stdout)
            self.assertIn("attempts_saved_by_patchers_approx=", proc.stdout)


if __name__ == "__main__":
    unittest.main()
