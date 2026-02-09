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
    timeout_seconds: float = 25.0
    max_output_chars: int = 20000
    max_stderr_chars: int = 800


class CodexProposer(Proposer):
    id = "codex_proposer"

    def __init__(self, config: CodexProposerConfig | None = None) -> None:
        self.config = config or CodexProposerConfig()

    def propose(self, ctx: ProposalContext) -> ProposalResult | None:
        command = os.getenv(self.config.command_env_var, "").strip()
        if not command:
            return None

        # Retry is intentionally 0 for deterministic behavior.
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

        stderr = self._truncate_text(proc.stderr or "", self.config.max_stderr_chars)
        if stderr:
            print(f"proposer_stderr={stderr}")

        if proc.returncode != 0:
            return None

        proposed_code = self._extract_code(proc.stdout or "")
        proposed_code = self._truncate_text(proposed_code, self.config.max_output_chars).strip()
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

    def _extract_code(self, text: str) -> str:
        stripped = text.strip()
        if "```" not in stripped:
            return stripped

        parts = stripped.split("```")
        if len(parts) < 3:
            return stripped

        fenced = parts[1]
        if "\n" in fenced:
            first_line, rest = fenced.split("\n", 1)
            language_marker = first_line.strip().lower()
            if language_marker in {"python", "py", "typescript", "ts", "javascript", "js"}:
                return rest.strip()
        return fenced.strip()

    def _truncate_text(self, text: str, max_chars: int) -> str:
        value = text.strip()
        if len(value) <= max_chars:
            return value
        return value[: max_chars - 14] + "...[truncated]"
