"use strict";
const fs = require("fs");
const path = require("path");
const solution = require("./solution");
function stable(value) {
    return JSON.stringify(value);
}
function fail(error_type, error_message) {
    return {
        passed: false,
        error_type,
        error_message
    };
}
function run() {
    const payloadPath = path.join(process.cwd(), "task_payload.json");
    let payload;
    try {
        payload = JSON.parse(fs.readFileSync(payloadPath, "utf-8"));
    }
    catch (err) {
        return fail("PayloadError", `invalid payload: ${String(err)}`);
    }
    const candidate = solution[payload.function_name];
    if (typeof candidate !== "function") {
        return fail("AssertionError", `missing callable '${payload.function_name}'`);
    }
    const fn = candidate;
    for (let index = 0; index < payload.testcases.length; index += 1) {
        const testcase = payload.testcases[index];
        try {
            const actual = fn(...testcase.inputs);
            if (stable(actual) !== stable(testcase.expected)) {
                return fail("AssertionError", `case ${index + 1} mismatch: expected=${stable(testcase.expected)} actual=${stable(actual)}`);
            }
        }
        catch (err) {
            return fail("RuntimeError", `case ${index + 1} raised ${String(err)}`);
        }
    }
    return { passed: true };
}
const result = run();
process.stdout.write(JSON.stringify(result));
