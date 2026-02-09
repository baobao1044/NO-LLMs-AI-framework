import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.task_spec import is_json_only


class TaskGenerationTests(unittest.TestCase):
    def test_deterministic_output_for_same_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            out1 = root / "tasks1.json"
            out2 = root / "tasks2.json"

            cmd = [
                sys.executable,
                "tools/generate_tasks.py",
                "--out",
                str(out1),
                "--seed",
                "123",
                "--count",
                "8",
                "--templates",
                "add,sub,mul,clamp,is_palindrome,parse_json_field,regex_findall",
            ]
            proc1 = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(proc1.returncode, 0)

            cmd[3] = str(out2)
            proc2 = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(proc2.returncode, 0)

            payload1 = json.loads(out1.read_text(encoding="utf-8"))
            payload2 = json.loads(out2.read_text(encoding="utf-8"))
            self.assertEqual(payload1, payload2)

    def test_json_only_no_duplicate_ids_valid_testcases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            out_file = root / "tasks.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "tools/generate_tasks.py",
                    "--out",
                    str(out_file),
                    "--seed",
                    "99",
                    "--count",
                    "10",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            payload = json.loads(out_file.read_text(encoding="utf-8"))
            tasks = payload["tasks"]
            ids = [task["task_id"] for task in tasks]
            self.assertEqual(len(ids), len(set(ids)))

            for task in tasks:
                self.assertTrue(is_json_only(task))
                self.assertIsInstance(task["testcases"], list)
                self.assertGreater(len(task["testcases"]), 0)
                for testcase in task["testcases"]:
                    self.assertIn("inputs", testcase)
                    self.assertIn("expected", testcase)

    def test_append_golden_adds_easy_tasks_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            out_file = root / "tasks.json"
            golden_file = root / "golden.json"
            golden_file.write_text(json.dumps({"tasks": []}, ensure_ascii=True, indent=2), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "tools/generate_tasks.py",
                    "--out",
                    str(out_file),
                    "--seed",
                    "7",
                    "--count",
                    "6",
                    "--templates",
                    "add,parse_json_field,regex_findall,clamp",
                    "--append-golden",
                    str(golden_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)

            generated = json.loads(out_file.read_text(encoding="utf-8"))["tasks"]
            easy_ids = {task["task_id"] for task in generated if task["difficulty"] == "easy"}
            golden = json.loads(golden_file.read_text(encoding="utf-8"))["tasks"]
            golden_ids = {item["task_id"] for item in golden}
            self.assertTrue(golden_ids.issubset(easy_ids))
            self.assertEqual(len(golden_ids), len(golden))


if __name__ == "__main__":
    unittest.main()
