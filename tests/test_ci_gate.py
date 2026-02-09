import unittest

from tools.ci_gate import evaluate_governance


class CiGateTests(unittest.TestCase):
    def test_pass_when_within_policy(self) -> None:
        policy = {
            "max_pass_rate_drop_allowed": 0.0,
            "max_replay_mismatch_allowed": 0,
            "max_env_fingerprint_mismatch_allowed": 0,
        }
        quality_baseline = {"overall_pass_rate": 0.90}
        quality_current = {"overall_pass_rate": 0.90}
        replay_metrics = {
            "replay_match": 10,
            "replay_eligible": 10,
            "env_fingerprint_mismatch_count": 0,
        }

        ok, failures = evaluate_governance(
            policy=policy,
            quality_baseline=quality_baseline,
            quality_current=quality_current,
            replay_metrics=replay_metrics,
        )

        self.assertTrue(ok)
        self.assertEqual(failures, [])

    def test_fail_when_policy_thresholds_are_violated(self) -> None:
        policy = {
            "max_pass_rate_drop_allowed": 0.0,
            "max_replay_mismatch_allowed": 0,
            "max_env_fingerprint_mismatch_allowed": 0,
        }
        quality_baseline = {"overall_pass_rate": 0.95}
        quality_current = {"overall_pass_rate": 0.90}
        replay_metrics = {
            "replay_match": 8,
            "replay_eligible": 10,
            "env_fingerprint_mismatch_count": 1,
        }

        ok, failures = evaluate_governance(
            policy=policy,
            quality_baseline=quality_baseline,
            quality_current=quality_current,
            replay_metrics=replay_metrics,
        )

        self.assertFalse(ok)
        self.assertGreaterEqual(len(failures), 3)
        self.assertTrue(any("pass_rate_drop_exceeded" in item for item in failures))
        self.assertTrue(any("replay_mismatch_exceeded" in item for item in failures))
        self.assertTrue(any("env_fingerprint_mismatch_exceeded" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
