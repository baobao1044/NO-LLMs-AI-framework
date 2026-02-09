import os
import unittest

from core.proposers.base import ProposalContext
from core.proposers.codex_proposer import CodexProposer, CodexProposerConfig


class CodexProposerRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prev = os.environ.get("CODEX_PROPOSER_COMMAND")

    def tearDown(self) -> None:
        if self.prev is None:
            os.environ.pop("CODEX_PROPOSER_COMMAND", None)
        else:
            os.environ["CODEX_PROPOSER_COMMAND"] = self.prev

    def _ctx(self) -> ProposalContext:
        return ProposalContext(
            language="py",
            task_id="t1",
            prompt="add",
            signature=None,
            function_name="add",
            code="def add(a, b):\n    return a - b\n",
            failure_type="assertion_fail",
            error_signature="AssertionError:case mismatch",
            error_message="case mismatch",
            verifier_stage_failed="unit_test",
            task_payload={"function_name": "add", "cases": [{"args": [1, 2], "expected": 3}]},
            payload_is_lossy=False,
        )

    def test_extracts_code_and_truncates_output(self) -> None:
        os.environ["CODEX_PROPOSER_COMMAND"] = (
            "python3 -c \"import sys;"
            "sys.stderr.write('ERR_' * 300);"
            "print('```python\\ndef add(a, b):\\n    return a + b\\n# ' + 'x'*200 + '\\n```')\""
        )
        proposer = CodexProposer(
            CodexProposerConfig(
                timeout_seconds=2.0,
                max_output_chars=80,
                max_stderr_chars=120,
            )
        )

        result = proposer.propose(self._ctx())

        self.assertIsNotNone(result)
        self.assertIn("def add(a, b):", result.proposed_code)
        self.assertLessEqual(len(result.proposed_code), 80)
        self.assertTrue(result.proposal_hash)

    def test_timeout_returns_none(self) -> None:
        os.environ["CODEX_PROPOSER_COMMAND"] = "python3 -c \"import time; time.sleep(2); print('x')\""
        proposer = CodexProposer(CodexProposerConfig(timeout_seconds=0.1))

        result = proposer.propose(self._ctx())

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
