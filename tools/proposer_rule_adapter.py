#!/usr/bin/env python3
from __future__ import annotations

import json
import sys


PY_RULES = {
    "add": "def add(a, b):\n    return a + b\n",
    "sub": "def sub(a, b):\n    return a - b\n",
    "mul": "def mul(a, b):\n    return a * b\n",
    "inc": "def inc(x):\n    return x + 1\n",
    "clamp": "def clamp(x, lo, hi):\n    return max(lo, min(hi, x))\n",
    "is_palindrome": "def is_palindrome(s):\n    return s == s[::-1]\n",
    "parse_json_field": (
        "import json\n\n"
        "def parse_json_field(s, key):\n"
        "    return json.loads(s).get(key)\n"
    ),
    "regex_findall": (
        "import re\n\n"
        "def regex_findall(pattern, text):\n"
        "    return re.findall(pattern, text)\n"
    ),
}

TS_RULES = {
    "add": (
        "export function add(a: number, b: number): number {\n"
        "  return a + b;\n"
        "}\n"
    ),
    "clamp": (
        "export function clamp(x: number, lo: number, hi: number): number {\n"
        "  return Math.max(lo, Math.min(hi, x));\n"
        "}\n"
    ),
    "isPalindrome": (
        "export function isPalindrome(s: string): boolean {\n"
        "  return s === s.split(\"\").reverse().join(\"\");\n"
        "}\n"
    ),
    "union_to_number": (
        "export function union_to_number(value: string | number): number {\n"
        "  if (typeof value === \"string\") {\n"
        "    return Number(value);\n"
        "  }\n"
        "  return value;\n"
        "}\n"
    ),
    "pick_user_name": (
        "export function pick_user_name(input: { user?: { name?: string } } | null): string {\n"
        "  return input?.user?.name ?? \"\";\n"
        "}\n"
    ),
    "identity": (
        "export function identity<T>(value: T): T {\n"
        "  return value;\n"
        "}\n"
    ),
    "format_row": (
        "export function format_row(item: { id: number; name: string }): string {\n"
        "  return `${item.id}:${item.name}`;\n"
        "}\n"
    ),
    "normalize_text": (
        "export function normalize_text(value: string | null | undefined): string {\n"
        "  return value?.trim() ?? \"\";\n"
        "}\n"
    ),
}


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        ctx = json.loads(raw)
    except json.JSONDecodeError:
        return 0

    language = str(ctx.get("language") or "").strip().lower()
    function_name = str(ctx.get("function_name") or "").strip()

    if language == "py":
        code = PY_RULES.get(function_name, "")
    elif language == "ts":
        code = TS_RULES.get(function_name, "")
    else:
        code = ""

    if code:
        sys.stdout.write(code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
