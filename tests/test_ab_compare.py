import unittest

from tools.ab_compare import compare


class AbCompareTests(unittest.TestCase):
    def test_enable_proposer_when_gain_and_no_regression(self) -> None:
        summary_a = {
            "overall_pass_rate": 0.80,
            "pass_rate_by_language": {"py": 0.9, "ts": 0.7},
            "signature_coverage": 0.30,
            "top_uncovered_signatures": [{"language": "ts", "error_signature": "TS2322"}],
            "timeout_rate": 0.01,
            "flaky_groups_count": 0,
            "proposer_budget_spent": {"calls": 0, "seconds": 0.0, "calls_by_proposer": {}},
        }
        summary_b = {
            "overall_pass_rate": 0.85,
            "pass_rate_by_language": {"py": 0.9, "ts": 0.8},
            "signature_coverage": 0.35,
            "top_uncovered_signatures": [{"language": "ts", "error_signature": "TS2304"}],
            "timeout_rate": 0.01,
            "flaky_groups_count": 0,
            "proposer_budget_spent": {"calls": 4, "seconds": 1.2, "calls_by_proposer": {"codex_proposer": 4}},
        }

        payload = compare(
            summary_a=summary_a,
            summary_b=summary_b,
            min_solve_rate_gain=0.01,
            max_timeout_increase=0.01,
            max_flaky_increase=0,
        )

        self.assertTrue(payload["decision"]["enable_proposer"])
        self.assertEqual(payload["solve_rate"]["delta"], 0.05)
        self.assertEqual(payload["top_uncovered_delta"]["added_count"], 1)
        self.assertEqual(payload["top_uncovered_delta"]["removed_count"], 1)

    def test_keep_disabled_when_timeout_or_flaky_regresses(self) -> None:
        summary_a = {
            "overall_pass_rate": 0.82,
            "pass_rate_by_language": {"py": 0.9, "ts": 0.74},
            "signature_coverage": 0.31,
            "top_uncovered_signatures": [],
            "timeout_rate": 0.01,
            "flaky_groups_count": 0,
            "proposer_budget_spent": {"calls": 0, "seconds": 0.0, "calls_by_proposer": {}},
        }
        summary_b = {
            "overall_pass_rate": 0.90,
            "pass_rate_by_language": {"py": 0.9, "ts": 0.9},
            "signature_coverage": 0.40,
            "top_uncovered_signatures": [],
            "timeout_rate": 0.05,
            "flaky_groups_count": 2,
            "proposer_budget_spent": {"calls": 8, "seconds": 3.0, "calls_by_proposer": {"codex_proposer": 8}},
        }

        payload = compare(
            summary_a=summary_a,
            summary_b=summary_b,
            min_solve_rate_gain=0.01,
            max_timeout_increase=0.01,
            max_flaky_increase=0,
        )

        self.assertFalse(payload["decision"]["enable_proposer"])
        self.assertGreater(payload["timeout_rate"]["delta"], 0.01)
        self.assertGreater(payload["flaky_groups_count"]["delta"], 0)


if __name__ == "__main__":
    unittest.main()
