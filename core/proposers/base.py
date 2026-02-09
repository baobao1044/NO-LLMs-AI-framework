from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ProposalContext:
    language: str
    task_id: str
    prompt: str
    signature: str | None
    function_name: str | None
    code: str
    failure_type: str | None
    error_signature: str | None
    error_message: str | None
    verifier_stage_failed: str | None
    task_payload: dict[str, Any]
    payload_is_lossy: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProposalResult:
    proposed_code: str
    proposer_id: str
    proposal_summary: str
    proposal_hash: str


class Proposer(ABC):
    id: str

    @abstractmethod
    def propose(self, ctx: ProposalContext) -> ProposalResult | None:
        raise NotImplementedError
