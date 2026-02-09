import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.task_spec import is_json_only
from core.verifier import build_ts_composite_verifier


class TsTaskGenerationTests(unittest.TestCase):
    def test_deterministic_ts_templates_with_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            out1 = root / "ts_tasks1.json"
            out2 = root / "ts_tasks2.json"
            templates = (
                "ts_union_narrowing,ts_optional_chaining,ts_generic_identity,"
                "ts_record_shape,ts_null_undefined_strict"
            )

            cmd = [
                sys.executable,
                "tools/generate_tasks.py",
                "--out",
                str(out1),
                "--seed",
                "321",
                "--count",
                "10",
                "--templates",
                templates,
                "--tag",
                "generated",
            ]
            first = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0)

            cmd[3] = str(out2)
            second = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(second.returncode, 0)

            payload1 = json.loads(out1.read_text(encoding="utf-8"))
            payload2 = json.loads(out2.read_text(encoding="utf-8"))
            self.assertEqual(payload1, payload2)

    def test_ts_tasks_have_signature_and_json_only_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            out_file = root / "ts_tasks.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "tools/generate_tasks.py",
                    "--out",
                    str(out_file),
                    "--seed",
                    "55",
                    "--count",
                    "8",
                    "--templates",
                    "ts_union_narrowing,ts_optional_chaining,ts_generic_identity,ts_record_shape,ts_null_undefined_strict",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)

            tasks = json.loads(out_file.read_text(encoding="utf-8"))["tasks"]
            ids = [task["task_id"] for task in tasks]
            self.assertEqual(len(ids), len(set(ids)))

            for task in tasks:
                self.assertEqual(task["language"], "ts")
                self.assertIsInstance(task["signature"], str)
                self.assertTrue(task["signature"])
                self.assertIsInstance(task["function_name"], str)
                self.assertTrue(is_json_only(task))

                verifier = build_ts_composite_verifier(
                    function_name=task["function_name"],
                    signature=task["signature"],
                    testcases=task["testcases"],
                )
                payload, lossy = verifier.task_payload_snapshot()
                self.assertFalse(lossy)
                self.assertTrue(is_json_only(payload))
                self.assertEqual(payload["function_name"], task["function_name"])
                self.assertEqual(payload["signature"], task["signature"])

    def test_append_golden_only_easy_ts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            out_file = root / "ts_tasks.json"
            golden_file = root / "ts_golden.json"
            golden_file.write_text(json.dumps({"tasks": []}, ensure_ascii=True, indent=2), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "tools/generate_tasks.py",
                    "--out",
                    str(out_file),
                    "--seed",
                    "77",
                    "--count",
                    "8",
                    "--templates",
                    "ts_union_narrowing,ts_optional_chaining,ts_generic_identity,ts_record_shape,ts_null_undefined_strict",
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
            golden_ids = {entry["task_id"] for entry in golden}

            self.assertTrue(golden_ids)
            self.assertTrue(golden_ids.issubset(easy_ids))
            for entry in golden:
                self.assertEqual(entry.get("language"), "ts")
                self.assertIn("testcases", entry)


if __name__ == "__main__":
    unittest.main()
