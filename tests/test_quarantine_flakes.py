import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class QuarantineFlakesTests(unittest.TestCase):
    def test_generates_quarantine_from_flaky_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            replay_metrics = root / "replay.json"
            out_file = root / "flaky_quarantine.json"
            replay_metrics.write_text(
                json.dumps(
                    {
                        "flaky_groups": [
                            {
                                "language": "ts",
                                "failure_type": "ts_type_error",
                                "error_signature": "TS2322:x",
                                "verifier_stage_failed": "tsc",
                            },
                            {
                                "language": "ts",
                                "failure_type": "ts_type_error",
                                "error_signature": "TS2322:x",
                                "verifier_stage_failed": "tsc",
                            },
                        ]
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )

            script = Path(__file__).resolve().parents[1] / "tools" / "quarantine_flakes.py"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--replay-metrics",
                    str(replay_metrics),
                    "--out",
                    str(out_file),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            payload = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["flaky_groups_count"], 1)
            self.assertEqual(payload["flaky_groups"][0]["language"], "ts")


if __name__ == "__main__":
    unittest.main()
