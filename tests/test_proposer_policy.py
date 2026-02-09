import unittest

from core.hashing import stable_hash
from core.proposers.base import ProposalContext, ProposalResult, Proposer
from core.proposers.policy import ProposerPolicy
from core.proposers.runtime import ProposerRuntime


class DummyProposer(Proposer):
    id = "dummy_proposer"

    def __init__(self) -> None:
        self.calls = 0

    def propose(self, ctx: ProposalContext) -> ProposalResult | None:
        self.calls += 1
        proposed_code = "def add(a, b):\n    return a + b\n"
        return ProposalResult(
            proposed_code=proposed_code,
            proposer_id=self.id,
            proposal_summary="return a + b",
            proposal_hash=stable_hash({"code": proposed_code, "task_id": ctx.task_id}),
        )


class ProposerPolicyTests(unittest.TestCase):
    def _ctx(self, signature: str) -> ProposalContext:
        return ProposalContext(
            language="py",
            task_id="task_1",
            prompt="add",
            signature="(a: number, b: number) => number",
            function_name="add",
            code="def add(a, b):\n    return a - b\n",
            failure_type="assertion_fail",
            error_signature=signature,
            error_message="case mismatch",
            verifier_stage_failed="unit_test",
            task_payload={"function_name": "add", "cases": [{"args": [1, 2], "expected": 3}]},
            payload_is_lossy=False,
        )

    def test_only_uncovered_signature_is_allowed(self) -> None:
        policy = ProposerPolicy(
            enabled=True,
            allowed_languages=("py",),
            max_calls_per_task=2,
            max_calls_per_day=10,
            max_total_seconds_per_day=5.0,
            only_for_uncovered_signatures=True,
            uncovered_signatures_path="",
            timeout_seconds=1.0,
        )
        proposer = DummyProposer()
        runtime = ProposerRuntime(
            policy=policy,
            proposer=proposer,
            uncovered_signatures={("py", "AssertionError:case mismatch")},
        )

        allowed = runtime.propose(self._ctx("AssertionError:case mismatch"))
        blocked = runtime.propose(self._ctx("AssertionError:other"))

        self.assertTrue(allowed.proposer_used)
        self.assertIsNotNone(allowed.result)
        self.assertFalse(blocked.proposer_used)
        self.assertIsNone(blocked.result)
        self.assertEqual(proposer.calls, 1)

    def test_max_calls_per_task_is_enforced(self) -> None:
        policy = ProposerPolicy(
            enabled=True,
            allowed_languages=("py",),
            max_calls_per_task=1,
            max_calls_per_day=10,
            max_total_seconds_per_day=5.0,
            only_for_uncovered_signatures=False,
            uncovered_signatures_path="",
            timeout_seconds=1.0,
        )
        proposer = DummyProposer()
        runtime = ProposerRuntime(policy=policy, proposer=proposer, uncovered_signatures=set())

        first = runtime.propose(self._ctx("AssertionError:case mismatch"))
        second = runtime.propose(self._ctx("AssertionError:case mismatch"))

        self.assertTrue(first.proposer_used)
        self.assertFalse(second.proposer_used)
        self.assertEqual(proposer.calls, 1)


if __name__ == "__main__":
    unittest.main()
