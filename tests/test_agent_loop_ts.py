import json
import tempfile
import unittest
from pathlib import Path

from core.agent import AgentLoop
from core.logger import JsonlLogger
from core.task import CodeTask
from core.verifier import build_ts_composite_verifier


class AgentLoopTsTests(unittest.TestCase):
    def test_fail_then_patch_and_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            task = CodeTask(
                task_id="ts_t1",
                prompt="add(a,b)",
                target_file=root / "src" / "solution.ts",
                attempts=[
                    "function add(a: number, b: number): number {\n  return a + b;\n}\n",
                ],
                language="ts",
            )
            verifier = build_ts_composite_verifier(
                function_name="add",
                signature="(a: number, b: number) => number",
                testcases=[
                    {"inputs": [2, 3], "expected": 5},
                    {"inputs": [0, 0], "expected": 0},
                ],
            )
            logger = JsonlLogger(root / "logs.jsonl")

            result = AgentLoop().run(task=task, verifier=verifier, logger=logger)

            self.assertTrue(result.done)
            self.assertEqual(result.attempts_used, 1)

            lines = logger.log_file.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            second = json.loads(lines[1])

            self.assertEqual(first["language"], "ts")
            self.assertEqual(first["failure_type"], "assertion_fail")
            self.assertTrue(first["patch_applied"])
            self.assertEqual(first["patcher_id"], "ts_export_patcher")
            self.assertTrue(second["passed"])
            self.assertEqual(second["language"], "ts")
            self.assertEqual(second["parent_artifact_hash"], first["artifact_hash"])

    def test_ts2322_patcher_fail_then_patch_then_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            task = CodeTask(
                task_id="ts_t2",
                prompt="to_number(value)",
                target_file=root / "src" / "solution.ts",
                attempts=[
                    (
                        "export function to_number(value: string): number {\n"
                        '  return "9";\n'
                        "}\n"
                    ),
                ],
                language="ts",
            )
            verifier = build_ts_composite_verifier(
                function_name="to_number",
                signature="(value: string) => number",
                testcases=[{"inputs": ["9"], "expected": 9}],
            )
            logger = JsonlLogger(root / "logs.jsonl")

            result = AgentLoop().run(task=task, verifier=verifier, logger=logger)

            self.assertTrue(result.done)
            lines = logger.log_file.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            second = json.loads(lines[1])
            self.assertEqual(first["failure_type"], "ts_type_error")
            self.assertEqual(first["verifier_stage_failed"], "tsc")
            self.assertTrue(first["patch_applied"])
            self.assertEqual(first["patcher_id"], "ts_ts2322_number_return_patcher")
            self.assertTrue(second["passed"])


if __name__ == "__main__":
    unittest.main()
