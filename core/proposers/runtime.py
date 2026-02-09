from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from core.hashing import stable_hash

from .base import ProposalContext, ProposalResult, Proposer
from .codex_proposer import CodexProposer, CodexProposerConfig
from .policy import (
    ProposerPolicy,
    budget_snapshot_dict,
    is_signature_uncovered,
    load_proposer_policy,
    load_uncovered_signatures,
)


@dataclass(frozen=True)
class ProposalExecution:
    result: ProposalResult | None
    proposer_used: bool
    proposer_id: str | None
    proposal_hash: str | None
    proposer_latency_ms: int | None
    proposer_budget_spent: dict[str, Any] | None
    proposer_input_hash: str | None


class ProposerRuntime:
    def __init__(
        self,
        policy: ProposerPolicy,
        proposer: Proposer | None = None,
        uncovered_signatures: set[tuple[str, str]] | None = None,
    ) -> None:
        self.policy = policy
        self.proposer = proposer
        self.uncovered_signatures = uncovered_signatures or set()
        self.calls_by_task: dict[str, int] = defaultdict(int)
        self.calls_day = 0
        self.seconds_day = 0.0
        self.day_key = self._utc_day()

    def propose(self, ctx: ProposalContext) -> ProposalExecution:
        self._rollover_day_if_needed()
        if not self._is_allowed(ctx):
            return ProposalExecution(
                result=None,
                proposer_used=False,
                proposer_id=None,
                proposal_hash=None,
                proposer_latency_ms=None,
                proposer_budget_spent=None,
                proposer_input_hash=None,
            )

        proposer_input_hash = stable_hash(ctx.to_dict())
        started = perf_counter()
        result = self.proposer.propose(ctx) if self.proposer is not None else None
        elapsed = perf_counter() - started
        latency_ms = int(elapsed * 1000)

        self.calls_day += 1
        self.calls_by_task[ctx.task_id] += 1
        self.seconds_day += elapsed
        budget = budget_snapshot_dict(
            calls_day=self.calls_day,
            seconds_day=self.seconds_day,
            calls_task=self.calls_by_task[ctx.task_id],
        )

        if result is None:
            return ProposalExecution(
                result=None,
                proposer_used=False,
                proposer_id=None,
                proposal_hash=None,
                proposer_latency_ms=latency_ms,
                proposer_budget_spent=budget,
                proposer_input_hash=proposer_input_hash,
            )

        return ProposalExecution(
            result=result,
            proposer_used=True,
            proposer_id=result.proposer_id,
            proposal_hash=result.proposal_hash,
            proposer_latency_ms=latency_ms,
            proposer_budget_spent=budget,
            proposer_input_hash=proposer_input_hash,
        )

    def _is_allowed(self, ctx: ProposalContext) -> bool:
        if not self.policy.enabled:
            return False
        if self.proposer is None:
            return False
        if ctx.language not in self.policy.allowed_languages:
            return False
        if self.calls_day >= self.policy.max_calls_per_day:
            return False
        if self.calls_by_task[ctx.task_id] >= self.policy.max_calls_per_task:
            return False
        if self.seconds_day >= self.policy.max_total_seconds_per_day:
            return False

        if self.policy.only_for_uncovered_signatures:
            if not is_signature_uncovered(
                language=ctx.language,
                error_signature=ctx.error_signature,
                uncovered_signatures=self.uncovered_signatures,
            ):
                return False

        return True

    def _rollover_day_if_needed(self) -> None:
        current_day = self._utc_day()
        if current_day == self.day_key:
            return
        self.day_key = current_day
        self.calls_day = 0
        self.seconds_day = 0.0
        self.calls_by_task.clear()

    def _utc_day(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d")


_DEFAULT_RUNTIME: ProposerRuntime | None = None


def get_default_proposer_runtime(force_reload: bool = False) -> ProposerRuntime:
    global _DEFAULT_RUNTIME
    if _DEFAULT_RUNTIME is not None and not force_reload:
        return _DEFAULT_RUNTIME

    policy = load_proposer_policy()
    uncovered = load_uncovered_signatures(Path(policy.uncovered_source))
    proposer: Proposer | None = None
    if policy.enabled:
        proposer = CodexProposer(
            CodexProposerConfig(
                timeout_seconds=policy.timeout_seconds,
            )
        )

    _DEFAULT_RUNTIME = ProposerRuntime(
        policy=policy,
        proposer=proposer,
        uncovered_signatures=uncovered,
    )
    return _DEFAULT_RUNTIME
