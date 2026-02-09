from __future__ import annotations

import multiprocessing as mp
from pathlib import Path

from .base import VerificationResult
from .function_verifier import FunctionVerifier


def _worker(conn: mp.connection.Connection, payload: dict, source_path: str) -> None:
    verifier = FunctionVerifier.from_task_payload(payload=payload)
    result = verifier.verify(Path(source_path))
    conn.send(result)
    conn.close()


class TimeoutVerifier:
    verifier_name = "timeout_verifier"
    verifier_version = "1.1.0"

    def __init__(self, unit_verifier: FunctionVerifier, timeout_seconds: float = 1.0) -> None:
        self.unit_verifier = unit_verifier
        self.timeout_seconds = timeout_seconds

    def verify(self, source_file: Path) -> VerificationResult:
        payload, _ = self.unit_verifier.task_payload_snapshot()
        parent_conn, child_conn = mp.Pipe(duplex=False)
        process = mp.Process(target=_worker, args=(child_conn, payload, str(source_file)))
        process.start()
        child_conn.close()
        process.join(timeout=self.timeout_seconds)

        if process.is_alive():
            process.terminate()
            process.join()
            return VerificationResult(
                passed=False,
                error=f"TimeoutError: exceeded {self.timeout_seconds:.3f}s",
                error_type="TimeoutError",
                error_message=f"exceeded {self.timeout_seconds:.3f}s",
                verifier_name=self.verifier_name,
                verifier_version=self.verifier_version,
                verifier_stage_failed="timeout",
            )

        if not parent_conn.poll(timeout=0):
            parent_conn.close()
            return VerificationResult(
                passed=False,
                error="RuntimeError: timeout worker returned no result",
                error_type="RuntimeError",
                error_message="timeout worker returned no result",
                verifier_name=self.verifier_name,
                verifier_version=self.verifier_version,
                verifier_stage_failed="unit_test",
            )
        result = parent_conn.recv()
        parent_conn.close()

        if not isinstance(result, VerificationResult):
            return VerificationResult(
                passed=False,
                error="RuntimeError: timeout worker returned invalid payload",
                error_type="RuntimeError",
                error_message="timeout worker returned invalid payload",
                verifier_name=self.verifier_name,
                verifier_version=self.verifier_version,
                verifier_stage_failed="unit_test",
            )
        return result

    def task_payload_snapshot(self) -> tuple[dict, bool]:
        return self.unit_verifier.task_payload_snapshot()

    def replay_config(self) -> dict:
        return {
            "kind": "timeout_wrapper",
            "timeout_seconds": self.timeout_seconds,
        }
