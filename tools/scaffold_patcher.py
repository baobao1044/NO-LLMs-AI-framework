#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


VALID_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


CATEGORY_CHOICES = [
    "type_fix",
    "name_or_import",
    "syntax_fix",
    "export_fix",
    "performance_or_infinite_loop",
    "other",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scaffold deterministic patcher and test skeleton files.")
    parser.add_argument("--language", choices=["py", "ts"], required=True)
    parser.add_argument("--category", choices=CATEGORY_CHOICES, required=True)
    parser.add_argument("--signature", type=str, default="", help="Error signature trigger for can_apply.")
    parser.add_argument("--name", type=str, required=True, help="Safe snake_case patcher base name.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output patcher directory. Defaults to core/patchers or core/patchers_ts.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    return parser.parse_args()


def _validate_name(name: str) -> None:
    if not VALID_NAME_RE.fullmatch(name):
        raise ValueError(f"invalid --name '{name}': use ^[a-z][a-z0-9_]*$")


def _class_name(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_")) + "Patcher"


def _patcher_import(language: str) -> str:
    if language == "ts":
        return "from core.patchers.base import PatchContext, PatchResult"
    return "from .base import PatchContext, PatchResult"


def _default_out_dir(language: str) -> Path:
    return Path("core/patchers_ts" if language == "ts" else "core/patchers")


def _build_can_apply(category: str, signature: str, language: str) -> str:
    category_map = {
        "type_fix": "type_error",
        "name_or_import": "name_error",
        "syntax_fix": "syntax_error",
        "export_fix": "assertion_fail",
        "performance_or_infinite_loop": "timeout",
        "other": "",
    }
    lang_guard = "        if ctx.language != \"ts\":\n            return False\n" if language == "ts" else ""
    sig_line = (
        f"        return \"{signature}\" in combined\n"
        if signature
        else (
            "        return False\n"
            if not category_map[category]
            else f"        return \"{category_map[category]}\" in failure\n"
        )
    )
    return (
        "    def can_apply(self, ctx: PatchContext) -> bool:\n"
        f"{lang_guard}"
        "        combined = (ctx.error_signature or \"\") + \" \" + (ctx.error_message or \"\")\n"
        "        failure = (ctx.failure_type or \"\").lower()\n"
        f"{sig_line}"
    )


def _patcher_content(name: str, language: str, category: str, signature: str) -> str:
    class_name = _class_name(name)
    patcher_id = f"{name}_patcher"
    can_apply_block = _build_can_apply(category=category, signature=signature, language=language)
    return (
        "from __future__ import annotations\n\n"
        f"{_patcher_import(language)}\n\n"
        f'PATCHER_ID = "{patcher_id}"\n\n\n'
        f"class {class_name}:\n"
        "    id = PATCHER_ID\n\n"
        f"{can_apply_block}\n"
        "    def apply(self, ctx: PatchContext) -> PatchResult | None:\n"
        "        # TODO: implement deterministic patch logic for this signature/category.\n"
        "        # Return None when the patch is not safe or cannot be applied.\n"
        "        # Example:\n"
        "        # patched_code = ctx.code\n"
        "        # if patched_code == ctx.code:\n"
        "        #     return None\n"
        "        # return PatchResult(\n"
        "        #     patched_code=patched_code,\n"
        "        #     patcher_id=self.id,\n"
        "        #     patch_summary=\"describe deterministic transformation\",\n"
        "        # )\n"
        "        return None\n"
    )


def _test_content(name: str, language: str) -> str:
    class_name = _class_name(name)
    module_path = f"core.patchers_ts.{name}_patcher" if language == "ts" else f"core.patchers.{name}_patcher"
    return (
        "import unittest\n\n"
        "from core.patchers.base import PatchContext\n"
        f"from {module_path} import {class_name}\n\n\n"
        f"class {class_name}Tests(unittest.TestCase):\n"
        "    def test_stub_context(self) -> None:\n"
        f"        patcher = {class_name}()\n"
        "        ctx = PatchContext(\n"
        "            task_id=\"stub_task\",\n"
        "            prompt=\"stub prompt\",\n"
        "            code=\"pass\\n\",\n"
        "            failure_type=\"runtime_error\",\n"
        "            error_signature=\"stub\",\n"
        "            error_message=\"stub\",\n"
        "            task_payload={},\n"
        f"            language=\"{language}\",\n"
        "        )\n"
        "        self.assertFalse(patcher.can_apply(ctx))\n"
        "        self.assertIsNone(patcher.apply(ctx))\n\n\n"
        "if __name__ == \"__main__\":\n"
        "    unittest.main()\n"
    )


def _write_file(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    _validate_name(args.name)

    out_dir = args.out_dir or _default_out_dir(args.language)
    patcher_file = out_dir / f"{args.name}_patcher.py"
    test_file = Path("tests") / f"test_{args.name}_patcher.py"

    patcher_content = _patcher_content(
        name=args.name,
        language=args.language,
        category=args.category,
        signature=args.signature,
    )
    test_content = _test_content(name=args.name, language=args.language)

    try:
        _write_file(patcher_file, patcher_content, force=args.force)
        _write_file(test_file, test_content, force=args.force)
    except FileExistsError as exc:
        print(str(exc))
        return 1

    print(f"patcher_file={patcher_file}")
    print(f"test_file={test_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
