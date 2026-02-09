import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MergeLogsTests(unittest.TestCase):
    def _write_log(self, path: Path, records: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    def test_merge_dedup_and_stable_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run1 = root / "runs" / "20260209" / "agent_runs.jsonl"
            run2 = root / "runs" / "20260210" / "agent_runs.jsonl"

            duplicate_key = {
                "task_hash": "t1",
                "artifact_hash": "a1",
                "attempt_index": 1,
                "verifier_stage_failed": "unit_test",
                "error_signature": "AssertionError:x",
            }
            self._write_log(
                run1,
                [
                    {
                        **duplicate_key,
                        "timestamp_utc": "2026-02-09T00:00:01+00:00",
                        "run_id": "r1",
                        "passed": False,
                    },
                    {
                        "task_hash": "t2",
                        "artifact_hash": "a2",
                        "attempt_index": 1,
                        "verifier_stage_failed": "tsc",
                        "error_signature": "TS2322:x",
                        "timestamp_utc": "2026-02-09T00:00:02+00:00",
                        "run_id": "r1",
                        "passed": False,
                    },
                ],
            )
            self._write_log(
                run2,
                [
                    {
                        **duplicate_key,
                        "timestamp_utc": "2026-02-10T00:00:01+00:00",
                        "run_id": "r2",
                        "passed": True,
                    }
                ],
            )

            script = Path(__file__).resolve().parents[1] / "tools" / "merge_logs.py"
            out_file = root / "logs" / "merged.jsonl"

            cmd = [sys.executable, str(script), str(run1), str(run2), "--out", str(out_file)]
            first = subprocess.run(cmd, capture_output=True, text=True, check=False)
            second = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0)
            self.assertEqual(second.returncode, 0)

            merged1 = out_file.read_text(encoding="utf-8")
            merged2 = out_file.read_text(encoding="utf-8")
            self.assertEqual(merged1, merged2)

            rows = [json.loads(line) for line in merged1.splitlines() if line.strip()]
            self.assertEqual(len(rows), 2)
            picked = [row for row in rows if row["task_hash"] == "t1"][0]
            self.assertTrue(picked["passed"])


if __name__ == "__main__":
    unittest.main()
