import unittest

from tools.replay import replay_records


class ReplayProposerRecordsTests(unittest.TestCase):
    def test_replay_uses_logged_proposed_code(self) -> None:
        records = [
            {
                "run_id": "r1",
                "attempt_index": 1,
                "task_id": "t1",
                "language": "py",
                "task_payload": {
                    "function_name": "add",
                    "cases": [{"args": [1, 2], "expected": 3}],
                },
                "payload_is_lossy": False,
                "code": "def add(a, b):\n    return a + b\n",
                "passed": True,
                "proposer_used": True,
                "proposer_id": "codex_proposer",
                "proposal_hash": "h1",
                "verifier_name": "function_verifier",
                "verifier_version": "1.1.0",
                "artifact_hash": "a1",
                "task_hash": "t_hash",
                "verifier_stage_failed": None,
                "failure_type": None,
                "error_signature": None,
            }
        ]

        code, metrics = replay_records(records)

        self.assertEqual(code, 0)
        self.assertEqual(metrics["replay_match"], 1)
        self.assertEqual(metrics["replay_eligible"], 1)
        self.assertEqual(metrics["unreplayable_proposer_missing_code"], 0)

    def test_missing_proposer_code_marked_unreplayable(self) -> None:
        records = [
            {
                "run_id": "r1",
                "attempt_index": 1,
                "task_id": "t1",
                "language": "py",
                "task_payload": {
                    "function_name": "add",
                    "cases": [{"args": [1, 2], "expected": 3}],
                },
                "payload_is_lossy": False,
                "code": None,
                "passed": False,
                "proposer_used": True,
                "proposer_id": "codex_proposer",
                "proposal_hash": "h1",
                "verifier_name": "function_verifier",
                "verifier_version": "1.1.0",
                "artifact_hash": "a1",
                "task_hash": "t_hash",
                "verifier_stage_failed": "unit_test",
                "failure_type": "assertion_fail",
                "error_signature": "AssertionError:oops",
            }
        ]

        code, metrics = replay_records(records)

        self.assertEqual(code, 0)
        self.assertEqual(metrics["replay_eligible"], 0)
        self.assertEqual(metrics["unreplayable_proposer_missing_code"], 1)


if __name__ == "__main__":
    unittest.main()
