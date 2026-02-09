from __future__ import annotations

from pathlib import Path


_TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "templates" / "ts_project"


def ensure_ts_project(source_file: Path) -> Path:
    if source_file.parent.name == "src":
        project_root = source_file.parent.parent
    else:
        project_root = source_file.parent

    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "src").mkdir(parents=True, exist_ok=True)

    _copy_template_file(project_root, "package.json")
    _copy_template_file(project_root, "package-lock.json")
    _copy_template_file(project_root, "tsconfig.json")
    _copy_template_file(project_root, "src/runner.ts")

    if not source_file.exists():
        placeholder = (_TEMPLATE_ROOT / "src" / "solution.ts").read_text(encoding="utf-8")
        source_file.write_text(placeholder, encoding="utf-8")

    return project_root


def _copy_template_file(project_root: Path, relative_path: str) -> None:
    source = _TEMPLATE_ROOT / relative_path
    destination = project_root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
