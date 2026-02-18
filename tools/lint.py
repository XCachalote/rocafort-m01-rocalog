"""Basic lint: compile Python files to catch syntax errors."""

from __future__ import annotations

import pathlib
import py_compile
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET_DIRS = [ROOT / "rocalog", ROOT / "tests", ROOT / "tools"]


def iter_python_files() -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for base in TARGET_DIRS:
        if not base.exists():
            continue
        files.extend(path for path in base.rglob("*.py") if "__pycache__" not in path.parts)
    return sorted(files)


def main() -> int:
    errors: list[str] = []
    for file_path in iter_python_files():
        try:
            py_compile.compile(str(file_path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{file_path.relative_to(ROOT)}: {exc.msg}")

    if errors:
        print("Lint failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Lint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
