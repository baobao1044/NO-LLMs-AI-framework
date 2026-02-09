import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RunPackCreationTests(unittest.TestCase):
    def test_create_run_pack_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            script = Path(__file__).resolve().parents[1] / "tools" / "create_run_pack.py"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--date",
                    "20260210",
                    "--seed",
                    "123",
                    "--task-config",
                    "configs/ts_generated_tasks.json",
                    "--policy",
                    "configs/backlog_policy.json",
                    "--budget",
                    "max_tasks=10",
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)

            run_dir = root / "runs" / "20260210"
            reports_dir = root / "reports" / "20260210"
            self.assertTrue(run_dir.exists())
            self.assertTrue(reports_dir.exists())
            self.assertTrue((run_dir / "agent_runs.jsonl").exists())
            metadata_file = run_dir / "metadata.json"
            self.assertTrue(metadata_file.exists())
            payload = json.loads(metadata_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["date"], "20260210")
            self.assertEqual(payload["seed"], 123)


if __name__ == "__main__":
    unittest.main()
