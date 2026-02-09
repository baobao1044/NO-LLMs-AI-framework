from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from .delta import compute_delta
from .env_fingerprint import get_env_fingerprint
from .error_classifier import classify_failure
from .hashing import stable_hash, text_hash
from .logger import JsonlLogger
from .patchers import PatchContext, apply_first
from .task import CodeTask
from .verifiers.base import VerificationResult, Verifier


@dataclass(frozen=True)
class AgentRunResult:
    run_id: str
    done: bool
    attempts_used: int
    last_error: str | None


class AgentLoop:
    """MVP loop: execute -> verify -> log -> done/fix."""

    def run(
        self,
        task: CodeTask,
        verifier: Verifier,
        logger: JsonlLogger,
    ) -> AgentRunResult:
        run_id = str(uuid4())
        last_error: str | None = None
        task_payload, payload_is_lossy = verifier.task_payload_snapshot()
        verifier_config = verifier.replay_config()
        env_fingerprint = get_env_fingerprint()
        task_hash = stable_hash(
            {
                "prompt": task.prompt,
                "task_payload": task_payload,
                "payload_is_lossy": payload_is_lossy,
                "verifier_config": verifier_config,
                "env_fingerprint": env_fingerprint,
            }
        )

        for attempt_index, candidate_code in enumerate(task.attempts, start=1):
            verification, elapsed_ms = self._execute_and_verify(
                target_file=task.target_file,
                code=candidate_code,
                verifier=verifier,
            )
            patch_result = None
            patcher_attempted = False
            patch_applied = False
            patcher_id = None
            patch_summary = None

            if not verification.passed:
                patcher_attempted = True
                classified_failure = classify_failure(verification, language=task.language)
                patch_ctx = PatchContext(
                    task_id=task.task_id,
                    prompt=task.prompt,
                    code=candidate_code,
                    failure_type=classified_failure.failure_type,
                    error_signature=classified_failure.error_signature,
                    error_message=self._short((verification.error_message or verification.error)),
                    task_payload=task_payload,
                    language=task.language,
                )
                patch_result = apply_first(patch_ctx, language=task.language)
                if patch_result is not None:
                    patch_applied = True
                    patcher_id = patch_result.patcher_id
                    patch_summary = self._short(patch_result.patch_summary)

            logger.log(
                self._build_event(
                    run_id=run_id,
                    task=task,
                    attempt_index=attempt_index,
                    task_hash=task_hash,
                    task_payload=task_payload,
                    payload_is_lossy=payload_is_lossy,
                    env_fingerprint=env_fingerprint,
                    verifier=verifier,
                    language=task.language,
                    verifier_config=verifier_config,
                    code=candidate_code,
                    verification=verification,
                    elapsed_ms=elapsed_ms,
                    patcher_attempted=patcher_attempted,
                    patcher_id=patcher_id,
                    patch_applied=patch_applied,
                    patch_summary=patch_summary,
                    parent_artifact_hash=None,
                    changed_lines_count=0,
                    changed_line_numbers=[],
                    delta_summary=None,
                )
            )

            if verification.passed:
                return AgentRunResult(
                    run_id=run_id,
                    done=True,
                    attempts_used=attempt_index,
                    last_error=None,
                )

            if patch_result is not None:
                delta_info = compute_delta(before=candidate_code, after=patch_result.patched_code)
                patch_verification, patch_elapsed_ms = self._execute_and_verify(
                    target_file=task.target_file,
                    code=patch_result.patched_code,
                    verifier=verifier,
                )
                logger.log(
                    self._build_event(
                        run_id=run_id,
                        task=task,
                        attempt_index=attempt_index,
                        task_hash=task_hash,
                        task_payload=task_payload,
                        payload_is_lossy=payload_is_lossy,
                        env_fingerprint=env_fingerprint,
                        verifier=verifier,
                        language=task.language,
                        verifier_config=verifier_config,
                        code=patch_result.patched_code,
                        verification=patch_verification,
                        elapsed_ms=patch_elapsed_ms,
                        patcher_attempted=True,
                        patcher_id=patch_result.patcher_id,
                        patch_applied=True,
                        patch_summary=self._short(patch_result.patch_summary),
                        parent_artifact_hash=text_hash(candidate_code),
                        changed_lines_count=delta_info.changed_lines_count,
                        changed_line_numbers=delta_info.changed_line_numbers,
                        delta_summary=self._short(delta_info.delta_summary),
                    )
                )
                if patch_verification.passed:
                    return AgentRunResult(
                        run_id=run_id,
                        done=True,
                        attempts_used=attempt_index,
                        last_error=None,
                    )
                last_error = patch_verification.error
                continue

            last_error = verification.error

        return AgentRunResult(
            run_id=run_id,
            done=False,
            attempts_used=len(task.attempts),
            last_error=last_error,
        )

    def _execute_and_verify(
        self,
        target_file,
        code: str,
        verifier: Verifier,
    ) -> tuple[VerificationResult, int]:
        started = perf_counter()
        self._execute(target_file, code)
        verification = verifier.verify(target_file)
        elapsed_ms = int((perf_counter() - started) * 1000)
        return verification, elapsed_ms

    def _build_event(
        self,
        *,
        run_id: str,
        task: CodeTask,
        attempt_index: int,
        task_hash: str,
        task_payload: dict[str, Any],
        payload_is_lossy: bool,
        env_fingerprint: dict[str, Any],
        verifier: Verifier,
        language: str,
        verifier_config: dict[str, Any],
        code: str,
        verification: VerificationResult,
        elapsed_ms: int,
        patcher_attempted: bool,
        patcher_id: str | None,
        patch_applied: bool,
        patch_summary: str | None,
        parent_artifact_hash: str | None,
        changed_lines_count: int,
        changed_line_numbers: list[int],
        delta_summary: str | None,
    ) -> dict[str, Any]:
        classified = classify_failure(verification, language=language)
        return {
            "schema_version": "2.4.0",
            "run_id": run_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "attempt_index": attempt_index,
            "task_id": task.task_id,
            "language": language,
            "task_prompt": task.prompt,
            "task_hash": task_hash,
            "task_payload": task_payload,
            "payload_is_lossy": payload_is_lossy,
            "env_fingerprint": env_fingerprint,
            "verifier_name": verifier.verifier_name,
            "verifier_version": verifier.verifier_version,
            "verifier_config": verifier_config,
            "verifier_stage_failed": verification.verifier_stage_failed,
            "artifact_hash": text_hash(code),
            "parent_artifact_hash": parent_artifact_hash,
            "target_file": str(task.target_file),
            "code": code,
            "passed": verification.passed,
            "failure_type": classified.failure_type,
            "error_signature": classified.error_signature,
            "error_type": verification.error_type,
            "error_message": verification.error_message,
            "error": verification.error,
            "patcher_attempted": patcher_attempted,
            "patcher_id": patcher_id,
            "patch_applied": patch_applied,
            "patch_summary": patch_summary,
            "changed_lines_count": changed_lines_count,
            "changed_line_numbers": changed_line_numbers,
            "delta_summary": delta_summary,
            "elapsed_ms": elapsed_ms,
        }

    def _short(self, value: str | None, max_len: int = 200) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if len(normalized) <= max_len:
            return normalized
        return normalized[: max_len - 3] + "..."

    def _execute(self, target_file, candidate_code: str) -> None:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(candidate_code, encoding="utf-8")
