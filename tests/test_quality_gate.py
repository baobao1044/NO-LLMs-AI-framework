import argparse
import unittest

from tools.patcher_quality_gate import evaluate


class QualityGateTests(unittest.TestCase):
    def _args(self, **kwargs):
        defaults = {
            "max_pass_rate_drop": 0.01,
            "max_timeout_increase": 0.01,
            "max_flaky_increase": 0,
            "min_coverage_gain": 0.0,
        }
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_pass_when_metrics_within_threshold(self) -> None:
        before = {
            "overall_pass_rate": 0.90,
            "timeout_rate": 0.01,
            "flaky_groups_count": 0,
            "signature_coverage": 0.30,
            "patcher_activity_by_id": {"p1": 2},
            "patcher_success_rate_by_id": {"p1": 0.5},
        }
        after = {
            "overall_pass_rate": 0.905,
            "timeout_rate": 0.015,
            "flaky_groups_count": 0,
            "signature_coverage": 0.31,
            "patcher_activity_by_id": {"p1": 3},
            "patcher_success_rate_by_id": {"p1": 0.5},
        }

        ok, failures, suspects = evaluate(before=before, after=after, args=self._args())

        self.assertTrue(ok)
        self.assertEqual(failures, [])
        self.assertEqual(suspects, [])

    def test_fail_and_flag_suspects(self) -> None:
        before = {
            "overall_pass_rate": 0.95,
            "timeout_rate": 0.01,
            "flaky_groups_count": 0,
            "signature_coverage": 0.35,
            "patcher_activity_by_id": {"stable_patcher": 5},
            "patcher_success_rate_by_id": {"stable_patcher": 0.8},
        }
        after = {
            "overall_pass_rate": 0.90,
            "timeout_rate": 0.03,
            "flaky_groups_count": 2,
            "signature_coverage": 0.34,
            "patcher_activity_by_id": {"stable_patcher": 6, "new_patcher": 3},
            "patcher_success_rate_by_id": {"stable_patcher": 0.6, "new_patcher": 0.2},
        }

        ok, failures, suspects = evaluate(before=before, after=after, args=self._args(min_coverage_gain=0.0))

        self.assertFalse(ok)
        self.assertGreaterEqual(len(failures), 3)
        self.assertIn("new_patcher", suspects)
        self.assertIn("stable_patcher", suspects)


if __name__ == "__main__":
    unittest.main()
