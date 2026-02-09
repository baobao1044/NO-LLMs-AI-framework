from __future__ import annotations

import traceback
import types
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import VerificationResult


@dataclass(frozen=True)
class FunctionCase:
    args: tuple
    expected: object


class FunctionVerifier:
    """Verifier treats test cases as source of truth."""

    def __init__(
        self,
        function_name: str,
        cases: list[FunctionCase],
        verifier_name: str = "function_verifier",
        verifier_version: str = "1.1.0",
    ) -> None:
        self.function_name = function_name
        self.cases = cases
        self.verifier_name = verifier_name
        self.verifier_version = verifier_version

    def verify(self, source_file: Path) -> VerificationResult:
        module = self._load_module(source_file)
        if isinstance(module, VerificationResult):
            return module

        fn = getattr(module, self.function_name, None)
        if not callable(fn):
            return self._failure(
                error_type="AssertionError",
                error_message=f"missing callable '{self.function_name}'",
                stage="unit_test",
            )

        for index, case in enumerate(self.cases, start=1):
            try:
                actual = fn(*case.args)
            except Exception as exc:
                return self._failure(
                    error_type=type(exc).__name__,
                    error_message=f"case {index} raised {exc}",
                    stage="unit_test",
                )
            if actual != case.expected:
                return self._failure(
                    error_type="AssertionError",
                    error_message=(
                        f"case {index} mismatch: args={case.args}, "
                        f"expected={case.expected}, actual={actual}"
                    ),
                    stage="unit_test",
                )

        return VerificationResult(
            passed=True,
            verifier_name=self.verifier_name,
            verifier_version=self.verifier_version,
            verifier_stage_failed=None,
        )

    def task_payload(self) -> dict[str, Any]:
        payload, _ = self.task_payload_snapshot()
        return payload

    def task_payload_snapshot(self) -> tuple[dict[str, Any], bool]:
        is_lossy = False
        cases_payload: list[dict[str, Any]] = []
        for case in self.cases:
            args_payload: list[Any] = []
            for arg in case.args:
                serialized_arg, arg_lossy = self._serialize_value(arg)
                args_payload.append(serialized_arg)
                is_lossy = is_lossy or arg_lossy

            expected_payload, expected_lossy = self._serialize_value(case.expected)
            is_lossy = is_lossy or expected_lossy
            cases_payload.append({"args": args_payload, "expected": expected_payload})

        payload = {
            "function_name": self.function_name,
            "cases": cases_payload,
        }
        return payload, is_lossy

    def replay_config(self) -> dict[str, Any]:
        return {"kind": "function"}

    @staticmethod
    def _is_json_primitive(value: Any) -> bool:
        return value is None or isinstance(value, (bool, int, float, str))

    @classmethod
    def _to_json_safe(cls, value: Any) -> tuple[Any, bool]:
        if cls._is_json_primitive(value):
            return value, False

        if isinstance(value, list):
            out: list[Any] = []
            lossy = False
            for item in value:
                safe_item, item_lossy = cls._to_json_safe(item)
                out.append(safe_item)
                lossy = lossy or item_lossy
            return out, lossy

        if isinstance(value, tuple):
            out: list[Any] = []
            lossy = True
            for item in value:
                safe_item, item_lossy = cls._to_json_safe(item)
                out.append(safe_item)
                lossy = lossy or item_lossy
            return out, lossy

        if isinstance(value, dict):
            out: dict[str, Any] = {}
            lossy = False
            for key, item in value.items():
                out_key = key
                if not isinstance(out_key, str):
                    out_key = str(out_key)
                    lossy = True
                safe_item, item_lossy = cls._to_json_safe(item)
                out[out_key] = safe_item
                lossy = lossy or item_lossy
            return out, lossy

        summary = " ".join(repr(value).split())
        if len(summary) > 200:
            summary = summary[:197] + "..."
        return {"type_name": type(value).__name__, "summary": summary}, True

    @staticmethod
    def from_task_payload(
        payload: dict[str, Any],
        verifier_name: str = "function_verifier",
        verifier_version: str = "1.1.0",
    ) -> "FunctionVerifier":
        cases: list[FunctionCase] = []
        for item in payload["cases"]:
            args = tuple(FunctionVerifier._deserialize_value(value) for value in item["args"])
            expected = FunctionVerifier._deserialize_value(item["expected"])
            cases.append(FunctionCase(args=args, expected=expected))
        return FunctionVerifier(
            function_name=payload["function_name"],
            cases=cases,
            verifier_name=verifier_name,
            verifier_version=verifier_version,
        )

    def _load_module(self, source_file: Path) -> types.ModuleType | VerificationResult:
        module_name = f"agent_solution_{uuid.uuid4().hex}"
        module = types.ModuleType(module_name)
        module.__file__ = str(source_file)
        try:
            source = source_file.read_text(encoding="utf-8")
            compiled = compile(source, str(source_file), "exec")
            exec(compiled, module.__dict__)
        except Exception as exc:
            details = traceback.format_exc(limit=1).strip()
            return self._failure(
                error_type=type(exc).__name__,
                error_message=f"{exc} | {details}",
                stage="unit_test",
            )
        return module

    @classmethod
    def _serialize_value(cls, value: Any) -> tuple[Any, bool]:
        return cls._to_json_safe(value)

    @staticmethod
    def _deserialize_value(value: Any) -> Any:
        return value

    def _failure(self, error_type: str, error_message: str, stage: str) -> VerificationResult:
        return VerificationResult(
            passed=False,
            error=f"{error_type}: {error_message}",
            error_type=error_type,
            error_message=error_message,
            verifier_name=self.verifier_name,
            verifier_version=self.verifier_version,
            verifier_stage_failed=stage,
        )
