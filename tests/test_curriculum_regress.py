import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.agent import AgentLoop
from core.logger import JsonlLogger
from core.task import CodeTask
from core.verifier import FunctionCase, FunctionVerifier


class CurriculumAndRegressionTests(unittest.TestCase):
    def test_curriculum_orders_easy_to_hard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            log_file = root / "events.jsonl"
            logger = JsonlLogger(log_file)

            easy_task = CodeTask(
                task_id="easy_mul",
                prompt="mul(a,b)",
                target_file=root / "easy.py",
                attempts=["def mul(a, b):\n    return a * b\n"],
            )
            easy_verifier = FunctionVerifier(
                function_name="mul",
                cases=[FunctionCase(args=(2, 3), expected=6)],
            )
            AgentLoop().run(task=easy_task, verifier=easy_verifier, logger=logger)

            hard_task = CodeTask(
                task_id="hard_add",
                prompt="add(a,b)",
                target_file=root / "hard.py",
                attempts=[
                    "def add(a, b):\n    return a - b\n",
                    "def add(a, b):\n    return a * b\n",
                    "def add(a, b):\n    return a + b\n",
                ],
            )
            hard_verifier = FunctionVerifier(
                function_name="add",
                cases=[FunctionCase(args=(2, 3), expected=5)],
            )
            AgentLoop().run(task=hard_task, verifier=hard_verifier, logger=logger)

            out_file = root / "curriculum.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "tools/curriculum.py",
                    str(log_file),
                    "--output",
                    str(out_file),
                    "--mode",
                    "easy_to_hard",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            payload = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["task_count"], 2)
            self.assertEqual(payload["tasks"][0]["task_id"], "easy_mul")
            self.assertEqual(payload["tasks"][1]["task_id"], "hard_add")

    def test_regression_gate_detects_pass_rate_drop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            golden_ok = root / "golden_ok.json"
            golden_bad = root / "golden_bad.json"
            baseline = root / "baseline.json"

            golden_ok.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "g1",
                                "prompt": "add(a,b)",
                                "attempts": [
                                    "def add(a, b):\n    return a - b\n",
                                    "def add(a, b):\n    return a + b\n",
                                ],
                                "verifier": {
                                    "function_name": "add",
                                    "cases": [{"args": [1, 2], "expected": 3}],
                                },
                            },
                            {
                                "task_id": "g2",
                                "prompt": "mul(a,b)",
                                "attempts": ["def mul(a, b):\n    return a * b\n"],
                                "verifier": {
                                    "function_name": "mul",
                                    "cases": [{"args": [2, 3], "expected": 6}],
                                },
                            },
                        ]
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )

            golden_bad.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "g1",
                                "prompt": "add(a,b)",
                                "attempts": [
                                    "def add(a, b):\n    return a - b\n",
                                    "def add(a, b):\n    return a - b\n",
                                ],
                                "verifier": {
                                    "function_name": "add",
                                    "cases": [{"args": [1, 2], "expected": 3}],
                                },
                            },
                            {
                                "task_id": "g2",
                                "prompt": "mul(a,b)",
                                "attempts": ["def mul(a, b):\n    return a * b\n"],
                                "verifier": {
                                    "function_name": "mul",
                                    "cases": [{"args": [2, 3], "expected": 6}],
                                },
                            },
                        ]
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )

            init_proc = subprocess.run(
                [
                    sys.executable,
                    "tools/regress.py",
                    "--golden-set",
                    str(golden_ok),
                    "--baseline",
                    str(baseline),
                    "--update-baseline",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(init_proc.returncode, 0)
            self.assertIn("baseline_update=enabled", init_proc.stdout)

            pass_proc = subprocess.run(
                [
                    sys.executable,
                    "tools/regress.py",
                    "--golden-set",
                    str(golden_ok),
                    "--baseline",
                    str(baseline),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(pass_proc.returncode, 0)
            self.assertIn("regression=PASS", pass_proc.stdout)

            fail_proc = subprocess.run(
                [
                    sys.executable,
                    "tools/regress.py",
                    "--golden-set",
                    str(golden_bad),
                    "--baseline",
                    str(baseline),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(fail_proc.returncode, 1)
            self.assertIn("regression=FAIL", fail_proc.stdout)
            self.assertIn("pass_rate regression", fail_proc.stdout)

    def test_regression_gate_reads_generated_task_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            generated = root / "generated_tasks.json"
            baseline = root / "generated_baseline.json"

            gen_proc = subprocess.run(
                [
                    sys.executable,
                    "tools/generate_tasks.py",
                    "--out",
                    str(generated),
                    "--seed",
                    "101",
                    "--count",
                    "5",
                    "--templates",
                    "add,sub,mul,clamp,is_palindrome",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(gen_proc.returncode, 0)

            baseline_proc = subprocess.run(
                [
                    sys.executable,
                    "tools/regress.py",
                    "--golden-set",
                    str(generated),
                    "--baseline",
                    str(baseline),
                    "--update-baseline",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(baseline_proc.returncode, 0)
            self.assertTrue(baseline.exists())

            pass_proc = subprocess.run(
                [
                    sys.executable,
                    "tools/regress.py",
                    "--golden-set",
                    str(generated),
                    "--baseline",
                    str(baseline),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(pass_proc.returncode, 0)
            self.assertIn("regression=PASS", pass_proc.stdout)

    def test_regression_gate_supports_ts_golden_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            golden_ts = root / "golden_ts.json"
            baseline = root / "baseline_ts.json"
            golden_ts.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "ts_add_regress",
                                "language": "ts",
                                "prompt": "add(a,b)",
                                "target_file": "src/solution.ts",
                                "function_name": "add",
                                "signature": "(a: number, b: number) => number",
                                "testcases": [
                                    {"inputs": [1, 2], "expected": 3},
                                    {"inputs": [5, 6], "expected": 11},
                                ],
                                "attempts": [
                                    "function add(a: number, b: number): number {\n  return a + b;\n}\n",
                                ],
                            }
                        ]
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )

            baseline_proc = subprocess.run(
                [
                    sys.executable,
                    "tools/regress.py",
                    "--golden-set",
                    str(golden_ts),
                    "--baseline",
                    str(baseline),
                    "--update-baseline",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(baseline_proc.returncode, 0)
            self.assertTrue(baseline.exists())

            pass_proc = subprocess.run(
                [
                    sys.executable,
                    "tools/regress.py",
                    "--golden-set",
                    str(golden_ts),
                    "--baseline",
                    str(baseline),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(pass_proc.returncode, 0)
            self.assertIn("regression=PASS", pass_proc.stdout)

    def test_regression_gate_from_log_with_flaky_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            baseline_log = root / "baseline.jsonl"
            current_log = root / "current.jsonl"
            baseline_file = root / "baseline_metrics.json"
            quarantine_file = root / "flaky_quarantine.json"

            baseline_records = [
                {
                    "run_id": "r1",
                    "attempt_index": 1,
                    "task_id": "t1",
                    "language": "py",
                    "passed": False,
                    "failure_type": "syntax_error",
                    "error_signature": "SyntaxError: expected ':'",
                    "verifier_stage_failed": "syntax",
                },
                {
                    "run_id": "r1",
                    "attempt_index": 2,
                    "task_id": "t1",
                    "language": "py",
                    "passed": True,
                    "failure_type": None,
                    "error_signature": None,
                    "verifier_stage_failed": None,
                },
            ]
            current_records = baseline_records + [
                {
                    "run_id": "r2",
                    "attempt_index": 1,
                    "task_id": "t2",
                    "language": "py",
                    "passed": False,
                    "failure_type": "syntax_error",
                    "error_signature": "SyntaxError: expected ':'",
                    "verifier_stage_failed": "syntax",
                },
                {
                    "run_id": "r2",
                    "attempt_index": 2,
                    "task_id": "t2",
                    "language": "py",
                    "passed": True,
                    "failure_type": None,
                    "error_signature": None,
                    "verifier_stage_failed": None,
                },
            ]

            with baseline_log.open("w", encoding="utf-8") as handle:
                for record in baseline_records:
                    handle.write(json.dumps(record, ensure_ascii=True) + "\n")
            with current_log.open("w", encoding="utf-8") as handle:
                for record in current_records:
                    handle.write(json.dumps(record, ensure_ascii=True) + "\n")

            init_proc = subprocess.run(
                [
                    sys.executable,
                    "tools/regress.py",
                    "--from-log",
                    str(baseline_log),
                    "--baseline",
                    str(baseline_file),
                    "--update-baseline",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(init_proc.returncode, 0)

            fail_proc = subprocess.run(
                [
                    sys.executable,
                    "tools/regress.py",
                    "--from-log",
                    str(current_log),
                    "--baseline",
                    str(baseline_file),
                    "--failure-spike",
                    "0",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(fail_proc.returncode, 1)
            self.assertIn("failure_type regression", fail_proc.stdout)

            quarantine_file.write_text(
                json.dumps(
                    {
                        "flaky_groups": [
                            {
                                "language": "py",
                                "failure_type": "syntax_error",
                                "error_signature": "SyntaxError: expected ':'",
                                "verifier_stage_failed": "syntax",
                            }
                        ]
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )

            pass_proc = subprocess.run(
                [
                    sys.executable,
                    "tools/regress.py",
                    "--from-log",
                    str(current_log),
                    "--baseline",
                    str(baseline_file),
                    "--failure-spike",
                    "0",
                    "--flaky-quarantine",
                    str(quarantine_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(pass_proc.returncode, 0)
            self.assertIn("regression=PASS", pass_proc.stdout)


if __name__ == "__main__":
    unittest.main()
