import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.pick_backlog_items import select_items


class PickBacklogItemsTests(unittest.TestCase):
    def _sample_backlog(self) -> dict:
        return {
            "items": [
                {
                    "language": "py",
                    "failure_type": "syntax_error",
                    "error_signature": "SyntaxError:expected ':'",
                    "verifier_stage_failed": "syntax",
                    "suggested_category": "syntax_fix",
                    "priority_score": 3.0,
                    "count_total": 5,
                    "solve_rate": 0.4,
                    "patch_hit_rate": 0.1,
                    "patch_success_rate": 0.0,
                    "examples": [],
                },
                {
                    "language": "ts",
                    "failure_type": "ts_type_error",
                    "error_signature": "TS2322:Type mismatch",
                    "verifier_stage_failed": "tsc",
                    "suggested_category": "type_fix",
                    "priority_score": 3.0,
                    "count_total": 4,
                    "solve_rate": 0.25,
                    "patch_hit_rate": 0.0,
                    "patch_success_rate": 0.0,
                    "examples": [],
                },
                {
                    "language": "ts",
                    "failure_type": "timeout",
                    "error_signature": "TimeoutError:exceeded",
                    "verifier_stage_failed": "timeout",
                    "suggested_category": "performance_or_infinite_loop",
                    "priority_score": 2.0,
                    "count_total": 6,
                    "solve_rate": 0.3,
                    "patch_hit_rate": 0.0,
                    "patch_success_rate": 0.0,
                    "examples": [],
                },
            ]
        }

    def test_policy_sort_is_deterministic(self) -> None:
        backlog = self._sample_backlog()
        policy = {
            "strategy": "max_impact",
            "language_priority": ["ts", "py"],
            "stage_priority": ["tsc", "unit_test", "timeout", "syntax"],
            "top_n": 3,
            "min_count": 1,
        }
        first = select_items(backlog=backlog, policy=policy)
        second = select_items(backlog=backlog, policy=policy)
        self.assertEqual(first, second)
        self.assertEqual(first[0]["language"], "ts")
        self.assertEqual(first[0]["verifier_stage_failed"], "tsc")
        self.assertEqual(first[1]["language"], "py")

    def test_cli_writes_selected_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            backlog = root / "backlog.json"
            policy = root / "policy.json"
            out = root / "selected.json"
            backlog.write_text(json.dumps(self._sample_backlog(), ensure_ascii=True, indent=2), encoding="utf-8")
            policy.write_text(
                json.dumps(
                    {
                        "strategy": "max_coverage",
                        "language_priority": ["ts", "py"],
                        "stage_priority": ["tsc", "timeout", "syntax"],
                        "top_n": 2,
                        "min_count": 1,
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )

            script = Path(__file__).resolve().parents[1] / "tools" / "pick_backlog_items.py"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--backlog",
                    str(backlog),
                    "--policy",
                    str(policy),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["items"]), 2)


if __name__ == "__main__":
    unittest.main()
