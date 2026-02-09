from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass

from core.hashing import stable_hash, text_hash

from .base import ProposalContext, ProposalResult, Proposer


@dataclass(frozen=True)
class CodexProposerConfig:
    command_env_var: str = "CODEX_PROPOSER_COMMAND"
    timeout_seconds: float = 2.0


class CodexProposer(Proposer):
    id = "codex_proposer"

    def __init__(self, config: CodexProposerConfig | None = None) -> None:
        self.config = config or CodexProposerConfig()

    def propose(self, ctx: ProposalContext) -> ProposalResult | None:
        command = os.getenv(self.config.command_env_var, "").strip()
        if not command:
            return None

        try:
            proc = subprocess.run(
                shlex.split(command),
                input=json.dumps(ctx.to_dict(), ensure_ascii=True),
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
                check=False,
            )
        except (subprocess.TimeoutExpired, ValueError, OSError):
            return None

        if proc.returncode != 0:
            return None

        proposed_code = (proc.stdout or "").strip()
        if not proposed_code:
            return None

        prompt_hash = text_hash(ctx.prompt)
        proposal_hash = stable_hash(
            {
                "proposed_code": proposed_code,
                "prompt_hash": prompt_hash,
            }
        )
        return ProposalResult(
            proposed_code=proposed_code,
            proposer_id=self.id,
            proposal_summary=self._build_summary(proposed_code),
            proposal_hash=proposal_hash,
        )

    def _build_summary(self, proposed_code: str, max_len: int = 200) -> str:
        summary = " ".join(proposed_code.split())
        if len(summary) <= max_len:
            return summary
        return summary[: max_len - 3] + "..."
