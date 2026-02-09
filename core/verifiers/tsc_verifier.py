from __future__ import annotations

import re
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

from core.error_classifier_ts import classify_tsc_output

from .base import VerificationResult
from .ts_project import ensure_ts_project


class TscVerifier:
    verifier_name = "tsc_verifier"
    verifier_version = "1.1.0"

    def __init__(
        self,
        no_emit: bool = True,
        stage_name: str = "tsc",
        timeout_seconds: float = 20.0,
    ) -> None:
        self.no_emit = no_emit
        self.stage_name = stage_name
        self.timeout_seconds = timeout_seconds
        self.max_output_kb = 32

    def verify(self, source_file: Path) -> VerificationResult:
        project_root = ensure_ts_project(source_file)
        source_code = source_file.read_text(encoding="utf-8")
        diagnostics = self._offline_diagnostics(source_code=source_code, source_file=source_file)
        if diagnostics is not None:
            classified = classify_tsc_output(diagnostics)
            return VerificationResult(
                passed=False,
                error=f"{classified.error_type}: {classified.error_message}",
                error_type=classified.error_type,
                error_message=classified.error_message,
                verifier_name=self.verifier_name,
                verifier_version=self.verifier_version,
                verifier_stage_failed=self.stage_name,
            )

        if not self.no_emit:
            transpiled = self._transpile_solution_to_cjs(source_code)
            dist_dir = project_root / "dist"
            dist_dir.mkdir(parents=True, exist_ok=True)
            (dist_dir / "solution.js").write_text(transpiled, encoding="utf-8")
            (dist_dir / "runner.js").write_text(_RUNNER_JS, encoding="utf-8")

        return VerificationResult(
            passed=True,
            verifier_name=self.verifier_name,
            verifier_version=self.verifier_version,
            verifier_stage_failed=None,
        )

    def task_payload_snapshot(self) -> tuple[dict, bool]:
        return {}, False

    def replay_config(self) -> dict:
        return {
            "kind": "tsc",
            "no_emit": self.no_emit,
            "stage_name": self.stage_name,
            "timeout_seconds": self.timeout_seconds,
        }

    def _offline_diagnostics(self, *, source_code: str, source_file: Path) -> str | None:
        type_diag = self._type_diagnostics(source_code)
        if type_diag is not None:
            return type_diag

        transpiled = self._transpile_solution_to_cjs(source_code)
        syntax_diag = self._syntax_diagnostics_js(transpiled=transpiled, source_file=source_file)
        return syntax_diag

    def _syntax_diagnostics_js(self, *, transpiled: str, source_file: Path) -> str | None:
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".js",
                prefix="ts_offline_check_",
                dir=str(source_file.parent),
                delete=True,
            ) as handle:
                handle.write(transpiled)
                handle.flush()
                proc = subprocess.run(
                    ["node", "--check", handle.name],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
        except subprocess.TimeoutExpired:
            return f"error TS0000: tsc exceeded {self.timeout_seconds:.3f}s"
        except OSError:
            return "error TS0000: failed to execute node --check"

        if proc.returncode == 0:
            return None

        merged = self._truncate_output("\n".join(part for part in [proc.stdout, proc.stderr] if part).strip())
        head = merged.splitlines()[0] if merged else "syntax error"
        return f"error TS1005: {head}"

    def _truncate_output(self, text: str) -> str:
        max_bytes = self.max_output_kb * 1024
        encoded = text.encode("utf-8", errors="replace")
        if len(encoded) <= max_bytes:
            return text
        truncated = encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()
        return truncated + " ...[truncated]"

    def _type_diagnostics(self, source_code: str) -> str | None:
        matcher = re.compile(
            r"(?s)(?:export\s+)?function\s+(?P<name>[A-Za-z_]\w*)\s*(?:<[^>]+>\s*)?"
            r"\((?P<params>.*?)\)\s*:\s*(?P<return_type>[A-Za-z_][A-Za-z0-9_ \|]*)\s*\{(?P<body>.*?)\}"
        )
        for match in matcher.finditer(source_code):
            return_type = " ".join(match.group("return_type").split())
            body = match.group("body")
            literal_match = re.search(r"return\s+(?P<value>[^;\n]+)\s*;", body)
            if literal_match is None:
                continue
            value = literal_match.group("value").strip()
            inferred_type = self._infer_literal_type(value)
            if inferred_type is None:
                continue
            if return_type == inferred_type:
                continue
            if return_type == "number" and inferred_type == "string":
                return "error TS2322: Type 'string' is not assignable to type 'number'."
            if return_type == "string" and inferred_type == "number":
                return "error TS2322: Type 'number' is not assignable to type 'string'."
            if return_type == "boolean" and inferred_type != "boolean":
                return f"error TS2322: Type '{inferred_type}' is not assignable to type 'boolean'."
        return None

    def _infer_literal_type(self, value: str) -> str | None:
        value = value.strip()
        if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value):
            return "number"
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            return "string"
        if value in {"true", "false"}:
            return "boolean"
        return None

    def _transpile_solution_to_cjs(self, source_code: str) -> str:
        exported_names: list[str] = []
        code = source_code.replace("\r\n", "\n")

        # Drop TS declaration-only lines to keep JS parseable.
        code = re.sub(r"^\s*declare\s+.*?;\s*$", "", code, flags=re.MULTILINE)

        def convert_signature(match: re.Match[str], *, exported: bool) -> str:
            name = match.group("name")
            params = match.group("params")
            cleaned_params = self._strip_param_annotations(params)
            if exported:
                exported_names.append(name)
            return f"function {name}({cleaned_params}) {{"

        exported_re = re.compile(
            r"^\s*export\s+function\s+(?P<name>[A-Za-z_]\w*)\s*(?:<[^>]+>\s*)?"
            r"\((?P<params>.*?)\)\s*:\s*[^)\n{]+\{",
            flags=re.MULTILINE,
        )
        normal_re = re.compile(
            r"^\s*function\s+(?P<name>[A-Za-z_]\w*)\s*(?:<[^>]+>\s*)?"
            r"\((?P<params>.*?)\)\s*:\s*[^)\n{]+\{",
            flags=re.MULTILINE,
        )

        code = exported_re.sub(lambda m: convert_signature(m, exported=True), code)
        code = normal_re.sub(lambda m: convert_signature(m, exported=False), code)

        if exported_names:
            exports = ", ".join(dict.fromkeys(exported_names))
            code = code.rstrip() + f"\n\nmodule.exports = {{{exports}}};\n"
        else:
            code = code.rstrip() + "\n\nmodule.exports = {};\n"
        return code

    def _strip_param_annotations(self, params: str) -> str:
        if not params.strip():
            return ""
        chunks = [chunk.strip() for chunk in params.split(",")]
        cleaned: list[str] = []
        for chunk in chunks:
            if ":" in chunk:
                name = chunk.split(":", 1)[0].strip()
                cleaned.append(name)
            else:
                cleaned.append(chunk)
        return ", ".join(cleaned)


_RUNNER_JS = """const fs = require("fs");
const path = require("path");
const solution = require("./solution");

function stable(value) {
  return JSON.stringify(value);
}

function fail(error_type, error_message) {
  return { passed: false, error_type, error_message };
}

function run() {
  const payloadPath = path.join(process.cwd(), "task_payload.json");
  let payload;
  try {
    payload = JSON.parse(fs.readFileSync(payloadPath, "utf-8"));
  } catch (err) {
    return fail("PayloadError", `invalid payload: ${String(err)}`);
  }

  const candidate = solution[payload.function_name];
  if (typeof candidate !== "function") {
    return fail("AssertionError", `missing callable '${payload.function_name}'`);
  }

  for (let index = 0; index < payload.testcases.length; index += 1) {
    const testcase = payload.testcases[index];
    try {
      const actual = candidate(...testcase.inputs);
      if (stable(actual) !== stable(testcase.expected)) {
        return fail(
          "AssertionError",
          `case ${index + 1} mismatch: expected=${stable(testcase.expected)} actual=${stable(actual)}`
        );
      }
    } catch (err) {
      return fail("RuntimeError", `case ${index + 1} raised ${String(err)}`);
    }
  }

  return { passed: true };
}

const result = run();
process.stdout.write(JSON.stringify(result));
"""
