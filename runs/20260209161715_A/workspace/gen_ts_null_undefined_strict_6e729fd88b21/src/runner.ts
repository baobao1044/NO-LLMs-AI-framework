declare function require(name: string): any;
declare const process: any;

const fs = require("fs");
const path = require("path");
const solution = require("./solution");

type Testcase = {
  inputs: unknown[];
  expected: unknown;
};

type RunnerPayload = {
  function_name: string;
  testcases: Testcase[];
};

type RunnerResult = {
  passed: boolean;
  error_type?: string;
  error_message?: string;
};

function stable(value: unknown): string {
  return JSON.stringify(value);
}

function fail(error_type: string, error_message: string): RunnerResult {
  return {
    passed: false,
    error_type,
    error_message
  };
}

function run(): RunnerResult {
  const payloadPath = path.join(process.cwd(), "task_payload.json");
  let payload: RunnerPayload;
  try {
    payload = JSON.parse(fs.readFileSync(payloadPath, "utf-8")) as RunnerPayload;
  } catch (err) {
    return fail("PayloadError", `invalid payload: ${String(err)}`);
  }

  const candidate = (solution as Record<string, unknown>)[payload.function_name];
  if (typeof candidate !== "function") {
    return fail("AssertionError", `missing callable '${payload.function_name}'`);
  }

  const fn = candidate as (...args: unknown[]) => unknown;
  for (let index = 0; index < payload.testcases.length; index += 1) {
    const testcase = payload.testcases[index];
    try {
      const actual = fn(...testcase.inputs);
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
