import json
import tempfile
import unittest
from pathlib import Path

from core.agent import AgentLoop
from core.hashing import stable_hash
from core.logger import JsonlLogger
from core.proposers.base import ProposalContext, ProposalResult, Proposer
from core.proposers.policy import ProposerPolicy
from core.proposers.runtime import ProposerRuntime
from core.task import CodeTask
from core.verifier import FunctionCase, FunctionVerifier


class FixedProposer(Proposer):
    id = "fixed_proposer"

    def propose(self, ctx: ProposalContext) -> ProposalResult | None:
        code = "def add(a, b):\n    return a + b\n"
        return ProposalResult(
            proposed_code=code,
            proposer_id=self.id,
            proposal_summary="switch to +",
            proposal_hash=stable_hash({"code": code, "prompt": ctx.prompt}),
        )


class ProposerLoggingTests(unittest.TestCase):
    def test_agent_logs_proposer_fields_when_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            policy = ProposerPolicy(
                enabled=True,
                allowed_languages=("py",),
                max_calls_per_task=1,
                max_calls_per_day=2,
                max_total_seconds_per_day=5.0,
                only_for_uncovered_signatures=False,
                uncovered_source="",
                timeout_seconds=1.0,
            )
            runtime = ProposerRuntime(policy=policy, proposer=FixedProposer(), uncovered_signatures=set())

            task = CodeTask(
                task_id="p1",
                prompt="add(a,b)",
                target_file=root / "solution.py",
                attempts=["def add(a, b):\n    return a - b\n"],
                language="py",
            )
            verifier = FunctionVerifier(
                function_name="add",
                cases=[FunctionCase(args=(2, 3), expected=5)],
            )
            logger = JsonlLogger(root / "logs.jsonl")

            result = AgentLoop(proposer_runtime=runtime).run(task=task, verifier=verifier, logger=logger)
            self.assertTrue(result.done)

            events = [json.loads(line) for line in logger.log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(events), 2)
            first, second = events
            self.assertEqual(first["schema_version"], "2.5.0")
            self.assertFalse(first["proposer_used"])
            self.assertTrue(second["proposer_used"])
            self.assertEqual(second["proposer_id"], "fixed_proposer")
            self.assertIsNotNone(second["proposal_hash"])
            self.assertIsNotNone(second["proposer_latency_ms"])
            self.assertIsNotNone(second["proposer_budget_spent"])
            self.assertIsNotNone(second["proposer_input_hash"])
            self.assertTrue(second["passed"])


if __name__ == "__main__":
    unittest.main()
