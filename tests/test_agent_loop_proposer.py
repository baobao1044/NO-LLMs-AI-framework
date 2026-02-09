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
from tools.replay import replay_records


class SequenceProposer(Proposer):
    id = "sequence_proposer"

    def __init__(self, codes: list[str]) -> None:
        self.codes = list(codes)
        self.calls = 0

    def propose(self, ctx: ProposalContext) -> ProposalResult | None:
        if not self.codes:
            return None
        self.calls += 1
        code = self.codes.pop(0)
        return ProposalResult(
            proposed_code=code,
            proposer_id=self.id,
            proposal_summary="sequence",
            proposal_hash=stable_hash({"code": code, "task_id": ctx.task_id, "calls": self.calls}),
        )


class AgentLoopProposerTests(unittest.TestCase):
    def _runtime(self, proposer: Proposer) -> ProposerRuntime:
        policy = ProposerPolicy(
            enabled=True,
            allowed_languages=("py",),
            max_calls_per_task=2,
            max_calls_per_day=10,
            max_total_seconds_per_day=10.0,
            only_for_uncovered_signatures=False,
            uncovered_source="",
            timeout_seconds=1.0,
        )
        return ProposerRuntime(policy=policy, proposer=proposer, uncovered_signatures=set())

    def test_patchers_run_before_proposer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposer = SequenceProposer(["def inc(x):\n    return x + 1\n"])

            task = CodeTask(
                task_id="p_order",
                prompt="inc(x)",
                target_file=root / "solution.py",
                attempts=["def inc(x)\n    return x + 1\n"],
                language="py",
            )
            verifier = FunctionVerifier(function_name="inc", cases=[FunctionCase(args=(1,), expected=2)])
            logger = JsonlLogger(root / "events.jsonl")

            result = AgentLoop(proposer_runtime=self._runtime(proposer)).run(
                task=task,
                verifier=verifier,
                logger=logger,
            )

            self.assertTrue(result.done)
            self.assertEqual(proposer.calls, 0)

    def test_proposer_then_fallback_attempt_and_replay_without_external_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposer = SequenceProposer(["def add(a, b):\n    return a * b\n"])
            runtime = self._runtime(proposer)

            task = CodeTask(
                task_id="p_fallback",
                prompt="add(a,b)",
                target_file=root / "solution.py",
                attempts=[
                    "def add(a, b):\n    return a - b\n",
                    "def add(a, b):\n    return a + b\n",
                ],
                language="py",
            )
            verifier = FunctionVerifier(function_name="add", cases=[FunctionCase(args=(2, 3), expected=5)])
            logger = JsonlLogger(root / "events.jsonl")

            result = AgentLoop(proposer_runtime=runtime).run(task=task, verifier=verifier, logger=logger)

            self.assertTrue(result.done)
            self.assertEqual(result.attempts_used, 2)
            self.assertEqual(proposer.calls, 1)

            records = [
                json.loads(line)
                for line in logger.log_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(records), 3)
            self.assertTrue(records[1]["proposer_used"])

            code, metrics = replay_records(records)
            self.assertEqual(code, 0)
            self.assertEqual(metrics["replay_match"], metrics["replay_eligible"])
            self.assertEqual(proposer.calls, 1)


if __name__ == "__main__":
    unittest.main()
