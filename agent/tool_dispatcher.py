from __future__ import annotations

import json
import time
from typing import Any, Callable

from agent.path_utils import normalize_repo_relative_path
from agent.tools.code_tools import (
    get_file_outline,
    list_files,
    read_file,
    search_code,
)
from agent.tools.db_tools import get_previous_findings, save_finding

PATH_TOOLS = {"list_files", "read_file", "get_file_outline"}


def execute_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    repo_root: str,
    session_id: int,
) -> tuple[str, int]:
    start_time = time.perf_counter()
    try:
        output = _execute(tool_name, tool_input, repo_root, session_id)
        output_string = output if isinstance(output, str) else json.dumps(output, indent=2)
    except Exception as exc:
        output_string = f"ERROR: {type(exc).__name__}: {exc}"

    duration_ms = int((time.perf_counter() - start_time) * 1000)
    return output_string, duration_ms


def _execute(
    tool_name: str,
    tool_input: dict[str, Any],
    repo_root: str,
    session_id: int,
) -> Any:
    code_tools: dict[str, Callable[..., Any]] = {
        "list_files": list_files,
        "read_file": read_file,
        "search_code": search_code,
        "get_file_outline": get_file_outline,
    }
    if tool_name in code_tools:
        if tool_name in PATH_TOOLS and "path" in tool_input:
            tool_input = {
                **tool_input,
                "path": normalize_repo_relative_path(
                    str(tool_input["path"]),
                    repo_root,
                ),
            }
        return code_tools[tool_name](repo_root, **tool_input)

    if tool_name == "save_finding":
        return save_finding(session_id=session_id, **tool_input)
    if tool_name == "get_previous_findings":
        return get_previous_findings(**tool_input)

    return f"ERROR: unknown tool: {tool_name}"
