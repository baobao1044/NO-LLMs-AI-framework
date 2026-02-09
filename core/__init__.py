"""Core modules for the verification-first agent loop MVP."""

from .agent import AgentLoop, AgentRunResult
from .delta import DeltaInfo, compute_delta
from .env_fingerprint import get_env_fingerprint
from .error_classifier import ClassifiedFailure, classify_failure
from .error_classifier_ts import ClassifiedTsDiagnostic, classify_tsc_output
from .hashing import stable_hash, text_hash
from .logger import JsonlLogger
from .patchers import (
    PatchContext,
    PatchResult,
    apply_first,
    apply_first_ts,
    patchers_in_priority,
    patchers_in_priority_ts,
)
from .task import CodeTask
from .task_spec import TaskSpec, is_json_only
from .verifier import (
    CompositeVerifier,
    FunctionCase,
    FunctionVerifier,
    SyntaxVerifier,
    TsCompositeVerifier,
    TsRunnerVerifier,
    TscVerifier,
    TimeoutVerifier,
    VerificationResult,
    build_composite_function_verifier,
    build_ts_composite_verifier,
)

__all__ = [
    "AgentLoop",
    "AgentRunResult",
    "ClassifiedFailure",
    "ClassifiedTsDiagnostic",
    "CompositeVerifier",
    "CodeTask",
    "DeltaInfo",
    "FunctionCase",
    "FunctionVerifier",
    "JsonlLogger",
    "PatchContext",
    "PatchResult",
    "SyntaxVerifier",
    "TsCompositeVerifier",
    "TsRunnerVerifier",
    "TscVerifier",
    "TaskSpec",
    "TimeoutVerifier",
    "VerificationResult",
    "apply_first",
    "apply_first_ts",
    "build_composite_function_verifier",
    "build_ts_composite_verifier",
    "classify_failure",
    "classify_tsc_output",
    "compute_delta",
    "get_env_fingerprint",
    "patchers_in_priority",
    "patchers_in_priority_ts",
    "stable_hash",
    "text_hash",
    "is_json_only",
]
