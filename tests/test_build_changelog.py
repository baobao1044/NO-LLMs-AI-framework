import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class BuildChangelogTests(unittest.TestCase):
    def test_build_changelog_is_deterministic_and_idempotent(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "tools" / "build_changelog.py"

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            changelog = root / "CHANGELOG.md"
            changelog.write_text(
                "# Changelog\n\nAll notable changes to this project will be documented in this file.\n\n",
                encoding="utf-8",
            )

            reports = root / "reports"
            reports.mkdir(parents=True, exist_ok=True)

            progress = reports / "progress_20260209.md"
            progress.write_text(
                "# Progress Report\n\n## Patchers Added\n\n- ts_ts2322_number_return_patcher\n",
                encoding="utf-8",
            )

            day_dir = reports / "20260209"
            day_dir.mkdir(parents=True, exist_ok=True)
            (day_dir / "daily_summary.json").write_text(
                json.dumps(
                    {
                        "date": "20260209",
                        "pass_rate_by_language": {
                            "py": {"delta": 0.1},
                            "ts": {"delta": -0.05},
                        },
                        "signature_coverage": {"delta": 0.02},
                        "top_uncovered": {
                            "before": [{"language": "ts", "error_signature": "TS2322:old"}],
                            "after": [{"language": "ts", "error_signature": "TS2304:new"}],
                        },
                        "regress_status": "PASS",
                        "quality_status": "PASS",
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (day_dir / "replay_metrics.json").write_text(
                json.dumps(
                    {
                        "replay_match": 8,
                        "replay_eligible": 8,
                        "env_fingerprint_mismatch_count": 0,
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )

            backlog_selected = root / "configs" / "backlog_selected.json"
            backlog_selected.parent.mkdir(parents=True, exist_ok=True)
            backlog_selected.write_text(json.dumps({"items": []}, ensure_ascii=True, indent=2), encoding="utf-8")

            cmd = [
                sys.executable,
                str(script),
                "--changelog",
                str(changelog),
                "--progress-glob",
                str(reports / "progress_*.md"),
                "--daily-glob",
                str(reports / "*" / "daily_summary.json"),
                "--backlog-selected",
                str(backlog_selected),
            ]
            first = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0)
            content1 = changelog.read_text(encoding="utf-8")

            second = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(second.returncode, 0)
            content2 = changelog.read_text(encoding="utf-8")

            self.assertEqual(content1, content2)
            self.assertIn("## [2026-02-09]", content1)
            self.assertIn("pass_rate_by_language delta: py:+0.100000, ts:-0.050000", content1)
            self.assertIn("patchers added: ts_ts2322_number_return_patcher", content1)
            self.assertIn("notes: regress=PASS; quality=PASS; replay=8/8 mismatch=0", content1)
            self.assertIn("proposer_budget=unknown", content1)

    def test_build_changelog_uses_ab_compare_when_available(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "tools" / "build_changelog.py"

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            changelog = root / "CHANGELOG.md"
            changelog.write_text("# Changelog\n\n", encoding="utf-8")

            reports = root / "reports"
            reports.mkdir(parents=True, exist_ok=True)
            day_dir = reports / "20260209"
            day_dir.mkdir(parents=True, exist_ok=True)
            (day_dir / "daily_summary.json").write_text(
                json.dumps({"date": "20260209", "pass_rate_by_language": {"py": {"delta": 0.0}}}, ensure_ascii=True),
                encoding="utf-8",
            )
            (day_dir / "ab_compare.json").write_text(
                json.dumps(
                    {
                        "pass_rate_by_language": {"py": {"delta": 0.2}},
                        "signature_coverage": {"delta": 0.15},
                        "top_uncovered_delta": {"added_count": 1, "removed_count": 3},
                        "cost": {"proposer_calls": 5, "proposer_seconds": 2.5, "solve_gain_per_call": 0.04},
                    },
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (day_dir / "replay_metrics_A.json").write_text(
                json.dumps(
                    {"replay_match": 10, "replay_eligible": 10, "env_fingerprint_mismatch_count": 0},
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )
            (day_dir / "replay_metrics_B.json").write_text(
                json.dumps(
                    {"replay_match": 9, "replay_eligible": 9, "env_fingerprint_mismatch_count": 0},
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )

            backlog_selected = root / "configs" / "backlog_selected.json"
            backlog_selected.parent.mkdir(parents=True, exist_ok=True)
            backlog_selected.write_text(json.dumps({"items": []}, ensure_ascii=True), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--changelog",
                    str(changelog),
                    "--progress-glob",
                    str(reports / "progress_*.md"),
                    "--daily-glob",
                    str(reports / "*" / "daily_summary*.json"),
                    "--backlog-selected",
                    str(backlog_selected),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            content = changelog.read_text(encoding="utf-8")
            self.assertIn("pass_rate_by_language delta: py:+0.200000", content)
            self.assertIn("signature_coverage delta: +0.150000", content)
            self.assertIn("top_uncovered delta: added=1, removed=3", content)
            self.assertIn("proposer_budget=calls=5 seconds=2.500000 solve_gain_per_call=0.04000000", content)


if __name__ == "__main__":
    unittest.main()
