#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.task_spec import TaskSpec, is_json_only


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic JSON-only task specs.")
    parser.add_argument("--out", type=Path, required=True, help="Output JSON file.")
    parser.add_argument("--seed", type=int, default=123, help="Random seed for deterministic generation.")
    parser.add_argument("--count", type=int, default=20, help="Number of tasks to generate.")
    parser.add_argument(
        "--templates",
        type=str,
        default="add,sub,mul,clamp,is_palindrome,parse_json_field,regex_findall",
        help="Comma-separated template names.",
    )
    parser.add_argument(
        "--append-golden",
        type=Path,
        default=None,
        help="Optional golden set path to append generated easy tasks.",
    )
    parser.add_argument(
        "--tag",
        type=str,
        default=None,
        help="Optional tag to append to every generated task.",
    )
    return parser.parse_args()


def _stable_task_id(template: str, params: dict[str, Any]) -> str:
    payload = json.dumps({"template": template, "params": params}, ensure_ascii=True, sort_keys=True)
    digest = sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"gen_{template}_{digest}"


# -----------------------------
# Python templates
# -----------------------------


def _sample_add(rng: random.Random, op: str) -> dict[str, Any]:
    a = rng.randint(-20, 20)
    b = rng.randint(-20, 20)
    values = [(a, b), (a + 1, b - 1), (0, b)]
    if op == "add":
        expected = [x + y for x, y in values]
        op_symbol = "+"
        wrong = "-"
    elif op == "sub":
        expected = [x - y for x, y in values]
        op_symbol = "-"
        wrong = "+"
    else:
        expected = [x * y for x, y in values]
        op_symbol = "*"
        wrong = "+"

    function_name = op
    attempts = [
        f"def {function_name}(a, b):\n    return a {wrong} b\n",
        f"def {function_name}(a, b):\n    return a {op_symbol} b\n",
    ]
    return {
        "template": op,
        "language": "py",
        "params": {"a": a, "b": b},
        "prompt": f"Write {function_name}(a, b) returning {function_name} result.",
        "function_name": function_name,
        "signature": None,
        "testcases": [{"inputs": [x, y], "expected": exp} for (x, y), exp in zip(values, expected)],
        "constraints": {"json_only": True},
        "difficulty": "easy",
        "tags": ["numeric", op],
        "attempts": attempts,
    }


def _sample_clamp(rng: random.Random) -> dict[str, Any]:
    lo = rng.randint(-10, 0)
    hi = rng.randint(1, 10)
    x_values = [lo - 3, (lo + hi) // 2, hi + 4]
    testcases = []
    for x in x_values:
        expected = max(lo, min(hi, x))
        testcases.append({"inputs": [x, lo, hi], "expected": expected})
    return {
        "template": "clamp",
        "language": "py",
        "params": {"lo": lo, "hi": hi},
        "prompt": "Write clamp(x, lo, hi) to bound x into [lo, hi].",
        "function_name": "clamp",
        "signature": None,
        "testcases": testcases,
        "constraints": {"json_only": True},
        "difficulty": "easy",
        "tags": ["numeric", "clamp"],
        "attempts": [
            "def clamp(x, lo, hi):\n    return x\n",
            "def clamp(x, lo, hi):\n    return max(lo, min(hi, x))\n",
        ],
    }


def _sample_palindrome(rng: random.Random) -> dict[str, Any]:
    pairs = [("level", True), ("robot", False), ("noon", True), ("apple", False)]
    rng.shuffle(pairs)
    chosen = pairs[:3]
    return {
        "template": "is_palindrome",
        "language": "py",
        "params": {"words": [word for word, _ in chosen]},
        "prompt": "Write is_palindrome(s) returning True if s reads the same backward.",
        "function_name": "is_palindrome",
        "signature": None,
        "testcases": [{"inputs": [word], "expected": expected} for word, expected in chosen],
        "constraints": {"json_only": True},
        "difficulty": "easy",
        "tags": ["string", "palindrome"],
        "attempts": [
            "def is_palindrome(s):\n    return False\n",
            "def is_palindrome(s):\n    return s == s[::-1]\n",
        ],
    }


def _sample_parse_json_field(rng: random.Random) -> dict[str, Any]:
    key = rng.choice(["name", "age", "city"])
    value = rng.choice(["alice", "bob", 22, 35, "hanoi"])
    base = {"name": "alice", "age": 22, "city": "hanoi"}
    base[key] = value
    text = json.dumps(base, ensure_ascii=True, sort_keys=True)
    missing_key = "missing_key"
    return {
        "template": "parse_json_field",
        "language": "py",
        "params": {"key": key},
        "prompt": "Write parse_json_field(s, key) to return value from JSON string or None.",
        "function_name": "parse_json_field",
        "signature": None,
        "testcases": [
            {"inputs": [text, key], "expected": value},
            {"inputs": [text, missing_key], "expected": None},
        ],
        "constraints": {"json_only": True},
        "difficulty": "medium",
        "tags": ["json", "dict"],
        "attempts": [
            "def parse_json_field(s, key):\n    return json.loads(s).get(key)\n",
            "import json\n\ndef parse_json_field(s, key):\n    return json.loads(s).get(key)\n",
        ],
    }


def _sample_regex_findall(rng: random.Random) -> dict[str, Any]:
    pool = [
        (r"\\d+", "a1 b22 c333", ["1", "22", "333"]),
        (r"[A-Z]", "AbCdeF", ["A", "C", "F"]),
        (r"ab", "abxxabyy", ["ab", "ab"]),
    ]
    pattern, text, expected = rng.choice(pool)
    return {
        "template": "regex_findall",
        "language": "py",
        "params": {"pattern": pattern, "text": text},
        "prompt": "Write regex_findall(pattern, text) returning re.findall result.",
        "function_name": "regex_findall",
        "signature": None,
        "testcases": [{"inputs": [pattern, text], "expected": expected}],
        "constraints": {"json_only": True},
        "difficulty": "medium",
        "tags": ["regex", "string"],
        "attempts": [
            "def regex_findall(pattern, text):\n    return re.findall(pattern, text)\n",
            "import re\n\ndef regex_findall(pattern, text):\n    return re.findall(pattern, text)\n",
        ],
    }


# -----------------------------
# TypeScript templates
# -----------------------------


def _sample_ts_union_narrowing(rng: random.Random) -> dict[str, Any]:
    value_a = rng.randint(10, 99)
    value_b = rng.randint(1, 9)
    return {
        "template": "ts_union_narrowing",
        "language": "ts",
        "params": {"a": value_a, "b": value_b},
        "prompt": "Write union_to_number(value) to convert string|number into number.",
        "function_name": "union_to_number",
        "signature": "(value: string | number) => number",
        "testcases": [
            {"inputs": [str(value_a)], "expected": value_a},
            {"inputs": [value_b], "expected": value_b},
        ],
        "constraints": {"json_only": True, "strict": True},
        "difficulty": "easy",
        "tags": ["ts", "union", "narrowing"],
        "attempts": [
            "export function union_to_number(value: string | number): number {\n  return value;\n}\n",
            "export function union_to_number(value: string | number): number {\n  if (typeof value === \"string\") {\n    return Number(value);\n  }\n  return value;\n}\n",
        ],
    }


def _sample_ts_optional_chaining(rng: random.Random) -> dict[str, Any]:
    person = rng.choice(["alice", "bob", "carol"])
    return {
        "template": "ts_optional_chaining",
        "language": "ts",
        "params": {"name": person},
        "prompt": "Write pick_user_name(input) using optional chaining; return empty string when missing.",
        "function_name": "pick_user_name",
        "signature": "(input: { user?: { name?: string } } | null) => string",
        "testcases": [
            {"inputs": [{"user": {"name": person}}], "expected": person},
            {"inputs": [{"user": {}}], "expected": ""},
            {"inputs": [None], "expected": ""},
        ],
        "constraints": {"json_only": True, "strict": True},
        "difficulty": "medium",
        "tags": ["ts", "optional_chaining", "null_safety"],
        "attempts": [
            "export function pick_user_name(input: { user?: { name?: string } } | null): string {\n  return input.user.name;\n}\n",
            "export function pick_user_name(input: { user?: { name?: string } } | null): string {\n  return input?.user?.name ?? \"\";\n}\n",
        ],
    }


def _sample_ts_generic_identity(rng: random.Random) -> dict[str, Any]:
    token = rng.choice(["x", "y", "z"])
    numeric = rng.randint(1, 20)
    return {
        "template": "ts_generic_identity",
        "language": "ts",
        "params": {"token": token},
        "prompt": "Write generic identity(value) preserving input type and value.",
        "function_name": "identity",
        "signature": "<T>(value: T) => T",
        "testcases": [
            {"inputs": [token], "expected": token},
            {"inputs": [numeric], "expected": numeric},
        ],
        "constraints": {"json_only": True, "strict": True},
        "difficulty": "medium",
        "tags": ["ts", "generic"],
        "attempts": [
            "export function identity<T>(value: T): T {\n  return undefined as unknown as T;\n}\n",
            "export function identity<T>(value: T): T {\n  return value;\n}\n",
        ],
    }


def _sample_ts_record_shape(rng: random.Random) -> dict[str, Any]:
    row_id = rng.randint(1, 9)
    name = rng.choice(["alice", "bob", "eve"])
    return {
        "template": "ts_record_shape",
        "language": "ts",
        "params": {"id": row_id, "name": name},
        "prompt": "Write format_row(item) returning `${id}:${name}` for a typed record.",
        "function_name": "format_row",
        "signature": "(item: { id: number; name: string }) => string",
        "testcases": [
            {"inputs": [{"id": row_id, "name": name}], "expected": f"{row_id}:{name}"},
            {"inputs": [{"id": 0, "name": "n/a"}], "expected": "0:n/a"},
        ],
        "constraints": {"json_only": True, "strict": True},
        "difficulty": "easy",
        "tags": ["ts", "record", "shape"],
        "attempts": [
            "export function format_row(item: { id: number; name: string }): string {\n  return item.id;\n}\n",
            "export function format_row(item: { id: number; name: string }): string {\n  return `${item.id}:${item.name}`;\n}\n",
        ],
    }


def _sample_ts_null_undefined_strict(rng: random.Random) -> dict[str, Any]:
    sample = rng.choice([" hello ", "world", "  trim  "])
    return {
        "template": "ts_null_undefined_strict",
        "language": "ts",
        "params": {"sample": sample},
        "prompt": "Write normalize_text(value) returning trimmed string or empty for null/undefined.",
        "function_name": "normalize_text",
        "signature": "(value: string | null | undefined) => string",
        "testcases": [
            {"inputs": [sample], "expected": sample.strip()},
            {"inputs": [None], "expected": ""},
        ],
        "constraints": {"json_only": True, "strict": True},
        "difficulty": "medium",
        "tags": ["ts", "null", "undefined", "strict"],
        "attempts": [
            "export function normalize_text(value: string | null | undefined): string {\n  return value.trim();\n}\n",
            "export function normalize_text(value: string | null | undefined): string {\n  return value?.trim() ?? \"\";\n}\n",
        ],
    }


TEMPLATE_BUILDERS = {
    "add": lambda rng: _sample_add(rng, "add"),
    "sub": lambda rng: _sample_add(rng, "sub"),
    "mul": lambda rng: _sample_add(rng, "mul"),
    "clamp": _sample_clamp,
    "is_palindrome": _sample_palindrome,
    "parse_json_field": _sample_parse_json_field,
    "regex_findall": _sample_regex_findall,
    "ts_union_narrowing": _sample_ts_union_narrowing,
    "ts_optional_chaining": _sample_ts_optional_chaining,
    "ts_generic_identity": _sample_ts_generic_identity,
    "ts_record_shape": _sample_ts_record_shape,
    "ts_null_undefined_strict": _sample_ts_null_undefined_strict,
}


def _task_target_file(task_id: str, language: str) -> str:
    if language == "ts":
        return f"workspace/{task_id}/src/solution.ts"
    return f"workspace/{task_id}.py"


def _apply_global_tag(tags: list[str], tag: str | None) -> list[str]:
    if tag is None or not tag.strip():
        return list(tags)
    normalized = tag.strip()
    if normalized in tags:
        return list(tags)
    return list(tags) + [normalized]


def generate_tasks(seed: int, count: int, templates: list[str], tag: str | None = None) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    tasks: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    template_index = 0
    unique_guard = 0

    while len(tasks) < count:
        template = templates[template_index % len(templates)]
        template_index += 1
        builder = TEMPLATE_BUILDERS[template]
        spec = builder(rng)
        task_id = _stable_task_id(template, spec["params"])
        if task_id in used_ids:
            unique_guard += 1
            task_id = _stable_task_id(template, {**spec["params"], "_guard": unique_guard})
        if task_id in used_ids:
            continue
        used_ids.add(task_id)

        language = str(spec.get("language") or "py")
        task_spec = TaskSpec(
            task_id=task_id,
            prompt=spec["prompt"],
            target_file=_task_target_file(task_id=task_id, language=language),
            function_name=spec["function_name"],
            testcases=spec["testcases"],
            language=language,
            signature=spec.get("signature"),
            constraints=spec["constraints"],
            difficulty=spec["difficulty"],
            tags=_apply_global_tag(spec["tags"], tag=tag),
            attempts=spec["attempts"],
        ).to_dict()
        if not is_json_only(task_spec):
            raise ValueError(f"generated non-JSON task: {task_id}")
        tasks.append(task_spec)

    return tasks


def append_to_golden(golden_path: Path, tasks: list[dict[str, Any]]) -> int:
    if golden_path.exists():
        payload = json.loads(golden_path.read_text(encoding="utf-8"))
    else:
        payload = {"tasks": []}

    existing_ids = {item.get("task_id") for item in payload.get("tasks", [])}
    appended = 0
    for task in tasks:
        if task.get("difficulty") != "easy":
            continue
        if task["task_id"] in existing_ids:
            continue

        language = str(task.get("language") or "py")
        if language == "ts":
            payload["tasks"].append(
                {
                    "task_id": task["task_id"],
                    "language": "ts",
                    "prompt": task["prompt"],
                    "target_file": task["target_file"],
                    "function_name": task["function_name"],
                    "signature": task.get("signature"),
                    "testcases": task["testcases"],
                    "difficulty": task.get("difficulty"),
                    "tags": task.get("tags", []),
                    "attempts": task["attempts"],
                }
            )
        else:
            payload["tasks"].append(
                {
                    "task_id": task["task_id"],
                    "prompt": task["prompt"],
                    "attempts": task["attempts"],
                    "verifier": {
                        "function_name": task["function_name"],
                        "cases": [
                            {"args": testcase["inputs"], "expected": testcase["expected"]}
                            for testcase in task["testcases"]
                        ],
                    },
                }
            )

        existing_ids.add(task["task_id"])
        appended += 1

    golden_path.parent.mkdir(parents=True, exist_ok=True)
    golden_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return appended


def main() -> int:
    args = parse_args()
    template_names = [item.strip() for item in args.templates.split(",") if item.strip()]
    if not template_names:
        raise ValueError("at least one template is required")
    unknown = [name for name in template_names if name not in TEMPLATE_BUILDERS]
    if unknown:
        raise ValueError(f"unknown templates: {unknown}")

    tasks = generate_tasks(seed=args.seed, count=args.count, templates=template_names, tag=args.tag)
    output = {
        "seed": args.seed,
        "count": args.count,
        "templates": template_names,
        "tag": args.tag,
        "tasks": tasks,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"generated_tasks={len(tasks)}")
    print(f"output={args.out}")

    if args.append_golden is not None:
        appended = append_to_golden(args.append_golden, tasks)
        print(f"golden_appended={appended}")
        print(f"golden_path={args.append_golden}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
