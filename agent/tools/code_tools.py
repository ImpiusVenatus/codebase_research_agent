from __future__ import annotations

import ast
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


IGNORE_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "vendor",
}
MAX_READ_LINES = 500
MAX_READ_BYTES = 20 * 1024
MAX_SEARCH_MATCHES = 50
MAX_LIST_FILES = 80


def list_files(repo_root: str, path: str = ".", max_depth: int = 1) -> list[str]:
    root = _safe_path(repo_root, path)
    if not root.exists():
        return [f"ERROR: path not found: {path}"]
    if root.is_file():
        return [_relative_path(Path(repo_root), root)]

    files: list[str] = []
    base_depth = len(root.relative_to(Path(repo_root).resolve()).parts)

    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        relative_depth = len(current_path.relative_to(Path(repo_root).resolve()).parts)
        if relative_depth - base_depth >= max_depth:
            dirnames[:] = []

        dirnames[:] = sorted(name for name in dirnames if name not in IGNORE_DIRS)

        for filename in sorted(filenames):
            files.append(_relative_path(Path(repo_root), current_path / filename))

    if len(files) > MAX_LIST_FILES:
        extra = len(files) - MAX_LIST_FILES
        files = files[:MAX_LIST_FILES]
        files.append(f"... and {extra} more files (use a subdirectory path)")

    return files


def read_file(
    repo_root: str,
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    file_path = _safe_path(repo_root, path)
    if not file_path.exists() or not file_path.is_file():
        return f"ERROR: file not found: {path}"
    if _is_binary(file_path):
        return f"ERROR: binary file cannot be read: {path}"

    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"ERROR: could not read {path}: {exc}"

    lines = text.splitlines()
    first = max((start_line or 1), 1)
    last = end_line or len(lines)
    if last < first:
        return "ERROR: end_line must be greater than or equal to start_line"

    selected = lines[first - 1 : last]
    selected = selected[:MAX_READ_LINES]

    output_lines: list[str] = []
    current_size = 0
    for index, line in enumerate(selected, start=first):
        rendered = f"{index}: {line}"
        encoded_size = len((rendered + "\n").encode("utf-8"))
        if current_size + encoded_size > MAX_READ_BYTES:
            break
        output_lines.append(rendered)
        current_size += encoded_size

    if not output_lines:
        return ""
    return "\n".join(output_lines)


def search_code(
    repo_root: str,
    query: str,
    file_pattern: str | None = None,
) -> list[dict[str, Any]]:
    rg_results = _search_with_rg(repo_root, query, file_pattern)
    if rg_results is not None:
        return rg_results
    return _search_with_python(repo_root, query, file_pattern)


def get_file_outline(repo_root: str, path: str) -> list[dict[str, Any]] | str:
    file_path = _safe_path(repo_root, path)
    if not file_path.exists() or not file_path.is_file():
        return f"ERROR: file not found: {path}"
    if _is_binary(file_path):
        return f"ERROR: binary file cannot be outlined: {path}"

    if file_path.suffix == ".py":
        return _python_outline(file_path)

    text = file_path.read_text(encoding="utf-8", errors="replace")
    declarations: list[dict[str, Any]] = []
    pattern = re.compile(
        r"^\s*(class|def|function|const|let|var|interface|type|struct|enum)\s+([A-Za-z_][\w-]*)",
    )
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = pattern.search(line)
        if match:
            declarations.append(
                {
                    "kind": match.group(1),
                    "name": match.group(2),
                    "line": line_number,
                }
            )
    return declarations


def _safe_path(repo_root: str, path: str) -> Path:
    root = Path(repo_root).resolve()
    resolved = (root / path).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"path escapes repository root: {path}")
    return resolved


def _relative_path(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _is_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:1024]
    except OSError:
        return False
    return b"\0" in chunk


def _search_with_rg(
    repo_root: str,
    query: str,
    file_pattern: str | None,
) -> list[dict[str, Any]] | None:
    command = ["rg", "--json", "--line-number", query, str(Path(repo_root).resolve())]
    if file_pattern:
        command[1:1] = ["--glob", file_pattern]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None

    if completed.returncode not in {0, 1}:
        return None

    results: list[dict[str, Any]] = []
    root = Path(repo_root).resolve()
    for line in completed.stdout.splitlines():
        if len(results) >= MAX_SEARCH_MATCHES:
            break
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "match":
            continue
        data = event["data"]
        file_path = Path(data["path"]["text"])
        results.append(
            {
                "file": _relative_path(root, file_path),
                "line": data["line_number"],
                "text": data["lines"]["text"].rstrip("\n"),
            }
        )
    return results


def _search_with_python(
    repo_root: str,
    query: str,
    file_pattern: str | None,
) -> list[dict[str, Any]]:
    root = Path(repo_root).resolve()
    pattern = re.compile(query)
    glob_pattern = file_pattern or "**/*"
    results: list[dict[str, Any]] = []

    for path in root.glob(glob_pattern):
        if len(results) >= MAX_SEARCH_MATCHES:
            break
        if not path.is_file() or any(part in IGNORE_DIRS for part in path.parts):
            continue
        if _is_binary(path):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if pattern.search(line):
                results.append(
                    {
                        "file": _relative_path(root, path),
                        "line": line_number,
                        "text": line,
                    }
                )
                if len(results) >= MAX_SEARCH_MATCHES:
                    break

    return results


def _python_outline(file_path: Path) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as exc:
        return [{"kind": "error", "name": str(exc), "line": exc.lineno or 1}]

    outline: list[dict[str, Any]] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            outline.append({"kind": "class", "name": node.name, "line": node.lineno})
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            outline.append({"kind": kind, "name": node.name, "line": node.lineno})
    return outline
