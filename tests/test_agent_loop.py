import json
import tempfile
import unittest
import uuid
from pathlib import Path

from core.agent import AgentLoop
from core.logger import JsonlLogger
from core.task import CodeTask
from core.verifier import FunctionCase, FunctionVerifier


class AgentLoopTests(unittest.TestCase):
    def test_fail_then_fix_and_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            task = CodeTask(
                task_id="t1",
                prompt="add(a,b)",
                target_file=root / "solution.py",
                attempts=[
                    "def add(a, b):\n    return a - b\n",
                    "def add(a, b):\n    return a + b\n",
                ],
            )
            verifier = FunctionVerifier(
                function_name="add",
                cases=[
                    FunctionCase(args=(2, 3), expected=5),
                    FunctionCase(args=(0, 0), expected=0),
                ],
            )
            logger = JsonlLogger(root / "logs.jsonl")

            result = AgentLoop().run(task=task, verifier=verifier, logger=logger)

            self.assertTrue(result.done)
            self.assertEqual(result.attempts_used, 2)
            self.assertIsNone(result.last_error)

            lines = logger.log_file.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            second = json.loads(lines[1])
            uuid.UUID(first["run_id"])
            self.assertEqual(first["run_id"], second["run_id"])
            self.assertEqual(first["schema_version"], "2.4.0")
            self.assertEqual(first["language"], "py")
            self.assertIn("env_fingerprint", first)
            self.assertEqual(first["attempt_index"], 1)
            self.assertEqual(second["attempt_index"], 2)
            self.assertFalse(first["payload_is_lossy"])
            self.assertEqual(first["failure_type"], "assertion_fail")
            self.assertIsNotNone(first["error_signature"])
            self.assertIsNone(second["failure_type"])
            self.assertIsNone(second["error_signature"])
            self.assertEqual(first["verifier_name"], "function_verifier")
            self.assertEqual(first["verifier_version"], "1.1.0")
            self.assertEqual(first["task_payload"]["function_name"], "add")
            self.assertEqual(len(first["artifact_hash"]), 64)
            self.assertEqual(len(first["task_hash"]), 64)
            self.assertEqual(first["task_hash"], second["task_hash"])
            self.assertTrue(first["patcher_attempted"])
            self.assertFalse(first["patch_applied"])
            self.assertFalse(first["passed"])
            self.assertTrue(second["passed"])

    def test_all_attempts_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            task = CodeTask(
                task_id="t2",
                prompt="add(a,b)",
                target_file=root / "solution.py",
                attempts=[
                    "def add(a, b):\n    return a * b\n",
                ],
            )
            verifier = FunctionVerifier(
                function_name="add",
                cases=[FunctionCase(args=(2, 3), expected=5)],
            )
            logger = JsonlLogger(root / "logs.jsonl")

            result = AgentLoop().run(task=task, verifier=verifier, logger=logger)

            self.assertFalse(result.done)
            self.assertEqual(result.attempts_used, 1)
            self.assertIsNotNone(result.last_error)

            line = logger.log_file.read_text(encoding="utf-8").strip()
            payload = json.loads(line)
            self.assertFalse(payload["passed"])
            self.assertEqual(payload["failure_type"], "assertion_fail")
            self.assertIsNotNone(payload["error_signature"])
            self.assertTrue(payload["patcher_attempted"])
            self.assertFalse(payload["patch_applied"])

    def test_syntax_error_is_auto_patched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            task = CodeTask(
                task_id="t3",
                prompt="add(a,b)",
                target_file=root / "solution.py",
                attempts=[
                    "def add(a, b)\n    return a + b\n",
                ],
            )
            verifier = FunctionVerifier(
                function_name="add",
                cases=[FunctionCase(args=(1, 2), expected=3)],
            )
            logger = JsonlLogger(root / "logs.jsonl")

            result = AgentLoop().run(task=task, verifier=verifier, logger=logger)

            self.assertTrue(result.done)
            lines = logger.log_file.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            second = json.loads(lines[1])
            self.assertEqual(first["failure_type"], "syntax_error")
            self.assertTrue(first["patch_applied"])
            self.assertEqual(first["patcher_id"], "syntax_fix_patcher")
            self.assertTrue(second["passed"])
            self.assertTrue(second["patch_applied"])
            self.assertEqual(second["parent_artifact_hash"], first["artifact_hash"])
            self.assertGreater(second["changed_lines_count"], 0)

    def test_payload_marks_lossy_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            marker = object()
            task = CodeTask(
                task_id="t4",
                prompt="echo(x)",
                target_file=root / "solution.py",
                attempts=[
                    "def echo(x):\n    return x\n",
                ],
            )
            verifier = FunctionVerifier(
                function_name="echo",
                cases=[FunctionCase(args=(marker,), expected=marker)],
            )
            logger = JsonlLogger(root / "logs.jsonl")

            result = AgentLoop().run(task=task, verifier=verifier, logger=logger)

            self.assertTrue(result.done)
            payload = json.loads(logger.log_file.read_text(encoding="utf-8").strip())
            self.assertTrue(payload["payload_is_lossy"])
            encoded_arg = payload["task_payload"]["cases"][0]["args"][0]
            self.assertEqual(encoded_arg["type_name"], "object")
            self.assertIn("summary", encoded_arg)
            self.assertLessEqual(len(encoded_arg["summary"]), 200)

    def test_patch_fails_then_fallback_to_next_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            task = CodeTask(
                task_id="t5",
                prompt="add(a,b)",
                target_file=root / "solution.py",
                attempts=[
                    "def add(a, b)\n    return a - b\n",
                    "def add(a, b):\n    return a + b\n",
                ],
            )
            verifier = FunctionVerifier(
                function_name="add",
                cases=[FunctionCase(args=(1, 2), expected=3)],
            )
            logger = JsonlLogger(root / "logs.jsonl")

            result = AgentLoop().run(task=task, verifier=verifier, logger=logger)

            self.assertTrue(result.done)
            self.assertEqual(result.attempts_used, 2)
            lines = logger.log_file.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 3)
            first = json.loads(lines[0])
            patched = json.loads(lines[1])
            second_attempt = json.loads(lines[2])
            self.assertEqual(first["attempt_index"], 1)
            self.assertTrue(first["patch_applied"])
            self.assertEqual(patched["attempt_index"], 1)
            self.assertTrue(patched["patch_applied"])
            self.assertFalse(patched["passed"])
            self.assertEqual(second_attempt["attempt_index"], 2)
            self.assertTrue(second_attempt["passed"])


if __name__ == "__main__":
    unittest.main()
